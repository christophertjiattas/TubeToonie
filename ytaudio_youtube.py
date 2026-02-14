from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def normalize_youtube_url(url: str) -> str:
    """Return a canonical YouTube watch URL when possible.

    Why:
    - Users often paste URLs with playlist/mix params like `&list=...`.
    - We only support single videos (`noplaylist=True`), so normalizing to
      `https://www.youtube.com/watch?v=<id>` avoids weird edge cases.

    If the URL can't be parsed, the original string is returned.
    """

    raw = (url or "").strip()
    if not raw:
        return raw

    try:
        parsed = urlparse(raw)

        host = (parsed.netloc or "").lower()
        path = parsed.path or ""

        video_id: str | None = None

        # https://youtu.be/<id>
        if "youtu.be" in host:
            candidate = path.strip("/")
            if candidate:
                video_id = candidate

        # https://www.youtube.com/watch?v=<id>
        if video_id is None and "youtube.com" in host:
            qs = parse_qs(parsed.query)
            v_values = qs.get("v")
            if v_values:
                video_id = v_values[0]

        if not video_id:
            return raw

        # Typical YouTube IDs are 11 chars, but don't be overly strict.
        video_id = video_id.strip()
        if not video_id:
            return raw

        return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        # Be conservative: never break downloads due to a bad parser.
        return raw
