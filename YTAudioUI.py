from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any, Optional

import streamlit as st
import yt_dlp

from ytaudio_secrets import (
    TonieCredentials,
    delete_tonie_credentials_from_keyring,
    get_tonie_credentials,
    set_tonie_credentials_in_keyring,
    supports_secure_store,
)
from ytaudio_core import DownloadProgress, download_audio, format_bytes, format_speed, prepare_output_dir
from ytaudio_inputs import resolve_urls
from ytaudio_tonie import (
    CreativeTonieDetail,
    TonieChapterEdit,
    list_creative_tonies_detailed,
    maybe_push_to_tonies,
    update_creative_tonie_chapters,
)


def _parse_percent(percent: Optional[str]) -> float:
    if not percent:
        return 0.0
    cleaned = percent.strip().strip("%")
    try:
        return max(0.0, min(100.0, float(cleaned)))
    except ValueError:
        return 0.0


def _init_state() -> None:
    st.session_state.setdefault("status_log", [])
    st.session_state.setdefault("downloaded_files", [])
    st.session_state.setdefault("tonie_target_ids", [])

    if "tonie_username" not in st.session_state or "tonie_password" not in st.session_state:
        env_user = os.getenv("TONIE_USERNAME", "").strip()
        env_pass = os.getenv("TONIE_PASSWORD", "").strip()
        creds = get_tonie_credentials()

        st.session_state.setdefault("tonie_username", env_user or (creds.username if creds else ""))
        st.session_state.setdefault("tonie_password", env_pass or (creds.password if creds else ""))


def _log(message: str) -> None:
    # Keep a bounded log so Streamlit doesn't balloon memory.
    log_list: list[str] = st.session_state.get("status_log", [])
    log_list.append(message)
    st.session_state["status_log"] = log_list[-200:]


def _status_callbacks(
    status_placeholder: Any,
    detail_placeholder: Any,
    progress_bar: Any,
):
    def on_status(message: str) -> None:
        _log(message)
        status_placeholder.info(message)

    def on_progress(progress: DownloadProgress) -> None:
        percent_value = _parse_percent(progress.percent)
        progress_bar.progress(int(percent_value))

        downloaded = format_bytes(progress.downloaded_bytes)
        total = format_bytes(progress.total_bytes)
        speed = format_speed(progress.speed)
        detail_placeholder.caption(f"{progress.percent or '0%'} | {downloaded} / {total} | {speed}")

    return on_status, on_progress


def _render_status_log() -> None:
    with st.expander("Activity log", expanded=False):
        if not st.session_state.get("status_log"):
            st.caption("No activity yet.")
            return
        st.code("\n".join(st.session_state["status_log"][-80:]), language="text")


def _guess_audio_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _render_download_results() -> None:
    files: list[str] = st.session_state.get("downloaded_files", [])
    if not files:
        return

    st.subheader("Results")
    st.success(f"Processed {len(files)} file(s)")

    for idx, file_str in enumerate(files, start=1):
        path = Path(file_str)
        cols = st.columns([3, 1])
        with cols[0]:
            st.write(f"**{path.name}**")
            st.caption(str(path))

            if path.exists():
                # Validation: user can play it directly.
                st.audio(path.read_bytes())
            else:
                st.warning("File not found on disk.")

        with cols[1]:
            if path.exists():
                st.download_button(
                    label="Download",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime=_guess_audio_mime(path),
                    key=f"dl-{idx}-{path.name}",
                )


def _save_uploaded_file_to_dir(uploaded_file, target_dir: Path) -> Path:
    """Save a Streamlit UploadedFile into target_dir without clobbering existing files."""

    target_dir.mkdir(parents=True, exist_ok=True)

    raw_name = Path(uploaded_file.name).name
    base = Path(raw_name).stem
    suffix = Path(raw_name).suffix

    candidate = target_dir / f"{base}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = target_dir / f"{base} ({counter}){suffix}"
        counter += 1

    candidate.write_bytes(uploaded_file.read())
    return candidate


