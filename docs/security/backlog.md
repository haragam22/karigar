# Security backlog
Medium/low findings from security-breaker runs. Cleared in the User simulation phase.

- [x] [medium] Quadratic regex in probe JSON pre-scan freezes the process (`_JSON_STRING`, 64 KB body of `\"` → 8.7 s; key required) — 6.5 — docs/security/6.5.md#N3 — replace regex with one linear left-to-right scan tracking string state, depth and node count
- [x] [medium] Unauthenticated flood rotates real Nonilion entries out of the probe log (rest of F2) — 6.5 — docs/security/6.5.md#N4 — small fixed-size summaries for unauth requests, per-IP rate limit, authed entries in a separate file
- [x] [medium] `/probe/log?n=500` can return ~32 MB and use ~0.5 GB under concurrency (key required) — 6.5 — docs/security/6.5.md#N5 — cap total bytes returned (e.g. 4 MB) or return per-entry summaries
- [x] [medium] Deeply nested LLM JSON → RecursionError — 1 — docs/security/1.md#F10 — catch RecursionError in llm.extract_json (or pre-scan depth like probe/server._parse_json) and return None so the regex fallback runs
- [x] [medium] No input length cap; repair loop resends huge text — 1 — docs/security/1.md#F11 — cap message length at intake (e.g. 2,000 chars → needs_info) and cut text resent in the repair prompt
- [x] [medium] "within 2 weeks" read as ₹2 budget — 1 — docs/security/1.md#F12 — kbud regex rejects a number followed by a time unit; require ₹/rs/budget/k/lakh context for small numbers
- [x] [medium] No budget ceiling → 60 kg modelled target — 1 — docs/security/1.md#F13 — le= on budget_inr (e.g. ₹1 crore) or check planned weight against piece max proportions before solving
- [x] [medium] Ring size: 12.5 read as mm, size/mm conflicts silent, Brief(ring_size="12") → 17.3 default — 1 — docs/security/1.md#F14 — non-integer "size N" under 12 unreadable; ask when size and mm disagree; coerce numeric strings
- [x] [low] Signs/exponents dropped in weights (-10 g → 10, 1e9 g → 9) — 1 — docs/security/1.md#F15 — extend NUM lookbehind to exclude [-+e]; report such tokens as unreadable
- [x] [low] Stone carat missed after "22 carat" — 1 — docs/security/1.md#F16 — skip karat matches when searching for gem_ct
- [x] [low] Language detector mistakes (double "do", "Sona" as a name, Devanagari → en) — 1 — docs/security/1.md#F17 — weight ambiguous words; Devanagari → Hindi/Hinglish; handle proper names


## Closed 2026-11-14

Reproductions are in `tests/test_security_completion.py`, with existing `test_security_phase1.py`, `test_llm.py` and `test_probe.py` retained.

- N3: a single linear string/escape/depth/node scan replaces the backtracking regex.
- N4: authenticated requests also go to a separately rotated `.authenticated` log. Unauthenticated floods cannot remove that evidence; the general diagnostics log still rotates.
- N5: tail reads and returned raw entries share a 1 MiB byte budget, including rotated files.
- F10: model JSON is capped at 256 KiB and depth64; decoding errors, oversized integers and recursion fail to the fallback. The CLI envelope uses the same guard.
- F11: intake caps original requests at2,000 characters before rate parsing/model calls. Repair excerpts remain bounded.
- F12/F13: time units are excluded from budget matches; budget is bounded to ₹1 crore as an operational limit, not a market estimate.
- F14: fractional Indian sizes and conflicting size/diameter text ask again; numeric-string sizes use the chart.
- F15/F16: signed/exponent weights are not silently reinterpreted; gemstone carats after karat mentions are found.
- F17: repeated English “do”, the name Sona in English context, and Devanagari have regressions.

Additional boundary fix: worker HTTP URLs use parsed exact loopback hostnames, rejecting `localhost.evil.example`, credential-bearing URLs and query/fragment URLs. Owner tokens must differ from API and worker tokens. Owner actions validate finite bounded calibration data, are queued off-handler, and repeated requests share an active job.
