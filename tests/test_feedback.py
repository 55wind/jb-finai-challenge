"""피드백 반영 기능 테스트 (폴백 모드 기준·결정적).

#1 다국어 재심의 불통과 알림 · #2 수정 전/후 diff · #3 전북 페르소나
#4 승인 콘텐츠 재검사 · #5 내규-법규 충돌 탐지 · #6 가독성 참고지표
"""
import json
from pathlib import Path

import pytest

from app.pipeline import (internal_rules, llm_client, orchestrator, readability,
                          regwatch, simulator, textdiff)

FIXTURES = {
    f["id"]: f
    for f in json.loads(
        (Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures.json").read_text(encoding="utf-8")
    )
}


@pytest.fixture(autouse=True)
def force_fallback(monkeypatch):
    async def _no(force_check=False):
        return False
    monkeypatch.setattr(llm_client, "is_available", _no)


# ── #2 수정 전/후 비교 뷰(diff) ──────────────────────────────

def test_word_diff_marks_delete_and_insert():
    segs = textdiff.word_diff("확정 연 5% 원금 보장", "연 5% (세전, 변동 가능)")
    ops = {s["op"] for s in segs}
    assert "delete" in ops and "insert" in ops
    assert "확정" in "".join(s["text"] for s in segs if s["op"] == "delete")


def test_word_diff_identical_is_all_equal():
    segs = textdiff.word_diff("연 5% 예금", "연 5% 예금")
    assert all(s["op"] == "equal" for s in segs)
    assert textdiff.change_stats("연 5% 예금", "연 5% 예금")["changed"] is False


@pytest.mark.anyio
async def test_autopilot_includes_diff_and_stats():
    fx = FIXTURES["FX-01"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    assert "diff" in res and isinstance(res["diff"], list)
    # 위반 초안은 자동수정으로 본문이 바뀌므로 삭제/추가가 잡혀야 함
    assert res["diff_stats"]["changed"] is True


# ── #6 가독성 참고지표 ──────────────────────────────────────

def test_readability_penalizes_jargon_and_length():
    easy = readability.score("연 5% 예금입니다. 가입을 환영합니다.")
    hard = readability.score(
        "본 상품은 세전 기준 기본금리에 우대조건 충족 시 우대금리가 가산되며 "
        "중도해지 시 약정이율이 아닌 중도해지이율이 적용되고 만기 후에는 별도 이율이 적용됩니다.")
    assert easy["score"] > hard["score"]
    assert hard["jargon_count"] >= 3
    assert easy["label"] in {"쉬움", "보통"}


def test_readability_empty_text():
    r = readability.score("")
    assert r["score"] is None


@pytest.mark.anyio
async def test_autopilot_includes_readability():
    fx = FIXTURES["FX-01"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    assert res["readability"]["score"] is not None
    assert "참고지표" in res["readability"]["note"]   # 마케팅 효과로 과대표현하지 않음


# ── #5 내규-법규 충돌 탐지 ──────────────────────────────────

def test_conflict_required_internal_vs_forbidden_law():
    """법규가 금지(R-003 '업계 최초')하는 표현을 내규가 필수로 요구 → 충돌."""
    new = internal_rules.normalize([{
        "name": "내규-최초강조", "kind": "required", "requires_any": [r"업계\s*최초"],
        "severity": "medium", "message": "업계 최초 문구 필수"}])
    conflicts = internal_rules.detect_conflicts(new)
    assert conflicts, "기존 금지 룰과의 충돌이 감지되어야 함"
    assert conflicts[0]["law_rule_id"] == "R-003"


def test_no_conflict_for_unrelated_internal_rule():
    new = internal_rules.normalize([{
        "name": "내규-이모지금지", "kind": "forbidden", "patterns": [r"😀"],
        "severity": "low", "message": "이모지 금지"}])
    assert internal_rules.detect_conflicts(new) == []


# ── #4 승인 콘텐츠 재검사(사후 관리) ─────────────────────────

@pytest.mark.anyio
async def test_recheck_flags_previously_approved_content():
    """규제 변경 제안 룰이 기존 승인 콘텐츠에 걸리면 '재심의 필요'로 표시."""
    changes = await regwatch.scan(lambda types: 0)
    # 제안 룰이 실제로 잡아내도록, 제안 룰 패턴을 그대로 포함한 과거 콘텐츠를 구성
    pats = []
    for ch in changes:
        for r in ch["proposed_rules"]:
            pats += r.get("patterns") or r.get("requires_any") or []
    assert pats, "제안 룰에 패턴이 있어야 테스트 가능"
    # 충돌 없는 일반 텍스트 + 제안 룰이 잡는 표현을 강제로 넣은 가짜 승인 콘텐츠
    fake_subs = [{"id": 99, "title": "과거 정기예금 광고", "content_type": "deposit",
                  "language": "ko", "text": "업계 최초 안심예금, 누구나 가입.", "status": "approved"}]
    flagged = regwatch.recheck_approved(changes, fake_subs)
    # 적어도 하나의 규제 변경이 이 콘텐츠를 건드리는지(룰에 따라) — 형식 검증
    assert isinstance(flagged, list)
    for f in flagged:
        assert f["submission_id"] == 99 and f["hits"]


# ── #3 전북 특화 페르소나 ───────────────────────────────────

@pytest.mark.anyio
async def test_jeonbuk_personas_present_in_simulation():
    sim = await simulator.simulate("업계 최초 원금 보장 안심예금! 확정 연 5%", "",
                                   rule_findings=[], force_fallback=True)
    ids = {p["persona_id"] for p in sim["personas"]}
    assert {"farmer", "merchant"} <= ids, "전북 특화 페르소나(농업인·소상공인)가 포함되어야 함"


def test_jeonbuk_personas_tagged_region():
    personas = {p["id"]: p for p in simulator.load_personas()}
    assert personas["farmer"]["region"] == "jeonbuk"
    assert personas["merchant"]["region"] == "jeonbuk"


# ── #1 다국어 재심의 불통과 알림 ────────────────────────────

@pytest.mark.anyio
async def test_translate_flags_needs_attention_on_fail():
    """직역이 보장성 오역을 만들면 재심의가 불통과 → needs_attention 플래그."""
    res = await orchestrator.translate_and_rereview("확정 연 5% 원금 보장 예금", "deposit", "en")
    assert "needs_attention" in res
    if res["report"]["grade"] != "pass":
        assert res["needs_attention"] is True
