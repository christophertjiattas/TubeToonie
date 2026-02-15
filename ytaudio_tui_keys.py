from __future__ import annotations

from contextlib import contextmanager
import os
import sys


Key = str


@contextmanager
def _raw_mode_unix():
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key() -> Key:
    """Read a single keypress and normalize to a small set of names.

    Returns one of:
        up, down, left, right, enter, esc, space, backspace, other

    Notes:
        - Uses termios/tty on unix.
        - Uses msvcrt on Windows.
    """

    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x1b":
            return "esc"
        if ch == " ":
            return "space"
        if ch in ("\x08",):
            return "backspace"

        # Arrow keys come as a prefix + code.
        if ch in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            return {
                "H": "up",
                "P": "down",
                "K": "left",
                "M": "right",
            }.get(code, "other")

        return "other"

    with _raw_mode_unix():
        ch1 = sys.stdin.read(1)
        if ch1 in ("\r", "\n"):
            return "enter"
        if ch1 == "\x1b":
            # Possibly an escape sequence
            ch2 = sys.stdin.read(1)
            if ch2 != "[":
                return "esc"
            ch3 = sys.stdin.read(1)
            return {
                "A": "up",
                "B": "down",
                "C": "right",
                "D": "left",
            }.get(ch3, "other")
        if ch1 == " ":
            return "space"
        if ch1 in ("\x7f",):
            return "backspace"

        return "other"
