"""Owner console read model. Standard library only; shop operations run on the worker."""
from __future__ import annotations

import math
import hashlib
import json


def snapshot(service):
    service.jobs.reap(service.render_timeout_s)
    jobs = service.jobs.recent()
    orders, commands = {}, {}
    for j in reversed(jobs):
        result = j.result or j.partial or {}
        if j.kind == "owner":
            action = j.payload.get("action")
            if result.get("data") is not None:
                commands[action] = result["data"]
                if action != "catalogue":
                    commands["current"] = result["data"]
            continue
        key = j.order_id or result.get("order_id") or j.job_id
        if key not in orders and j.conv_key:
            pending = next((old_key for old_key, old in orders.items()
                            if old.get('conversation') == j.conv_key and not old['versions']), None)
            if pending:
                orders[key] = orders.pop(pending)
        row = orders.setdefault(key, {"order_id": j.order_id, "job_id": j.job_id,
                                     "created": j.created, "versions": {}, "messages": [], "job_ids": []})
        row["job_ids"].append(j.job_id)
        row['order_id'] = j.order_id or result.get('order_id') or row['order_id']
        row.update(status=result.get("status", j.status) if j.status == "done" else j.status,
                   job_id=j.job_id, updated=j.updated,
                   conversation=j.conv_key, error=j.error)
        row["messages"].append({"text": j.payload.get("text") or j.payload.get("request_text", ""),
                                "result": result, "status": j.status})
        for field in ("brief", "plan", "edit", "explanation", "question", "infeasible"):
            if result.get(field) is not None:
                row[field] = result[field]
        for r in result.get("results") or []:
            row["versions"][str(r.get("version"))] = r
    return {"orders": list(reversed(list(orders.values()))), "shop": commands,
            "system": {"worker_online": service.worker_online(),
                       "queue_depth": sum(j.status == "queued" for j in jobs),
                       "running": sum(j.status in ("running", "solved") for j in jobs),
                       "jobs": [{"job_id": j.job_id, "kind": j.kind, "status": j.status,
                                 "created": j.created, "updated": j.updated, "error": j.error}
                                for j in jobs[:30]], "version": "P0"}}


def enqueue(service, body):
    if not isinstance(body, dict):
        raise ValueError("Expected a JSON object")
    action = body.get("action")
    if action not in ("shop", "rates_refresh", "calibrate", "catalogue"):
        raise ValueError("Unknown owner action")
    payload = {"action": action}
    if action == "calibrate":
        workshop = body.get("workshop")
        if not isinstance(workshop, str) or not workshop.strip() or len(workshop) > 64:
            raise ValueError("Name the workshop (up to 64 characters)")
        payload["workshop"] = workshop.strip()
        for field in ("designed_g", "actual_g"):
            v = body.get(field)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 < v <= 500:
                raise ValueError("Cast weights must be finite and between zero and 500 g")
            payload[field] = v
        if payload["actual_g"] > payload["designed_g"]:
            raise ValueError("Actual weight cannot exceed designed weight for loss calibration")
    # Repeated clicks while the same operation is queued/running share one job.
    previous = None
    for j in service.jobs.recent():
        if j.kind == "owner" and j.active and j.payload == payload:
            return j
        if previous is None and j.kind == 'owner' and j.payload == payload:
            previous = j.job_id
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return service.jobs.enqueue("owner", payload, idem=f'owner:{digest}:{previous or "first"}')[0]
