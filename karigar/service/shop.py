"""Owner operations, executed by the Blender worker, never the HTTP handler."""
from pathlib import Path


def shop_snapshot():
    import os
    from ..core.calibration import CalibrationStore
    from ..packs.jewellery import rates
    store = CalibrationStore()
    source = rates.rate_source()
    rate_rows = []
    for k in (24, 22, 18, 14):
        problem = source.problem([k])
        item = rates.GoldRateStore().load().get(str(k), {})
        rate_rows.append({"karat": k, **item, "status": problem.kind if problem else "current"})
    names = sorted(set(store.data) | {os.environ.get("KARIGAR_WORKSHOP", "demo-workshop")})
    return {"rates": rate_rows, "rate_policy": rates.rate_card()["gold_rate"],
            "workshops": [{"name": name, "loss_pct": store.loss_pct(name),
                           "tolerance": store.tolerance(name),
                           "records": store.data.get(name, {}).get("records", [])} for name in names]}


def run_owner(payload, out_dir, quality, progress):
    action = payload["action"]
    if action == "rates_refresh":
        from ..packs.jewellery.ratejob import refresh
        result = refresh()
        if not result.ok:
            return {"status": "done", "data": {**shop_snapshot(), "notice": result.message}}
    elif action == "calibrate":
        from ..core.calibration import CalibrationStore
        CalibrationStore().record(payload["workshop"], payload["designed_g"], payload["actual_g"])
    elif action == "catalogue":
        return catalogue(Path(out_dir), quality, progress)
    return {"status": "done", "data": shop_snapshot()}


def catalogue(out_dir, quality, progress):
    import os
    from ..core.calibration import CalibrationStore
    from ..core.gold import density
    from ..packs.jewellery import geometry, meshdfm, render
    from ..packs.jewellery.families import CATALOGUE, FAMILIES, LABELS
    from ..packs.jewellery.schema import DesignSpec
    rows = []
    loss = CalibrationStore().loss_pct(os.environ.get('KARIGAR_WORKSHOP'))
    for index, name in enumerate(CATALOGUE):
        f = FAMILIES[name]
        progress(f"Building catalogue: {f.title or name}")
        weights = {}
        for label in LABELS:
            spec = DesignSpec(**{"name": f.title, "piece_type": f.piece_type, "family": name,
                                 **f.variant_fields(label)})
            weights[label] = geometry.gold_volume(spec, 1.0) * density(spec.karat) / 1000
        spec = DesignSpec(**{"name": f.title, "piece_type": f.piece_type, "family": name,
                             **f.default_spec})
        size = (f'inner diameter {spec.inner_d_mm:g} mm, ' if f.piece_type in ('ring', 'bangle')
                else f'{spec.length_in} inch, ' if f.piece_type == 'chain' else '')
        prompt = (f'{spec.karat}K {name} {f.title} {f.piece_type}, {size}'
                  f'{weights["balanced"] * (1 - loss / 100):.2f}g')
        geometry.clear_scene()
        built = geometry.build(spec, 1.0)
        checks = meshdfm.check_built(spec, built).as_list()
        folder = out_dir / "catalogue" / name
        folder.mkdir(parents=True, exist_ok=True)
        center, size = render.stage(built.gold, built.gems, spec.metal, spec.karat, spec.gem)
        files = {"glb": render.export_glb([built.gold, *built.gems, *built.mirror], folder / "model.glb")}
        files.update(render.render_views(center, size, folder, quality))
        rows.append({"version": index + 1, "family": name, "variant": f.title or spec.name,
                     "piece_type": f.piece_type, "spec": spec.model_dump(),
                     "order_prompt": prompt,
                     "catalogue_weights": weights, "mesh_checks": checks,
                     "files": {k: str(v) for k, v in files.items()}})
    geometry.clear_scene()
    return {"status": "done", "results": rows, "data": {"catalogue": rows}}
