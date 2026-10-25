"""Entry point for ATC-ClearCast."""

import argparse
import sys
from config import Config
from phraseology import PhraseologyConverter
from tracker import FlightTracker
from tts import TTSService
from ui import TerminalUI
from watcher import ATCSimWatcher


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="ATC-ClearCast: Real-time text-to-speech for ATC-SIM communications."
    )
    parser.add_argument(
        "--url",
        default="https://atc-sim.com/",
        help="Target simulator URL (default: https://atc-sim.com/)",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=175,
        help="Speech speed rate in words per minute (default: 175)",
    )
    parser.add_argument(
        "--browser",
        default="chrome",
        help="Browser channel to launch (e.g. 'chrome', 'msedge', or empty for bundled Chromium)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--speak-typed",
        action="store_true",
        help="Also speak commands typed into the input field",
    )
    parser.add_argument(
        "--flight-prefix",
        action="store_true",
        help="Prefix aircraft callsign with 'Flight' (e.g., 'Flight United 123')",
    )
    parser.add_argument(
        "--aviation-digits",
        action="store_true",
        help="Use ICAO aviation pronunciation ('tree', 'fife', 'niner')",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw DOM text captured from the game",
    )

    args = parser.parse_args()

    return Config(
        url=args.url,
        speech_rate=args.rate,
        browser_channel=args.browser if args.browser else None,
        headless=args.headless,
        speak_typed_input=args.speak_typed,
        flight_prefix=args.flight_prefix,
        aviation_digits=args.aviation_digits,
        debug=args.debug,
    )


def main():
    config = parse_args()

    phraseology = PhraseologyConverter(config)
    tts = TTSService(speech_rate=config.speech_rate)
    tts.start()

    tracker = FlightTracker()
    ui = TerminalUI(tracker)

    watcher = ATCSimWatcher(config, phraseology, tts, tracker, ui)

    try:
        watcher.run()
    except KeyboardInterrupt:
        print("\nExiting ATC-ClearCast...")
    finally:
        tts.stop()


if __name__ == "__main__":
    main()
