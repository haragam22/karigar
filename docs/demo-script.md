# Demo and deployment handoff

## Local walkthrough

Start `.venv/bin/python scripts/preview_console.py`. Open http://127.0.0.1:8080/console/ with public loopback-only token `local-demo-owner`. The workspace uses clearly labelled sample rates/orders. The first full catalogue render takes a few minutes; wait for the worker to finish before recording.

| Time budget | Show | Say/do |
|---|---|---|
| 0:00–0:45 | Design studio and real rotatable ring | Old gold or a budget becomes measured geometry. Point out the sample-data label. |
| 0:45–1:30 | Hinglish brief | Use the old-gold exchange below; missing size/purity gets a question. |
| 1:30–2:30 | Three variants and selected design | Inspect finished/casting weight, tolerance and the real GLB. |
| 2:30–3:30 | Quote and job card | Show rate timestamp/source, assumed policies, mesh checks and production downloads. |
| 3:30–4:30 | Edit | “Middle one, but make the flower slightly bigger.” The solver reruns; inspect the new version and deltas. |
| 4:30–5:15 | Impossible request | Use the refusal brief below; show the constraint, best achievable weight and alternatives. |
| 5:15–6:00 | Formula proof and calibration | The mesh proof is not a physical casting claim; calibration uses actual shop weights. |

Hero request: `Purani 8.4g 22K chain exchange karni hai, uske badle 22K ladies ring chahiye, size 12, chhota floral design`.

Budget request: `₹60,000 all-in for an 18K solitaire with a lab-grown diamond, size 14`.

Refusal request: `22K ring, size 14, under 1.2 g, with a 1 ct diamond`.

The engine’s hero/order/edit/refusal paths are covered by the automated suite. This table is a rehearsal plan, not a claim that the external room rehearsal happened.

## Backup recording

`scripts/record_demo.mjs` records the actual local sample-data UI, without a fake product mockup or login-token capture. It shows the studio, collection, order/quote, rotatable GLB, workshop and a real streamed impossible-request response. The output is silent, with separate WebVTT narration captions and a held actual result screenshot at the end; it is a backup walkthrough, not an external Nonilion recording.

Run with development-only Puppeteer tooling available through `HALLMARK_PUPPETEER`. The recorder uses `imageio-ffmpeg` from the development environment. Output: `out/karigar-backup.mp4`, `out/karigar-backup.webm` and `out/karigar-backup.vtt`. The MP4 is the verified presentation copy. Generated video stays outside Git.

## Deployment

Follow [nonilion-setup.md](nonilion-setup.md). Deploy the thin stdlib service using render.yaml; do not install bpy there. Set three distinct secrets and run the Blender worker on the laptop. Refresh a verified market rate for a live demo; never present the preview’s sample rate as current.

The local build/downloads incurred no new paid-service purchase. The documented budget remains the user’s $50 Render credits, with no cash GPU rental. No claim is made about current monthly plan prices, credits redemption or actual account charges; confirm these in the Render account before selecting a plan.

Still pending: Render deployment, real Nonilion agent import/key tests, and the six-minute external-room rehearsal. The user explicitly requested local completion and deployment instructions first.

Verified presentation copy: `out/karigar-backup.mp4`, 149.6 seconds, 1440×900, silent H.264 MP4, approximately 2.8 MB. Full decoding and actual start/middle/final frames were checked.
