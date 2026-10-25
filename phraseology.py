"""ATC radiotelephony phraseology formatting and conversion.

Powered by standard ICAO Doc 4444 / Doc 9432 grammar pipeline.
"""

from phraseology_icao import (
    ICAOPhraseologyEngine,
    ATCIntent,
    IntentPriority,
    DIGITS_ICAO,
    DIGITS_PLAIN,
    SIDES,
    CALLSIGN_PATTERN,
)

# Alias for backwards compatibility across the project
PhraseologyConverter = ICAOPhraseologyEngine

__all__ = [
    "PhraseologyConverter",
    "ICAOPhraseologyEngine",
    "ATCIntent",
    "IntentPriority",
    "DIGITS_ICAO",
    "DIGITS_PLAIN",
    "SIDES",
    "CALLSIGN_PATTERN",
]
