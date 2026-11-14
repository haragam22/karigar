# Seeded user simulation

Run `.venv/bin/python sim/run.py --users 1000 --seed 20261114`.

Mix: 60% valid complete briefs, 20% incomplete/out-of-scope requests, 15% malformed or hostile inputs, 5% rate-authorization attempts. Users are sampled reproducibly; each gets a separate conversation and idempotency key.

The harness exercises the real deterministic intake, schemas, owner/staff rate authorization, and SQLite service queue/idempotency. It uses an isolated fresh **sample** rate store, not a network or production rate. It does not simulate physical castings, the live Nonilion client, 1,000 Blender renders, network latency, or 1,000 simultaneous browser sessions. The real geometry/render/service pipeline is separately covered by the full pytest suite and browser checks.

Pass bars at this scope: zero crashes/unhandled exceptions, valid-input error rate below 1%, every selected invalid/incomplete/unauthorized input gets its expected refusal/question topic, and intake p95 below 200 ms on the test machine. This latency target applies to counter intake and queue acknowledgement, not solving/rendering.

Examples cover rings, bangles, pendants, chains, earrings, coins, nose pins, old-gold exchange, budget, Hinglish, missing size/purity, unsupported necklaces, signed/exponent weights, huge budgets, conflicting sizes, excessive input length, claimed purity and instructions to change rates. No real model is called.
