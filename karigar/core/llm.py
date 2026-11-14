"""Optional LLM access. The pipeline must work without it (demo safety),
so every caller has a deterministic fallback and `complete_json` returns None
on any failure.

Backends (KARIGAR_LLM_BACKEND, default "auto"):
  agentrouter  AgentRouter through the official Claude Code CLI in headless mode.
               AgentRouter rejects direct HTTP from unapproved clients
               ("unauthorized client detected"), so we run the real `claude -p`
               with ANTHROPIC_BASE_URL pointed at AgentRouter. Built-in tools are
               off (native tool calls fail intermittently there); system prompt is
               appended, never replaced (replacing it was `400 content-blocked`).
               See docs/decisions.md "LLM provider: AgentRouter".
  anthropic    Anthropic SDK directly (kept so the service can move providers).
  none         No LLM; callers use their deterministic paths.
  auto         agentrouter if AGENTROUTER_API_KEY is set, else anthropic if
               ANTHROPIC_API_KEY is set, else none.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

DEFAULT_MODEL = "gpt-6.1-sol"   # measured working on AgentRouter (decisions.md)
DEFAULT_BASE_URL = "https://agentrouter.org"
DEFAULT_TIMEOUT_S = 45          # chat-facing: past this the deterministic path answers

_SK_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")


def load_env_file(path: Path | None = None) -> None:
    """Minimal .env reader: KEY=VALUE lines; never overrides variables already set."""
    path = path or ENV_FILE  # looked up per call so tests can point it elsewhere
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _cfg() -> dict:
    load_env_file()
    e = os.environ.get
    return {
        "backend": e("KARIGAR_LLM_BACKEND", "auto"),
        "model": e("KARIGAR_MODEL", DEFAULT_MODEL),
        "agentrouter_key": e("AGENTROUTER_API_KEY", ""),
        "agentrouter_base_url": e("AGENTROUTER_BASE_URL", DEFAULT_BASE_URL),
        "anthropic_key": e("ANTHROPIC_API_KEY", ""),
        "claude_bin": e("KARIGAR_CLAUDE_BIN", "claude"),
        "timeout_s": float(e("KARIGAR_LLM_TIMEOUT_S", str(DEFAULT_TIMEOUT_S))),
    }


def backend() -> str:
    c = _cfg()
    b = c["backend"]
    if b == "auto":
        if c["agentrouter_key"]:
            return "agentrouter"
        if c["anthropic_key"]:
            return "anthropic"
        return "none"
    return b


def available() -> bool:
    b = backend()
    if b == "agentrouter":
        return bool(_cfg()["agentrouter_key"])
    if b == "anthropic":
        if not _cfg()["anthropic_key"]:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def redact(text: str, key: str) -> str:
    """Remove the key, any 12+ character fragment of it, and any sk-style token."""
    if key:
        text = text.replace(key, "[REDACTED]")
        n = 12
        if len(key) >= n:
            frags = {key[i:i + n] for i in range(len(key) - n + 1)}
            text = re.sub(r"[A-Za-z0-9_\-]{%d,}" % n,
                          lambda m: "[REDACTED]" if any(f in m.group(0) for f in frags) else m.group(0), text)
    return _SK_TOKEN.sub("[REDACTED]", text)


def _log(msg: str) -> None:
    print(f"  (llm) {msg}", file=sys.stderr, flush=True)


def _agentrouter_text(system: str, user: str, c: dict, runner=None) -> str | None:
    runner = runner or subprocess.run  # looked up per call so tests can patch it
    cmd = [c["claude_bin"], "-p", "--bare", "--disable-slash-commands", "--strict-mcp-config",
           "--tools", "", "--model", c["model"], "--output-format", "json", "--max-turns", "1",
           "--append-system-prompt", system]
    env = dict(os.environ)
    env.update({
        "ANTHROPIC_BASE_URL": c["agentrouter_base_url"],
        "ANTHROPIC_AUTH_TOKEN": c["agentrouter_key"],
        "ANTHROPIC_API_KEY": "",
        "MAX_THINKING_TOKENS": "0",
    })
    t0 = time.monotonic()
    try:
        # Prompt over stdin: no argv length limits, and the key never appears in argv.
        proc = runner(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                      errors="replace", env=env, timeout=c["timeout_s"])
    except subprocess.TimeoutExpired:
        _log(f"agentrouter timed out after {c['timeout_s']:.0f}s; using fallback")
        return None
    except OSError as exc:
        _log(f"claude CLI could not start ({type(exc).__name__}); using fallback")
        return None
    data = None
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                parsed = extract_json(line)
                if isinstance(parsed, dict):
                    data = parsed
                    break
            except (ValueError, RecursionError):
                continue
    if data is None:
        snippet = redact((proc.stdout or "") + (proc.stderr or ""), c["agentrouter_key"])[:200]
        _log(f"unparseable claude output (rc={proc.returncode}): {snippet}; using fallback")
        return None
    if data.get("is_error"):
        _log(f"agentrouter error: {redact(str(data.get('result', '')), c['agentrouter_key'])[:200]}; using fallback")
        return None
    _log(f"agentrouter {c['model']} ok in {time.monotonic() - t0:.1f}s")
    return str(data.get("result") or "")


def _anthropic_text(system: str, user: str, c: dict, max_tokens: int) -> str | None:
    try:
        import anthropic

        client = anthropic.Anthropic(timeout=c["timeout_s"])
        msg = client.messages.create(
            model=c["model"], max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception as e:  # network, auth: never crash the demo
        _log(f"anthropic unavailable ({type(e).__name__}); using fallback")
        return None


def extract_json(text: str) -> dict | list | None:
    """First JSON object or array in the text (models sometimes add prose or fences)."""
    if len(text or '') > 262144:
        return None
    m = re.search(r"(\{.*\}|\[.*\])", text or "", re.S)
    if not m:
        return None
    depth = 0
    quoted = escaped = False
    for ch in m.group(1):
        if quoted:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in '[{':
            depth += 1
            if depth > 64:
                return None
        elif ch in ']}':
            depth -= 1
    try:
        return json.loads(m.group(1))
    except (ValueError, RecursionError):
        return None


def complete_json(system: str, user: str, max_tokens: int = 2000, runner=None) -> dict | list | None:
    """Ask the model for JSON. Returns None on any failure so callers fall back."""
    if not available():
        return None
    c = _cfg()
    system = system + "\nRespond with JSON only. No prose, no code fences."
    b = backend()
    text = _agentrouter_text(system, user, c, runner) if b == "agentrouter" else _anthropic_text(system, user, c, max_tokens)
    if text is None:
        return None
    out = extract_json(text)
    if out is None:
        _log("model reply had no valid JSON; using fallback")
    return out
