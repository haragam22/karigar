"""Jewellery pack: weight-locked gold design for old-gold exchange, weight or budget."""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

from karigar.core import gold as G
from karigar.core.lang import detect
from karigar.core.registry import DomainPack, EditOutcome, Intake, Plan, Solved, register
from karigar.core.solver import SolveResult, solve_monotone

from . import brief as B
from . import designer, dfm, edits, pricing, rates
from . import messages as M
from .schema import Brief, DesignSpec, gem_ct_from_d


def solve_failure(r: SolveResult, loss_pct: float, spec: DesignSpec | None = None) -> dict:
    """Infeasible contract for a solver miss: explanation, binding rule, best result, options.
    With the spec, the binding rule names the casting rule that stops the design (dfm.binding_rule)."""
    fin = lambda g: g * (1 - loss_pct / 100)
    best = {"value": round(fin(r.value), 2), "unit": "g"}
    if r.reason == "below_min":
        alts = ["a slimmer design", "a smaller stone", f"add {fin(r.value - r.target):.2f} g of gold"]
        if spec is not None and spec.gem == "none":
            alts[1] = "a design with fewer parts (a plain band)" if spec.piece_type == "ring" else "a smaller design"
        expl = (f"too little gold for this design. Its lightest castable version finishes at "
                f"{fin(r.value):.2f} g; you have {fin(r.target):.2f} g. Try {alts[0]}, "
                f"{alts[1]}, or {alts[2]}.")
        binding = (dfm.binding_rule(spec, "lo") if spec is not None
                   else "minimum castable thickness/width (casting rules)")
    elif r.reason == "above_max":
        alts = ["a bolder design", "a matching set (ring + pendant)",
                f"keep {fin(r.target - r.value):.2f} g as credit"]
        expl = (f"this design tops out at {fin(r.value):.2f} g; you have {fin(r.target):.2f} g. "
                f"Pick a bolder design, make a matching set (ring + pendant), or keep "
                f"{fin(r.target - r.value):.2f} g as credit.")
        binding = (dfm.binding_rule(spec, "hi") if spec is not None
                   else "maximum sensible proportions for this design")
    else:
        alts = ["another design from the set", "a slightly different target weight"]
        expl = (f"the solver couldn't settle this design on the target; closest was {fin(r.value):.2f} g "
                f"for {fin(r.target):.2f} g.")
        binding = "solver did not converge"
    return {"explanation": expl, "binding_constraint": binding, "best_achievable": best,
            "alternatives": alts}


def stone_too_big(spec: DesignSpec, lo: float) -> dict:
    """Infeasible contract when the stone can't sit on this design at any castable scale:
    the largest stone it can carry (bounds only, dfm.max_stone_d) is the best achievable."""
    d = dfm.max_stone_d(spec)
    ct = round(gem_ct_from_d(spec.gem, d), 2)
    alts = ([f"a {ct:.2f} ct {spec.gem} ({d:.2f} mm), the largest this design can hold"] if d > 0 else []) + [
        "a design with a wider band or a bigger head", "a pendant, which frames a bigger stone"]
    return {"explanation": (f"a {spec.gem_ct:.2f} ct {spec.gem} ({spec.gem_d_mm:g} mm) is too big for "
                            f"this design at any castable size"
                            + (f"; it can carry up to {ct:.2f} ct ({d:.2f} mm)." if d > 0 else ".")),
            "binding_constraint": (f"stone size vs. minimum castable proportions: "
                                   f"{dfm.binding_rule(spec, 'lo')}" if not spec.family else
                                   "stone size vs. minimum castable proportions"),
            "best_achievable": {"value": ct, "unit": "ct"},
            "alternatives": alts[:3]}


