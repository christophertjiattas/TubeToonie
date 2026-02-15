from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ytaudio_tui_keys import read_key


def _build_panel(
    title: str,
    options: list[str],
    selected_index: int,
    *,
    selected: set[int] | None = None,
) -> Panel:
    lines: list[Text] = []

    for idx, label in enumerate(options):
        is_active = idx == selected_index
        cursor = ">" if is_active else " "

        if selected is None:
            row = f"{cursor} {label}"
        else:
            mark = "[x]" if idx in selected else "[ ]"
            row = f"{cursor} {mark} {label}"

        style = "bold cyan" if is_active else ""
        lines.append(Text(row, style=style))

    hint = (
        "↑/↓ to move, Enter to select, Esc to cancel"
        if selected is None
        else "↑/↓ to move, Space to toggle, Enter to confirm, Esc to cancel"
    )

    body = Text("")
    for line in lines:
        body.append(line)
        body.append("\n")
    body.append(Text(hint, style="dim"))

    return Panel(body, title=title, expand=False)


def select_one(console: Console, title: str, options: Iterable[str], *, default_index: int = 0) -> str | None:
    """Arrow-key single-select.

    Returns:
        Selected option label, or None if user cancels (Esc).
    """

    opts = list(options)
    if not opts:
        return None

    selected_index = max(0, min(default_index, len(opts) - 1))

    with Live(
        _build_panel(title, opts, selected_index),
        console=console,
        refresh_per_second=30,
    ) as live:
        while True:
            key = read_key()

            if key == "up":
                selected_index = (selected_index - 1) % len(opts)
            elif key == "down":
                selected_index = (selected_index + 1) % len(opts)
            elif key == "enter":
                return opts[selected_index]
            elif key == "esc":
                return None

            live.update(_build_panel(title, opts, selected_index))


def select_many(console: Console, title: str, options: Iterable[str]) -> list[str] | None:
    """Arrow-key multi-select.

    Returns:
        List of selected option labels, or None if user cancels (Esc).
    """

    opts = list(options)
    if not opts:
        return None

    selected_index = 0
    picked: set[int] = set()

    with Live(
        _build_panel(title, opts, selected_index, selected=picked),
        console=console,
        refresh_per_second=30,
    ) as live:
        while True:
            key = read_key()

            if key == "up":
                selected_index = (selected_index - 1) % len(opts)
            elif key == "down":
                selected_index = (selected_index + 1) % len(opts)
            elif key == "space":
                if selected_index in picked:
                    picked.remove(selected_index)
                else:
                    picked.add(selected_index)
            elif key == "enter":
                return [opts[i] for i in sorted(picked)]
            elif key == "esc":
                return None

            live.update(_build_panel(title, opts, selected_index, selected=picked))
