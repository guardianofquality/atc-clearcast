"""Configuration options for ATC-ClearCast."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


DEFAULT_AIRLINES: Dict[str, str] = {
    "AAL": "American",
    "UAL": "United",
    "DAL": "Delta",
    "SWA": "Southwest",
    "BAW": "Speedbird",
    "UAE": "Emirates",
    "QFA": "Qantas",
    "JAL": "Japan Air",
    "ANA": "All Nippon",
    "DLH": "Lufthansa",
    "AFR": "Air France",
    "VIR": "Virgin",
    "ACA": "Air Canada",
    "FDX": "FedEx",
    "GFA": "Gulf Air",
    "FDB": "FlyDubai",
}

DEFAULT_ACRONYMS: List[str] = [
    "ILS", "VOR", "DME", "ATIS", "NDB", "RNAV", "VFR", "IFR", "QNH", "TCAS"
]


@dataclass
class Config:
    url: str = "https://atc-sim.com/"
    speech_rate: int = 100
    browser_channel: str = "chrome"
    headless: bool = False

    speak_typed_input: bool = False
    debug: bool = False

    airport_name: str = "Approach"
    airport_code: str = ""

    use_airline_names: bool = True
    flight_prefix: bool = False
    say_feet: bool = True
    aviation_digits: bool = False

    airlines: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_AIRLINES))
    acronyms: List[str] = field(default_factory=lambda: list(DEFAULT_ACRONYMS))
    custom_phrases: List[Tuple[str, str]] = field(default_factory=list)
