# Karigar
AI artisan inside Nonilion: turns a jeweller's Hinglish request into a castable design solved to a gold weight or budget, with renders, STL, job card and quote. Phase 1 = jewellery pack.

## Stack
Python3.13, Blender as a module (`bpy`5.3.0), Pydantic 2. LLM optional: AgentRouter via the `claude` CLI (`core/llm.py`, keys in `.env`). Native macOS/Linux and WSL are supported; run `bash scripts/test.sh`. Implemented: standalone service on Render (OpenAI-compatible endpoint that Nonilion imports) + Blender worker.

## Commands (inside WSL, repo root)
- Run: `./venv/bin/python run.py order "<request>" --quality draft`
- Calibrate: `./venv/bin/python run.py calibrate --workshop <id> --designed <g> --actual <g>`
- Test: see `.claude/test-command`

## Docs (read on demand)
- docs/STATUS.md — resume point: phase states, what's pending, repo state
- docs/implementation.md — phases + gates (source of truth for scope)
- docs/decisions.md — why things are the way they are
- docs/flow.md — entry points and code/data flow
- docs/testing.md — manual + automated testing guide
- docs/QUESTIONS.md — open questions for the user
- docs/security/backlog.md — medium/low security findings
- docs/nonilion.md — what Nonilion supports today and the integration route
- docs/pitch.md — pitch deck source of truth (one section per slide): the idea as P0, P1/P2 as future scope; no build status in it
- README.md — product pitch, weight-solving math, layout
- Spec (external): "Karigar Phase 1 (Jewellery): Full-Scope Spec & Review" — https://claude.ai/artifact/XRcZnqdvBeCwNECf7sUDrB

## Project rules
- The LLM never produces a number shown to the user (weight, price, rate, dimension). Code + data only.
- Every LLM path keeps a deterministic fallback; the demo must run offline.
- Manufacturability checks run on the mesh, never on the spec alone.
- Tests never write `data/calibration.json` or `out/`; use temp paths.
- Tests never call a real model; AgentRouter is driven through a fake runner.
- AgentRouter: only through the official `claude` CLI; never spoof client headers; never put the key in argv or logs.
