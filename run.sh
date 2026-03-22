#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec python -m uvicorn dashboard.main:app \
  --reload \
  --port 8765 \
  --reload-dir dashboard \
  --reload-dir core
