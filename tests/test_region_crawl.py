import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "skills/sole-search/scripts"))
import region_crawl as rc

# ---- 픽스처: 2026-07-20 실제 응답에서 발췌 ----

FANFAN_BIZ_JSON = {
    "list": [
        {"sprtBizCd": "202603030800", "sprtBizNm": "온라인쇼핑몰 판매 지원사업",
         "sprtBizYr": "2026", "sprtBizTyNm": "유통∙판로", "sprtBizTrgtNm": "소상공인",
         "sprtBizCtpvNm": "", "rcritBgngYmd": "2026-03-12", "rcritEndYmd": "2026-04-01"},
        {"sprtBizCd": "202603121702", "sprtBizNm": "소상공인 온라인 홍보 지원",
         "sprtBizYr": "2026", "sprtBizTyNm": "홍보∙마케팅", "sprtBizTrgtNm": "소상공인",
         "sprtBizCtpvNm": "", "rcritBgngYmd": "2026-03-12", "rcritEndYmd": "2099-12-31"},
    ],
    "years": ["2026", "2025"],
}

FANFAN_NTC_HTML = """
<div class="listTable"><ul class="listType">
<li class="noticeImportant"><div class="subject"><span class="badge v11">HOT</span>
<a href="javascript:detailPage('20238');" class="title">
[모집] 2026년 소상공인 온라인쇼핑몰 판매지원 3차 소상공인 모집 공고
</a></div><span class="date">2026-07-20 09:04:01</span><span class="views">63</span></li>
<li><div class="subject">
<a href="javascript:detailPage('20195');" class="title">[모집] 2026년 판판셀러 지원사업 모집 안내</a>
</div><span class="date">2026-07-15 10:00:00</span><span class="views">120</span></li>
</ul></div>
<script>totalRecordCount = "385";</script>
"""

SSB_LIST_HTML = """
<tr><td>166</td>
<td class="t_left"><a href="javascript:bbs.goView('1', '21371')"><span class="ellipsis">2026년 서울시 자영업자 고용보험료 지원사업 공고</span></a></td>
<td>소상공인정책팀</td>
<td>2026-01-05</td>
<td>2</td></tr>
<tr><td>165</td>
<td class="t_left"><a href="javascript:bbs.goView('1', '22680')"><span class="ellipsis">2026년 하반기 위기 소상공인 조기발굴 및 선제지원(Track2) 사업공고</span></a></td>
<td>사업운영팀</td>
<td>2026-06-30</td>
<td>2</td></tr>
<tr><td>165</td>
<td class="t_left"><a href="javascript:bbs.goView('1', '22680')"><span class="ellipsis">2026년 하반기 위기 소상공인 조기발굴 및 선제지원(Track2) 사업공고</span></a></td>
<td>사업운영팀</td>
<td>2026-06-30</td>
<td>2</td></tr>
"""

FANFAN_VIEW_ATTACH = (
    'fn_setViewDownCntAjax("https://viewer.fanfandaero.kr:8443/SynapDocViewServer/job'
    '?fid=1866053_a.pdf&amp;filePath=https://fanfandaero.kr/download.do'
    '?fileName=/gfsdata/imstars/upload/cmmn/20260720/27B9FE48-472F-B05B-B277-6C02ED91CC17.pdf'
    '&amp;convertType=0&amp;fileType=URL","1866053",'
    '"「2026년 소상공인 온라인쇼핑몰 판매지원사업」참여기업 모집공고.pdf","20238","1")'
)

SSB_VIEW_ATTACH = """
<div class="download_detail"><a class="attach_down" href="javascript:common.download(21371,'9a2d29ea-a240-40e0-a7a5-891247065d28')" title="다운로드"><span class="ellipsis">1.+2026년+서울시+자영업자+고용보험료+지원사업+공고.hwp</span><span class="file_down_wrap"></span></a></div>
<div class="download_detail"><a class="attach_down" href="javascript:common.download(21371,'9a2d29ea-a240-40e0-a7a5-891247065d28')" title="다운로드"><span class="ellipsis">1.+2026년+서울시+자영업자+고용보험료+지원사업+공고.hwp</span><span class="file_down_wrap"></span></a></div>
"""


def test_fanfan_biz_parse():
    items = rc.parse_fanfan_biz(FANFAN_BIZ_JSON)
    assert len(items) == 2
    a = items[0]
    assert a["source"] == "fanfandaero" and a["source_id"] == "biz-202603030800"
    assert a["apply_end"] == "2026-04-01" and a["status"] == "마감"
    assert "sprtBizCd=202603030800" in a["canonical_url"]
    assert items[1]["status"] == "접수중"  # 2099 마감
    assert items[1]["tags"] == ["홍보∙마케팅"]


def test_fanfan_ntc_parse():
    items = rc.parse_fanfan_ntc(FANFAN_NTC_HTML)
    assert len(items) == 2
    a = items[0]
    assert a["source_id"] == "ntc-20238"
    assert a["title"].startswith("[모집] 2026년 소상공인 온라인쇼핑몰")
    assert a["status"] == "불명"  # 접수기간 미상 — 상세 확인 대상
    assert a["raw"]["posted"] == "2026-07-20"
    assert rc.fanfan_ntc_total(FANFAN_NTC_HTML) == 385


