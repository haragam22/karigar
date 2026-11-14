# Status / resume point
Updated 2026-11-14. Current local implementation and verification supersede the old Claude/WSL resume notes. See [COMPLETION.md](COMPLETION.md) for evidence and [implementation.md](implementation.md) for scope.

## Current scope

User: finish phases1–10 locally and provide deployment instructions; **no deployment exists yet** (confirmed this session). Use Impeccable and Hallmark for a bold but clear console. Do not commit/push under an assistant identity; no commits or pushes have been made.

| Phase | Current local state |
|---|---|
| 1 | Verified; input/security backlog closed with regressions |
| 2 / 2.5 | All 19 families verified by full suite; catalogue rendered locally; prior user visual approval remains historical evidence |
| 3 | Weight, seats, solver/budget and coin gates pass on native Blender5.3 |
| 4 | Mesh-check/retry/job-card tests pass; process defaults remain labelled assumptions |
| 5 | Quote/rate/package tests pass; no real market rate was fetched for sample preview |
| 6 | Store, concurrent versions, edits and failure-persistence tests pass |
| 6.5 | Prior live probe findings retained; parser/log security backlog closed |
| 7 | Local service+worker integration verified; heartbeat and URL/auth boundaries hardened; deployment guide ready |
| 8 | Personas and import/acceptance guide ready; actual room run deferred |
| 8.5 | Seeded1,000-user intake/queue simulation passes; documented security backlog closed; scope/limits recorded |
| 9 | README, formula proof, calibration demo and local demo runbook ready; local backup recorded; live rehearsal deferred |
| 10 | Eight-screen console built; real GLBs and19-family renders; owner APIs; responsive/browser and independent design review tracked in COMPLETION.md |

## Runtime and evidence

- Native macOS arm64, Python 3.13.5, pinned `bpy==5.3.0`. Run `bash scripts/test.sh`; WSL is optional.
- Final full gate: **1,119 passed**, 155 warnings, 925.80 seconds. All local regression evidence is recorded in COMPLETION.md.
- Reference-shape proof: maximum volume error **0.2913%**, not physical casting proof.
- Simulation:1,000 users, zero failures; see user-sim-report.md for exact scope and timings.
- Preview: `.venv/bin/python scripts/preview_console.py`, http://127.0.0.1:8080/console/, public loopback-only token `local-demo-owner`. Sample runtime files are under `/tmp/karigar-console-preview`.
- Uncommitted changes remain in the working tree. Do not assume STATUS.md describes staged files.

## Remaining external/manual gates

Render deployment, credits/account confirmation, actual Sakhi/Karigar imports and live room rehearsal, are not claimed complete. A silent local backup is available in out/karigar-backup.mp4. Follow nonilion-setup.md and demo-script.md when deployment is requested. No paid services were purchased.

The small-ornament wall floor remains the existing assumed0.6 mm policy pending the question in QUESTIONS.md; no new geometry policy was silently adopted.
