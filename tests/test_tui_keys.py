from __future__ import annotations

from ytaudio_tui_keys import parse_ansi_escape_sequence


def test_parse_ansi_escape_sequence_bracket_arrows():
    assert parse_ansi_escape_sequence("[A") == "up"
    assert parse_ansi_escape_sequence("[B") == "down"
    assert parse_ansi_escape_sequence("[C") == "right"
    assert parse_ansi_escape_sequence("[D") == "left"


def test_parse_ansi_escape_sequence_application_arrows():
    # Some terminals send ESC O A/B/C/D
    assert parse_ansi_escape_sequence("OA") == "up"
    assert parse_ansi_escape_sequence("OB") == "down"
    assert parse_ansi_escape_sequence("OC") == "right"
    assert parse_ansi_escape_sequence("OD") == "left"


def test_parse_ansi_escape_sequence_modifier_variant():
    # Example of a longer ANSI sequence; last byte defines direction.
    assert parse_ansi_escape_sequence("[1;5A") == "up"


def test_parse_ansi_escape_sequence_unknown_is_esc():
    assert parse_ansi_escape_sequence("") == "esc"
    assert parse_ansi_escape_sequence("?") == "esc"
    assert parse_ansi_escape_sequence("[Z") == "esc"
