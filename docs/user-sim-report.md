# User simulation report

Seed 20261114; 1000 users. Result: PASS.

Scope: Real deterministic intake, authorization, schemas and queue/idempotency; no rendering, external client or physical casting simulation. Input mix and limits: [sim/users.md](../sim/users.md).

Mix: `{'valid': 609, 'incomplete': 189, 'hostile': 160, 'unauthorized_rate': 42}`.

Failures: 0. Intake p95: 1.21 ms. Queue acknowledgement plus idempotent retry p95: 2.71 ms.

This is counter/queue evidence, not a claim that 1,000 simultaneous rendering users can be served by a laptop. Real model, geometry and rendering checks are recorded separately in the test ledger.
