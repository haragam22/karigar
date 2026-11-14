"""The Blender worker (Phase 7): polls the service for jobs, runs the Orchestrator, uploads results.

Runs on the laptop in WSL (bpy + Node + `claude` CLI; scripts/setup_worker.sh), or on any box
with the same setup. It only makes outgoing HTTPS calls to the service (`KARIGAR_SERVICE_URL`,
`KARIGAR_WORKER_TOKEN`), so no tunnel is needed. All LLM calls (AgentRouter through the `claude`
CLI, core/llm.py) happen here, never in the service's request handlers.

Per job (`kind` "continue" or "edit", payload from KarigarService):
- payload has `order_id` → `Orchestrator.handle_edit` (a pick, an edit). If the edit parser does
  not understand the text (`needs_info`, topic `edit`) and the text reads as a new order on its
  own, it becomes a new order in the same conversation.
- else → `Orchestrator.handle(request_text, conversation=...)` (`request_text` = earlier
  unanswered request + this answer, so answering the counter's questions completes the brief).
Progress lines go up as they happen; at the "solved" stage (spec, weights, quote) the partial
result goes up before rendering starts, so the customer gets numbers even if renders are slow
or fail. Output files are uploaded and their paths replaced by the service's `/files/<token>/…`.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

from ..core.stagelog import log_stage
from ..core.transport import Transport

UPLOAD_KINDS = ("render_hero", "render_top", "render_side", "stl", "glb", "job_card", "job_card_md",
                "quote", "edit")
MAX_UPLOAD = 25 * 1024 * 1024


class ServiceError(RuntimeError):
    pass


class LocalClient:
    """The worker's view of a KarigarService in the same process (CLI `run.py ask`, tests)."""

    def __init__(self, service):
        self.s = service

    def claim(self):
        return self.s.claim()

    def progress(self, job_id, lines):
        self.s.progress(job_id, lines)

    def solved(self, job_id, partial):
        self.s.stage_solved(job_id, partial)

    def upload(self, job_id, name, data: bytes) -> str:
        return self.s.upload_file(job_id, name, data)

    def finish(self, job_id, result):
        self.s.finish(job_id, result)

    def fail(self, job_id, error):
        self.s.fail(job_id, error)


