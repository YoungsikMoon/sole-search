"""gov24_crawl — 첫 페이지 0건 fail-closed (CI 스모크가 파손을 녹색 통과하지 않도록)."""
import argparse
import json

import pytest


def _args(tmp_path, max_pages=None):
    return argparse.Namespace(output=str(tmp_path / "gov24.jsonl"),
                              filter_target=None, delay=0.5, max_pages=max_pages)


def _svc(sid, name):
    return {"서비스ID": sid, "서비스명": name, "신청기한": "상시",
            "소관기관명": "행정안전부", "지원유형": "현금"}


def _patch_api(monkeypatch, gov24, payload):
    monkeypatch.setattr(gov24, "api_get", lambda path, key, params: payload)


class _FakeResp:
    def __init__(self, body):
        self._body = body
    def read(self):
        return self._body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_api_get_401_message_redacts_key(monkeypatch, gov24):
    """401 응답의 msg는 서버 반사 문자열 — 키를 되비추면 그대로 예외에 실려
    stderr로 새어나간다. _redact를 거쳐 마스킹돼야 한다(Codex #7, '키는 어떤
    경로로도 출력 금지' 하드룰)."""
    KEY = "SYNTHmY_SECRET_KEY_abc123=="
    body = json.dumps({"code": 401, "msg": f"rejected key {KEY}"}).encode()
    monkeypatch.setattr(gov24, "_open_validated", lambda url, timeout: _FakeResp(body))
    with pytest.raises(PermissionError) as ei:
        gov24.api_get("serviceList", KEY, {"page": 1})
    assert KEY not in str(ei.value)
    assert "[REDACTED]" in str(ei.value)


def test_api_get_401_message_redacts_decoded_key(monkeypatch, gov24):
    """인코딩 형태('%2B') 키를 서버가 디코딩('A+B')해서 반사해도 마스킹돼야
    한다 — data.go.kr은 인코딩 키를 명시 지원한다(Codex #7 residual)."""
    KEY = "A%2BB"
    body = json.dumps({"code": 401, "msg": "rejected key A+B"}).encode()
    monkeypatch.setattr(gov24, "_open_validated", lambda url, timeout: _FakeResp(body))
    with pytest.raises(PermissionError) as ei:
        gov24.api_get("serviceList", KEY, {"page": 1})
    assert "A+B" not in str(ei.value)
    assert "[REDACTED]" in str(ei.value)


def test_redact_masks_mixed_case_percent_echo(gov24):
    """서버가 %XX를 대·소문자 섞어 반사해도(A%2bB) 마스킹돼야 한다 — ir/KIPRIS
    리댁터와 동일한 대소문자 무관 강도(Codex #7 residual)."""
    for echo in ("A%2bB", "A%2BB", "A+B", "rejected A%2bB now"):
        out = gov24._redact(echo, "A%2BB")
        assert "A%2bB" not in out and "A%2BB" not in out and "A+B" not in out


def test_filter_mode_invalid_row_is_partial(monkeypatch, gov24, tmp_path, no_network):
    """--filter-target 모드에서 정규화 실패 행이 있으면(식별자 누락) 매칭 대상이
    조용히 사라질 수 있으므로 exit 2(partial)로 내려야 한다(Codex #13)."""
    payload = {"totalCount": 2, "data": [_svc("S1", "소상공인 경영지원"),
                                         {"서비스명": "소상공인 노아이디"}]}  # 2번째 식별자 없음
    _patch_api(monkeypatch, gov24, payload)
    args = argparse.Namespace(output=str(tmp_path / "g.jsonl"),
                              filter_target="소상공인", delay=0.5, max_pages=None)
    assert gov24.cmd_list(args, key="k") == 2


def test_empty_first_page_with_positive_total_is_failed(monkeypatch, gov24, tmp_path,
                                                        no_network, capsys):
    """totalCount>0인데 data=[] → 파서/API 파손 신호, exit 2 (Codex NO-GO 3 회귀).
    스모크(--max-pages 1)에서도 동일하게 실패해야 한다."""
    _patch_api(monkeypatch, gov24, {"totalCount": 10, "data": []})
    assert gov24.cmd_list(_args(tmp_path), key="k") == 2
    assert "0건" in capsys.readouterr().err
    assert gov24.cmd_list(_args(tmp_path, max_pages=1), key="k") == 2


def test_zero_total_is_failed_signal(monkeypatch, gov24, tmp_path, no_network):
    """totalCount=0은 기존 계약대로 장애 신호(exit 2) — 전량 사라진 응답을
    '공고 없음 성공'으로 넘기지 않는다."""
    _patch_api(monkeypatch, gov24, {"totalCount": 0, "data": []})
    assert gov24.cmd_list(_args(tmp_path), key="k") == 2


def test_first_page_smoke_success(monkeypatch, gov24, tmp_path, no_network):
    """정상 첫 페이지 + --max-pages 1 → coverage 검증 생략하고 성공."""
    _patch_api(monkeypatch, gov24,
               {"totalCount": 1000, "data": [_svc("SVC1", "소상공인 요금감면")]})
    assert gov24.cmd_list(_args(tmp_path, max_pages=1), key="k") == 0
    recs = [json.loads(l) for l in
            (tmp_path / "gov24.jsonl").read_text().splitlines()]
    assert recs[0]["source_id"] == "SVC1"


def test_missing_id_fields_fail_closed(monkeypatch, gov24, tmp_path, no_network):
    _patch_api(monkeypatch, gov24,
               {"totalCount": 5, "data": [{"이상한키": "값"}]})
    assert gov24.cmd_list(_args(tmp_path, max_pages=1), key="k") == 2
