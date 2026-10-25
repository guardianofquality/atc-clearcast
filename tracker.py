"""Flight progress strip data model and state tracker."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import re


class FlightType(str, Enum):
    ARRIVAL = "ARR"
    DEPARTURE = "DEP"
    UNKNOWN = "FLT"


class FlightStage(str, Enum):
    ENTERING = "ENTERING"           # Initial contact / entered airspace
    READY_TAKEOFF = "READY TKOF"    # Holding short / ready on runway
    CLEARED_TAKEOFF = "CLRD TKOF"   # Cleared for takeoff
    MANEUVERING = "VECTORING"       # Headings / altitudes / speeds assigned
    CLEARED_APPROACH = "CLRD APP"   # Cleared ILS / visual
    CLEARED_LAND = "CLRD LAND"      # Cleared to land
    HANDOFF = "HANDOFF"             # Contact departure / center / ground


@dataclass
class FlightStrip:
    callsign: str
    flight_type: FlightType = FlightType.UNKNOWN
    stage: FlightStage = FlightStage.ENTERING
    runway: Optional[str] = None
    altitude: Optional[str] = None
    heading: Optional[str] = None
    aircraft_model: Optional[str] = None   # e.g., "B77W", "A388", "B738"
    destination_fix: Optional[str] = None  # e.g., "MAXMO", "DAVUS"
    last_instruction: str = ""
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    @property
    def elapsed_seconds(self) -> int:
        return int(time.time() - self.first_seen)

    @property
    def formatted_age(self) -> str:
        """Format elapsed time as '2m 13s' once over 60s, or '45s'."""
        total_sec = self.elapsed_seconds
        if total_sec < 60:
            return f"{total_sec}s"
        mins, secs = divmod(total_sec, 60)
        return f"{mins}m {secs:02d}s"


class FlightTracker:
    """Maintains active flight progress strips and their stages."""

    def __init__(self):
        self.flights: Dict[str, FlightStrip] = {}
        self.airport_name: str = "Terminal"
        self.airport_code: str = ""

    def set_airport(self, code: str, name: str):
        if code:
            self.airport_code = code
        if name:
            self.airport_name = name

    def update_from_dom_strip(
        self,
        callsign: str,
        runway: Optional[str] = None,
        model: Optional[str] = None,
        dest_or_fix: Optional[str] = None,
        heading: Optional[str] = None,
    ) -> FlightStrip:
        """Enrich flight strip with authoritative data scraped directly from DOM ProgressStrip."""
        now = time.time()
        strip = self.flights.get(callsign)
        if not strip:
            strip = FlightStrip(callsign=callsign, first_seen=now)
            self.flights[callsign] = strip

        strip.last_updated = now
        if runway and not strip.runway:
            strip.runway = runway
        if model:
            strip.aircraft_model = model
        if dest_or_fix:
            strip.destination_fix = dest_or_fix
        if heading:
            strip.heading = heading
        return strip

    def update_from_game_line(self, callsign: str, message: str) -> FlightStrip:
        """Parse the message, update the flight's state strip, and return the strip."""
        now = time.time()
        strip = self.flights.get(callsign)
        if not strip:
            strip = FlightStrip(callsign=callsign, first_seen=now)
            self.flights[callsign] = strip

        strip.last_updated = now
        strip.last_instruction = message

        msg_lower = message.lower()

        # Arrival: Entering terminal area
        if "entering" in msg_lower:
            strip.flight_type = FlightType.ARRIVAL
            strip.stage = FlightStage.ENTERING

        # Departure: Ready for takeoff
        elif "ready for takeoff" in msg_lower or "ready on runway" in msg_lower:
            strip.flight_type = FlightType.DEPARTURE
            strip.stage = FlightStage.READY_TAKEOFF
            rwy_match = re.search(r"runway\s+([0-9]{1,2}[LRC]?)", message, re.I)
            if rwy_match:
                strip.runway = rwy_match.group(1).upper()

        # Cleared for takeoff
        elif "cleared for takeoff" in msg_lower:
            strip.flight_type = FlightType.DEPARTURE
            strip.stage = FlightStage.CLEARED_TAKEOFF
            rwy_match = re.search(r"runway\s+([0-9]{1,2}[LRC]?)", message, re.I)
            if rwy_match:
                strip.runway = rwy_match.group(1).upper()

        # Cleared to land
        elif "cleared to land" in msg_lower:
            strip.stage = FlightStage.CLEARED_LAND
            rwy_match = re.search(r"runway\s+([0-9]{1,2}[LRC]?)", message, re.I)
            if rwy_match:
                strip.runway = rwy_match.group(1).upper()

        # Cleared ILS / approach
        elif "cleared ils" in msg_lower or "cleared approach" in msg_lower:
            strip.stage = FlightStage.CLEARED_APPROACH

        # Handoff / departure contact
        elif "contact departure" in msg_lower or "contact center" in msg_lower or "contact ground" in msg_lower:
            strip.stage = FlightStage.HANDOFF

        # Maneuvering (turn, descend, climb, maintain)
        else:
            if strip.stage not in (FlightStage.CLEARED_LAND, FlightStage.HANDOFF):
                strip.stage = FlightStage.MANEUVERING

        # Extract runway if mentioned
        rwy = re.search(r"\b(?:runway|rwy)\s+([0-9]{1,2}[LRC]?)\b", message, re.I)
        if rwy:
            strip.runway = rwy.group(1).upper()

        # Extract heading if mentioned
        hdg = re.search(r"\bheading\s+([0-9]{1,3})\b", message, re.I)
        if hdg:
            strip.heading = hdg.group(1)

        # Extract altitude if mentioned
        alt = re.search(r"\b(?:maintain|climb|descend|to)\s+([0-9]{3,5})\b", message, re.I)
        if alt:
            strip.altitude = alt.group(1)

        return strip

    def get_active_strips(self) -> List[FlightStrip]:
        """Return strips sorted by most recently updated."""
        return sorted(self.flights.values(), key=lambda s: s.last_updated, reverse=True)