class HttpClient:
    """The worker's view of the service over HTTPS (`/worker/...`, Bearer worker token)."""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        if not token:
            raise ValueError("KARIGAR_WORKER_TOKEN is required")
        u = base_url.rstrip("/")
        parsed = urlsplit(u)
        if not (parsed.scheme == "https" and parsed.hostname or
                parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")) \
                or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("the service URL must be https:// (http only for localhost)")
        self.base, self.token, self.timeout = u, token, timeout

    def _call(self, method: str, path: str, body: bytes | None = None,
              ctype: str = "application/json"):
        req = urllib.request.Request(self.base + path, data=body, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if body is not None:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read(4 * 1024 * 1024)
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raise ServiceError(f"{method} {path} → HTTP {e.code}") from None
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            raise ServiceError(f"{method} {path} → {type(e).__name__}") from None

    def _json(self, method, path, obj):
        return self._call(method, path, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def claim(self):
        status, data = self._call("GET", "/worker/jobs")
        return data.get("job") if status == 200 and data else None

    def progress(self, job_id, lines):
        self._json("POST", f"/worker/jobs/{job_id}/progress", {"lines": lines})

    def solved(self, job_id, partial):
        self._json("POST", f"/worker/jobs/{job_id}/solved", {"result": partial})

    def upload(self, job_id, name, data: bytes) -> str:
        from urllib.parse import quote
        _, out = self._call("POST", f"/worker/jobs/{job_id}/files?name={quote(name)}", data,
                            "application/octet-stream")
        return out["path"]

    def finish(self, job_id, result):
        self._json("POST", f"/worker/jobs/{job_id}/result", {"result": result})

    def fail(self, job_id, error):
        self._json("POST", f"/worker/jobs/{job_id}/fail", {"error": str(error)[:300]})


class ProgressTransport(Transport):
    """Sends the shop floor's say/progress lines to the service (batched, at most every 1 s)."""

    def __init__(self, client, job_id: str, min_interval: float = 1.0):
        self.c, self.job_id, self.min_interval = client, job_id, min_interval
        self.buf: list[str] = []
        self.last = 0.0

    def _push(self, line: str, force: bool = False) -> None:
        self.buf.append(line)
        now = time.monotonic()
        if force or now - self.last >= self.min_interval:
            lines, self.buf, self.last = self.buf, [], now
            try:
                self.c.progress(self.job_id, lines)
            except ServiceError:
                pass                            # progress is best effort

    def flush(self):
        if self.buf:
            self._push(self.buf.pop(), force=True)

    def say(self, agent, text):
        self._push(f"{agent}: {text}")

    def progress(self, agent, text):
        self._push(f"{agent}: {text}")

    def send_file(self, agent, path, caption=""):
        pass                                    # files go up with the result

    def ask(self, agent, question):
        pass                                    # the question is the result's reply


def make_orchestrator(transport, on_stage, out_dir: Path, quality: str):
    """The real shop floor (imports bpy through the pack only when a design is built)."""
    from ..core import registry
    from ..core.orchestrator import Orchestrator
    import karigar.packs.jewellery  # noqa: F401  (registers the pack)
    return Orchestrator(registry.get("jewellery"), transport=transport, out_dir=out_dir,
                        quality=quality, workshop=os.environ.get("KARIGAR_WORKSHOP") or None,
                        on_stage=on_stage)


class Worker:
    def __init__(self, client, out_dir: Path | str = Path("out"), quality: str = "preview",
                 orchestrator_factory=None, poll_s: float = 3.0, sleep=time.sleep):
        self.c, self.out_dir, self.quality = client, Path(out_dir), quality
        self.factory, self.poll_s, self.sleep = orchestrator_factory, poll_s, sleep
        self.stop = threading.Event()

    def _upload_files(self, job_id: str, result: dict) -> dict:
        """Upload every output file of each variant; replace local paths with service paths."""
        for r in result.get("results") or []:
            files = {}
            for k, p in (r.get("files") or {}).items():
                if k not in UPLOAD_KINDS and not k.startswith("render"):
                    continue
                path = Path(p)
                try:
                    if not path.is_file() or path.stat().st_size > MAX_UPLOAD:
                        continue
                    name = f"v{r.get('version')}-{path.name}"
                    files[k] = self.c.upload(job_id, name, path.read_bytes())
                except (ServiceError, OSError, KeyError) as e:
                    log_stage("upload_failed", event="worker", job=job_id, kind=k, error=type(e).__name__)
            r["files"] = files
        return result

    def run_job(self, job: dict) -> dict:
        """Keep the lease and online status alive even during a long blocking render."""
        finished = threading.Event()
        def heartbeat():
            while not finished.wait(30):
                try:
                    self.c.progress(job["job_id"], [])
                except (ServiceError, OSError):
                    pass
        thread = threading.Thread(target=heartbeat, daemon=True, name="worker-heartbeat")
        thread.start()
        try:
            return self._run_job(job)
        finally:
            finished.set()
            thread.join(timeout=1)

    def _run_job(self, job: dict) -> dict:
        job_id, payload = job["job_id"], job.get("payload") or {}
        t0 = time.time()
        log_stage("job_start", event="worker", job=job_id, kind=job.get("kind"))
        tr = ProgressTransport(self.c, job_id)
        if job.get("kind") == "owner":
            from .shop import run_owner
            try:
                res = run_owner(payload, self.out_dir, self.quality,
                                lambda text: tr._push(text, force=True))
                res = self._upload_files(job_id, res)
                if payload.get("action") == "catalogue":
                    res["data"]["catalogue"] = res["results"]
                self.c.finish(job_id, res)
                return res
            except Exception as e:
                self.c.fail(job_id, type(e).__name__)
                return {"status": "failed", "error": type(e).__name__}
        sent = {"solved": False}

        def on_stage(stage: str, data: dict) -> None:
            tr._push(f"stage: {stage}", force=True)
            if stage == "solved" and not sent["solved"]:
                sent["solved"] = True
                try:
                    self.c.solved(job_id, data)
                except ServiceError:
                    pass
        orch = (self.factory or make_orchestrator)(tr, on_stage, self.out_dir, self.quality)
        conv = payload.get("conversation")
        text = str(payload.get("text", ""))
        try:
            if payload.get("order_id"):
                res = orch.handle_edit(payload["order_id"], text)
                if res.get("status") == "needs_info" and "edit" in (res.get("topics") or []):
                    alt = orch.handle(text, conversation=conv)       # a new order in the same chat?
                    if alt.get("status") != "needs_info":
                        res = alt
            else:
                res = orch.handle(str(payload.get("request_text") or text), conversation=conv)
        except Exception as e:                                # report, never crash the loop
            tr.flush()
            log_stage("job_failed", event="worker", job=job_id, error=type(e).__name__,
                      ms=round((time.time() - t0) * 1000))
            self.c.fail(job_id, type(e).__name__)
            return {"status": "failed", "error": type(e).__name__}
        tr.flush()
        res = self._upload_files(job_id, res)
        self.c.finish(job_id, res)
        log_stage("job_done", event="worker", job=job_id, status=str(res.get("status")),
                  ms=round((time.time() - t0) * 1000))
        return res

    def run_once(self) -> dict | None:
        job = self.c.claim()
        if not job:
            return None
        return self.run_job(job)

    def run_forever(self) -> None:
        backoff = self.poll_s
        while not self.stop.is_set():
            try:
                did = self.run_once()
                backoff = self.poll_s
            except ServiceError as e:
                log_stage("poll_failed", event="worker", error=str(e)[:80])
                did, backoff = None, min(backoff * 2, 60.0)
            if not did:
                self.sleep(backoff)


def main(argv=None) -> int:
    """`run.py worker`: env KARIGAR_SERVICE_URL, KARIGAR_WORKER_TOKEN (from .env or the shell)."""
    from ..core.llm import load_env_file
    load_env_file()
    url = os.environ.get("KARIGAR_SERVICE_URL", "")
    token = os.environ.get("KARIGAR_WORKER_TOKEN", "")
    if not url or not token:
        print("Set KARIGAR_SERVICE_URL and KARIGAR_WORKER_TOKEN (in .env or the shell).", file=sys.stderr)
        return 2
    quality = os.environ.get("KARIGAR_WORKER_QUALITY", "draft")
    out = Path(os.environ.get("KARIGAR_WORKER_OUT", Path(__file__).resolve().parents[2] / "out"))
    w = Worker(HttpClient(url, token), out_dir=out, quality=quality)
    print(f"karigar worker polling {url} (quality {quality}); Ctrl+C to stop", flush=True)
    try:
        w.run_forever()
    except KeyboardInterrupt:
        pass
    return 0
