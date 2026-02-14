#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse

import sys

import yt_dlp

from ytaudio_core import DownloadProgress, download_audio, format_bytes, format_speed, prepare_output_dir
from ytaudio_tonie import list_creative_tonies, load_tonie_target_ids_from_env, maybe_push_to_tonies


def prompt_for_url() -> str:
    url = input("Enter YouTube URL: ").strip()
    if not url:
        raise ValueError("URL cannot be empty.")
    return url


def prompt_for_output_dir() -> Path:
    raw_dir = input("Output directory (default: current folder): ").strip()
    output_dir = Path(raw_dir) if raw_dir else Path.cwd()
    return prepare_output_dir(output_dir)


def cli_status(message: str) -> None:
    print(message)


def cli_progress(progress: DownloadProgress) -> None:
    percent = progress.percent or "0%"
    speed = format_speed(progress.speed)
    downloaded = format_bytes(progress.downloaded_bytes)
    total = format_bytes(progress.total_bytes)
    print(f"Downloading: {percent.strip()} | {downloaded} / {total} | {speed}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YTAudio  YouTube to MP3 downloader")
    parser.add_argument("--list-tonies", action="store_true", help="List Creative Tonies and their chapters")
    return parser


def _print_tonies() -> int:
    try:
        tonies = list_creative_tonies(on_status=cli_status)
        if not tonies:
            print(
                "No Tonies loaded. Set TONIE_USERNAME and TONIE_PASSWORD (and install requirements-tonie.txt) to use this."
            )
            return 0

        for tonie in tonies:
            print(f"\n{tonie.name} ({tonie.id})")
            if not tonie.chapters:
                print("  (no chapters)")
            else:
                for index, chapter in enumerate(tonie.chapters, start=1):
                    print(f"  {index:02d}. {chapter.title}")

        return 0
    except Exception as error:
        print(f"Failed to list Tonies: {error}")
        return 4


def main() -> int:
    print("YTAudio: YouTube to MP3 downloader")

    args = _build_parser().parse_args()
    if args.list_tonies:
        return _print_tonies()

    try:
        url = prompt_for_url()
        output_dir = prompt_for_output_dir()
        mp3_path = download_audio(url, output_dir, on_progress=cli_progress, on_status=cli_status)
        maybe_push_to_tonies(mp3_path, creative_tonie_ids=load_tonie_target_ids_from_env(), on_status=cli_status)
        print(f"All done! File saved in: {output_dir}")
        return 0
    except ValueError as error:
        print(f"Input error: {error}")
        return 1
    except yt_dlp.utils.DownloadError as error:
        print(f"Download error: {error}")
        return 2
    except KeyboardInterrupt:
        print("Cancelled by user.")
        return 130
    except Exception as error:
        print(f"Unexpected error: {error}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
