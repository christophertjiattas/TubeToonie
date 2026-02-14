#!/usr/bin/env bash
set -euo pipefail

# "Just run it" launcher:
# - ensures we're in the project folder (works even with spaces in path)
# - creates/uses .venv
# - installs deps into the venv
# - starts Streamlit

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${script_dir}"

echo "== YTAudio: easy Streamlit launcher =="

# Ensure base scripts are executable (harmless if already set)
chmod +x setup.sh run-ui.sh >/dev/null 2>&1 || true

# Core setup (ffmpeg + .venv + python deps)
./setup.sh

python_bin=".venv/bin/python"

# Optional Tonie integration deps (best-effort)
if [ -f "requirements-tonie.txt" ]; then
  echo "Installing optional Tonie dependencies into venv (best-effort)..."
  set +e
  "${python_bin}" -m pip install -r requirements-tonie.txt
  status=$?
  set -e

  if [ $status -ne 0 ]; then
    echo "Warning: Tonie deps failed to install. (Likely Python version mismatch; tonie-api requires Python 3.11+.)"
    echo "The app will still run; Tonie features will be disabled until deps install cleanly."
  fi
fi

echo "Starting Streamlit UI..."
exec "${python_bin}" -m streamlit run YTAudioUI.py
