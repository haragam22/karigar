"""Owner boundaries, queued shop operations and the console read model."""
import math

import pytest

from karigar.service.console import enqueue, snapshot
from karigar.service.core import KarigarService
from karigar.service.worker import LocalClient, Worker
from test_service_http import env, req, OWNER, KEY, WTOK


def test_console_data_is_owner_only(env):
    for token in (None, KEY, WTOK):
        assert req(env, 'GET', '/api/console', token=token)[0] == 401
        assert req(env, 'POST', '/api/console/actions', {'action':'rates_refresh'}, token=token)[0] == 401
    status, data, _ = req(env, 'GET', '/api/console', token=OWNER)
    assert status == 200 and data['orders'] == []
    assert 'worker_online' in data['system']


def test_owner_action_queues_and_worker_runs_it(env, monkeypatch):
    from karigar.service import shop
    calls = []
    monkeypatch.setattr(shop, 'run_owner', lambda payload, *args:
                        calls.append(payload) or {'status':'done', 'data':{'rates':[]}})
    status, data, _ = req(env, 'POST', '/api/console/actions', {'action':'shop'}, token=OWNER)
    assert status == 202
    assert req(env, 'POST', '/api/console/actions', {'action':'shop'}, token=OWNER)[1]['job_id'] == data['job_id']
    Worker(LocalClient(env.svc)).run_once()
    assert calls == [{'action':'shop'}]
    result = req(env, 'GET', '/api/console', token=OWNER)[1]
    assert result['shop']['current'] == {'rates':[]}
    assert result['orders'] == []


@pytest.mark.parametrize('body', [None, [], {'action':'exec'}, {'action':'calibrate'},
    {'action':'calibrate','workshop':'x','designed_g':float('nan'),'actual_g':1},
    {'action':'calibrate','workshop':'x','designed_g':1,'actual_g':2},
    {'action':'calibrate','workshop':'x','designed_g':True,'actual_g':1}])
def test_bad_owner_operations_never_enter_queue(tmp_path, body):
    s = KarigarService(tmp_path)
    with pytest.raises(ValueError):
        enqueue(s, body)
    assert s.jobs.recent() == []


def test_order_snapshot_keeps_all_versions_and_the_original_numbers(tmp_path):
    s = KarigarService(tmp_path)
    first = s.jobs.enqueue('continue', {'text':'22K ring 8g size 12'})[0]
    s.jobs.claim(300)
    s.finish(first.job_id, {'status':'done','order_id':'ORD-demo','brief':{'karat':22},
                           'results':[{'version':1,'weights':{'finished_g':7.985},'quote':{'total':98765}}]})
    edit = s.jobs.enqueue('edit', {'order_id':'ORD-demo','text':'1 g lighter'})[0]
    s.jobs.claim(300)
    s.finish(edit.job_id, {'status':'done','order_id':'ORD-demo',
                          'results':[{'version':2,'weights':{'finished_g':6.986},'quote':{'total':86000}}]})
    rows = snapshot(s)['orders']
    assert len(rows) == 1
    assert rows[0]['versions']['1']['weights']['finished_g'] == 7.985
    assert rows[0]['versions']['2']['quote']['total'] == 86000
    assert rows[0]['job_ids'] == [first.job_id, edit.job_id]


def test_all_catalogue_defaults_have_valid_complete_specs():
    from karigar.packs.jewellery.families import CATALOGUE, FAMILIES, LABELS
    from karigar.packs.jewellery.schema import DesignSpec
    for name in CATALOGUE:
        f = FAMILIES[name]
        for label in LABELS:
            s = DesignSpec(**{'name':f.title,'piece_type':f.piece_type,'family':name,**f.variant_fields(label)})
            assert s.family == name


def test_canonical_catalogue_name_orders_that_exact_family():
    from karigar.packs.jewellery.brief import analyse
    r = analyse('22K ring_floral_cluster floral ring 8 g size 12')
    assert r.brief.family == 'ring_floral_cluster'


def test_progress_keeps_busy_worker_online(tmp_path):
    clock = [1000.0]
    s = KarigarService(tmp_path, clock=lambda:clock[0])
    j = s.jobs.enqueue('owner', {'action':'catalogue'})[0]
    s.claim()
    clock[0] += 100
    assert not s.worker_online()
    s.progress(j.job_id, [])
    assert s.worker_online()


def test_console_question_ack_allows_answer_to_continue(env):
    from test_service_http import start_worker
    start_worker(env)
    _, t, _ = req(env, 'POST', '/api/orders', {'text':'22K ring 8g'}, token=OWNER)
    import time
    for _ in range(100):
        job = env.svc.jobs.get(t['job_id'])
        if job.status == 'done': break
        time.sleep(.01)
    assert job.result['status'] == 'needs_info'
    assert req(env, 'POST', f'/api/console/jobs/{job.job_id}/seen', {}, token=OWNER)[0] == 200
    _, answer, _ = req(env, 'POST', f'/api/conversations/{t["conversation"]}/messages',
                       {'text':'size 12'}, token=OWNER)
    assert answer['job_id'] != t['job_id']
    assert env.svc.jobs.get(answer['job_id']).payload['request_text'] == '22K ring 8g\nsize 12'
