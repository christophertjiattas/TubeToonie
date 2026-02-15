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
from rich.prompt import Confirm, Prompt
from rich.text import Text

from ytaudio_core import DownloadProgress, download_audio, prepare_output_dir
from ytaudio_inputs import load_urls_from_file, parse_urls_from_text
from ytaudio_tonie import (
    TonieChapterEdit,
    list_creative_tonies,
    list_creative_tonies_detailed,
    load_tonie_target_ids_from_env,
    maybe_push_to_tonies,
    update_creative_tonie_chapters,
)


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


def _prompt_for_output_dir(console: Console) -> Path:
    default_dir = str(Path.cwd() / "downloads")
    output_dir = Path(Prompt.ask("Output directory", default=default_dir)).expanduser()
    return prepare_output_dir(output_dir)


def _prompt_for_youtube_inputs(console: Console) -> ResolvedInputs:
    console.print(Panel("[b]TubeToonie TUI[/b] \u2014 YouTube/Local audio \u2192 MP3 \u2192 Tonie", expand=False))

    mode = Prompt.ask(
        "YouTube input mode",
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

    if not urls:
        raise ValueError("No URLs provided.")

    return ResolvedInputs(urls=urls, output_dir=_prompt_for_output_dir(console))


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
            self._task_id = self._progress.add_task(label, total=100)
        return self._task_id

    def reset(self, label: str) -> None:
        if self._task_id is not None:
            self._progress.remove_task(self._task_id)
            self._task_id = None
        self._ensure_task(label)
        self._progress.update(self._task_id, completed=0)
        self.set_status("Preparing...")

    def set_status(self, message: str) -> None:
        self._status.plain = message

    def on_progress(self, progress: DownloadProgress, *, label: str) -> None:
        task_id = self._ensure_task(label)

        if progress.total_bytes and progress.downloaded_bytes is not None:
            self._progress.update(task_id, total=progress.total_bytes, completed=progress.downloaded_bytes)
            return

        percent_value = _parse_percent(progress.percent)
        self._progress.update(task_id, total=100, completed=percent_value)

    def renderable(self) -> Group:
        return Group(Panel(self._status, title="Status", expand=False), self._progress)


def _download_youtube_to_mp3(console: Console) -> int:
    inputs = _prompt_for_youtube_inputs(console)

    failures: list[str] = []
    display = _RichDownloadDisplay(console)

    targets = load_tonie_target_ids_from_env()

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
                uploaded = maybe_push_to_tonies(mp3_path, creative_tonie_ids=targets, on_status=on_status)
                if targets:
                    display.set_status(f"Uploaded to {uploaded} Tonie(s)")
                else:
                    display.set_status("Done")
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


def _push_local_audio(console: Console) -> int:
    console.print(Panel("[b]Push local audio[/b] \u2014 upload files to one/both Tonies", expand=False))
    raw = Prompt.ask("Enter file path(s), comma-separated")
    paths = [Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()]
    if not paths:
        raise ValueError("No files provided.")

    missing = [p for p in paths if not p.exists()]
    if missing:
        raise ValueError("Missing file(s): " + ", ".join(str(p) for p in missing))

    targets = load_tonie_target_ids_from_env()
    if not targets:
        console.print("[yellow]No TONIE_CREATIVE_TONIE_ID(S) set. Upload will use default Tonie selection.[/yellow]")

    for p in paths:
        title = Prompt.ask(f"Chapter title for {p.name}", default=p.stem)
        console.print(f"Uploading: {p}")
        uploaded = maybe_push_to_tonies(p, creative_tonie_ids=targets, chapter_title=title)
        console.print(f"Uploaded to {uploaded} Tonie(s).")

    return 0


def _list_tonies(console: Console) -> int:
    tonies = list_creative_tonies()
    if not tonies:
        console.print("[yellow]No Tonies loaded. Configure credentials and install requirements-tonie.txt[/yellow]")
        return 0

    for tonie in tonies:
        console.print(f"\n[bold]{tonie.name}[/bold] ({tonie.id})")
        if not tonie.chapters:
            console.print("  (no chapters)")
        else:
            for idx, ch in enumerate(tonie.chapters, start=1):
                console.print(f"  {idx:02d}. {ch.title}")

    return 0


def _edit_tonie(console: Console) -> int:
    tonies = list_creative_tonies_detailed()
    if not tonies:
        console.print("[yellow]No Tonies loaded. Configure credentials and install requirements-tonie.txt[/yellow]")
        return 0

    console.print("\nAvailable Creative Tonies:")
    for idx, t in enumerate(tonies, start=1):
        console.print(f"  {idx}. {t.name} ({t.id})")

    choice = int(Prompt.ask("Select Tonie number"))
    selected = tonies[choice - 1]

    if not selected.chapters:
        console.print("This Tonie has no chapters.")
        return 0

    chapters = list(selected.chapters)

    # Rename
    while True:
        console.print("\nChapters:")
        for idx, ch in enumerate(chapters, start=1):
            console.print(f"  {idx:02d}. {ch.title}")

        if not Confirm.ask("Rename a chapter?", default=False):
            break

        index = int(Prompt.ask("Chapter number"))
        if index < 1 or index > len(chapters):
            console.print("[red]Invalid chapter number.[/red]")
            continue

        new_title = Prompt.ask("New title").strip()
        old = chapters[index - 1]
        chapters[index - 1] = TonieChapterEdit(
            id=old.id,
            title=new_title,
            file=old.file,
            seconds=old.seconds,
            transcoding=old.transcoding,
        )

    # Reorder
    if Confirm.ask("Reorder chapters?", default=False):
        raw = Prompt.ask("New order (comma-separated indices, e.g. 3,1,2)").strip()
        order = [int(p.strip()) for p in raw.split(",") if p.strip()]
        if sorted(order) != list(range(1, len(chapters) + 1)):
            raise ValueError("Order must be a permutation of 1..N")
        chapters = [chapters[i - 1] for i in order]

    console.print("Applying changes...")
    update_creative_tonie_chapters(selected.id, chapters)
    console.print("[green]Done.[/green] Refresh your Toniebox to sync.")

    return 0


def main() -> int:
    console = Console()

    try:
        console.print(Panel("[b]TubeToonie TUI[/b]", expand=False))

        action = Prompt.ask(
            "What do you want to do?",
            choices=["download", "push-local", "list-tonies", "edit-tonie", "quit"],
            default="download",
        )

        if action == "download":
            return _download_youtube_to_mp3(console)
        if action == "push-local":
            return _push_local_audio(console)
        if action == "list-tonies":
            return _list_tonies(console)
        if action == "edit-tonie":
            return _edit_tonie(console)
        return 0

    except ValueError as error:
        console.print(f"[red]Input error:[/red] {error}")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