def job_card(spec: DesignSpec, solved: Solved, brief: Brief, plan: Plan, dims: dict,
             pieces: int, rc: dict, seats_in_model: bool = True) -> dict:
    """The job card's data (job_card.json; jobcard.job_card_md renders it). bpy-free."""
    from .jobcard import size_text

    loss = plan.detail["casting_loss_pct"]
    wt = pricing.weights(solved.value, plan)
    tol = plan.detail.get("tolerance") or G.tolerance()
    stone_assumed = spec.gem != "none" and brief.gem != "none" and not brief.gem_ct
    warnings = list(getattr(solved, "warnings", []) or [])
    if stone_assumed:
        warnings.append(f"stone size assumed: {spec.gem_ct:.2f} ct ({spec.gem_d_mm:g} mm, the design's own stone)")
    if spec.gem != "none" and not seats_in_model:
        warnings.append("stone seats are NOT cut in casting.stl (no clean boolean seat cut): "
                        "the setter cuts them; the weights already exclude the seat metal")
    warnings += [a for a in brief.assumptions if a not in warnings]
    return {
        "design": spec.name, "piece": spec.piece_type, "family": spec.family or None,
        "karat": spec.karat, "metal": spec.metal,
        "pieces_to_cast": pieces,   # an earring pair: casting.stl is one earring
        "size": size_text(spec.piece_type, brief),
        "modelled_weight_g": round(solved.value, 3),
        "casting_weight_g": wt["casting_g"],
        "expected_finished_weight_g": round(solved.value * (1 - loss / 100), 3),
        "assumed_casting_loss_pct": round(loss, 2),
        "expected_loss_g": wt["expected_loss_g"],
        "tolerance_g": wt["tolerance_g"],
        "tolerance_pct": wt["tolerance_pct"],
        "tolerance_source": tol["source"] + (" (assumed)" if tol.get("assumed") else ""),
        "weight_text": pricing.weight_text(wt),
        "stl_shrinkage_pct": rc["casting_shrinkage_pct"],
        "tolerance_note": "Weigh after polishing and record it: `run.py calibrate` sharpens the next prediction.",
        "dimensions_mm": dims,
        "stone": {"type": spec.gem, "diameter_mm": spec.gem_d_mm, "approx_ct": round(spec.gem_ct, 2),
                  "setting": f"{spec.prongs}-claw" if spec.piece_type == "ring" else "bezel",
                  "size_assumed": stone_assumed}
                 if spec.gem != "none" else None,
        "hallmark_articles": pricing.articles(spec.piece_type, spec.pair),
        "hallmark_fee_inr": rc["hallmark_fee_inr_per_article"],
        "warnings": warnings,
        "checks_passed": solved.issues,
        "mesh_checks": list(getattr(solved, "mesh_checks", []) or []),
        "spec": spec.model_dump(),
        "solver": {"scale": round(solved.scale, 4), "passes": solved.iterations},
    }


def with_mesh(solved: Solved, rep, extra: list[str] | None = None) -> Solved:
    """`solved` with the mesh-check results attached: warn/fail lines as warnings, passes
    added to the checks passed, every rule result in mesh_checks (job card)."""
    return dataclasses.replace(solved, warnings=list(extra or []) + rep.warning_texts(),
                               mesh_checks=rep.as_list(),
                               issues=list(solved.issues) + [f"mesh: {t}" for t in rep.passed_texts()])


def mesh_refusal(solved: Solved | None, spec: DesignSpec, rep, what: str, plan: Plan) -> Solved:
    """Infeasible contract for a design whose built mesh fails a casting rule (after the one
    relaxed retry): the binding constraint is the failing rule, naming the thin part."""
    from . import meshdfm

    loss = plan.detail.get("casting_loss_pct", 0.0)
    thin = meshdfm.failure_text(rep)
    tried = (f" Retried once with a {what}; it still fails." if what
             else " The design has nothing optional to relax.")
    alts = ["more gold, so the thin part can be made thicker", "a simpler design from the set",
            "a smaller or bezel-set stone" if spec.gem != "none" else "a plainer, more compact design"]
    s = solved.scale if solved is not None else 0.0
    v = solved.value if solved is not None else 0.0
    return Solved(solved.spec if solved is not None else spec, False, s, v, plan.target_value,
                  solved.iterations if solved is not None else 0,
                  explanation=f"this design can't be cast safely as solved: {thin}.{tried}",
                  binding_constraint=f"mesh check: {rep.failed[0].text}",
                  best_achievable={"value": round(v * (1 - loss / 100), 2), "unit": "g"},
                  alternatives=alts, warnings=rep.warning_texts(), mesh_checks=rep.as_list())


STONE_LADDER = (0.75, 0.5, 0.33, 0.25, 0.2, 0.15, 0.1)   # ct, the smaller-stone option for Hero D
BUDGET_MARGIN = 0.004       # budget solve aims 0.4% under the budget so the bill never tops it
COIN_ACCEPT_G = 0.05      # a coin is solved to its stamped weight within +/-0.05 g (Phase 3 gate)


