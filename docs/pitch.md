# Karigar — pitch deck source of truth

One `##` section = one slide. **Title** is the slide headline, **On slide** is what goes on it, **Say** is the speaker note.
This deck is about the idea: the P0 product is Karigar as pitched; P1 and P2 are its future scope.
Numbers come from `docs/decisions.md`; if one changes there, change it here.

---

## 1. Title
**Title:** Karigar — the AI artisan for India's jewellers
**On slide:**
- Old gold in. A castable new design out, at exactly that gold weight.
- Lives inside the shop's Nonilion office.
- Team: [names]
**Say:** Every Indian home has a drawer of old gold. Karigar turns it into a new piece that carries exactly that gold, ready for the caster.

## 2. The problem
**Title:** Custom jewellery is guesswork, and gold is billed by the gram
**On slide:**
- Small and mid-size jewellers sell custom pieces but have no CAD designer.
- Today: WhatsApp sketches → freelancer CAD → days of back-and-forth.
- The final weight surprises everyone. 1.5 g extra in 22K ≈ ₹22,000 at ₹14,730/g.
- Customers trading old gold want a new piece that uses exactly the gold they own.
**Say:** The weight is the price. A design that comes out heavy is a broken promise to the customer.

## 3. Who it's for
**Title:** The jeweller at the counter
**On slide:**
| Role | What they do | What they get |
|---|---|---|
| Jeweller (primary) | Describes the customer's wish, sets the gold weight or budget | 3 design options, renders, a quote, a job card |
| Karigar / caster | Receives the job in the office | STL file, job card with weights, stones and process notes |
| Customer | Sees options shared by the jeweller | Catalogue images and a price breakdown |
**Say:** The customer reaches Karigar through the jeweller. The jeweller stays in charge.

## 4. What Karigar does
**Title:** Describe it in Hinglish. Get three castable designs at your gold weight.
**On slide:**
1. The jeweller types the request in the office chat: "Nani ka purana 18.4g 22K kangan hai, naya beaded kada banana hai, size 2-6".
2. Karigar asks only what's missing (size, purity, gold or budget), at most 3 questions.
3. Three design variants: lighter, balanced, statement.
4. Each one solved to the target gold weight or budget.
5. Each one checked against casting rules on the actual 3D model.
6. Renders, an STL for the caster, a job card and a quote.
7. Edits like "make the flower bigger" change only that, and the gold weight holds.
8. Impossible requests get a clear "no" with options, never a bad design.
**Say:** It talks like the shop talks, and it only asks when it has to.

## 5. The core idea
**Title:** The AI never draws and never invents a number
**On slide:**
- The language model writes a structured design spec (validated JSON). That's all.
- Deterministic code builds the 3D geometry, measures the gold, enforces casting rules and computes the price.
- Every number shown carries its source: measured, shop config, today's rate, or assumed.
**Say:** That's what makes this more than a chatbot. The model reasons and talks; the code guarantees.

## 6. Five agents on one shop floor
**Title:** A real workshop, as five named agents
**On slide:**
| Agent | Zone | Job |
|---|---|---|
| Sakhi | Counter | Understands Hinglish or English, asks follow-ups |
| Jauhari | Pricing desk | Old gold or budget → target weight; the quote |
| Naqqash | Design studio | Proposes 3 variants as validated specs |
| Karigar | Workshop | Solves each design to the gram, checks it can be cast, exports STL and job card |
| Chitrakar | Photo studio | Catalogue renders |
**Say:** In the Nonilion room the jeweller talks to Sakhi at the counter and Karigar in the workshop.

## 7. Hero scenarios
**Title:** Four requests every Indian jeweller hears
**On slide:**
- **Design inside my old gold:** 8.4 g of 22K chain → a women's ring, size 12, small floral motif, using exactly that gold after loss; shows the balance.
- **Budget first:** ₹60,000 all-in for an 18K solitaire with a lab-grown diamond → metal weight and stone size solved together.
- **Make this, but lighter:** a catalogue ring rebuilt 20% lighter.
- **Impossible:** "22K, under 1.2 g, with a 1 ct stone" → the rule that blocks it, the smallest feasible version, two alternatives.
**Say:** The old-gold scenario leads: it's Indian, emotional, and you can check it on a scale.

## 8. How the gold maths works
**Title:** Old gold → exact new weight
**On slide:**
1. Fine gold: 18.4 g × 0.916 purity × (1 − 2% melting) = **16.52 g**
2. Finished 22K weight: 16.52 ÷ 0.916 = **18.03 g**
3. Weight to model: 18.03 ÷ (1 − 3% workshop loss) = **18.59 g**
4. The solver scales the design's cross-section (ring size fixed), measuring real 3D volume × alloy density each pass, and aims for **±0.3%**, within a fixed iteration cap and a hard acceptance window of the tighter of 0.1 g and 2%.
5. Casting rules bound the scaling. Outside them → explain + options.
**Say:** The solver target and finished-casting tolerance are different. Uncalibrated results show the configured ±4% assumed band; actual shop records refine it. No physical casting accuracy is claimed yet.

## 9. Honest by design
**Title:** It says no, and shows you the way out
**On slide:**
- "1 ct diamond ring under ₹10k" → the stone alone costs more than the budget; options: a plain ring, a smaller stone, or a ruby.
- "22K, under 1.2 g, with a 1 ct stone" → below the minimum castable weight; Karigar names the rule and the nearest feasible version.
- Unclear request ("kuch sundar sa bana do") → one short question, not a guess.
- Gold rate missing or older than 24 h → it asks; it never estimates the rate.
**Say:** Every failure ends in a clear message and a next step, never silence or an invented number.