def test_ssb_parse_dedups_double_markup():
    items = rc.parse_ssb(SSB_LIST_HTML)
    assert len(items) == 2  # 22680 이중 마크업은 1건으로
    a = items[0]
    assert a["source"] == "seoulshinbo" and a["source_id"] == "ntc-21371"
    assert a["title"] == "2026년 서울시 자영업자 고용보험료 지원사업 공고"
    assert a["agency"] == "서울신용보증재단/소상공인정책팀"
    assert a["raw"]["posted"] == "2026-01-05"
    assert a["region_scope"] == "서울"
    assert "/bbs/view/21371.do?mng_cd=STRY9788" in a["canonical_url"]


def test_fanfan_attachments():
    out = rc.fanfan_attachments(FANFAN_VIEW_ATTACH, "https://fanfandaero.kr/x?nttId=20238")
    assert len(out) == 1
    assert out[0]["url"].startswith("https://fanfandaero.kr/download.do?fileName=")
    assert "&amp;" not in out[0]["url"]
    assert out[0]["filename"].endswith("모집공고.pdf")


def test_ssb_attachments_dedup():
    url = "https://www.seoulshinbo.co.kr/wbase/contents/bbs/view/21371.do?mng_cd=STRY9788"
    out = rc.ssb_attachments(SSB_VIEW_ATTACH, url)
    assert len(out) == 1  # serial 중복 제거
    assert out[0]["url"] == ("https://www.seoulshinbo.co.kr/download/21371/"
                             "9a2d29ea-a240-40e0-a7a5-891247065d28.do?mng_cd=STRY9788")
    # '+' 인코딩 복원 포함
    assert out[0]["filename"] == "1. 2026년 서울시 자영업자 고용보험료 지원사업 공고.hwp"


def test_detail_target_dispatch():
    s, sid, cont, fn = rc.detail_target(
        "https://fanfandaero.kr/portal/v2/readUcenterNtcBbsView.do?nttId=20238")
    assert (s, sid) == ("fanfandaero", "ntc-20238") and fn is rc.fanfan_attachments
    s, sid, _, fn = rc.detail_target(
        "https://fanfandaero.kr/portal/v2/preSprtBizPbancDetail.do?sprtBizCd=202603030800")
    assert (s, sid) == ("fanfandaero", "biz-202603030800")
    s, sid, _, fn = rc.detail_target(
        "https://www.seoulshinbo.co.kr/wbase/contents/bbs/view/21371.do?mng_cd=STRY9788")
    assert (s, sid) == ("seoulshinbo", "ntc-21371") and fn is rc.ssb_attachments
    s, sid, _, _ = rc.detail_target("https://example.com/x")
    assert s is None


FANFAN_VIEW_BODY = """
<div class="contents">
 <div class="head"><h3>[모집] 3차 소상공인 모집 공고</h3>
  <ul><li>등록일</li><li>2026-07-20 09:04:01</li><li>조회수</li><li>105</li></ul>
 </div>
 <div class="body"><p>소상공인의 디지털 판로 확대 및 매출활성화를 지원하는
  온라인쇼핑몰 판매지원 사업에 참여할 소상공인을 모집하오니</p></div>
</div>
<div class="nav"><span>다음글</span> [안내] 판판대로 웹서버 버전 업데이트</div>
<div id="footer">푸터메뉴</div>
"""


def test_extract_body_spans_nested_divs():
    # 회귀(2026-07-20 r2 실전): 중첩 div에서 첫 </div>로 잘려 본문이 비던 버그
    text = rc.extract_body(FANFAN_VIEW_BODY, r'<div[^>]+class="[^"]*contents[^"]*"')
    assert "디지털 판로 확대" in text          # 실제 본문 포함
    assert "다음글" not in text and "푸터메뉴" not in text  # 끝 마커에서 절단
    # 조회수 숫자 라인은 해시 안정성 위해 제거
    assert "105" not in text


def test_extract_body_stable_across_view_count():
    t1 = rc.extract_body(FANFAN_VIEW_BODY, r'class="[^"]*contents')
    t2 = rc.extract_body(FANFAN_VIEW_BODY.replace(">105<", ">9999<"),
                         r'class="[^"]*contents')
    assert t1 == t2


def test_merge_detail_roundtrip(tmp_path):
    p = tmp_path / "fanfandaero.jsonl"
    rec = rc.base_record("fanfandaero", "ntc-20238", "u", "t", "a")
    p.write_text(json.dumps(rec, ensure_ascii=False) + "\n")
    ok = rc.merge_detail(str(p), "fanfandaero", "ntc-20238", "h1",
                         [{"url": "u", "filename": "f.pdf"}], complete=False)
    assert ok
    r = json.loads(p.read_text())
    assert r["content_hash"] == "h1" and r["attachments_complete"] is False
    assert rc.merge_detail(str(p), "fanfandaero", "ntc-999", "h", [], True) is False


def test_diff_compat_schema():
    """diff_surveys.load_dir가 요구하는 최소 계약: source, source_id 문자열."""
    rec = rc.base_record("seoulshinbo", "ntc-1", "u", "t", "a")
    assert rec["source"] and rec["source_id"]
    for f in ["title", "status", "apply_start", "apply_end", "agency", "content_hash"]:
        assert f in rec


def test_detail_biz_skipped(tmp_path, capsys):
    # biz 상세는 JS 렌더 — 조용히 잘못된 해시를 만들지 말고 SKIP해야 한다
    import types
    args = types.SimpleNamespace(
        urls=["https://fanfandaero.kr/portal/v2/preSprtBizPbancDetail.do?sprtBizCd=202603121702"],
        output=str(tmp_path), merge_into=None, delay=0.5)
    code = rc.cmd_detail(args)
    err = capsys.readouterr().err
    assert code == 2 and "SKIP biz-202603121702" in err
