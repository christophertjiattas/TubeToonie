#!/usr/bin/env bash
set -euo pipefail

# Double-click launcher for macOS.
# It opens in Terminal and runs the Streamlit UI via the repo's easy runner.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

cd "${project_dir}"

chmod +x run-ui-easy.sh >/dev/null 2>&1 || true

./run-ui-easy.sh