def _refresh_tonies() -> list[CreativeTonieDetail]:
    username = str(st.session_state.get("tonie_username", "")).strip() or None
    password = str(st.session_state.get("tonie_password", "")).strip() or None

    try:
        tonies = list_creative_tonies_detailed(username=username, password=password, on_status=_log)
    except ModuleNotFoundError as error:
        st.warning(str(error))
        return []
    except Exception as error:
        st.error(f"Failed to load Tonies: {error}")
        return []

    st.session_state["tonie_details"] = tonies
    return tonies


def _render_settings_tab() -> None:
    st.header("Settings")

    st.subheader("Tonie credentials")
    creds_missing = not st.session_state.get("tonie_username") or not st.session_state.get("tonie_password")

    if creds_missing:
        st.info("Enter your Tonie credentials to enable listing/editing/uploading.")

    st.text_input("Tonie username (email)", key="tonie_username")
    st.text_input("Tonie password", type="password", key="tonie_password")

    if supports_secure_store():
        col_save, col_forget = st.columns([1, 1])
        with col_save:
            if st.button("Save to Keychain / Credential Manager"):
                user = str(st.session_state.get("tonie_username", "")).strip()
                pwd = str(st.session_state.get("tonie_password", "")).strip()
                if not user or not pwd:
                    st.error("Enter both username and password before saving.")
                else:
                    set_tonie_credentials_in_keyring(TonieCredentials(username=user, password=pwd))
                    st.success("Saved Tonie credentials securely.")
        with col_forget:
            if st.button("Forget saved credentials"):
                delete_tonie_credentials_from_keyring()
                st.success("Deleted saved Tonie credentials (if any).")
    else:
        st.warning(
            "Secure credential storage is only supported on macOS and Windows (with the 'keyring' package installed).\n"
            "You can still use TONIE_USERNAME/TONIE_PASSWORD env vars."
        )

    with st.expander("Shell export commands (optional)"):
        st.caption(
            "Streamlit can’t automatically export env vars into your parent shell. Copy/paste if you prefer env vars."
        )
        include_pw = st.checkbox("Include password in export", value=False)
        pw_value = str(st.session_state.get("tonie_password", "")) if include_pw else "<your-password>"
        st.code(
            f"export TONIE_USERNAME=\"{st.session_state.get('tonie_username','')}\"\n"
            f"export TONIE_PASSWORD=\"{pw_value}\"\n",
            language="bash",
        )

    st.divider()

    st.subheader("Creative Tonie targets")
    st.caption("Pick one, the other, or both. Used for automatic uploads after downloads.")

    tonies: list[CreativeTonieDetail] = st.session_state.get("tonie_details") or []
    if st.button("Refresh Tonies", type="secondary"):
        tonies = _refresh_tonies()

    if tonies:
        label_to_id = {f"{t.name} ({t.id})": t.id for t in tonies}
        labels = list(label_to_id.keys())

        # Defaults from env vars if present
        env_single = os.getenv("TONIE_CREATIVE_TONIE_ID", "").strip()
        env_multi = os.getenv("TONIE_CREATIVE_TONIE_IDS", "").strip()  # optional comma-separated
        env_defaults: list[str] = []
        if env_multi:
            env_defaults = [part.strip() for part in env_multi.split(",") if part.strip()]
        elif env_single:
            env_defaults = [env_single]

        current_ids = list(st.session_state.get("tonie_target_ids") or [])
        if not current_ids and env_defaults:
            current_ids = env_defaults

        # Convert current ids to labels
        current_labels = [label for label, tid in label_to_id.items() if tid in set(current_ids)]

        chosen_labels = st.multiselect(
            "Auto-upload to these Creative Tonies",
            options=labels,
            default=current_labels,
        )

        st.session_state["tonie_target_ids"] = [label_to_id[label] for label in chosen_labels]

        if st.session_state["tonie_target_ids"]:
            st.success(f"Auto-upload enabled for {len(st.session_state['tonie_target_ids'])} Tonie(s).")
        else:
            st.info("Auto-upload is currently off (no Tonies selected).")
    else:
        st.info("Refresh Tonies to enable selection (requires credentials + tonie-api installed).")


