from __future__ import annotations

import io

from rich.console import Console

import ytaudio_tui_select


def test_select_one_navigation(monkeypatch):
    # Simulate: down, down, enter
    keys = iter(["down", "down", "enter"])

    def fake_read_key():
        return next(keys)

    monkeypatch.setattr(ytaudio_tui_select, "read_key", fake_read_key)

    console = Console(file=io.StringIO(), force_terminal=False, color_system=None, width=60)

    choice = ytaudio_tui_select.select_one(console, "Pick", ["a", "b", "c"], default_index=0)
    assert choice == "c"


def test_select_one_cancel(monkeypatch):
    keys = iter(["esc"])

    def fake_read_key():
        return next(keys)

    monkeypatch.setattr(ytaudio_tui_select, "read_key", fake_read_key)

    console = Console(file=io.StringIO(), force_terminal=False, color_system=None, width=60)
    choice = ytaudio_tui_select.select_one(console, "Pick", ["a", "b"], default_index=0)
    assert choice is None
