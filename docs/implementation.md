# Implementation plan — Karigar Phase 1 (Jewellery), P0

Source spec: "Karigar Phase 1 (Jewellery): Full-Scope Spec & Review" (https://claude.ai/artifact/XRcZnqdvBeCwNECf7sUDrB).
This plan covers the spec's **P0 list** (qualify + demo). P1/P2 items are listed at the end and get phases only after P0 ships.

Order: the engine gets honest first (tests, scope, geometry, weight, checks, quote, edits). The service and Nonilion
come after that, because they're blocked on the Nonilion developer guide (QUESTIONS.md). Phases 1–6 can run while we wait.

Current runtime: native Python3.13 with bpy5.3.0 on macOS; Linux/WSL use the same pinned requirements. Historical WSL notes below describe the original build. See STATUS.md and decisions.md.
Architecture: standalone Karigar service; Nonilion is one adapter (decisions.md). LLM: AgentRouter via the `claude` CLI, always optional.

## P0 — what's left (2026-11-11)
| Spec P0 item | State now | Closed by |
|---|---|---|
| Bot connected to Nonilion, replies inside the office | Missing. Route found: Import → Other (OpenAI-compatible) | 6.5 probe → 7 → 8 |
| Service acks fast; Blender jobs on a separate worker via a queue | Missing | 7 |
| Brief JSON schema + validation + 3-question policy | Partial: schema + parser exist; asks 1 question, never asks size | 1 |
| ≥ 3 ring families, watertight, correct Indian size | Partial: band + solitaire; no motif ring, no size table, no mesh check | 2 |
| Weight from mesh × density, loss and tolerance shown | Mostly: no ± tolerance, density in code | 3 |
| Solver hits gram target; proves and explains infeasible cases | Mostly: doesn't name the binding constraint; budget mode holds stone fixed | 3 |
| Mesh checks: wall, prongs, shank → pass/warn/fail | Missing (rules run on the spec) | 4 |
| Preview render + STL + job card + quote returned as files | Local files only; job card JSON; not delivered to chat | 5 (MD job card), 7 (URLs) |
| Gold rate from KB/config with timestamp; stale/missing handled | Partial: `as_of` exists; no stale check, no source | 5 |
| Edits as spec patches, solver rerun | Missing | 6 |
| Tests (spec's test suite) | 44 unit tests; no bpy/golden/end-to-end yet | 0, then every phase |
| LLM provider | Done: AgentRouter gateway + fallbacks (`core/llm.py`); live call verified (13.6 s) | 0

### Phase 0 — Baseline and test harness
**Status**: done
Existing code works in a terminal, according to the README; nobody has re-run it on this machine yet. No tests exist.
**Done when**:
- [x] `pytest` is in requirements.txt and `.claude/test-command` runs the suite in WSL and exits 0
- [x] Unit tests for `gold.py`: exchange target matches the README example (18.4 g 22K → 16.52 g fine → 18.03 g finished → 18.59 g modelled at 3%) — `tests/test_gold.py`
- [x] Unit tests for `solver.py`: converges within 0.3% on a synthetic monotone function; returns `below_min` / `above_max` outside the bounds — `tests/test_solver.py`
- [x] Unit tests for `calibration.py`: default loss with no records; mean loss over records; rejects non-positive weights (uses a temp path, never `data/calibration.json`) — `tests/test_calibration.py`
- [x] Quote arithmetic unit tests for `pricing.quote`, including old-gold credit and `to_pay` — `tests/test_pricing.py`
- [x] Regex brief parser tests for the README requests (no LLM) — `tests/test_brief.py`
- [x] AgentRouter gateway in `core/llm.py`: call shape, key never in argv or logs, every failure (timeout, no CLI, provider error, no JSON) returns None and the regex/fallback path answers — `tests/test_llm.py`
- [x] (manual) Live AgentRouter call: `.env` with `AGENTROUTER_API_KEY`; one brief parsed by the model, latency recorded in decisions.md — 2026-11-11: "mujhe 22 carat sone ki ek anguthi chahiye, size 12" → `{'piece_type': 'ring', 'karat': 22}` in 13.6 s
- [x] Golden-file test: the same spec gives the same `gold_volume` weight to 0.01 g across runs (bpy) — `tests/test_geometry_bpy.py` + `tests/golden/gold_volume.json`
- [x] The 5 README example orders run end to end at `--quality draft` with the expected `status` (done / done / done / infeasible / needs_info) — `tests/test_orders_e2e.py`
- [x] Laptop CPU render time measured for draft and preview and recorded in decisions.md (decides whether demo day needs a rented GPU) — draft 15–25 s/order, preview 78–211 s/order (decisions.md)

### Phase 0.5 — Blender MCP as a dev tool
**Status**: manual
Decision 2026-11-11 (decisions.md). User installs Blender 5.x desktop on Windows; Claude picks and scans the server.
**Done when**:
- [x] Candidate Blender MCP server scanned with `skill-inspector`; findings reported and approved by the user before install — official Blender Lab server, CAUTION, approved 2026-11-11 (decisions.md)
- [x] Server registered in this project's MCP config (not global); Blender desktop version recorded in decisions.md — `.mcp.json` server `blender`; Blender 5.3.0
- [x] (manual) From Claude Code: build a ring from a `DesignSpec` in the live Blender scene and take a viewport screenshot — 2026-11-13, catalogue loaded via MCP, user approved
- [x] testing.md documents how to start Blender + the MCP addon and connect

### Phase 1 — Scope and data contracts
**Status**: done
Spec §1 Brief agent, §Data contracts, Reliability table.
Reviewer PASS 2026-11-13 (398 tests). Security F1–F9 fixed (docs/security/1.md); F10–F17 in backlog. Tests: test_brief.py, test_sizes.py, test_rates.py, test_result.py, test_scripted_briefs.py, test_claimed_purity.py, test_security_phase1.py.
**Done when**:
- [x] Phase 1 piece scope settled in decisions.md: ring, bangle, pendant (user, 2026-11-11)
- [x] Out-of-scope pieces (necklace, earrings, …) get the "explain scope + nearest supported piece" reply (test)
- [x] Indian ring size → inner diameter table (sizes 1–30, one cited brand chart) in `data/ring_sizes.json`; `Brief` takes `ring_size` and converts through it (test per size)
- [x] Replies mirror the request language: Hinglish in → Hinglish out, English in → English out (test on both)
- [x] "aaj ka rate 22K 14730"-style messages set the gold rate with a timestamp instead of starting an order (test)
- [x] Brief agent asks up to 3 questions per turn, only for blocking fields; **always asks for ring size when it's missing** (no silent 17.3 mm default); never assumes new-piece purity silently (tests)
- [x] Ambiguous style words ("traditional", "modern") produce 3 variants, no question (test)
- [x] `JobResult` Pydantic schema written by code only; infeasible results carry `{binding_constraint, best_achievable, alternatives[]}` (≥ 2 alternatives)
- [x] LLM output that fails validation is repaired once, then falls back to the deterministic path (test with a mocked LLM client returning bad JSON)
- [x] 10 scripted test briefs (including the 4 hero scenarios) all produce a valid Brief or the right question

### Phase 2 — Ring families and mesh hygiene
**Status**: done
Spec §3 Builder. Hero A needs a floral motif ring.
Reviewer PASS 2026-11-13 (398 tests). Tests: test_ring_families_bpy.py, test_mesh_hygiene_bpy.py, test_designer_variants_bpy.py.
**Done when**:
- [x] At least 3 ring families build: plain band (≥ 2 profiles), solitaire (4- and 6-prong), motif ring with a parametric floral top
- [x] Every build is watertight and manifold, with consistent normals and no loose parts (automated mesh check run on every family × 3 scales)
- [x] Inner diameter within ±0.05 mm of the size-table target (test per family)
- [x] Designer proposes 3 variants (lighter / balanced / statement) whose weights differ by ≥ 15% (test on fallback designer)

### Phase 2.5 — Design catalogue: 19 original families across 7 piece types
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
User decision 2026-11-13 (decisions.md "Design catalogue"): full engine families, original designs in the best-reviewed Indian retail styles (no brand copies, no plain bands in the showcase). Every family is parametric, weight-solvable and orderable.
Families: rings R1 floral cluster, R2 three-stone, R3 halo solitaire, R4 butterfly; pendants P1 heart halo, P2 paisley with stones, P3 layered temple lotus; chains C1 rope, C2 curb; coin K1 10 g lotus coin (raised rim, purity + weight stamp on back); bangles B1 antique temple kada, B2 twisted rope bangle, B3 leaf-vine bangle; earrings E1 flower jhumka, E2 chandbali, E3 floral cluster stud, E4 bali hoop; nose N1 flower nosepin (L-pin, tiny stone), N2 convertible screw-back stud (fits nose and ear).
**Done when**:
- [x] Piece types chain, coin, earring, nosepin added to schema, brief intake (sizes: chain length in inches, bangle/ring as before, earring sold as a pair, nosepin gauge) and designer; out-of-scope reply updated to the new scope (tests)
- [x] Each of the 19 families builds from a `DesignSpec`; every build watertight, manifold, consistent normals, no loose parts at 3 scales (mesh check test per family)
- [x] Gold volume rises monotonically with scale for every family, so the solver can hit a gram target (test per family)
- [x] Chains: link-by-link geometry, weight scales with length; links don't intersect each other except where they interlock (test)
- [x] Coin: solved to its stated weight within ±0.05 g; stamp text embossed from code-supplied karat and weight (test)
- [x] Earrings built and weighed as a pair; posts/hooks ≥ 0.8 mm; nosepin post 0.8 mm gauge; N2 thread fits both uses (test on dimensions)
- [x] Designer proposes 3 variants (lighter / balanced / statement) per family, weights differ by ≥ 15% (test)
- [x] (manual) Every family shown in the user's live Blender via MCP (decisions.md 2026-11-13) and approved; flagged designs fixed — user approved 2026-11-13 after pendants 0.9× and weight rule

### Phase 3 — Weight and solver honesty
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
Spec §4 Weight measurement, §5 Constraint solver, Hero D.
**Done when**:
- [x] Metal volume measured after stone seats are cut; density comes from a config file, not code constants (sourced values in decisions.md "Shop numbers")
- [x] DFM minimums updated to the sourced values: ring shank 1.5 mm, walls 0.8 mm, prongs 0.8 mm (tests)
- [x] Every result reports finished weight, casting weight and expected loss, and shows a tolerance (e.g. `7.6 g ± 0.3 g`)
- [x] Solver hits the target within ±0.1 g or 2%, within a fixed iteration cap; builds are cached by spec hash
- [x] Every infeasible case names the binding constraint, the best achievable value and 2 alternatives (tests for below_min, above_max, stone-too-big)
- [x] Hero D ("22K, under 1.2 g, 1 ct stone") is refused with the minimum achievable weight and 2 options (test)
- [x] Budget mode: stone size and metal weight are solved together, not with the stone held fixed (Hero B test)

### Phase 4 — Mesh-based manufacturability checks
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
Spec §6. Checks run on the mesh, never on the spec. Rule values in a per-process config.
**Done when**:
- [x] Minimum wall thickness measured on the mesh (ray-cast or voxel thickness map)
- [x] Minimum prong diameter and minimum shank thickness checked on the mesh
- [x] Prong setting with a large stone in 22K is flagged
- [x] Each rule reports pass / warn / fail with a location; the result goes into the job card
- [x] A set of deliberately bad specs each triggers its expected rule (test per rule)
- [x] A failed build or check retries once with optional features relaxed, then reports the failing rule (test)

### Phase 5 — Quote, gold rate and production package
**Status**: done
Spec §9 Quote engine, §10 Production package, Reliability table.
Reviewer PASS 2026-11-13 (750 tests). Rate = data/gold_rates.json via one RateSource, filled by `run.py rates refresh` (MCX + ₹5,000/10 g, decisions.md); chat rates refused (no Nonilion sender ID). Tests: test_pricing.py, test_ratesource.py, test_ratejob.py, test_rates.py, test_jobcard.py, test_stl_shrinkage_bpy.py, test_orders_e2e.py. Open for Phase 4: job card rule warnings read `solved.warnings`, not yet produced.
**Done when**:
- [x] Gold rate comes through one `RateSource` (rate set in chat, else config) with a timestamp shown in every quote
- [x] Rate missing, outside a sane range, or older than 24 h → Karigar says so and asks for today's rate; never estimates (tests)
- [x] Quote = gold value + making charge (3.5%) + stones + hallmarking (₹75) + GST (3% on gold and stones, 5% on making); old-gold credit = weight × purity × rate − 2% deduction (one deduction, no separate melt loss); every line labelled with its source, assumed values marked (tests)
- [x] Same inputs give the same quote to the rupee (test)
- [x] STL is shrinkage-scaled by a configured factor (1.0% default); job card written as Markdown (renders, dimensions, size, purity, weights, stones, finishing notes, HUID reminder, rule warnings)

### Phase 6 — Order store and edits as spec patches
**Status**: done
Spec §11. Needed for the demo's edit step.
Reviewer PASS 2026-11-13 (67 scoped tests; full suite 815). karigar/core/orders.py (SQLite), karigar/packs/jewellery/edits.py. Carried to Phase 7: version number allocated inside the store transaction (concurrent edits), order row saved before delivery (mark failed on export error).
**Done when**:
- [x] SQLite order store holds the brief, every spec version and every output path
- [x] An edit is a patch to the chosen spec; solver and checks rerun on it
- [x] "make it 0.5 mm thinner" changes only that parameter (test diffing v1 and v2 specs)
- [x] "Middle one, but make the flower slightly bigger" keeps the gold target by re-solving the band (test)
- [x] Weight and price difference between two versions is reported

### Phase 6.5 — Nonilion probe (what does "Import → Other" actually send?)
**Status**: manual
Route per decisions.md "Karigar is an OpenAI-compatible service". Small and early: its answers shape Phase 7. Can run in parallel with Phases 1–6.
Automated items: reviewer PASS 2026-11-13 (tests/test_probe.py, 62 tests); security N1/N2/N6/N7 fixed, N3–N5 backlog (docs/security/6.5.md). Left: the two manual items.
**Done when**:
- [x] `probe/` server implements `GET /v1/models` and `POST /v1/chat/completions` (streaming and non-streaming), API-key checked, and logs every request's headers and body with secrets redacted (tests)
- [x] Probe can delay its reply by N seconds and stream N progress lines, to measure Nonilion's timeout and streaming behaviour
- [ ] (manual) Probe reachable over HTTPS (Render or a tunnel); imported into a Nonilion room as "Other"; "Test the key" passes
- [ ] (manual) Every unknown in docs/nonilion.md's table answered and recorded there (history, IDs, stream, timeout, Markdown/images, uploads, tools, several agents)

### Phase 7 — Service: Karigar as an OpenAI-compatible endpoint, with a Blender worker
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
Spec §Nonilion integration (hosting), Engineering rules. Final shape depends on the Phase 6.5 findings.
**Done when**:
- [x] Transport-free `KarigarService` (start order, continue conversation, edit, status, quote); CLI, JSON HTTP API and the OpenAI-compatible endpoint are thin adapters over it (tests per adapter)
- [x] `/v1/models` and `/v1/chat/completions` served by Karigar; requests validated; API-key auth; unknown fields (e.g. `tools`) ignored without error (tests)
- [x] LLM calls (AgentRouter, up to minutes) run only in the worker, never in a request handler (test)
- [x] Split per decisions.md "Hosting": thin service on Render (API, queue, output files); worker on the laptop (WSL) polls Render over HTTPS for jobs and uploads results; no tunnel (tests with both sides local)
- [x] Worker setup script for the laptop (bpy + Node + `claude` CLI); same worker runs on a rented GPU box if needed; secrets from `.env` / Render env vars
- [x] Conversation → order mapping per Phase 6.5 findings (conversation ID if sent, else derived from history); a new message continues the same order: answers a question, picks a variant, or edits (tests)
- [x] Replies return within Nonilion's measured timeout; long work runs in a separate worker; the reply says what is running and how the next message gets the result (or streams progress if Phase 6.5 shows streaming works) (tests)
- [x] Every number in a reply comes from code (weights, prices, rates, dimensions); the LLM only words the text around them (test: numbers in the reply match the order record)
- [x] Renders and files served over HTTPS with unguessable URLs, shown as images or links per Phase 6.5 findings
- [x] Idempotent: a retried request never builds twice (test)
- [x] Worker down or render timeout → spec, weight and quote are sent first, renders on the next message (test)
- [x] One structured log line per pipeline stage
- [ ] (manual) Deployed on Render (or a tunnel for the worker); every team member has redeemed Render credits

### Phase 8 — Nonilion room setup and live checks
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
Agents are imported by hand (Import → Other) and point at Karigar.
**Done when**:
- [x] Two imported agents: **Sakhi** (counter: brief, questions, rate, quote) and **Karigar** (workshop: variants, solving, files, edits), each at its own base URL on our service
- [x] docs/nonilion-setup.md: step-by-step import of both agents (name, avatar, base URL, key, instructions) that a teammate can follow
- [x] Instruction texts for both agents stored in `nonilion/`
- [x] Text in chat or uploads can't change rules or invent rates (prompt-injection tests)
- [ ] (manual) In a live room: a Hinglish brief returns 3 variants with renders, weights and quotes
- [ ] (manual) The edit and impossible-request steps of the demo script work in the room

### Phase 8.5 — User simulation (≥ 1,000 users) and security hardening
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
Implemented with the local seeded harness in `sim/`; the historical named skill is not available in this environment. Scope and pass bars: sim/users.md.
**Done when**:
- [x] `sim/` harness simulates ≥ 1,000 seeded users with the documented input mix (sim/users.md).
- [x] Pass bar met (user-sim reference.md, overrides in decisions.md): 0 crashes/hangs/unhandled exceptions, valid-input error rate < 1 %, 100 % of invalid inputs rejected correctly, p95 within the stated target.
- [x] Every failure cluster has a reproducing test and a root-cause fix; docs/user-sim-report.md written.
- [x] docs/security/backlog.md cleared (fixed with tests, or risk accepted by the user).
- [x] security-breaker full-project run: 0 open critical/high findings.

### Phase 9 — Demo readiness
**Status**: implemented and locally verified (2026-11-14); external/manual gates remain unchecked
Spec §Live demo script, §Judging map.
**Done when**:
- [x] Every scripted demo input is pre-tested end to end and listed in testing.md
- [x] Weight-maths proof table: mesh volume vs exact formula volume for ≥ 3 simple shapes (plain bands of several sizes, a disc pendant), error < 0.5% (test generates the table); calibration loop shown learning a workshop loss (decisions.md "Product choices")
- [x] Budget check: Render plan + any GPU rental + AgentRouter usage recorded, total under $50
- [ ] (manual) 6-minute live flow rehearsed inside Nonilion
- [x] Local2–3minute backup recorded, decoded and visually checked; out/karigar-backup.mp4 (silent, actual sample-data UI with completed result screen held at end)

### Phase 10 — Karigar web console
**Status**: built; browser verification and independent design review recorded in COMPLETION.md
User 2026-11-14: structure approved ("the structure of web is great"); design with the **impeccable** skill; **3D viewer wanted**: the worker exports each design as GLB from Blender, the page shows it rotatable in the browser. Preview (layout only, sample data): https://claude.ai/artifact/JJYXLKoSueCSFk2cRh5hFQ. Resolved: judge-friendly shop workbench, plain HTML/JS on the existing stdlib service, with locally vendored model-viewer and fonts for offline use.
Drafted and approved2026-11-14; implemented by the current request. The frontend now lives in console/. Served by the Phase 7 service on Render (same auth, same store), so it adds no new server. Must run the `hallmark` skill (global rule). Mobile-first: shop staff use phones at the counter.
Pages:
1. **Orders**: list (order id, piece, karat, status, finished weight, total ₹, time); filter by status; search.
2. **Order detail**: the brief (as parsed, with assumptions), the 3 variants side by side (renders, finished/casting weight ± tolerance, dimensions, mesh-check pass/warn/fail), quote with every line's source and "assumed" marks, job card (Markdown rendered), STL/render downloads, version history with v1→v2 diff and weight/₹ deltas, an edit box ("make it 0.5 mm thinner").
3. **3D viewer**: rotate the chosen design in the browser (needs GLB export + a viewer library — decision below).
4. **Catalogue**: the 19 families with renders, default weight, lighter/balanced/statement weights, and "start an order from this design".
5. **Gold rate**: current rate per karat, timestamp, source (MCX + ₹5,000), staleness badge, "refresh now" (owner only), rate history.
6. **Workshop / calibration**: record actual cast weight for an order → loss %, the workshop's tolerance and record count.
7. **Try it (demo console)**: type a Hinglish request, see the Sakhi/Karigar reply stream exactly as Nonilion would — the demo backup if Nonilion is down.
8. **System**: worker online/offline, queue depth, last job times, version.
**Done when** (draft):
- [x] Every page above served by the Karigar service behind owner login (token); file links stay unguessable
- [x] All numbers on pages come from the order store / pricing code, never typed in the browser (test)
- [x] Works at phone width (360 px) and desktop; Hinglish/English labels
- [x] Demo console reproduces the chat flow end to end against the local service (test)
- [x] `hallmark` and `impeccable` skills run; screenshots and browser report in docs/
**Historical open decisions (resolved by PRODUCT.md and the latest user authorization)**: (a) audience priority — shop owner tool vs judge-facing showcase; (b) 3D viewer: add GLB export + a viewer library from a CDN (new dependency) or static renders only; (c) build tooling — plain HTML/JS served by the stdlib server (no new dependency) vs a framework.

## After P0 (not yet phased)
- **P1:** comparison table for 3 variants; photo → family + parameters with confidence; vision critic loop (≤ 2 revisions); walk-to handover into the karigar's channel; turntable GIF + technical view; weight validated against ≥ 3 real pieces.
- **P2:** all Phase 1 families (halo/three-stone, signet, pendants, studs); Hindi/English voice summary; Cycles catalogue renders with gem shaders; customer card PNG; Brief/Designer/Critic as separate Nonilion characters; injection tests on KB and uploads.
- **Design council + drawer agent** (decisions.md 2026-11-11): several agents agree on a design; one drawer agent builds it through Karigar's parametric builder ops exposed as MCP tools (no raw `bpy`), with every call logged as a replayable spec op. Phase it after P0.
- Calibration loop is verified, including three synthetic actuals and the next prediction in scripts/weight_proof.py; real casting validation remains future work.