## 10. Accuracy
**Title:** How do we know the weight is right?
**On slide:**
- Five reference meshes agree with their exact formulas within 0.30%. The rounded flat-band cross-section uses Pappus’s theorem; the disc uses πr²h.
- Same design in → same weight out, to 0.01 g, every time.
- Real-world loss (casting, polishing) is learned per workshop: the karigar weighs the finished piece, Karigar records it, the next prediction uses it.
**Say:** Reference-shape meshes agree with their exact formulas within the measured error. Real workshop loss still needs actual weighings.

## 11. Numbers come from sources, not from the model
**Title:** Every shop number is cited
**On slide:**
| Number | Value | Source |
|---|---|---|
| Hallmarking (BIS HUID) | Configured ₹75 per piece | Shop demo policy; confirm for production |
| GST | Configured 3% gold/stones, 5% making | Assumed shop treatment; confirm with the shop’s CA |
| Old-gold deduction | 2% | Shop policy; brands charge 2–5% |
| Making charge | 3.5% | Shop policy |
| Min ring shank | 1.5 mm | Ganoksin casting guidance |
| Densities 22K / 18K / 14K | 17.75 / 15.45 / 13.05 g/cm³ | Published alloy tables |
| Casting shrinkage | 1% | US patent 4283831 |
**Say:** All of these live in the shop's config. A shop swaps in its own numbers without touching code.

## 12. Why Nonilion
**Title:** Jewellery is teamwork. Karigar works in the office.
**On slide:**
- The jeweller, the customer and the karigar share one Nonilion room.
- Karigar joins the room as an imported AI agent; the room's chat goes to Karigar's own engine.
- The owner refreshes the timestamped gold rate through the worker or console. Anonymous room messages cannot change it.
- Results come back in the room: comparison, renders, quote, and the job card for the karigar.
**Say:** The office is where the whole job happens, from the counter to the workshop.

## 13. Architecture
**Title:** One engine, thin adapters
**On slide (diagram):**
- Nonilion room → (OpenAI-compatible chat API) → Karigar service on Render (API, queue, files)
- Karigar service ← Blender worker (brief → plan → design → solve → check → render → quote)
- Language model through AgentRouter; every model step has a deterministic fallback.
**Say:** The engine doesn't know about Nonilion. Moving to another platform means a new adapter, not a new engine.

## 14. Tech stack
**Title:** Built on open tools
**On slide:**
- Python, Blender as a Python module for geometry and Cycles rendering
- Pydantic data contracts between every stage
- AgentRouter for language; deterministic fallbacks keep it working offline
- Render for hosting
**Say:** Draft renders take 15–25 s per order on a laptop CPU, so no GPU is needed.

## 15. Demo (6 minutes)
**Title:** Watch a vague request become a castable ring
**On slide:**
1. The room: Karigar, the jeweller, the karigar, today's gold rate.
2. Messy Hinglish brief → Karigar asks only for the ring size.
3. Progress → 3 variants with weights and prices.
4. Edit: "Middle one, flower slightly bigger" → only that changes; the band rebalances to stay in the gold.
5. Impossible: "add a 1 ct diamond, still under 1.2 g" → named rule + 2 options.
6. Handover: STL + job card to the karigar.
**Say:** Steps 4 and 5 are where judges can change things live.

## 16. Future scope (P1)
**Title:** Next: smarter, more visual
**On slide:**
- 3-variant comparison table in the chat
- Reference photo → design family and parameters, with confidence per parameter
- Vision critic: checks renders against the brief (motif present, stones visible), up to 2 revisions
- Progress posts during long jobs; @mention handling in room chat
- Walk-to handover: the job card delivered to the karigar's channel
- Turntable GIF and a technical view with dimensions
- Order history with every design version and v-to-v comparison
- Weight validated against real pieces of known weight
**Say:** P1 turns a working engine into a full shop assistant.

## 17. Future scope (P2)
**Title:** Then: every piece, every voice
**On slide:**
- All jewellery families: halo, three-stone, signet, motif rings, pendants, stud earrings
- Spoken quote summary in Hindi and English
- Per-shop calibration of loss, shown on every quote
- Catalogue-grade renders with purity-tinted metals and gem shaders
- Customer card image ready for WhatsApp
- Sakhi, Naqqash and the critic as separate characters in the office
- A designer agent that builds in Blender through Karigar's own tools
**Say:** P2 is the full shop floor.

## 18. Beyond jewellery
**Title:** One engine, many crafts
**On slide:**
| Domain pack | Constraint solved | Output |
|---|---|---|
| Jewellery | Gold grams, budget | STL, job card, quote |
| Hardware enclosures | Fit around PCB and parts, strength, print grams | STEP, STL, bill of materials |
| Clothing | Size chart, fabric metres, cost | Pattern PDF/DXF, cutting plan |
| Brass handicrafts | Metal weight, casting limits | STL for casting |
| Flat-pack furniture | Plywood sheet use, load | CNC cut files |
**Say:** Only the builder, the constraints and the rules change per craft. The engine stays.

## 19. Close
**Title:** Karigar: the design obeys the gold
**On slide:**
- [Ask: pilot jewellers / feedback]
- [Business model: per design, per month, or a share of order value]
**Say:** [One-line close.]

---

## Judge Q&A (backup slides)
- **How accurate is the weight?** Reference meshes agree with exact formulas within 0.30%; the solver aims for ±0.3%; uncalibrated finished-weight estimates show an assumed ±4% band, refined with actual shop records.
- **What if the gold rate changes?** The owner refreshes it through the worker or console; every quote shows the rate and its time; older than 24 h → Karigar asks.
- **Why not a CAD jeweller?** Days and a fee per design vs minutes, and the weight is solved, not guessed.
- **What stops the AI inventing a price?** The model never outputs a number shown to the customer; code computes every one from cited data.
- **Who pays?** [Fill before the pitch.]
