"""attach_extract — 합성 HWPX 성공, unsupported의 .failed.json + stale 보존."""
import json
import zipfile

import pytest


def make_hwpx(path, text="지원대상: 상시근로자 5명 미만 소상공인"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("Contents/section0.xml",
                   f'<hp:p xmlns:hp="urn:hwpx"><hp:t>{text}</hp:t></hp:p>')


def test_synthetic_hwpx_extracts(attach, tmp_path):
    p = tmp_path / "notice.hwpx"
    make_hwpx(p)
    r = attach.extract(str(p))
    assert r["ok"] is True and not r["reason"]
    assert "상시근로자 5명 미만" in r["text"]


def test_hwpx_without_sections_fails(attach, tmp_path):
    p = tmp_path / "empty.hwpx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
    r = attach.extract(str(p))
    assert r["ok"] is False and r["reason"] == "hwpx_no_sections"


def test_unsupported_writes_failed_json_and_preserves_stale(attach, tmp_path,
                                                            monkeypatch, capsys):
    f = tmp_path / "attach.xyz"
    f.write_bytes(b"whatever")
    out = tmp_path / "attach.txt"
    out.write_text("이전 실행의 성공 출력", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["attach_extract.py", str(f), "-o", str(out)])
    with pytest.raises(SystemExit) as e:
        attach.main()
    assert e.value.code == 1
    assert not out.exists()  # 빈/유령 출력 금지 — stale로 이동
    stales = list(tmp_path.glob("attach.txt.stale-*"))
    assert len(stales) == 1
    assert stales[0].read_text(encoding="utf-8") == "이전 실행의 성공 출력"
    failed = json.loads((tmp_path / "attach.txt.failed.json").read_text())
    assert failed == {"ok": False, "reason": "unsupported_extension",
                      "file": str(f)}


def test_missing_file(attach):
    assert attach.extract("/nonexistent/x.pdf")["reason"] == "file_not_found"


# ---- #11 위조 HWPX(구조 마커 없음) 거부 ----
def test_forged_zip_without_hwpx_markers_fails(attach, tmp_path):
    """임의 zip에 Contents/section0.xml만 넣은 위조 첨부는 정품 HWPX로 완전
    추출됐다고 인정하지 않는다(Codex #11)."""
    p = tmp_path / "forged.hwpx"
    with zipfile.ZipFile(p, "w") as z:  # mimetype/version.xml/container 없음
        z.writestr("Contents/section0.xml",
                   '<hp:p xmlns:hp="urn:hwpx"><hp:t>가짜 자격</hp:t></hp:p>')
    r = attach.extract(str(p))
    assert r["ok"] is False and r["reason"] == "hwpx_unverified_container"


def test_bad_mimetype_hwpx_fails(attach, tmp_path):
    p = tmp_path / "bad.hwpx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/zip")  # 잘못된 mimetype
        z.writestr("Contents/section0.xml",
                   '<hp:p xmlns:hp="urn:hwpx"><hp:t>x</hp:t></hp:p>')
    r = attach.extract(str(p))
    assert r["ok"] is False and r["reason"] == "hwpx_bad_mimetype"


# ---- #16 심링크 출력 경로 거부 ----
def test_symlink_output_refused(attach, tmp_path):
    import os
    import subprocess
    import sys
    make_hwpx(tmp_path / "n.hwpx")
    victim = tmp_path / "victim.txt"
    victim.write_text("소중한 원본", encoding="utf-8")
    link = tmp_path / "out.txt"
    os.symlink(victim, link)  # out.txt -> victim.txt (덮어쓰기 유도)
    r = subprocess.run([sys.executable, attach.__file__, str(tmp_path / "n.hwpx"),
                        "-o", str(link)], capture_output=True, text=True)
    assert r.returncode == 1
    assert victim.read_text(encoding="utf-8") == "소중한 원본"  # 원본 무손상
