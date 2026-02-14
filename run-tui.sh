#!/usr/bin/env bash
set -euo pipefail

if [ ! -x ".venv/bin/python" ]; then
  echo "Error: .venv/bin/python not found. Run ./setup.sh first."
  exit 1
fi

.venv/bin/python YTAudioTUI.py
