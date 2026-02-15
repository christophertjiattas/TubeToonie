#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yt_dlp

from ytaudio_core import DownloadProgress, download_audio, format_bytes, format_speed, prepare_output_dir
from ytaudio_tonie import (
    TonieChapterEdit,
    list_creative_tonies,
    list_creative_tonies_detailed,
    load_tonie_target_ids_from_env,
    maybe_push_to_tonies,
    update_creative_tonie_chapters,
)


def cli_status(message: str) -> None:
    print(message)


def cli_progress(progress: DownloadProgress) -> None:
    percent = progress.percent or "0%"
    speed = format_speed(progress.speed)
    downloaded = format_bytes(progress.downloaded_bytes)
    total = format_bytes(progress.total_bytes)
    print(f"Downloading: {percent.strip()} | {downloaded} / {total} | {speed}")


def _prompt_for_url() -> str:
    url = input("Enter YouTube URL: ").strip()
    if not url:
        raise ValueError("URL cannot be empty.")
    return url


def _prompt_for_output_dir() -> Path:
    raw_dir = input("Output directory (default: current folder): ").strip()
    output_dir = Path(raw_dir) if raw_dir else Path.cwd()
    return prepare_output_dir(output_dir)


def _cmd_list_tonies() -> int:
    try:
        tonies = list_creative_tonies(on_status=cli_status)
        if not tonies:
            print("No Tonies loaded. Configure credentials (env vars or keyring) and install requirements-tonie.txt.")
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


def _cmd_download(args: argparse.Namespace) -> int:
    try:
        url = args.url or _prompt_for_url()
        output_dir = Path(args.output_dir).expanduser() if args.output_dir else _prompt_for_output_dir()

        mp3_path = download_audio(url, output_dir, on_progress=cli_progress, on_status=cli_status)

        targets = load_tonie_target_ids_from_env()
        uploaded = maybe_push_to_tonies(mp3_path, creative_tonie_ids=targets, on_status=cli_status)
        if targets:
            print(f"Tonie uploads attempted: {uploaded}")

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


def _cmd_push_local(args: argparse.Namespace) -> int:
    paths = [Path(p).expanduser() for p in args.files]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print("Missing file(s):")
        for p in missing:
            print(f" - {p}")
        return 1

    targets = load_tonie_target_ids_from_env()

    failures = 0
    for p in paths:
        try:
            title = args.title or p.stem
            uploaded = maybe_push_to_tonies(p, creative_tonie_ids=targets, chapter_title=title, on_status=cli_status)
            if targets:
                print(f"Uploaded '{p.name}' to {uploaded} Tonie(s)")
            else:
                print("Tonie upload not configured (no targets selected).")
        except Exception as error:
            failures += 1
            print(f"Failed to upload {p}: {error}")

    return 0 if failures == 0 else 2


def _prompt_reorder(current_count: int) -> list[int] | None:
    raw = input(
        "New order as comma-separated positions (example: 3,1,2). Enter to skip reordering: "
    ).strip()
    if not raw:
        return None

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    order: list[int] = []
    for p in parts:
        order.append(int(p))

    if sorted(order) != list(range(1, current_count + 1)):
        raise ValueError("Order must be a permutation of 1..N.")

    return order


def _cmd_edit_tonie(args: argparse.Namespace) -> int:
    try:
        tonies = list_creative_tonies_detailed(on_status=cli_status)
        if not tonies:
            print("No Tonies loaded. Configure credentials and install requirements-tonie.txt.")
            return 0

        selected = None
        if args.tonie_id:
            selected = next((t for t in tonies if t.id == args.tonie_id), None)
            if selected is None:
                print("Tonie ID not found.")
                return 1
        else:
            print("\nAvailable Creative Tonies:")
            for idx, t in enumerate(tonies, start=1):
                print(f"  {idx}. {t.name} ({t.id})")
            choice = int(input("Select Tonie number: ").strip())
            selected = tonies[choice - 1]

        if not selected.chapters:
            print("This Tonie has no chapters.")
            return 0

        chapters = list(selected.chapters)

        # rename loop
        while True:
            print("\nChapters:")
            for idx, ch in enumerate(chapters, start=1):
                print(f"  {idx:02d}. {ch.title}")

            raw = input("Rename a chapter? Enter number (or Enter to continue): ").strip()
            if not raw:
                break

            index = int(raw)
            if index < 1 or index > len(chapters):
                print("Invalid chapter number.")
                continue

            new_title = input("New title: ").strip()
            if not new_title:
                print("Title cannot be empty.")
                continue

            old = chapters[index - 1]
            chapters[index - 1] = TonieChapterEdit(
                id=old.id,
                title=new_title,
                file=old.file,
                seconds=old.seconds,
                transcoding=old.transcoding,
            )

        # reorder
        order = _prompt_reorder(len(chapters))
        if order is not None:
            chapters = [chapters[i - 1] for i in order]

        print("\nApplying changes...")
        update_creative_tonie_chapters(selected.id, chapters, on_status=cli_status)
        print("Done. (Your Toniebox will sync changes when online.)")
        return 0

    except KeyboardInterrupt:
        print("Cancelled.")
        return 130
    except Exception as error:
        print(f"Failed to edit Tonie: {error}")
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tubetoonie", description="TubeToonie  YouTube/Local audio > MP3 > Tonie")
    sub = parser.add_subparsers(dest="command")

    p_dl = sub.add_parser("download", help="Download YouTube audio to MP3 (and optionally upload to Tonies)")
    p_dl.add_argument("--url", help="YouTube URL")
    p_dl.add_argument("--output-dir", help="Output directory")
    p_dl.set_defaults(func=_cmd_download)

    p_list = sub.add_parser("list-tonies", help="List Creative Tonies and their chapters")
    p_list.set_defaults(func=lambda _args: _cmd_list_tonies())

    p_push = sub.add_parser("push-local", help="Upload local audio file(s) to Tonies (no YouTube)")
    p_push.add_argument("files", nargs="+", help="Path(s) to local audio files")
    p_push.add_argument("--title", help="Chapter title to use (single title; defaults to filename)")
    p_push.set_defaults(func=_cmd_push_local)

    p_edit = sub.add_parser("edit-tonie", help="Rename/reorder chapters on a Creative Tonie")
    p_edit.add_argument("--tonie-id", help="Creative Tonie ID (if omitted, you'll pick from a list)")
    p_edit.set_defaults(func=_cmd_edit_tonie)

    return parser


def main() -> int:
    # Backwards compat: `python YTAudio.py` acts like interactive download
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        return _cmd_download(argparse.Namespace(url=None, output_dir=None))

    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
