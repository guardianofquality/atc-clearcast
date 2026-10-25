"""Browser automation and DOM watcher for ATC-SIM."""

import re
from playwright.sync_api import sync_playwright
from config import Config
from phraseology import PhraseologyConverter
from tts import TTSService
from tracker import FlightTracker
from ui import TerminalUI

INJECT_JS_TEMPLATE = r"""
(() => {
  const LINE = /([A-Za-z]{2,3}\d{1,4}[A-Za-z]?)\s*:\s*[^\n]+/g;
  const recent = new Map();
  const lastText = new WeakMap();
  const DEBUG = %DEBUG%;
  const TYPED = %TYPED%;

  function detectAirport() {
    // Check .SanSerif9 explicitly as provided
    const sanSerif = document.querySelectorAll('.SanSerif9');
    for (const el of sanSerif) {
      const txt = (el.textContent || '').trim();
      if (txt && /Intl|Airport|OMDB|DXB|ORD|LHR/i.test(txt)) {
        window.pySetAirport('', txt);
        return;
      }
    }

    // Check elements containing airport name
    const candidates = Array.from(document.querySelectorAll('body *'));
    for (const el of candidates) {
      if (el.children.length === 0 && el.textContent) {
        const txt = el.textContent.trim();
        if (/Intl\.|Airport|Approach/i.test(txt) && txt.length < 80) {
          window.pySetAirport('', txt);
          return;
        }
      }
    }

    // Fallback: Check <select name="selAirport">
    const sel = document.querySelector('select[name="selAirport"]');
    if (sel && sel.selectedIndex >= 0) {
      const opt = sel.options[sel.selectedIndex];
      if (opt && opt.text) {
        window.pySetAirport(opt.value || '', opt.text);
        return;
      }
    }
  }

  function scanProgressStrips() {
    // Scrape .ProgressStrip elements e.g.:
    // <div id="UAE757" class="ProgressStrip"><div class="info">UAE757 &nbsp;30L &nbsp;34=<br>B77W &nbsp; To: MAXMO</div></div>
    const strips = document.querySelectorAll('.ProgressStrip');
    for (const strip of strips) {
      const cs = (strip.getAttribute('id') || strip.getAttribute('name') || '').trim();
      if (!cs) continue;
      const info = strip.querySelector('.info');
      const rawText = info ? (info.innerText || info.textContent || '') : '';
      if (!rawText) continue;

      // Normalize non-breaking spaces and whitespace
      const cleanText = rawText.replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();

      // Extract Runway: e.g. "30L", "27R", "04", "12C"
      const rwyMatch = cleanText.match(/\b(\d{1,2}[LRC]?)\b/);
      const rwy = rwyMatch ? rwyMatch[1] : '';

      // Extract Heading: in ATC-SIM strips, headings appear like "34=" (meaning 340 deg)
      // or "H270", "HDG 240", "270°"
      let heading = '';
      const hdgEqual = cleanText.match(/\b(\d{2})=\b/);
      if (hdgEqual) {
        heading = String(parseInt(hdgEqual[1], 10) * 10).padStart(3, '0');
      } else {
        const hdgDirect = cleanText.match(/\b(?:HDG|H)?\s*([0-3]\d{2})\b/i);
        if (hdgDirect && hdgDirect[1] !== cs) heading = hdgDirect[1];
      }

      // Extract Model: e.g. "B77W", "A388", "A320", "B738", "B773"
      const modelMatch = cleanText.match(/\b([A-Z]\d{2,3}[A-Z0-9]?)\b/);
      let model = '';
      if (modelMatch && modelMatch[1] !== cs && modelMatch[1] !== rwy) {
        model = modelMatch[1];
      }

      // Extract Destination / Fix: e.g. "To: MAXMO"
      const fixMatch = cleanText.match(/To:\s*([A-Za-z0-9]+)/i);
      const fix = fixMatch ? fixMatch[1].toUpperCase() : '';

      window.pyStripData(cs, rwy, model, fix, heading);
    }
  }

  function emit(line) {
    line = line.trim();
    const now = Date.now();
    if (recent.has(line) && now - recent.get(line) < 3000) return;  // de-dupe
    recent.set(line, now);
    window.pyGameLine(line);
  }

  function scan(text) {
    if (!text) return;
    if (DEBUG) window.pyDebug(text.slice(0, 200));

    // Also detect standalone system errors / warnings like "Unable to comply" or "Invalid command"
    if (/unable to comply/i.test(text) && !LINE.test(text)) {
      emit('SYSTEM: Unable to comply');
    } else if (/invalid command/i.test(text) && !LINE.test(text)) {
      emit('SYSTEM: Invalid command');
    }

    LINE.lastIndex = 0;
    let m;
    while ((m = LINE.exec(text)) !== null) emit(m[0]);
  }

  function start() {
    detectAirport();
    scanProgressStrips();
    setInterval(detectAirport, 4000);
    setInterval(scanProgressStrips, 2000);

    new MutationObserver((muts) => {
      for (const mu of muts) {
        if (mu.type === 'characterData') {
          // Text node edited: only read what was newly appended.
          const now = mu.target.textContent || '';
          const old = lastText.get(mu.target) || '';
          lastText.set(mu.target, now);
          scan(now.startsWith(old) ? now.slice(old.length) : now);
        } else {
          for (const n of mu.addedNodes) {
            const t = n.textContent || '';
            // Skip huge re-renders so old history isn't read out again.
            if (t.length > 0 && t.length < 400) scan(t);
          }
        }
      }
    }).observe(document.documentElement,
               {childList: true, subtree: true, characterData: true});
  }

  if (document.documentElement) start();
  else document.addEventListener('DOMContentLoaded', start);

  if (TYPED) {
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const el = e.target;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA'))
        window.pyTyped(el.value);
    }, true);
  }
})();
"""


