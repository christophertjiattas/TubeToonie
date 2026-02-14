from __future__ import annotations

from pathlib import Path


def parse_urls_from_text(text: str) -> list[str]:
    """Parse newline-separated URLs.

    Empty lines are ignored and whitespace is trimmed.
    """

    return [line.strip() for line in text.splitlines() if line.strip()]


def load_urls_from_file(path: Path) -> list[str]:
    """Load URLs from a text file (one URL per line)."""

    return parse_urls_from_text(path.read_text(encoding="utf-8"))


def resolve_urls(single_url: str, uploaded_text: str | None) -> list[str]:
    """Resolve URLs from either a single-url field or uploaded text."""

    if uploaded_text:
        return parse_urls_from_text(uploaded_text)
    if single_url.strip():
        return [single_url.strip()]
    return []
