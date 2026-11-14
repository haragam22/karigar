"""Phase 7 CLI adapter (`run.py ask|serve|worker`), worker setup script, Render blueprint."""
import json
import subprocess
import sys
from pathlib import Path

import run
from karigar.service import worker as W
from service_fakes import Script, make_factory

ROOT = Path(__file__).resolve().parents[1]


def test_run_ask_is_a_thin_adapter_over_the_service(tmp_path, monkeypatch, capsys):
    script = Script()
    monkeypatch.setattr(W, "make_orchestrator", make_factory(script))
    sd = str(tmp_path / "svc")
    assert run.main(["ask", "22K ring 5g", "--service-dir", sd, "--out", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "Which ring size?" in out
    conv = json.loads(out.strip().splitlines()[-1])["conversation"]
    assert run.main(["ask", "size 12", "--conversation", conv, "--service-dir", sd,
                     "--out", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "Floral" in out and "/files/" in out
    assert script.calls[-1] == ("handle", "22K ring 5g\nsize 12", conv)


def test_serve_and_worker_refuse_without_secrets(monkeypatch, tmp_path):
    from karigar.core import llm
    for k in ("KARIGAR_API_KEY", "KARIGAR_WORKER_TOKEN", "KARIGAR_SERVICE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm, "ENV_FILE", tmp_path / "none.env")
    assert run.main(["serve"]) == 2
    assert run.main(["worker"]) == 2


def test_python_m_karigar_service_refuses_open_start(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "KARIGAR_SERVICE_DIR": str(tmp_path / "s")}
    r = subprocess.run([sys.executable, "-m", "karigar.service"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "refusing" in r.stderr


def test_service_refusal_names_the_missing_secret_and_near_misses_but_no_values(tmp_path):
    """A typo'd name (trailing space, wrong case) is listed by name; secret values never print."""
    env = {"PATH": "/usr/bin:/bin", "KARIGAR_SERVICE_DIR": str(tmp_path / "s"),
           "KARIGAR_WORKER_TOKEN": "w-secret-value", "KARIGAR_API_KEY ": "k-secret-value"}
    r = subprocess.run([sys.executable, "-m", "karigar.service"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2
    assert "Missing or empty: KARIGAR_API_KEY." in r.stderr
    assert "'KARIGAR_API_KEY '" in r.stderr
    assert "secret-value" not in r.stderr


def test_setup_worker_script_is_valid_bash_and_installs_the_three_parts():
    p = ROOT / "scripts" / "setup_worker.sh"
    r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    s = p.read_text()
    for need in ("requirements.txt", "import bpy", "nvm", "@anthropic-ai/claude-code",
                 "KARIGAR_SERVICE_URL", "KARIGAR_WORKER_TOKEN", "run.py worker"):
        assert need in s
    assert "AGENTROUTER_API_KEY=" not in s.replace("#   AGENTROUTER_API_KEY=", "")   # never writes secrets


def test_render_blueprint_runs_the_stdlib_service_with_secrets_unsynced():
    s = (ROOT / "render.yaml").read_text()
    assert "startCommand: python -m karigar.service" in s and "healthCheckPath: /" in s
    assert "pip install" not in s
    for k in ("KARIGAR_API_KEY", "KARIGAR_WORKER_TOKEN"):
        i = s.index(f"key: {k}")
        assert "sync: false" in s[i:i + 120]
