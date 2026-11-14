#!/usr/bin/env bash
# Karigar worker setup (Phase 7): bpy + Node + the `claude` CLI, then a check.
# Run inside WSL (Ubuntu) or on any Linux box (e.g. a rented GPU machine), from the repo root:
#   bash scripts/setup_worker.sh
# Idempotent: re-running skips what is already installed. Secrets are never written by this
# script; put them in .env (git-ignored) yourself:
#   KARIGAR_SERVICE_URL=https://<your-app>.onrender.com
#   KARIGAR_WORKER_TOKEN=<same value as on Render>
#   AGENTROUTER_API_KEY=<optional; without it the deterministic fallbacks run>
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
say() { printf '\n== %s\n' "$*"; }

# 1. Python + venv with bpy (requirements.txt pins bpy; bpy 5.x needs Python 3.11/3.13 per wheel).
PY="${KARIGAR_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.13 python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
  done
fi
[ -n "$PY" ] || { echo "No python3 found. Install it: sudo apt-get install -y python3 python3-venv"; exit 1; }
"$PY" -c 'import sys; assert sys.version_info[:2] == (3, 13), "Use Python 3.13 for the pinned bpy wheel"'
if [ ! -x venv/bin/python ]; then
  say "Creating venv with $PY"
  "$PY" -m venv venv || { echo "venv failed. Try: sudo apt-get install -y python3-venv"; exit 1; }
fi
say "Installing Python requirements (bpy is large; first run takes a few minutes)"
./venv/bin/python -m pip install --upgrade pip >/dev/null
./venv/bin/python -m pip install -r requirements.txt
# bpy needs a few X/GL libraries even headless on a bare server
if ! ./venv/bin/python -c "import bpy" >/dev/null 2>&1; then
  echo "bpy did not import. On Ubuntu try:"
  echo "  sudo apt-get install -y libxrender1 libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libsm6 libgl1 libegl1"
  exit 1
fi

# 2. Node (for the claude CLI). Uses an existing node >= 18, else installs nvm + LTS for this user.
node_ok() { command -v node >/dev/null 2>&1 && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ]; }
if ! node_ok; then
  say "Installing Node LTS with nvm (user-local, no sudo)"
  export NVM_DIR="$HOME/.nvm"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  fi
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm install --lts
fi

# 3. The official Claude Code CLI (core/llm.py runs it headless against AgentRouter).
if ! command -v claude >/dev/null 2>&1; then
  say "Installing the claude CLI (@anthropic-ai/claude-code)"
  npm install -g @anthropic-ai/claude-code
fi

# 4. Checks.
say "Checks"
./venv/bin/python -c "import bpy; print('bpy', bpy.app.version_string)"
node --version
claude --version || echo "claude CLI not on PATH in this shell; open a new shell or set KARIGAR_CLAUDE_BIN"
if [ -f .env ]; then
  for k in KARIGAR_SERVICE_URL KARIGAR_WORKER_TOKEN; do
    grep -q "^$k=" .env || echo "missing in .env: $k"
  done
else
  echo "No .env yet: cp .env.example .env, then set KARIGAR_SERVICE_URL and KARIGAR_WORKER_TOKEN."
fi
say "Done. Start the worker with:  cd $ROOT && ./venv/bin/python run.py worker"