def _render_download_tab() -> None:
    st.header("Download / Upload")

    st.write("Pick a source, then hit the big button. Results show up below so you can *prove* it worked.")

    source = st.radio("Audio source", options=["YouTube", "Local audio file"], horizontal=True)

    col_left, col_right = st.columns([2, 1])

    with col_right:
        default_dir = str(Path.cwd() / "downloads")
        output_dir = st.text_input("Output directory", value=default_dir)
        st.caption("Tip: keep a dedicated downloads folder.")

    urls: list[str] = []
    local_files = []
    chapter_title_override: str | None = None

    with col_left:
        if source == "YouTube":
            url = st.text_input("YouTube URL")
            upload = st.file_uploader("...or upload a .txt file of URLs", type=["txt"])
            uploaded_text = upload.read().decode("utf-8") if upload else None
            urls = resolve_urls(url, uploaded_text)
        else:
            st.write("Upload audio from your computer (no YouTube needed).")
            local_files = st.file_uploader(
                "Audio file(s)",
                type=["mp3", "m4a", "wav", "aac", "flac", "ogg", "opus", "wma", "aif", "aiff"],
                accept_multiple_files=True,
            )
            if local_files and len(local_files) == 1:
                chapter_title_override = st.text_input(
                    "Chapter title (optional)",
                    help="If blank, we use the filename.",
                ).strip() or None

    st.divider()

    status_placeholder = st.empty()
    detail_placeholder = st.empty()
    progress_bar = st.progress(0)

    on_status, on_progress = _status_callbacks(status_placeholder, detail_placeholder, progress_bar)

    button_label = "Download MP3" if source == "YouTube" else "Save & upload"

    if st.button(button_label, type="primary"):
        st.session_state["downloaded_files"] = []

        try:
            target_dir = prepare_output_dir(Path(output_dir))
            output_paths: list[Path] = []

            if source == "YouTube":
                if not urls:
                    st.error("Add a URL or upload a .txt file with links.")
                    return

                for index, video_url in enumerate(urls, start=1):
                    on_status(f"Starting download {index} of {len(urls)}")
                    progress_bar.progress(0)

                    mp3_path = download_audio(video_url, target_dir, on_progress=on_progress, on_status=on_status)
                    output_paths.append(mp3_path)
            else:
                if not local_files:
                    st.error("Upload at least one audio file.")
                    return

                for idx, uploaded in enumerate(local_files, start=1):
                    on_status(f"Saving file {idx} of {len(local_files)}")
                    progress_bar.progress(0)
                    saved_path = _save_uploaded_file_to_dir(uploaded, target_dir)
                    output_paths.append(saved_path)

            # Optional Tonie upload (one, the other, or both)
            target_ids: list[str] = list(st.session_state.get("tonie_target_ids") or [])

            for path in output_paths:
                count = maybe_push_to_tonies(
                    path,
                    creative_tonie_ids=target_ids,
                    chapter_title=chapter_title_override if source != "YouTube" else None,
                    username=st.session_state.get("tonie_username"),
                    password=st.session_state.get("tonie_password"),
                    on_status=on_status,
                )

                if target_ids and count == 0:
                    on_status("Tonie upload skipped (missing credentials or Tonie dependency not installed).")
                elif count > 0:
                    on_status(f"Uploaded to {count} Tonie(s). Your Toniebox will sync when online.")

            st.session_state["downloaded_files"] = [str(p) for p in output_paths]
            status_placeholder.success(f"Done! Files saved to: {target_dir}")

        except yt_dlp.utils.DownloadError as error:
            st.error(f"Download error: {error}")
        except Exception as error:
            st.error(f"Unexpected error: {error}")

    _render_download_results()
    _render_status_log()


