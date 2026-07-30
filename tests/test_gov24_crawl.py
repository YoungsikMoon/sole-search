import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "skills/sole-search/scripts"))
import gov24_crawl as g

V3_ROW = {
    "서비스ID": "SVC000012345",
    "서비스명": "소상공인 고용보험료 지원",
    "서비스목적요약": "자영업자 고용보험 가입 촉진",
    "신청기한": "상시신청",
    "지원대상": "소상공인 중 자영업자 고용보험 가입자",
    "지원내용": "보험료 일부 지원",
    "지원유형": "현금",
    "소관기관명": "중소벤처기업부",
    "부서명": "소상공인정책과",
    "사용자구분": "개인",
    "서비스분야": "고용·창업",
    "상세조회URL": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/SVC000012345",
    "수정일시": "2026-07-01 00:00:00",
}

V1_ROW = {
    "SVC_ID": "SVC999",
    "서비스명": "전통시장 화재공제 지원",
    "신청기한": "2026년 12월 31일까지",
    "지원대상": "전통시장 상인",
    "소관기관명": "소상공인시장진흥공단",
}


def test_to_record_v3():
    r = g.to_record(V3_ROW)
    assert r["source"] == "gov24" and r["source_id"] == "SVC000012345"
    assert r["status"] == "상시" and r["apply_end"] is None
    assert r["agency"] == "중소벤처기업부 / 소상공인정책과"
    assert r["tags"] == ["현금"]
    assert r["attachments_complete"] is True
    assert r["raw"]["target"].startswith("소상공인")
    assert r["raw"]["user_type"] == "개인" and r["raw"]["field"] == "고용·창업"


def test_to_record_v1_key_variant_and_deadline_parse():
    r = g.to_record(V1_ROW)
    assert r["source_id"] == "SVC999"
    assert r["apply_end"] == "2026-12-31"
    assert r["status"] in ("접수중", "마감")  # 실행 시점 의존 — 파싱만 검증
    assert r["canonical_url"].endswith("/dtlEx/SVC999")


def test_to_record_missing_id_fails_closed():
    assert g.to_record({"서비스명": "이름만 있음"}) is None
    assert g.to_record({"서비스ID": "X"}) is None  # 서비스명 없음


def test_status_from_deadline():
    assert g.status_from_deadline("상시신청") == ("상시", None)
    assert g.status_from_deadline("연중") == ("상시", None)
    assert g.status_from_deadline("") == ("불명", None)
    assert g.status_from_deadline("예산 소진 시") == ("불명", None)
    s, end = g.status_from_deadline("2020.01.31 마감")
    assert s == "마감" and end == "2020-01-31"


def test_match_target():
    r = g.to_record(V3_ROW)
    assert g.match_target(r, "소상공인") is True
    assert g.match_target(r, "청년농업인") is False


def test_encode_key():
    assert g.encode_key("abc+def==") == "abc%2Bdef%3D%3D"
    assert g.encode_key("abc%2Bdef%3D%3D") == "abc%2Bdef%3D%3D"  # 이중 인코딩 방지


def test_resolve_key_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "KEY_FILE", str(tmp_path / "api_key"))
    monkeypatch.delenv("DATA_GO_KR_API_KEY", raising=False)
    assert g.resolve_key(None) == ""
    (tmp_path / "api_key").write_text("filekey\n두번째줄무시\n")
    assert g.resolve_key(None) == "filekey"
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "envkey")
    assert g.resolve_key(None) == "envkey"
    assert g.resolve_key("argkey") == "argkey"


def test_cli_inactive_without_key(tmp_path, monkeypatch):
    script = pathlib.Path(__file__).parent.parent / "skills/sole-search/scripts/gov24_crawl.py"
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    p = subprocess.run([sys.executable, str(script), "list", "-o",
                        str(tmp_path / "out.jsonl")],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 4
    assert "INACTIVE" in p.stderr and "미활성" in p.stderr


def test_merge_detail_roundtrip(tmp_path):
    p = tmp_path / "gov24.jsonl"
    r = g.to_record(V3_ROW)
    p.write_text(json.dumps(r, ensure_ascii=False) + "\n")
    ok = g.merge_detail(str(p), "SVC000012345", "h1", {"docs": "신분증"})
    assert ok
    out = json.loads(p.read_text())
    assert out["content_hash"] == "h1" and out["raw"]["docs"] == "신분증"
    assert g.merge_detail(str(p), "SVC-none", "h", {}) is False
