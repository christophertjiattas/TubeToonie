from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Optional

import yt_dlp

from ytaudio_youtube import normalize_youtube_url


def _find_latest_mp3(output_dir: Path) -> Path | None:
    candidates = sorted(output_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

StatusCallback = Callable[[str], None]


@dataclass
class DownloadProgress:
    status: str
    percent: Optional[str]
    downloaded_bytes: Optional[float]
    total_bytes: Optional[float]
    speed: Optional[float]


def prepare_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def format_bytes(value: Optional[float]) -> str:
    if not value:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:,.2f} {unit}"
        size /= 1024
    return f"{size:,.2f} TB"


def format_speed(value: Optional[float]) -> str:
    if not value:
        return "0 B/s"
    return f"{format_bytes(value)}/s"


def _cookiefile_from_env() -> str | None:
    raw = os.getenv("YTAUDIO_COOKIEFILE", "").strip()
    if not raw:
        return None
    return str(Path(raw).expanduser())


def _cookies_from_browser_from_env() -> tuple[str, ...] | None:
    """Parse cookies-from-browser setting.

    Expected format (env var):
      YTAUDIO_COOKIES_FROM_BROWSER=chrome
      YTAUDIO_COOKIES_FROM_BROWSER=chrome,Default

    We intentionally keep this minimal (YAGNI): its enough for most cases.
    """

    raw = os.getenv("YTAUDIO_COOKIES_FROM_BROWSER", "").strip()
    if not raw:
        return None
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        return None
    return tuple(parts)


def _youtube_player_client_from_env() -> str:
    """Pick a YouTube player client for yt-dlp.

    YouTube breaks the web client extraction semi-regularly. The Android client
    is often more stable.

    Override via:
      export YTAUDIO_YOUTUBE_PLAYER_CLIENT=web
    """

    raw = os.getenv("YTAUDIO_YOUTUBE_PLAYER_CLIENT", "").strip().lower()
    return raw or "android"


def _progress_hook_factory(
    on_progress: Optional[Callable[[DownloadProgress], None]],
    on_status: Optional[StatusCallback],
):
    def progress_hook(progress: dict[str, Any]) -> None:
        status = progress.get("status") or ""
        if status == "downloading":
            event = DownloadProgress(
                status=status,
                percent=progress.get("_percent_str"),
                downloaded_bytes=progress.get("downloaded_bytes"),
                total_bytes=progress.get("total_bytes") or progress.get("total_bytes_estimate"),
                speed=progress.get("speed"),
            )
            if on_progress:
                on_progress(event)
        elif status == "finished" and on_status:
            on_status("Download complete. Starting conversion to MP3...")

    return progress_hook


def _postprocess_hook(on_status: Optional[StatusCallback]):
    def postprocess_hook(progress: dict[str, Any]) -> None:
        status = progress.get("status")
        if status == "started" and on_status:
            on_status("Converting with FFmpeg...")
        elif status == "finished" and on_status:
            on_status("Conversion finished.")

    return postprocess_hook


def download_audio(
    url: str,
    output_dir: Path,
    *,
    on_progress: Optional[Callable[[DownloadProgress], None]] = None,
    on_status: Optional[StatusCallback] = None,
) -> Path:
    if on_status:
        on_status("Preparing download...")

    url = normalize_youtube_url(url)

    cookiefile = _cookiefile_from_env()
    cookies_from_browser = _cookies_from_browser_from_env()
    youtube_player_client = _youtube_player_client_from_env()

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # YouTube occasionally throws 403s; retries + a normal UA helps.
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        "cookiefile": cookiefile,
        "cookiesfrombrowser": cookies_from_browser,
        "extractor_args": {"youtube": {"player_client": [youtube_player_client]}},
        "progress_hooks": [_progress_hook_factory(on_progress, on_status)],
        "postprocessor_hooks": [_postprocess_hook(on_status)],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    # Keep opts clean: don't pass None values into yt-dlp.
    if ydl_opts.get("cookiefile") is None:
        ydl_opts.pop("cookiefile", None)
    if ydl_opts.get("cookiesfrombrowser") is None:
        ydl_opts.pop("cookiesfrombrowser", None)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        # When a playlist sneaks in, yt-dlp can return an 'entries' list.
        if isinstance(info, dict) and info.get("entries"):
            entries = list(info.get("entries") or [])
            if entries:
                info = entries[0]

        expected = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
        if expected.exists():
            return expected

        # Fallback: find the newest mp3 in the directory.
        latest = _find_latest_mp3(output_dir)
        if latest is not None:
            return latest

        raise FileNotFoundError(
            "Download finished but MP3 could not be located in output directory. "
            f"Expected: {expected}"
        )