class ATCSimWatcher:
    """Watches an ATC-Sim session and dispatches ATC speech events."""

    def __init__(
        self,
        config: Config,
        converter: PhraseologyConverter,
        tts: TTSService,
        tracker: FlightTracker,
        ui: TerminalUI,
    ):
        self.config = config
        self.converter = converter
        self.tts = tts
        self.tracker = tracker
        self.ui = ui

    def on_set_airport(self, code: str, full_name: str):
        # Extract friendly name from strings like:
        # "Dubai (United Arab Emirates) Intl." -> "Dubai"
        # "Chicago O'Hare (ORD)" -> "Chicago O'Hare"
        clean = full_name
        # Remove parenthetical details like (United Arab Emirates) or (DXB / OMDB)
        clean = re.sub(r"\(.*?\)", "", clean)
        # Remove suffixes like Intl., International, Airport, and leftover dots
        clean = re.sub(r"\b(Intl|International|Airport|Airfield)\b\.?", "", clean, flags=re.I)
        clean = clean.replace(".", "").strip()
        clean = re.sub(r"\s+", " ", clean).strip()
        clean = clean or "Approach"

        self.tracker.set_airport(code, clean)
        self.config.airport_name = clean
        self.config.airport_code = code
        self.ui.render()

    def on_game_line(self, text: str):
        parsed = self.converter.parse_game_line(text)
        if not parsed:
            return
        callsign, message = parsed

        # Update flight tracker & strips
        self.tracker.update_from_game_line(callsign, message)

        # Convert to authentic phraseology
        spoken = self.converter.convert(callsign, message)
        self.tts.speak(spoken)

        # Update Live Terminal UI
        self.ui.set_last_transmission(f"{callsign}: {message} -> \"{spoken}\"")
        self.ui.render()

    def on_strip_data(self, callsign: str, runway: str, model: str, fix: str, heading: str = ""):
        self.tracker.update_from_dom_strip(
            callsign=callsign,
            runway=runway or None,
            model=model or None,
            dest_or_fix=fix or None,
            heading=heading or None,
        )
        self.ui.render()

    def on_debug(self, text: str):
        if self.config.debug:
            print(f"[debug] {text!r}")

    def on_typed(self, text: str):
        text = (text or "").strip()
        if text:
            # Check if typed input has a callsign prefix like "GF535 C 5000"
            parts = text.split(maxsplit=1)
            if len(parts) == 2 and self.converter.parse_game_line(f"{parts[0]}: {parts[1]}"):
                cs, cmd = parts[0].upper(), parts[1]
                self.tracker.update_from_game_line(cs, cmd)
                self.ui.render()
            self.tts.speak(text)

    def _build_injection_script(self) -> str:
        return (
            INJECT_JS_TEMPLATE
            .replace("%DEBUG%", "true" if self.config.debug else "false")
            .replace("%TYPED%", "true" if self.config.speak_typed_input else "false")
        )

    def run(self):
        js = self._build_injection_script()

        # Initial render of terminal strip board
        self.ui.render()

        with sync_playwright() as p:
            launch_kwargs = {"headless": self.config.headless}
            if self.config.browser_channel:
                launch_kwargs["channel"] = self.config.browser_channel

            try:
                browser = p.chromium.launch(**launch_kwargs)
            except Exception as e:
                if self.config.browser_channel:
                    print(f"Warning: Channel '{self.config.browser_channel}' failed ({e}). Trying default Chromium.")
                    launch_kwargs.pop("channel", None)
                    browser = p.chromium.launch(**launch_kwargs)
                else:
                    raise e

            context = browser.new_context()
            context.expose_function("pyGameLine", self.on_game_line)
            context.expose_function("pyDebug", self.on_debug)
            context.expose_function("pyTyped", self.on_typed)
            context.expose_function("pySetAirport", self.on_set_airport)
            context.expose_function("pyStripData", self.on_strip_data)
            context.add_init_script(js)

            page = context.new_page()
            page.goto(self.config.url)

            while not page.is_closed():
                page.wait_for_timeout(500)

            browser.close()

