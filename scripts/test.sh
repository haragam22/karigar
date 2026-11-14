#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif [ -x venv/bin/python ]; then
  PY=venv/bin/python
else
  PY="${KARIGAR_PYTHON:-python3}"
fi
if [ "$#" -eq 0 ]; then set -- -q; fi
exec "$PY" -m pytest "$@"
