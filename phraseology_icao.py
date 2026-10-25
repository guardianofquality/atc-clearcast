"""Standard ICAO Doc 4444 / Doc 9432 Radiotelephony Grammar and Intent Pipeline.

This module models ATC transmissions as structured intents rather than ad-hoc regexes.
Intents are extracted and serialized in standard international ATC sequence:
1. Callsign
2. Route / Clearance Limit (e.g. direct FIX)
3. Heading / Maneuver
4. Level / Altitude
5. Speed
6. Radio / Frequency
7. Critical Clearances (Takeoff / Land / Approach)
"""

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional
from config import Config

DIGITS_ICAO = {
    "0": "zero", "1": "one", "2": "two", "3": "tree", "4": "four",
    "5": "fife", "6": "six", "7": "seven", "8": "eight", "9": "niner",
}
DIGITS_PLAIN = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}
SIDES = {"L": "left", "R": "right", "C": "center"}
CALLSIGN_PATTERN = re.compile(r"^\s*([A-Za-z]{2,3}\d{1,4}[A-Za-z]?)\s*:\s*(.+?)\s*$")


class IntentPriority(IntEnum):
    """ICAO Doc 4444 sequencing order for ATC clearances."""
    SPECIAL_ALERT = 0    # Unable to comply, invalid command
    CHECK_IN = 1         # Entering airspace, ready on runway
    ROUTE_FIX = 2        # Route clearance limit / direct waypoint
    HEADING = 3          # Turn left/right heading XXX
    LEVEL = 4            # Climb / descend / maintain altitude
    SPEED = 5            # Speeds (knots)
    APPROACH = 6         # Cleared ILS / visual approach / intercept localizer
    HOLD_SHORT = 7       # Hold short of runway
    FREQUENCY = 8        # Contact tower / departure / ground
    CRITICAL = 9         # Cleared for takeoff / Cleared to land / Go-around


@dataclass(order=True)
class ATCIntent:
    priority: IntentPriority
    phrase: str = field(compare=False)