def _render_tonie_library_tab() -> None:
    st.header("Tonie Library")
    st.write("Browse your Creative Tonies, verify whats on them, and edit chapter order/titles.")

    tonies: list[CreativeTonieDetail] = st.session_state.get("tonie_details") or []

    cols = st.columns([1, 3])
    with cols[0]:
        if st.button("Refresh", type="secondary"):
            tonies = _refresh_tonies()

    if not tonies:
        st.info("No Tonies loaded. Go to **Settings** and enter credentials, then refresh.")
        _render_status_log()
        return

    by_label = {f"{t.name} ({t.id})": t for t in tonies}
    selected_label = st.selectbox("Select a Creative Tonie", options=list(by_label.keys()))
    selected = by_label[selected_label]

    st.caption(
        f"Chapters: {selected.chapters_present} | Remaining chapters: {selected.chapters_remaining} | "
        f"Seconds: {int(selected.seconds_present)}/{int(selected.seconds_present + selected.seconds_remaining)}"
    )

    st.subheader("Chapters")
    if not selected.chapters:
        st.write("This Creative Tonie has no chapters yet.")
        _render_status_log()
        return

    # Editable table.
    rows = [
        {
            "Pos": i,
            "Title": ch.title,
            "Seconds": int(ch.seconds),
            "Transcoding": ch.transcoding,
            "_id": ch.id,
            "_file": ch.file,
        }
        for i, ch in enumerate(selected.chapters, start=1)
    ]

    edited = st.data_editor(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pos": st.column_config.NumberColumn(min_value=1, step=1, help="Playback order"),
            "Title": st.column_config.TextColumn(help="Rename the chapter"),
            "Seconds": st.column_config.NumberColumn(disabled=True),
            "Transcoding": st.column_config.CheckboxColumn(disabled=True),
            "_id": st.column_config.TextColumn(disabled=True),
            "_file": st.column_config.TextColumn(disabled=True),
        },
        disabled=["Seconds", "Transcoding", "_id", "_file"],
        key=f"editor-{selected.id}",
    )

    st.caption("Tip: change **Pos** values to reorder. Change **Title** to rename. Then click Apply.")

    if st.button("Apply changes", type="primary"):
        try:
            # Validate and apply ordering.
            desired: list[dict[str, Any]] = list(edited)
            positions = [int(item["Pos"]) for item in desired]
            if len(set(positions)) != len(positions):
                st.error("Positions must be unique.")
                return

            desired_sorted = sorted(desired, key=lambda x: int(x["Pos"]))
            chapter_edits = [
                TonieChapterEdit(
                    id=str(item["_id"]),
                    title=str(item["Title"]).strip() or "(untitled)",
                    file=str(item["_file"]),
                    seconds=float(item["Seconds"]),
                    transcoding=bool(item["Transcoding"]),
                )
                for item in desired_sorted
            ]

            update_creative_tonie_chapters(
                selected.id,
                chapter_edits,
                username=st.session_state.get("tonie_username"),
                password=st.session_state.get("tonie_password"),
                on_status=_log,
            )

            st.success("Updated chapters. Refresh to confirm the changes are live.")
            _refresh_tonies()
        except Exception as error:
            st.error(f"Failed to update chapters: {error}")

    _render_status_log()


def main() -> None:
    st.set_page_config(page_title="TubeToonie", page_icon="🎵", layout="wide")
    _init_state()

    st.title("TubeToonie")
    st.caption("Turn YouTube bops into kiddo tunes  then beam them onto a Tonie for storytime dance parties.")

    tabs = st.tabs(["Download", "Tonie Library", "Settings"])

    with tabs[0]:
        _render_download_tab()

    with tabs[1]:
        _render_tonie_library_tab()

    with tabs[2]:
        _render_settings_tab()

    st.divider()
    st.subheader("Exit")
    st.write("To exit, close this tab and stop the server in your terminal (Ctrl+C).")


if __name__ == "__main__":
    main()
