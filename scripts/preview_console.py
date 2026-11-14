"""Local console preview with real engine output and isolated demo data.

Run: .venv/bin/python scripts/preview_console.py
Open http://127.0.0.1:8080/console/ and use owner token local-demo-owner.
This token is deliberately public and only suitable for this loopback preview.
"""
from pathlib import Path
import os
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from karigar.service.core import KarigarService
    from karigar.service.http import make_server
    from karigar.service.worker import Worker, LocalClient
    from karigar.packs.jewellery import rates
    from karigar.core import llm
    llm.ENV_FILE = Path('/tmp/karigar-console-preview/no.env')
    os.environ['KARIGAR_LLM_BACKEND'] = 'none'
    base = Path('/tmp/karigar-console-preview')
    base.mkdir(parents=True, exist_ok=True)
    os.environ['KARIGAR_ORDERS_DB'] = str(base / 'orders.sqlite3')
    os.environ['KARIGAR_CALIBRATION_FILE'] = str(base / 'calibration.json')
    rates.RATES_FILE = base / 'rates.json'
    rates.GoldRateStore().set({24:14200,22:13007.2,18:10650,14:8307}, source='SAMPLE offline demo rate, not a market quote')
    svc = KarigarService(base / 'service')
    worker = Worker(LocalClient(svc), out_dir=base / 'out', quality='draft')
    threading.Thread(target=worker.run_forever, daemon=True).start()
    if not svc.jobs.recent():
        svc.jobs.enqueue('owner', {'action':'shop'})
        svc.start_order('SAMPLE demo: 22K floral ring of 8g, size 12', idem='preview-floral')
        svc.jobs.enqueue('owner', {'action':'catalogue'})
    elif not any(j.kind == 'owner' and j.payload.get('action') == 'catalogue'
                 and j.status in ('queued','running','done') for j in svc.jobs.recent()):
        svc.jobs.enqueue('owner', {'action':'catalogue'})
    server = make_server('127.0.0.1', 8080, svc, 'local-demo-api', 'local-demo-worker',
                         owner_token='local-demo-owner', console_dir=ROOT/'console')
    print('Preview: http://127.0.0.1:8080/console/ (token: local-demo-owner)', flush=True)
    try:
        server.serve_forever()
    finally:
        worker.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
