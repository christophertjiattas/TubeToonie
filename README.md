# TubeToonie

TubeToonie turns YouTube videos into kid-friendly audio files and (optionally) beams them onto **Creative Tonies** for your Toniebox.

What it can do:
- Download audio from **YouTube** and save as **MP3**.
- Upload **local audio files** from your computer (no YouTube needed).
- Optional Tonie integration:
  - list your Creative Tonies + chapters
  - auto-upload to **one, the other, or both** Tonies
  - rename + reorder chapters on a Creative Tonie

## Requirements
- Python 3.10+
- `ffmpeg` installed and available on your PATH (system dependency)
- Python deps (installed into a venv): `yt-dlp`, `streamlit`, `rich`, `keyring`

Optional Tonie integration:
- `tonie-api` (community library)
- Note: `tonie-api` requires **Python 3.11+**

## Quick start (Streamlit UI)
This is the easiest way to run TubeToonie.

### Option A: double-click (macOS / Windows)
- macOS: double-click `launchers/TubeToonie.command`
- Windows: double-click `launchers/TubeToonie.bat`

macOS notes:
- The first time you run it, you may need to right-click > Open (Gatekeeper).
- If it opens in a text editor instead of Terminal, run once:
  ```bash
  chmod +x launchers/TubeToonie.command
  ```

Windows note:
- `TubeToonie.bat` expects **Git Bash** (`bash`) so it can run the existing `.sh` scripts. Install Git for Windows: https://git-scm.com/download/win

### Option B: terminal
```bash
chmod +x run-ui-easy.sh
./run-ui-easy.sh
```

What it does:
- Creates/uses `.venv`
- Installs Python deps into `.venv`
- Ensures `ffmpeg` exists (Homebrew/apt)
- Starts the Streamlit UI

## Usage
### Streamlit UI
```bash
./run-ui-easy.sh
# or
./run-ui.sh
# or
.venv/bin/python -m streamlit run YTAudioUI.py
```

### CLI
```bash
.venv/bin/python YTAudio.py
```

### TUI
```bash
./run-tui.sh
```

## Streamlit app guide (tabs)
### 1) Download / Upload
Pick an audio source:
- **YouTube**: paste a URL or upload a `.txt` file (1 URL per line)
- **Local audio file**: upload one or more audio files from your computer

Click the big button.

Validation:
- The **Results** section shows an audio preview + a download button.
- The **Activity log** shows what happened step-by-step.

### 2) Settings
#### Tonie credentials (secure)
TubeToonie supports secure storage using your OS credential store:
- macOS: **Keychain**
- Windows: **Credential Manager**

This is implemented via the Python `keyring` package.

In the Streamlit UI, enter your Tonie username/password and click:
- **Save to Keychain / Credential Manager**

Or, if you prefer env vars:
```bash
export TONIE_USERNAME="you@example.com"
export TONIE_PASSWORD="your-password"
```

Security notes:
- Credentials are never written into this repository.
- Don’t paste real passwords into README/examples.
- Streamlit cannot "export" env vars into your parent shell (process isolation).

#### Auto-upload targets (one / the other / both)
After you refresh Tonies, select one or more Creative Tonies in the multi-select.

Env var alternative:
```bash
export TONIE_CREATIVE_TONIE_ID="id1"          # single
export TONIE_CREATIVE_TONIE_IDS="id1,id2"     # multiple
```

### 3) Tonie Library
- Refresh Tonies
- Pick a Creative Tonie
- Edit chapters:
  - change **Pos** to reorder
  - change **Title** to rename
- Click **Apply changes**

## Install / setup (manual)
```bash
chmod +x setup.sh
./setup.sh
```

Install `ffmpeg` manually (if needed):
- macOS: `brew install ffmpeg`
- Windows: `choco install ffmpeg`

## Common issues
### “cannot execute binary file”
You ran a binary *through* `bash`.

Wrong:
```bash
bash .venv/bin/python YTAudio.py
```

Right:
```bash
.venv/bin/python YTAudio.py
```

### YouTube 403 / blocked
Upgrade yt-dlp:
```bash
./setup.sh
```

Then try cookies:
```bash
export YTAUDIO_COOKIES_FROM_BROWSER=chrome
.venv/bin/python YTAudio.py
```

## Credits / upstream projects
TubeToonie stands on the shoulders of giants:
- **yt-dlp**: https://github.com/yt-dlp/yt-dlp
- **ffmpeg**: https://ffmpeg.org/
- **Streamlit**: https://streamlit.io/
- **Rich**: https://github.com/Textualize/rich
- **tonie-api** (optional Tonie Cloud integration): https://github.com/Wilhelmsson177/tonie-api

This project is not affiliated with YouTube, Google, Boxine, or Tonies.

## License
MIT (see `LICENSE`).
