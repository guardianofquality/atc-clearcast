"""
ATC-SIM Voice Plugin v2
-----------------------
Watches atc-sim.com for command lines like
    GF535: Climb and maintain 5000 feet.
and speaks them as
    "Flight G F five three five, climb and maintain 5000 feet."

Run (inside your venv):
    python3 atc_voice_v2.py
"""

import queue
import re
import subprocess
import sys
import threading

import pyttsx3
from playwright.sync_api import sync_playwright

URL = "https://atc-sim.com/"
SPEECH_RATE = 175

SPEAK_TYPED_INPUT = False   # True = also speak the raw text you type (v1 behaviour)
DEBUG = False               # True = print every new piece of text the page adds
                            # (useful if nothing is being spoken)

# Callsign style: True  -> "Emirates nine six five"   (uses AIRLINES below)
#                 False -> "U A E nine six five"
USE_AIRLINE_NAMES = True
# True -> "Flight Emirates nine six five", False -> "Emirates nine six five"
FLIGHT_PREFIX = False
# True -> "four thousand feet", False -> "four thousand" (as controllers usually say it)
SAY_FEET = True
# True -> "tree / fife / niner" (ICAO pronunciation), False -> "three / five / nine"
AVIATION_DIGITS = False
AIRLINES = {
    "AAL": "American", "UAL": "United", "DAL": "Delta", "SWA": "Southwest",
    "BAW": "Speedbird", "UAE": "Emirates", "QFA": "Qantas", "JAL": "Japan Air",
    "ANA": "All Nippon", "DLH": "Lufthansa", "AFR": "Air France",
    "VIR": "Virgin", "ACA": "Air Canada", "FDX": "FedEx", "GFA": "Gulf Air",
}

DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "tree", "4": "four",
          "5": "fife", "6": "six", "7": "seven", "8": "eight", "9": "niner"}
PLAIN_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
                "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}
D = DIGITS if AVIATION_DIGITS else PLAIN_DIGITS


def spell_callsign(cs: str) -> str:
    m = re.fullmatch(r"([A-Z]{2,3})(\d+[A-Z]?)", cs.upper())
    if not m:
        return " ".join(cs)
    prefix, number = m.groups()
    if USE_AIRLINE_NAMES and prefix in AIRLINES:
        head = AIRLINES[prefix]
    else:
        head = " ".join(prefix)
    return head + " " + " ".join(D.get(c, c) for c in number)


SIDES = {"L": "left", "R": "right", "C": "center"}


def say_number(num: str) -> str:
    """'27R' -> 'two seven right'"""
    return " ".join(D[c] if c.isdigit() else SIDES.get(c.upper(), c) for c in num)


def digits_out(match: re.Match) -> str:
    return match.group(1) + " " + say_number(match.group(2))


ACRONYMS = ["ILS", "VOR", "DME", "ATIS", "NDB", "RNAV", "VFR", "IFR", "QNH", "TCAS"]

# Your own find/replace rules, applied last: (regex, replacement).
# Example: (r"\bcleared ILS\b", "cleared I L S approach")
PHRASES = []


def digits(s: str) -> str:
    """'270' -> 'two seven zero'"""
    return " ".join(D.get(c, c) for c in s)


def say_altitude(n: int) -> str:
    """3000 -> 'three thousand', 2500 -> 'two thousand five hundred',
    12000 -> 'one two thousand', 800 -> 'eight hundred'."""
    thousands, rest = divmod(n, 1000)
    parts = []
    if thousands:
        parts.append(digits(str(thousands)) + " thousand")
    if rest:
        hundreds, tens = divmod(rest, 100)
        if hundreds:
            parts.append(D[str(hundreds)] + " hundred")
        if tens:
            parts.append(digits(f"{tens:02d}"))
    return " ".join(parts) or D["0"]