class ICAOPhraseologyEngine:
    """Decomposes game text into ICAO intents and serializes them in standard order."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    @property
    def digits_map(self):
        return DIGITS_ICAO if self.config.aviation_digits else DIGITS_PLAIN

    def digits(self, s: str) -> str:
        d = self.digits_map
        return " ".join(d.get(c, c) for c in s)

    def say_number(self, num: str) -> str:
        d = self.digits_map
        return " ".join(d[c] if c.isdigit() else SIDES.get(c.upper(), c) for c in num)

    def spell_callsign(self, cs: str) -> str:
        d = self.digits_map
        m = re.fullmatch(r"([A-Z]{2,3})(\d+[A-Z]?)", cs.upper())
        if not m:
            return " ".join(cs)

        prefix, number = m.groups()
        if self.config.use_airline_names and prefix in self.config.airlines:
            head = self.config.airlines[prefix]
        else:
            head = " ".join(prefix)

        spoken_number = " ".join(d.get(c, c) for c in number)
        return f"{head} {spoken_number}"

    def say_altitude(self, n: int) -> str:
        d = self.digits_map
        thousands, rest = divmod(n, 1000)
        parts = []

        if thousands:
            parts.append(self.digits(str(thousands)) + " thousand")
        if rest:
            hundreds, tens = divmod(rest, 100)
            if hundreds:
                parts.append(d[str(hundreds)] + " hundred")
            if tens:
                parts.append(self.digits(f"{tens:02d}"))

        return " ".join(parts) or d["0"]

    def extract_intents(self, text: str) -> List[ATCIntent]:
        """Extract all ICAO standard intents from raw text."""
        intents: List[ATCIntent] = []
        raw = text.strip()

        # Special Alert 1: Unable to Comply
        if re.search(r"\bunable to comply\b", raw, re.I):
            intents.append(ATCIntent(
                priority=IntentPriority.SPECIAL_ALERT,
                phrase="unable to comply, conflict detected on runway or separation. Controller, please verify your last transmission and resequence"
            ))
            return intents

        # Special Alert 2: Invalid command
        if re.search(r"\binvalid command\b", raw, re.I):
            intents.append(ATCIntent(
                priority=IntentPriority.SPECIAL_ALERT,
                phrase="say again instruction, transmission unreadable. Tower, please guide and issue valid heading, altitude, or clearance"
            ))
            return intents

        # Check-in: Entering terminal area
        if re.search(r"\bentering terminal area\b", raw, re.I):
            airport = self.config.airport_name or "Approach"
            intents.append(ATCIntent(
                priority=IntentPriority.CHECK_IN,
                phrase=f"with you entering {airport} terminal area, awaiting instructions"
            ))
            return intents

        # Check-in: Ready for takeoff
        m_ready = re.search(r"\bready (?:for takeoff on|on)?\s*(?:runway\s+)?(\d{1,2}[LRC]?)\b", raw, re.I)
        if m_ready and not re.search(r"\bcleared for takeoff\b", raw, re.I):
            rwy = self.say_number(m_ready.group(1))
            intents.append(ATCIntent(
                priority=IntentPriority.CHECK_IN,
                phrase=f"holding short runway {rwy}, ready for departure"
            ))
            return intents

        # Route / Clearance Limit (e.g. "Cleared to MIADA" -> "direct MIADA")
        for m_fix in re.finditer(r"\b(?:cleared to|direct)\s+([A-Za-z]{3,6})\b", raw, re.I):
            fix_name = m_fix.group(1).upper()
            if not fix_name.isdigit() and fix_name not in ("FEET", "LAND", "TAKEOFF"):
                intents.append(ATCIntent(
                    priority=IntentPriority.ROUTE_FIX,
                    phrase=f"direct {fix_name}"
                ))

        # Heading / Turn
        m_hdg = re.search(r"\b(?:turn\s+(left|right)\s+)?(?:heading|hdg)\s+([0-3]?\d{2})\b", raw, re.I)
        if m_hdg:
            turn_dir = m_hdg.group(1).lower() if m_hdg.group(1) else ""
            hdg_spoken = self.digits(m_hdg.group(2))
            prefix = f"turn {turn_dir} " if turn_dir else ""
            intents.append(ATCIntent(
                priority=IntentPriority.HEADING,
                phrase=f"{prefix}heading {hdg_spoken}".strip()
            ))

        # Level / Altitude (FL or feet)
        # 1. Flight Level: "FL240" / "flight level 240"
        m_fl = re.search(r"\b(?:flight level|FL)\s*(\d{2,3})\b", raw, re.I)
        if m_fl:
            fl_spoken = self.digits(m_fl.group(1))
            intents.append(ATCIntent(
                priority=IntentPriority.LEVEL,
                phrase=f"climb and maintain flight level {fl_spoken}"
            ))
        else:
            # 2. Altitudes: "cleared to 10000", "maintain 4000", "descend to 3000"
            m_alt = re.search(r"\b(?:maintain|climb|descend|cleared to|to)\s+(\d{3,5})\s*(?:feet|foot|ft|\'|\b)", raw, re.I)
            if m_alt:
                alt_val = int(m_alt.group(1))
                spoken_alt = self.say_altitude(alt_val)
                feet_str = " feet" if self.config.say_feet else ""
                
                # Determine verb (climb / descend / maintain)
                if re.search(r"\bdescend", raw, re.I):
                    verb = "descend and maintain"
                elif re.search(r"\bclimb", raw, re.I) or re.search(r"\bcleared for takeoff", raw, re.I):
                    verb = "climb and maintain"
                else:
                    verb = "maintain"

                expedite_str = ""
                if re.search(r"\bexpedite\b", raw, re.I):
                    expedite_str = ", expedite descent" if "descend" in verb else ", expedite climb"

                intents.append(ATCIntent(
                    priority=IntentPriority.LEVEL,
                    phrase=f"{verb} {spoken_alt}{feet_str}{expedite_str}"
                ))

        # Speed (e.g. "reduce speed to 180 knots")
        m_spd = re.search(r"\b(?:reduce speed to|speed)\s+(\d{2,3})\s*(?:knots|kts|kt)?\b", raw, re.I)
        if m_spd:
            spd_spoken = self.digits(m_spd.group(1))
            intents.append(ATCIntent(
                priority=IntentPriority.SPEED,
                phrase=f"speed {spd_spoken} knots"
            ))

        # Frequency (e.g. "contact tower 118.5")
        m_freq = re.search(r"\b(?:contact\s+([A-Za-z]+)\s+)?(\d{3})\.(\d{1,3})\b", raw, re.I)
        if m_freq:
            station = m_freq.group(1).lower() if m_freq.group(1) else "tower"
            freq_spoken = self.digits(m_freq.group(2)) + " point " + self.digits(m_freq.group(3))
            intents.append(ATCIntent(
                priority=IntentPriority.FREQUENCY,
                phrase=f"contact {station} {freq_spoken}"
            ))

        # Critical Clearance 1: Takeoff
        m_tkof = re.search(r"\b(?:runway\s+)?(\d{1,2}[LRC]?)[,\.\s]+cleared for takeoff\b", raw, re.I)
        if m_tkof:
            rwy_spoken = self.say_number(m_tkof.group(1))
            intents.append(ATCIntent(
                priority=IntentPriority.CRITICAL,
                phrase=f"runway {rwy_spoken}, cleared for takeoff"
            ))
        elif re.search(r"\bcleared for takeoff\b", raw, re.I):
            intents.append(ATCIntent(
                priority=IntentPriority.CRITICAL,
                phrase="cleared for takeoff"
            ))

        # Critical Clearance 2: Landing
        m_land = re.search(r"\bcleared to land(?:\s+runway\s+(\d{1,2}[LRC]?))?\b", raw, re.I)
        if m_land:
            rwy = m_land.group(1)
            rwy_str = f" runway {self.say_number(rwy)}" if rwy else ""
            intents.append(ATCIntent(
                priority=IntentPriority.CRITICAL,
                phrase=f"cleared to land{rwy_str}"
            ))

        # Approach (ILS / Visual / Intercept)
        m_app = re.search(r"\bcleared\s+(?:visual\s+approach|ils|approach)(?:\s+runway\s+(\d{1,2}[LRC]?))?\b", raw, re.I)
        if m_app:
            rwy_txt = f" runway {self.say_number(m_app.group(1))}" if m_app.group(1) else ""
            if "visual" in raw.lower():
                intents.append(ATCIntent(
                    priority=IntentPriority.APPROACH,
                    phrase=f"cleared visual approach{rwy_txt}"
                ))
            else:
                intents.append(ATCIntent(
                    priority=IntentPriority.APPROACH,
                    phrase=f"cleared I L S approach{rwy_txt}"
                ))

        if re.search(r"\bintercept\s+localizer\b", raw, re.I):
            intents.append(ATCIntent(
                priority=IntentPriority.APPROACH,
                phrase="intercept localizer"
            ))

        # Hold Short (Runway safety critical)
        m_hold = re.search(r"\bhold\s+short(?:\s+of)?\s+(?:runway\s+)?(\d{1,2}[LRC]?)\b", raw, re.I)
        if m_hold:
            rwy_spoken = self.say_number(m_hold.group(1))
            intents.append(ATCIntent(
                priority=IntentPriority.HOLD_SHORT,
                phrase=f"hold short runway {rwy_spoken}"
            ))

        # Go-around / Missed approach
        if re.search(r"\bgo\s*around\b", raw, re.I):
            intents.append(ATCIntent(
                priority=IntentPriority.CRITICAL,
                phrase="go around, fly missed approach"
            ))

        return intents

    def convert(self, callsign: str, raw_message: str) -> str:
        """Compose standard ATC transmission using sorted ICAO intents."""
        intents = self.extract_intents(raw_message)

        prefix = "Flight " if self.config.flight_prefix else ""
        spoken_cs = self.spell_callsign(callsign) if callsign and callsign != "SYSTEM" else ""

        if not intents:
            # Fallback for unrecognized phrases
            clean = raw_message.strip().rstrip(".")
            return f"{prefix}{spoken_cs}, {clean}." if spoken_cs else f"{clean}."

        # Sort strictly by ICAO Priority order:
        # Route -> Heading -> Altitude -> Speed -> Approach -> Runway/Takeoff/Land
        intents.sort()

        clauses = [item.phrase for item in intents]

        # For critical takeoff clearances, format cleanly with period separation:
        # e.g., "Speedbird 123, direct MIADA, climb and maintain 10000. Runway 30L, cleared for takeoff."
        if any(i.priority == IntentPriority.CRITICAL for i in intents) and len(clauses) > 1:
            pre_critical = clauses[:-1]
            critical = clauses[-1]
            first_sentence = ", ".join(pre_critical)
            if spoken_cs:
                return f"{prefix}{spoken_cs}, {first_sentence}. {critical[0].upper() + critical[1:]}."
            else:
                return f"{first_sentence}. {critical[0].upper() + critical[1:]}."

        main_body = ", ".join(clauses)
        if spoken_cs:
            return f"{prefix}{spoken_cs}, {main_body}."
        else:
            return f"{main_body[0].upper() + main_body[1:]}."

    def parse_game_line(self, line: str) -> tuple[str, str] | None:
        m = CALLSIGN_PATTERN.match(line or "")
        if not m:
            return None
        return m.group(1).upper(), m.group(2)
