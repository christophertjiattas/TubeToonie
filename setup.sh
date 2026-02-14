#!/usr/bin/env bash
set -euo pipefail

echo "YTAudio setup: installing dependencies"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ and retry."
  exit 1
fi

install_ffmpeg_macos() {
  if command -v brew >/dev/null 2>&1; then
    echo "Installing ffmpeg via Homebrew..."
    brew install ffmpeg
  else
    echo "Error: Homebrew not found. Install it from https://brew.sh and rerun."
    exit 1
  fi
}

install_ffmpeg_linux() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing ffmpeg via apt-get..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg
  else
    echo "Error: apt-get not found. Install ffmpeg manually and rerun."
    exit 1
  fi
}

if ! command -v ffmpeg >/dev/null 2>&1; then
  os_name="$(uname -s)"
  case "$os_name" in
    Darwin)
      install_ffmpeg_macos
      ;;
    Linux)
      install_ffmpeg_linux
      ;;
    *)
      echo "Error: Unsupported OS ($os_name). Install ffmpeg manually."
      exit 1
      ;;
  esac
fi

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi

python_bin=".venv/bin/python"

"${python_bin}" -m pip install --upgrade pip
"${python_bin}" -m pip install -r requirements.txt

# yt-dlp changes frequently; upgrading helps avoid random YouTube 403 failures.
"${python_bin}" -m pip install --upgrade yt-dlp

echo "Setup complete."
echo "CLI: ${python_bin} YTAudio.py"
echo "TUI: chmod +x run-tui.sh && ./run-tui.sh"
echo "Streamlit UI: chmod +x run-ui.sh && ./run-ui.sh"