class JewelleryPack(DomainPack):
    name = "jewellery"
    title = "Jeweller's Shop"

    def parse_brief(self, text, attachments=None):
        return B.parse(text)

    def intake(self, text, attachments=None, sender=None) -> Intake:
        """Rate updates first (owner/staff senders only), then the brief (scope, questions, or a Brief)."""
        if len(text) > B.MAX_INPUT_CHARS:
            a = B.analyse(text)
            return Intake("needs_info", reply=a.reply, lang=a.lang, questions=a.questions, topics=a.topics)
        lang = detect(text)
        r = rates.parse_rate_message(text)
        if r and not any(re.search(p, text.lower()) for p in B.PIECE_WORDS.values()):
            if not rates.may_set_rate(sender):
                q = M.t("rate_not_allowed", lang)
                return Intake("needs_info", reply=q, lang=lang, questions=[q], topics=["rate_permission"])
            if r.bad:   # malformed, out-of-format or conflicting numbers: nothing is saved
                q = M.t("rate_invalid", lang, bad=", ".join(r.bad))
                return Intake("needs_info", reply=q, lang=lang, questions=[q], topics=["rate"])
            saved = rates.GoldRateStore().set(r.rates)
            shown = ", ".join(f"{k}K {pricing.inr(v)}/g" for k, v in sorted(r.rates.items(), reverse=True))
            when = saved["set_at"].replace("T", " ")[:16]
            return Intake("rate_set", reply=M.t("rate_set", lang, rates=shown, when=when),
                          lang=lang, data={"rates": saved})
        a = B.analyse(text, attachments)
        if a.status == "brief":
            # No usable gold rate (missing, stale > 24 h, future-dated, out of range): say so and
            # ask for today's rate before any work; never estimate one (Phase 5).
            need = rates.karats_needed(a.brief.karat, bool(a.brief.old_gold))
            problem = rates.rate_source().problem(need)
            if problem:
                q = problem.reply(a.lang)
                return Intake("needs_info", reply=q, lang=a.lang, questions=[q], topics=["gold_rate"],
                              data={"rate_problem": problem.kind})
            return Intake("brief", brief=a.brief, lang=a.lang)
        return Intake(a.status, reply=a.reply, lang=a.lang, questions=a.questions, topics=a.topics,
                      data={"suggestion": a.suggestion} if a.suggestion else {})

    def describe_brief(self, brief: Brief, lang: str | None = None) -> str:
        lang = lang or brief.lang
        return f"{M.t('got_it', lang)} {B.describe(brief, lang)}"

    def plan(self, brief: Brief, loss_pct: float) -> Plan:
        p = pricing.plan(brief, loss_pct)
        if not p.ok and p.detail.get("min_weight_g") is not None and p.detail.get("mode") != "budget":
            return self._below_minimum(brief, p, loss_pct)
        return p

    def _lightest(self, brief: Brief, ct: float, loss_pct: float) -> float | None:
        """Finished weight of the lightest castable design for the brief carrying a `ct` stone:
        every deterministic variant built (stone seats cut) at the low end of its castable
        range. None when no variant can be cast with that stone."""
        from . import geometry

        best = None
        for spec in designer.deterministic(brief, ct):
            lo, hi = dfm.scale_bounds(spec)
            if lo > hi:
                continue
            g = G.mm3_to_grams(geometry.gold_volume(spec, lo), spec.karat) * (1 - loss_pct / 100)
            best = g if best is None else min(best, g)
        return best

    def _below_minimum(self, brief: Brief, p: Plan, loss_pct: float) -> Plan:
        """Weight / exchange target under the piece's minimum (Hero D). The refusal carries the
        minimum ACHIEVABLE finished weight, measured on the lightest castable design with the
        customer's stone, and options: keep the stone at that weight, or a smaller stone."""
        min_w, want = p.detail["min_weight_g"], p.detail["finished_gross_g"]
        ct = p.detail.get("requested_ct") or 0.0
        k, piece = brief.karat, brief.piece_type
        try:
            light = self._lightest(brief, ct, loss_pct)
        except designer.NoFamily:
            return p
        if light is None:
            return p
        best = max(min_w, light)
        has_stone = brief.gem != "none" and ct > 0
        stone = f"a {ct:g} ct {brief.gem}" if has_stone else ""
        if light > min_w:
            binding = (f"minimum castable weight for a {k}K {piece}"
                       + (f" holding {stone}" if has_stone else "")
                       + f" ({best:.2f} g at the casting minimums: "
                       f"{dfm.binding_rule(designer.deterministic(brief, ct)[0], 'lo')})")
        else:
            binding = f"minimum finished weight for a {piece} ({min_w:g} g)"
        alts = [f"a {best:.2f} g {k}K {piece}" + (f" with the {ct:g} ct {brief.gem}" if has_stone else "")]
        if has_stone:
            # Smaller stones: the lightest piece any of them allows, then the largest stone that
            # gets (within 0.02 g) that light.
            ladder = [(c, self._lightest(brief, c, loss_pct)) for c in STONE_LADDER if c < ct]
            ladder = [(c, max(min_w, lc)) for c, lc in ladder if lc is not None]
            if ladder:
                w_star = min(w for _, w in ladder)
                c, w = next((c, w) for c, w in ladder if w <= w_star + 0.02)
                if w < best - 0.005:
                    alts.append(f"a smaller {c:g} ct {brief.gem} in a {w:.2f} g {k}K {piece}")
        alts += [a for a in p.alternatives if a not in alts]
        alts = alts[:3]
        expl = (f"A {k}K {piece}" + (f" holding {stone}" if has_stone else "")
                + f" can't be made at {want:.2f} g: the lightest castable version finishes at "
                f"{best:.2f} g. Options: " + "; ".join(f"({i}) {a}" for i, a in enumerate(alts, 1)) + ".")
        return Plan(False, explanation=expl, detail={**p.detail, "min_achievable_g": round(best, 3)},
                    binding_constraint=binding,
                    best_achievable={"value": round(best, 2), "unit": "g"}, alternatives=alts)

    def propose(self, brief: Brief, n: int = 3) -> list[DesignSpec]:
        return designer.propose(brief, pricing.requested_ct(brief), n)

    def solve(self, spec: DesignSpec, plan: Plan, on_iter=None) -> Solved:
        """Solve to the target, then check the built mesh (Phase 4, meshdfm). A failed build or
        check retries ONCE with optional features relaxed (meshdfm.relax); if that fails too,
        the result is infeasible and names the failing rule and the thin part."""
        from . import meshdfm

        try:
            solved = self._solve_core(spec, plan, on_iter)
            rep = meshdfm.check_spec(solved.spec, solved.scale) if solved.ok else None
        except Exception as e:                    # a builder that raised mid-solve
            solved, rep = None, meshdfm.build_failure(e)
        if solved is not None and not solved.ok:
            return solved
        if rep.ok:
            return with_mesh(solved, rep)
        relaxed, what = meshdfm.relax(spec, rep)
        if relaxed is None:
            return mesh_refusal(solved, spec, rep, "", plan)
        try:
            s2 = self._solve_core(relaxed, plan, on_iter)
            rep2 = meshdfm.check_spec(s2.spec, s2.scale) if s2.ok else None
        except Exception as e:
            s2, rep2 = None, meshdfm.build_failure(e)
        if s2 is not None and s2.ok and rep2.ok:
            return with_mesh(s2, rep2, [f"first mesh check failed ({meshdfm.failure_text(rep)}); "
                                        f"retried once with a {what}"])
        if s2 is not None and s2.ok:
            return mesh_refusal(s2, relaxed, rep2, what, plan)
        return mesh_refusal(solved, spec, rep, what, plan)

    def _solve_core(self, spec: DesignSpec, plan: Plan, on_iter=None) -> Solved:
        from . import geometry  # bpy is imported only when geometry is needed

        if spec.piece_type == "coin" and spec.stamp and plan.detail.get("finished_gross_g"):
            # The back stamp states the weight being made (code-derived, never the LLM).
            spec = spec.model_copy(update={"params": {**spec.params,
                                                       "stamp_g": round(plan.detail["finished_gross_g"], 2)}})
        if plan.detail.get("joint_stone") and spec.gem != "none" and spec.gem_d_mm > 0:
            return self._solve_budget(spec, plan, on_iter)
        lo, hi = dfm.scale_bounds(spec)
        if lo > hi:
            return Solved(spec, False, lo, 0, plan.target_value, 0, **stone_too_big(spec, lo))
        f = lambda s: G.mm3_to_grams(geometry.gold_volume(spec, s), spec.karat)
        # A coin is sold by its stamped weight: accepted only within COIN_ACCEPT_G of the target.
        win = {"accept_abs": COIN_ACCEPT_G} if spec.piece_type == "coin" else {}
        r = solve_monotone(f, plan.target_value, lo, hi, on_iter=on_iter, **win)
        fail = {} if r.ok else solve_failure(r, plan.detail["casting_loss_pct"], spec)
        return Solved(spec, r.ok, r.scale, r.value, r.target, len(r.iterations),
                      issues=dfm.check(spec, r.scale) if r.ok else [], **fail)

    def _solve_budget(self, spec: DesignSpec, plan: Plan, on_iter=None) -> Solved:
        """Budget mode, stone size not named (Hero B): the stone and the gold are solved together.
        One scale s grows the whole design, band AND stone (gem_d = d0 * s), so the design keeps
        its stone-to-metal proportion; s is solved until the quote total (gold, making, stone,
        hallmark, GST: pricing.quote) lands just under the budget. The bill never tops it."""
        from . import geometry

        budget = float(plan.detail["budget_inr"])
        d0 = spec.gem_d_mm
        plain = spec.model_copy(update={"gem": "none", "gem_d_mm": 0.0})
        ref = Brief(piece_type=spec.piece_type, karat=spec.karat, gem=spec.gem)
        lo, hi = dfm.scale_bounds(plain)               # band rules; the stone scales with the band
        hi = min(hi, 12.0 / d0)                       # schema's largest stone
        at = lambda s: spec.model_copy(update={"gem_d_mm": round(d0 * s, 4)})
        grams = lambda s: G.mm3_to_grams(geometry.gold_volume(at(s), s), spec.karat)
        total = lambda s: pricing.quote(at(s), grams(s), ref, plan)["total"]
        if lo > hi:
            return Solved(spec, False, lo, 0, plan.target_value, 0, **stone_too_big(spec, lo))
        aim = budget * (1 - BUDGET_MARGIN)
        r = solve_monotone(total, aim, lo, hi, rel_tol=BUDGET_MARGIN * 0.75,
                           accept_abs=None, accept_rel=BUDGET_MARGIN * 0.75, on_iter=on_iter)
        s = r.scale
        if r.ok and total(s) > budget:                # rupee rounding: step down until it fits
            s = self._fit_budget(total, budget, lo, s)
            if s is None:                             # even the lightest version tops the budget
                r = SolveResult(False, lo, total(lo), aim, r.iterations, "below_min")
                s = lo
        final, g = at(s), grams(s)
        if not r.ok:
            t = r.value
            if r.reason == "below_min":
                alts = [f"a budget of about {pricing.inr(t)}", "14K gold", "a plain design without a stone"]
                expl = (f"the cheapest castable version of this design with its stone costs "
                        f"{pricing.inr(t)}, more than the {pricing.inr(budget)} budget.")
                binding = f"budget vs. {dfm.binding_rule(plain, 'lo')}"
            else:
                alts = ["a bolder design", f"keep {pricing.inr(budget - t)} of the budget", "a matching set"]
                expl = (f"this design tops out at {pricing.inr(t)} with the largest stone it can "
                        f"carry; the budget is {pricing.inr(budget)}.")
                binding = f"budget vs. {dfm.binding_rule(plain, 'hi')}"
            return Solved(final, False, s, g, g, len(r.iterations), explanation=expl,
                          binding_constraint=binding, best_achievable={"value": float(t), "unit": "INR"},
                          alternatives=alts)
        b_lo, b_hi = dfm.scale_bounds(final)
        if not b_lo - 1e-9 <= s <= b_hi + 1e-9:       # the grown stone outruns its band
            return Solved(final, False, s, g, g, len(r.iterations), **stone_too_big(final, s))
        return Solved(final, True, s, g, g, len(r.iterations), issues=dfm.check(final, s))

    @staticmethod
    def _fit_budget(total, budget: float, lo: float, s: float):
        """Largest scale in [lo, s] whose quote total is within the budget (total rises with the
        scale): a few small steps down, then bisection. None when even `lo` tops the budget, so
        an ok result can never cost more than the budget."""
        for _ in range(20):
            s = lo + (s - lo) * 0.999
            if total(s) <= budget:
                return s
        if total(lo) > budget:
            return None
        a, b = lo, s                                  # total(a) <= budget < total(b)
        for _ in range(40):
            m = 0.5 * (a + b)
            a, b = (m, b) if total(m) <= budget else (a, m)
        return a

    def weights(self, solved: Solved, plan: Plan) -> dict:
        """Casting, finished, expected loss and tolerance for one solved design (pricing.weights)."""
        return pricing.weights(solved.value, plan)

    def deliver(self, solved: Solved, brief: Brief, plan: Plan, out_dir: Path, quality: str):
        from . import geometry, jobcard, render

        spec: DesignSpec = solved.spec
        rc = pricing.rate_card()
        shrink = rc["casting_shrinkage_pct"]
        out_dir.mkdir(parents=True, exist_ok=True)
        geometry.clear_scene()
        b = geometry.build(spec, solved.scale)
        if not getattr(solved, "mesh_checks", None):     # a Solved made outside solve(): check now
            from . import meshdfm
            solved = with_mesh(solved, meshdfm.check_built(spec, b))
        files = {
            "stl": render.export_stl(b.gold, out_dir / "casting.stl", shrinkage_pct=shrink),
        }
        c, S = render.stage(b.gold, b.gems, spec.metal, spec.karat, spec.gem,
                            float_up=spec.piece_type == "pendant")
        files["glb"] = render.export_glb([b.gold, *b.gems, *b.mirror], out_dir / "model.glb")
        files.update(render.render_views(c, S, out_dir, quality))
        renders = {k: v for k, v in files.items() if k.startswith("render")}
        job = job_card(spec, solved, brief, plan, b.dims, 2 if b.mirror else 1, rc,
                       seats_in_model=getattr(b, "seats_in_model", True))
        (out_dir / "job_card.json").write_text(json.dumps(job, indent=2, ensure_ascii=False))
        (out_dir / "job_card.md").write_text(jobcard.job_card_md(job, renders, out_dir), encoding="utf-8")
        files["job_card"] = out_dir / "job_card.json"
        files["job_card_md"] = out_dir / "job_card.md"
        geometry.clear_scene()
        return files

    def quote(self, solved: Solved, brief: Brief, plan: Plan) -> dict:
        return pricing.quote(solved.spec, solved.value, brief, plan)

    # ---------------------------------------------------------- Phase 6: edits
    def load_brief(self, data: dict) -> Brief:
        return Brief.model_validate(data)

    def load_spec(self, data: dict) -> DesignSpec:
        return DesignSpec.model_validate(data)

    def parse_edit(self, text: str):
        return edits.understand(text)

    def pick_index(self, pick, n: int) -> int:
        return edits.pick_index(pick, n)

    def edit_text(self, key: str, lang: str) -> str:
        table = {"help": edits.HELP, "which": edits.WHICH}[key]
        return table.get(lang, table["en"])

    def apply_edit(self, spec, scale, modelled_g, request, plan, lang="en", on_iter=None) -> EditOutcome:
        """Patch the chosen version's spec, re-solve it (gold target kept unless the edit is
        about weight) and rerun the checks. `plan` is a fresh plan (today's rate)."""
        spec = spec if isinstance(spec, DesignSpec) else DesignSpec.model_validate(spec)
        try:
            patched = edits.apply(spec, scale, request)
            if patched.weight is not None:
                plan = edits.retarget(plan, modelled_g, patched.weight)
        except edits.EditRefused as e:
            return EditOutcome("refused", reply=edits.refused_text(e, lang))
        solved = edits.resolve(patched.spec, plan, patched.locked, scale, on_iter=on_iter)
        if solved.ok:                     # Phase 4: the edited mesh is checked (no relaxed retry:
            from . import meshdfm         # the customer asked for exactly this change)
            rep = meshdfm.check_spec(solved.spec, solved.scale)
            solved = with_mesh(solved, rep) if rep.ok else mesh_refusal(solved, solved.spec, rep, "", plan)
        return EditOutcome("solved" if solved.ok else "infeasible", solved=solved, plan=plan,
                           data={"patched": patched, "base_spec": spec, "base_scale": scale,
                                 "base_modelled": modelled_g})

    def edit_report(self, base: dict, new_version: int, outcome: EditOutcome, brief, lang="en") -> dict:
        d, plan = outcome.data, outcome.plan
        before = Solved(d["base_spec"], True, d["base_scale"], d["base_modelled"], plan.target_value, 0)
        q0 = self.quote(before, brief, plan)          # both priced at the same (current) rate
        q1 = self.quote(outcome.solved, brief, plan)
        rep = edits.report(base["version"], new_version, d["base_spec"], d["base_scale"],
                           d["base_modelled"], outcome.solved, d["patched"], q0, q1,
                           plan.detail["casting_loss_pct"], lang)
        rep["quote"] = q1
        return rep


PACK = register(JewelleryPack())
