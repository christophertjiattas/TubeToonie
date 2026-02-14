#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Prompt
from rich.text import Text

from ytaudio_core import DownloadProgress, download_audio, prepare_output_dir
from ytaudio_tonie import load_tonie_target_ids_from_env, maybe_push_to_tonies
from ytaudio_inputs import load_urls_from_file, parse_urls_from_text


@dataclass(frozen=True)
class ResolvedInputs:
    urls: list[str]
    output_dir: Path


def _parse_percent(percent: str | None) -> float:
    if not percent:
        return 0.0
    cleaned = percent.strip().strip("%")
    try:
        return max(0.0, min(100.0, float(cleaned)))
    except ValueError:
        return 0.0


def _prompt_multiline(console: Console) -> str:
    console.print("Paste URLs (one per line). Submit an empty line to finish:")
    lines: list[str] = []
    while True:
        line = console.input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def _prompt_for_inputs(console: Console) -> ResolvedInputs:
    console.print(Panel("[b]YTAudio TUI[/b] \u2014 YouTube \u2192 MP3 downloader", expand=False))

    mode = Prompt.ask(
        "Input mode",
        choices=["single", "paste", "file"],
        default="single",
    )

    if mode == "single":
        url = Prompt.ask("YouTube URL").strip()
        urls = [url] if url else []
    elif mode == "paste":
        pasted = _prompt_multiline(console)
        urls = parse_urls_from_text(pasted)
    else:
        raw_path = Prompt.ask("Path to .txt file containing URLs")
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise ValueError(f"File does not exist: {path}")
        urls = load_urls_from_file(path)

    default_dir = str(Path.cwd() / "downloads")
    output_dir = Path(Prompt.ask("Output directory", default=default_dir)).expanduser()

    if not urls:
        raise ValueError("No URLs provided.")

    return ResolvedInputs(urls=urls, output_dir=prepare_output_dir(output_dir))


class _RichDownloadDisplay:
    def __init__(self, console: Console) -> None:
        self._status = Text("Ready")
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            expand=True,
        )
        self._task_id: int | None = None

    def _ensure_task(self, label: str) -> int:
        if self._task_id is None:
            # Total is unknown at first; we set it when we learn it.
            self._task_id = self._progress.add_task(label, total=100)
        return self._task_id

    def reset(self, label: str) -> None:
        if self._task_id is not None:
            self._progress.remove_task(self._task_id)
            self._task_id = None
        self._ensure_task(label)
        self._progress.update(self._task_id, completed=0)
        self.set_status("Preparing download...")

    def set_status(self, message: str) -> None:
        self._status.plain = message

    def on_progress(self, progress: DownloadProgress, *, label: str) -> None:
        task_id = self._ensure_task(label)

        if progress.total_bytes and progress.downloaded_bytes is not None:
            self._progress.update(task_id, total=progress.total_bytes, completed=progress.downloaded_bytes)
            return

        # Fallback if yt-dlp can't provide total bytes.
        percent_value = _parse_percent(progress.percent)
        self._progress.update(task_id, total=100, completed=percent_value)

    def renderable(self) -> Group:
        return Group(Panel(self._status, title="Status", expand=False), self._progress)


def main() -> int:
    console = Console()

    try:
        inputs = _prompt_for_inputs(console)

        failures: list[str] = []
        display = _RichDownloadDisplay(console)
        with Live(display.renderable(), console=console, refresh_per_second=12):
            total = len(inputs.urls)
            for index, url in enumerate(inputs.urls, start=1):
                label = f"({index}/{total}) Downloading"
                display.reset(label)

                def on_status(message: str) -> None:
                    display.set_status(message)

                def on_progress(event: DownloadProgress) -> None:
                    display.on_progress(event, label=label)

                try:
                    mp3_path = download_audio(url, inputs.output_dir, on_progress=on_progress, on_status=on_status)
                    maybe_push_to_tonies(mp3_path, creative_tonie_ids=load_tonie_target_ids_from_env(), on_status=on_status)
                    display.set_status(f"Done: {url}")
                except yt_dlp.utils.DownloadError as error:
                    failures.append(url)
                    display.set_status(f"Download error: {error}")
                except Exception as error:
                    failures.append(url)
                    display.set_status(f"Unexpected error: {error}")

        if failures:
            console.print("\n[bold red]Some downloads failed:[/bold red]")
            for bad in failures:
                console.print(f" - {bad}")
            console.print(f"\nSaved successful files to: [bold]{inputs.output_dir}[/bold]")
            return 2

        console.print(f"\n[bold green]All done![/bold green] Saved files to: [bold]{inputs.output_dir}[/bold]")
        return 0

    except ValueError as error:
        console.print(f"[red]Input error:[/red] {error}")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
