# Final local security review, 2026-11-14

Scope: the runtime entry points and previously reported findings, with targeted adversarial regressions. This is an engineering review and test sweep, not an external penetration-test certificate or a dependency vulnerability scan.

| Boundary | Verification |
|---|---|
| HTTP authentication | Chat, worker and owner tokens separated; authentication precedes parsing; owner data/actions reject chat and worker keys |
| Public request costs | Header/body/depth/node limits, connection cap and deadlines retained; JSON prescan now linear |
| Model output | Bounded length/depth, finite schema values, closed style vocabulary, repair/fallback and no real model calls in tests |
| Numbers/rates | No anonymous rate updates; old-gold purity claims ignored; stale/missing rates refuse; ambiguous numeric inputs ask again |
| Queue | Atomic idempotency for chat/API and owner actions; retries preserve versions; render heartbeat renews the worker lease |
| Files/UI | Safe upload names/types, capability file URLs, traversal tests, escaped content/Markdown, no token in a query string, no external viewer/font dependency |
| Probe evidence | Redaction retained, authenticated evidence independently rotated, bounded tail response |
| Worker transport | HTTPS or exact loopback hosts only; host-prefix lookalikes and embedded credentials rejected |

Every historical backlog finding now has a regression or existing direct test. No critical/high finding remains open in this reviewed local scope. Remaining deployment limits are documented: one shared Nonilion API key and history-derived conversation references, bearer tokens without per-user roles, and ephemeral free-instance storage. Live deployment and the external room have not been tested. Store only demo data until access and durable storage are configured for a real shop.