def to_speech(callsign: str, message: str) -> str:
    """Rewrite a game line into natural radio phraseology.

    'Descend and maintain 3000 feet, expedite.' ->
    'descend and maintain three thousand, expedite descent'
    """
    msg = message.strip().rstrip(".")

    # Flight levels: "FL240" / "flight level 240" -> "flight level two four zero"
    msg = re.sub(r"\b(?:flight level|FL)\s*(\d{2,3})\b",
                 lambda m: "flight level " + digits(m.group(1)), msg, flags=re.I)
    # Altitudes: "3000 feet" -> "three thousand" (ATC drops the word "feet").
    # Accepts "4,000 feet", "4000ft", "4000 ft.", "4000'" and a bare number
    # after "maintain" / "to" (e.g. "climb and maintain 4000").
    msg = re.sub(r"(?<=\d),(?=\d{3}\b)", "", msg)
    feet = " feet" if SAY_FEET else ""
    msg = re.sub(r"\b(\d{3,5})\s*(?:(?:feet|foot|ft)\b\.?|')",
                 lambda m: say_altitude(int(m.group(1))) + feet, msg, flags=re.I)
    msg = re.sub(r"\b(maintain|to)\s+(\d{4,5})\b(?!\.\d)",
                 lambda m: m.group(1) + " " + say_altitude(int(m.group(2))) + feet,
                 msg, flags=re.I)
    # Speeds: "reduce speed to 180 knots" -> "reduce speed to one eight zero"
    msg = re.sub(r"\b(\d{2,3})\s*(?:knots|kts|kt)\b",
                 lambda m: digits(m.group(1)), msg, flags=re.I)
    # Frequencies: "118.5" -> "one one eight point five"
    msg = re.sub(r"\b(\d{3})\.(\d{1,3})\b",
                 lambda m: digits(m.group(1)) + " point " + digits(m.group(2)), msg)

    # Headings, runways, squawk codes are read digit by digit (27R -> two seven right).
    msg = re.sub(r"\b(heading|runway|squawk)\s+(\d+[LRClrc]?)", digits_out,
                 msg, flags=re.I)
    # Any other runway-style designator, e.g. "cleared to land 27R".
    msg = re.sub(r"\b(\d{2}[LRC])\b", lambda m: say_number(m.group(1)), msg)
    # A standalone R or L (e.g. "Turn R heading ...") becomes right / left.
    msg = re.sub(r"\bR\b", "right", msg)
    msg = re.sub(r"\bL\b", "left", msg)

    # Spell out acronyms: ILS -> "I L S"
    for word in ACRONYMS:
        msg = re.sub(rf"\b{word}\b", " ".join(word), msg)

    # A trailing "expedite" becomes "expedite descent" / "expedite climb".
    if re.search(r"\bexpedite$", msg, re.I):
        if re.search(r"\bdescen", msg, re.I):
            msg += " descent"
        elif re.search(r"\bclimb", msg, re.I):
            msg += " climb"

    for pattern, replacement in PHRASES:
        msg = re.sub(pattern, replacement, msg, flags=re.I)

    prefix = "Flight " if FLIGHT_PREFIX else ""
    return f"{prefix}{spell_callsign(callsign)}, {msg[0].lower() + msg[1:]}."


# ---- Speech worker ----------------------------------------------------------
speech_q: "queue.Queue[str | None]" = queue.Queue()


def tts_worker():
    """Speaks one phrase at a time; the next starts only after the last finishes."""
    use_mac_say = sys.platform == "darwin"
    engine = None
    if not use_mac_say:
        engine = pyttsx3.init()
        engine.setProperty("rate", SPEECH_RATE)
    while True:
        phrase = speech_q.get()
        if phrase is None:
            break
        if use_mac_say:
            # subprocess.run blocks until `say` has finished talking.
            subprocess.run(["say", "-r", str(SPEECH_RATE), phrase])
        else:
            engine.say(phrase)
            engine.runAndWait()


LINE = re.compile(r"^\s*([A-Za-z]{2,3}\d{1,4}[A-Za-z]?)\s*:\s*(.+?)\s*$")


def on_game_line(text: str):
    m = LINE.match(text or "")
    if not m:
        return
    callsign, message = m.group(1).upper(), m.group(2)
    phrase = to_speech(callsign, message)
    print(f"[game] {callsign}: {message}\n   -> {phrase}")
    speech_q.put(phrase)


def on_debug(text: str):
    print(f"[debug] {text!r}")


def on_typed(text: str):
    text = (text or "").strip()
    if text:
        print(f"[typed] {text}")
        speech_q.put(text)


# ---- JavaScript injected into every page/frame -------------------------------
INJECT_JS = r"""
(() => {
  const LINE = /([A-Za-z]{2,3}\d{1,4}[A-Za-z]?)\s*:\s*[^\n]+/g;
  const recent = new Map();
  const lastText = new WeakMap();
  const DEBUG = %DEBUG%;
  const TYPED = %TYPED%;

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
    LINE.lastIndex = 0;
    let m;
    while ((m = LINE.exec(text)) !== null) emit(m[0]);
  }

  function start() {
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


def main():
    threading.Thread(target=tts_worker, daemon=True).start()
    js = (INJECT_JS
          .replace("%DEBUG%", "true" if DEBUG else "false")
          .replace("%TYPED%", "true" if SPEAK_TYPED_INPUT else "false"))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)        
        context = browser.new_context()
        context.expose_function("pyGameLine", on_game_line)
        context.expose_function("pyDebug", on_debug)
        context.expose_function("pyTyped", on_typed)
        context.add_init_script(js)
        page = context.new_page()
        page.goto(URL)
        print("Game open. Close the window to quit.")
        while not page.is_closed():
            page.wait_for_timeout(500)
        browser.close()
    speech_q.put(None)


if __name__ == "__main__":
    main()
