from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable

from ytaudio_secrets import TonieCredentials, get_tonie_credentials

StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class TonieChapterSummary:
    title: str
    seconds: float
    transcoding: bool


@dataclass(frozen=True)
class CreativeTonieSummary:
    id: str
    name: str
    household_id: str
    seconds_remaining: float
    seconds_present: float
    chapters_remaining: int
    chapters_present: int
    chapters: list[TonieChapterSummary]


@dataclass(frozen=True)
class TonieConfig:
    username: str
    password: str
    creative_tonie_id: str | None
    creative_tonie_name: str | None


def resolve_tonie_credentials(
    *,
    username: str | None = None,
    password: str | None = None,
) -> TonieCredentials | None:
    """Resolve Tonie credentials.

    Order:
    1) Explicit args (from UI inputs)
    2) Environment variables (TONIE_USERNAME / TONIE_PASSWORD)
    3) OS secure store (macOS Keychain / Windows Credential Manager)

    Returns None if nothing is configured.
    """

    if username and password:
        return TonieCredentials(username=username.strip(), password=password.strip())

    # Use env vars if present, otherwise keyring.
    return get_tonie_credentials()

def _getenv(name: str) -> str:
    return os.getenv(name, "").strip()


def load_tonie_target_ids_from_env() -> list[str]:
    """Load comma-separated Creative Tonie IDs from env.

    Supported:
      - TONIE_CREATIVE_TONIE_IDS=id1,id2,id3
      - TONIE_CREATIVE_TONIE_ID=id1 (single)

    Returns:
        list[str]: zero or more IDs.
    """

    multi = _getenv("TONIE_CREATIVE_TONIE_IDS")
    if multi:
        return [part.strip() for part in multi.split(",") if part.strip()]

    single = _getenv("TONIE_CREATIVE_TONIE_ID")
    return [single] if single else []


def load_tonie_config_from_env() -> TonieConfig | None:
    """Load Tonie credentials/target from env vars.

    Required:
      - TONIE_USERNAME
      - TONIE_PASSWORD

    Target (pick one):
      - TONIE_CREATIVE_TONIE_ID
      - TONIE_CREATIVE_TONIE_NAME

    If required vars are missing, returns None (meaning feature disabled).
    """

    username = _getenv("TONIE_USERNAME")
    password = _getenv("TONIE_PASSWORD")

    if not username or not password:
        return None

    creative_tonie_id = _getenv("TONIE_CREATIVE_TONIE_ID") or None
    creative_tonie_name = _getenv("TONIE_CREATIVE_TONIE_NAME") or None

    return TonieConfig(
        username=username,
        password=password,
        creative_tonie_id=creative_tonie_id,
        creative_tonie_name=creative_tonie_name,
    )


def _import_tonie_api():
    try:
        from tonie_api.api import TonieAPI  # type: ignore

        return TonieAPI
    except ModuleNotFoundError as exc:
        msg = (
            "Tonie feature requested but 'tonie-api' is not installed. "
            "Install it with: .venv/bin/python -m pip install -r requirements-tonie.txt"
        )
        raise ModuleNotFoundError(msg) from exc


def _import_tonie_models():
    try:
        from tonie_api.models import Chapter  # type: ignore

        return Chapter
    except ModuleNotFoundError as exc:
        msg = (
            "Tonie feature requested but 'tonie-api' is not installed. "
            "Install it with: .venv/bin/python -m pip install -r requirements-tonie.txt"
        )
        raise ModuleNotFoundError(msg) from exc


@dataclass(frozen=True)
class TonieChapterEdit:
    """Represents a desired chapter state when editing a Creative Tonie."""

    id: str
    title: str
    file: str
    seconds: float
    transcoding: bool


@dataclass(frozen=True)
class CreativeTonieDetail:
    id: str
    name: str
    household_id: str
    seconds_remaining: float
    seconds_present: float
    chapters_remaining: int
    chapters_present: int
    chapters: list[TonieChapterEdit]


def list_creative_tonies_detailed(
    *,
    username: str | None = None,
    password: str | None = None,
    on_status: StatusCallback | None = None,
) -> list[CreativeTonieDetail]:
    """List Creative Tonies including chapter IDs + file tokens.

    This is used for chapter editing (rename/reorder). Credentials can be provided
    explicitly, via env vars, or via local config.
    """

    creds = resolve_tonie_credentials(username=username, password=password)
    if creds is None:
        return []

    TonieAPI = _import_tonie_api()

    if on_status:
        on_status("Connecting to Tonie Cloud...")

    api = TonieAPI(creds.username, creds.password)
    tonies = api.get_all_creative_tonies()

    results: list[CreativeTonieDetail] = []
    for ct in tonies:
        chapters = [
            TonieChapterEdit(
                id=ch.id,
                title=ch.title,
                file=ch.file,
                seconds=float(ch.seconds),
                transcoding=bool(ch.transcoding),
            )
            for ch in (ct.chapters or [])
        ]
        results.append(
            CreativeTonieDetail(
                id=ct.id,
                name=ct.name,
                household_id=ct.householdId,
                seconds_remaining=float(ct.secondsRemaining),
                seconds_present=float(ct.secondsPresent),
                chapters_remaining=int(ct.chaptersRemaining),
                chapters_present=int(ct.chaptersPresent),
                chapters=chapters,
            )
        )

    return results


