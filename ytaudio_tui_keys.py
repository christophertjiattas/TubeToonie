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


_ARROW_MAP = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
}


def parse_ansi_escape_sequence(seq: str) -> Key:
    """Parse the bytes *after* an ESC (\x1b) into a normalized key.

    Examples:
        "[A"     -> up
        "OA"     -> up (application cursor mode)
        "[1;5A"  -> up (modifier variants)

    Returns:
        up/down/left/right if recognized.
        esc if *no* bytes followed ESC (standalone Esc key).
        other for unknown escape sequences.

    Rationale:
        Arrow keys must never be misinterpreted as Esc (cancel). If we see some
        bytes after ESC but dont recognize them, we return `other` so callers
        can safely ignore it.
    """

    if not seq:
        return "esc"

    # Common cases:
    #   ESC [ A
    #   ESC O A
    if seq[0] not in ("[", "O"):
        return "other"

    last = seq[-1]
    return _ARROW_MAP.get(last, "other")


def _read_after_escape_unix(
    *,
    max_bytes: int = 8,
    first_timeout_s: float = 0.10,
    next_timeout_s: float = 0.02,
) -> str:
    """Read extra bytes after ESC without blocking forever.

    Terminals usually send arrow keys as a quick multi-byte sequence. The first
    byte can arrive slightly later than ESC, so we wait a touch longer for it.
    """

    import select

    buf: list[str] = []

    # Wait a bit longer for the *first* byte after ESC.
    rlist, _, _ = select.select([sys.stdin], [], [], first_timeout_s)
    if not rlist:
        return ""

    buf.append(sys.stdin.read(1))

    # Then drain remaining bytes quickly.
    for _ in range(max_bytes - 1):
        rlist2, _, _ = select.select([sys.stdin], [], [], next_timeout_s)
        if not rlist2:
            break
        buf.append(sys.stdin.read(1))

    return "".join(buf)


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

        # If stdin isn't a real TTY (or is closed), read() can return "".
        # Treat it like cancel to avoid a tight loop.
        if ch1 == "":
            return "eof"

        if ch1 in ("\r", "\n"):
            return "enter"
        if ch1 == " ":
            return "space"
        if ch1 in ("\x7f",):
            return "backspace"

        if ch1 == "\x1b":
            # Esc can be a standalone key OR the start of an arrow escape sequence.
            seq = _read_after_escape_unix()
            return parse_ansi_escape_sequence(seq)

        return "other"
