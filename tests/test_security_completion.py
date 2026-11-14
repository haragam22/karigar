"""Reproductions for documented backlog items; no network or real model calls."""
import json
import time

import pytest

from karigar.core.llm import extract_json
from probe.server import BadBody, _parse_json
from probe.server import RequestLog
from karigar.packs.jewellery import brief
from karigar.packs.jewellery.schema import Brief
from karigar.core.lang import detect


def test_deep_model_json_falls_back_instead_of_crashing():
    assert extract_json("[" * 20000 + "0" + "]" * 20000) is None
    assert extract_json("[" * 100 + "0" + "]" * 100) is None


def test_oversized_integer_model_json_falls_back():
    assert extract_json('{"value":' + "9" * 5000 + "}") is None


def test_malformed_escaped_json_is_scanned_in_linear_time():
    raw = b'\\"' * 32000
    start = time.monotonic()
    with pytest.raises(BadBody, match="valid JSON"):
        _parse_json(raw)
    assert time.monotonic() - start < 1


def test_json_complexity_ignores_escaped_strings():
    value = {"text": '[{\\\"' * 1000}
    assert _parse_json(json.dumps(value).encode()) == value


def test_deep_request_json_refused_before_decode():
    with pytest.raises(BadBody) as exc:
        _parse_json(b"[" * 65 + b"0" + b"]" * 65)
    assert exc.value.code == "json_too_complex"


def test_oversized_intake_never_calls_model(monkeypatch):
    monkeypatch.setattr(brief.llm, "complete_json", lambda *a: pytest.fail("model called"))
    assert brief.analyse("ring " * 500).topics == ["request_length"]


def test_delivery_time_is_not_a_budget():
    assert "budget_inr" not in brief._regex_parse("22K ring size 12 within 2 weeks")


@pytest.mark.parametrize("weight", ["-10", "+10", "1e9", "1.2e3"])
def test_signed_or_exponent_weight_is_not_silently_reinterpreted(weight):
    assert "target_weight_g" not in brief._regex_parse(f"22K ring size 12 {weight} g")


def test_carat_after_karat_is_found():
    assert brief._regex_parse("22 carat ring with 0.5 carat diamond")["gem_ct"] == 0.5


@pytest.mark.parametrize("size", ["size 12.5", "size 12, inner diameter 20 mm"])
def test_ambiguous_size_asks_again(size):
    assert "ring_size" in brief.analyse(f"22K ring 5g {size}").topics


def test_string_ring_size_uses_the_size_chart():
    assert Brief(piece_type="ring", ring_size="12").ring_inner_d_mm == brief.sizes.ring_inner_d_mm(12)


def test_conflicting_model_size_cannot_silently_override_the_chart():
    with pytest.raises(ValueError, match='conflict'):
        brief.BriefDraft(piece_type='ring', ring_size=12, ring_inner_d_mm=20)


def test_budget_has_a_finite_operational_ceiling():
    assert brief.analyse("22K ring size 12 budget 20000000").status == "needs_info"


def test_language_ambiguous_english_and_devanagari():
    assert detect("Do you do rings for Sona?") == "en"
    assert detect("मुझे अंगूठी चाहिए") == "hinglish"


def test_unauthenticated_flood_cannot_rotate_authenticated_evidence(tmp_path):
    log = RequestLog(tmp_path/'probe.jsonl', max_bytes=1024, keep=1)
    log.write({'event':'request','auth_ok':True,'body':'real evidence'})
    for i in range(100):
        log.write({'event':'request','auth_ok':False,'body_bytes':i,'headers':{'x':'x'*300}})
    assert log.authenticated.tail(10)[0]['body'] == 'real evidence'


def test_log_tail_has_a_total_byte_budget(tmp_path):
    log = RequestLog(tmp_path/'probe.jsonl')
    for i in range(100):
        log.write({'i':i,'value':'x'*3000})
    tail = log.tail(500, max_bytes=16000)
    assert tail[-1]['i'] == 99
    assert len(json.dumps(tail)) < 17000


@pytest.mark.parametrize('url', ['http://localhost.evil.example','http://127.0.0.1.evil.example',
                               'https://name:password@example.com','https://example.com?token=x'])
def test_worker_does_not_send_token_to_loopback_lookalikes(url):
    from karigar.service.worker import HttpClient
    with pytest.raises(ValueError):
        HttpClient(url, 'worker-secret')