def list_creative_tonies(
    *,
    username: str | None = None,
    password: str | None = None,
    on_status: StatusCallback | None = None,
) -> list[CreativeTonieSummary]:
    """List Creative Tonies and their chapters (summary view)."""

    details = list_creative_tonies_detailed(username=username, password=password, on_status=on_status)

    results: list[CreativeTonieSummary] = []
    for ct in details:
        chapters = [
            TonieChapterSummary(title=ch.title, seconds=float(ch.seconds), transcoding=bool(ch.transcoding))
            for ch in (ct.chapters or [])
        ]
        results.append(
            CreativeTonieSummary(
                id=ct.id,
                name=ct.name,
                household_id=ct.household_id,
                seconds_remaining=float(ct.seconds_remaining),
                seconds_present=float(ct.seconds_present),
                chapters_remaining=int(ct.chapters_remaining),
                chapters_present=int(ct.chapters_present),
                chapters=chapters,
            )
        )

    return results


def update_creative_tonie_chapters(
    creative_tonie_id: str,
    chapters: list[TonieChapterEdit],
    *,
    username: str | None = None,
    password: str | None = None,
    on_status: StatusCallback | None = None,
) -> None:
    """Rename/reorder chapters on a Creative Tonie.

    This uses the Tonie Cloud PATCH endpoint under the hood via tonie-api's
    `sort_chapter_of_tonie`, which accepts a full chapter list.

    Raises:
        ValueError: If credentials are missing or the tonie can't be found.
    """

    creds = resolve_tonie_credentials(username=username, password=password)
    if creds is None:
        raise ValueError("Missing Tonie credentials. Provide username/password or set env/config.")

    TonieAPI = _import_tonie_api()
    Chapter = _import_tonie_models()

    if on_status:
        on_status("Connecting to Tonie Cloud...")

    api = TonieAPI(creds.username, creds.password)
    creative_tonies = api.get_all_creative_tonies()
    tonie = next((ct for ct in creative_tonies if ct.id == creative_tonie_id), None)
    if tonie is None:
        raise ValueError("Creative Tonie not found.")

    sort_list = [
        Chapter(id=ch.id, title=ch.title, file=ch.file, seconds=ch.seconds, transcoding=ch.transcoding)
        for ch in chapters
    ]

    if on_status:
        on_status("Updating chapters (rename/reorder)...")

    api.sort_chapter_of_tonie(tonie, sort_list)

    if on_status:
        on_status("Chapters updated.")


def maybe_push_to_tonies(
    audio_path: Path,
    *,
    creative_tonie_ids: list[str] | None = None,
    chapter_title: str | None = None,
    username: str | None = None,
    password: str | None = None,
    on_status: StatusCallback | None = None,
) -> int:
    """Upload audio to one or more Creative Tonies.

    Returns:
        int: number of uploads attempted.

    Notes:
        - If `creative_tonie_ids` is empty/None, we fall back to `maybe_push_to_tonie`
          which uses env/default selection rules.
        - Uploads are performed sequentially.
    """

    if not creative_tonie_ids:
        attempted = maybe_push_to_tonie(
            audio_path,
            chapter_title=chapter_title,
            username=username,
            password=password,
            on_status=on_status,
        )
        return 1 if attempted else 0

    count = 0
    for tid in creative_tonie_ids:
        attempted = maybe_push_to_tonie(
            audio_path,
            chapter_title=chapter_title,
            creative_tonie_id=tid,
            username=username,
            password=password,
            on_status=on_status,
        )
        if attempted:
            count += 1

    return count


def maybe_push_to_tonie(
    mp3_path: Path,
    *,
    chapter_title: str | None = None,
    creative_tonie_id: str | None = None,
    creative_tonie_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
    on_status: StatusCallback | None = None,
) -> bool:
    """Upload an MP3 to a Creative Tonie.

    If credentials aren't available, this returns False (feature disabled).

    Credentials resolution order:
    - explicit args (username/password)
    - env vars (TONIE_USERNAME/TONIE_PASSWORD)
    - OS credential store via `keyring` (macOS Keychain / Windows Credential Manager)

    Target resolution order:
    - explicit args (creative_tonie_id/name)
    - env vars (TONIE_CREATIVE_TONIE_ID/NAME)
    - fallback: first Creative Tonie on the account
    """

    creds = resolve_tonie_credentials(username=username, password=password)
    if creds is None:
        return False

    # env vars still supported for backwards compatibility
    cfg = load_tonie_config_from_env()

    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 not found: {mp3_path}")

    TonieAPI = _import_tonie_api()

    if on_status:
        on_status("Connecting to Tonie Cloud...")

    api = TonieAPI(creds.username, creds.password)
    creative_tonies = api.get_all_creative_tonies()

    if not creative_tonies:
        raise ValueError("No Creative Tonies found for this account.")

    effective_id = creative_tonie_id or (cfg.creative_tonie_id if cfg else None)
    effective_name = creative_tonie_name or (cfg.creative_tonie_name if cfg else None)

    selected = None
    if effective_id:
        selected = next((ct for ct in creative_tonies if ct.id == effective_id), None)
        if selected is None:
            raise ValueError("Creative Tonie ID did not match any Creative Tonie on this account.")
    elif effective_name:
        selected = next(
            (ct for ct in creative_tonies if ct.name.strip().lower() == effective_name.strip().lower()),
            None,
        )
        if selected is None:
            available = ", ".join(f"{ct.name} ({ct.id})" for ct in creative_tonies)
            raise ValueError(f"Creative Tonie name did not match. Available tonies: {available}")
    else:
        selected = creative_tonies[0]

    final_title = chapter_title or mp3_path.stem

    if on_status:
        on_status(f"Uploading to Creative Tonie: {selected.name} ({selected.id})")

    api.upload_file_to_tonie(selected, mp3_path, final_title)

    if on_status:
        on_status("Upload complete. Sync your Toniebox to fetch the new chapter.")

    return True
