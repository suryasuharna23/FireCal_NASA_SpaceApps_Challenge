#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' 'Install uv and Node.js 22.19+ first, then run ./run.sh again.' >&2
  exit 1
fi
exec uv run --locked --all-packages --python 3.12 python scripts/run_app.py "$@"
