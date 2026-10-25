"""Unit tests for ATC phraseology conversion."""

from config import Config
from phraseology import PhraseologyConverter


def test_callsign_conversion():
    conv = PhraseologyConverter(Config(use_airline_names=True))
    assert conv.spell_callsign("BAW123") == "Speedbird one two three"
    assert conv.spell_callsign("UAL456") == "United four five six"
    assert conv.spell_callsign("XYZ99") == "X Y Z nine nine"


def test_aviation_digits():
    conv_icao = PhraseologyConverter(Config(aviation_digits=True))
    assert conv_icao.digits("359") == "tree fife niner"

    conv_plain = PhraseologyConverter(Config(aviation_digits=False))
    assert conv_plain.digits("359") == "three five nine"


def test_altitude_conversion():
    conv = PhraseologyConverter(Config(say_feet=True))
    assert conv.say_altitude(3000) == "three thousand"
    assert conv.say_altitude(2500) == "two thousand five hundred"
    assert conv.say_altitude(12000) == "one two thousand"
    assert conv.say_altitude(800) == "eight hundred"


def test_sentence_conversion():
    conv = PhraseologyConverter(Config(say_feet=True, use_airline_names=True))
    line = "Descend and maintain 3000 feet, expedite."
    converted = conv.convert("BAW535", line)
    assert converted == "Speedbird five three five, descend and maintain three thousand feet, expedite descent."


def test_runway_heading_frequency():
    conv = PhraseologyConverter(Config())
    # Runway designator
    assert "runway two seven right" in conv.convert("AAL1", "cleared to land runway 27R")
    # Heading
    assert "heading two seven zero" in conv.convert("AAL1", "turn heading 270")
    # Frequency
    assert "one one eight point five" in conv.convert("AAL1", "contact tower 118.5")


def test_arrival_departure_realism():
    conv = PhraseologyConverter(Config(use_airline_names=True, airport_name="Dubai"))
    # Arrival initial contact
    arr = conv.convert("UAE160", "Entering terminal area.")
    assert "Emirates one six zero" in arr
    assert "entering Dubai terminal area, awaiting instructions" in arr

    # Departure ready
    dep = conv.convert("UAE757", "Ready for takeoff on runway 30L.")
    assert "Emirates seven five seven" in dep
    assert "holding short runway three zero left, ready for departure" in dep


def test_unable_and_invalid_commands():
    conv = PhraseologyConverter(Config(use_airline_names=True))

    # Test 'unable to comply'
    unable_with_cs = conv.convert("UAE757", "Unable to comply.")
    assert "Emirates seven five seven" in unable_with_cs
    assert "conflict detected on runway or separation" in unable_with_cs
    assert "please verify your last transmission" in unable_with_cs

    unable_system = conv.convert("SYSTEM", "Unable to comply")
    assert "conflict detected on runway or separation" in unable_system

    # Test 'invalid command'
    invalid_with_cs = conv.convert("BAW123", "Invalid command.")
    assert "Speedbird one two three" in invalid_with_cs
    assert "say again instruction, transmission unreadable" in invalid_with_cs
    assert "please guide" in invalid_with_cs


def test_compound_departure_clearance():
    conv = PhraseologyConverter(Config(use_airline_names=True, say_feet=True))
    raw = "Cleared to 10000 feet. Runway 30L, cleared for takeoff. Cleared to MIADA."
    spoken = conv.convert("FDB287", raw)
    assert "FlyDubai two eight seven" in spoken
    assert "direct MIADA" in spoken
    assert "climb and maintain one zero thousand feet" in spoken
    assert "Runway three zero left, cleared for takeoff." in spoken


if __name__ == "__main__":
    test_callsign_conversion()
    test_aviation_digits()
    test_altitude_conversion()
    test_sentence_conversion()
    test_runway_heading_frequency()
    test_arrival_departure_realism()
    test_unable_and_invalid_commands()
    test_compound_departure_clearance()
    print("All phraseology tests passed successfully!")
