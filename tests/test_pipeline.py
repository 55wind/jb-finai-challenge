"""통합 시나리오 테스트 — 데모 플로우 end-to-end (LLM 폴백 모드 기준)."""
import json
from pathlib import Path

import pytest

from app.pipeline import llm_client, orchestrator
from app.pipeline.retriever import retrieve

FIXTURES = {
    f["id"]: f
    for f in json.loads(
        (Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures.json").read_text(encoding="utf-8")
    )
}


@pytest.fixture(autouse=True)
def force_fallback(monkeypatch):
    """테스트는 결정적이어야 하므로 LLM을 폴백 모드로 고정."""
    async def _no(force_check=False):
        return False
    monkeypatch.setattr(llm_client, "is_available", _no)


@pytest.mark.parametrize("fx_id", list(FIXTURES), ids=list(FIXTURES))
@pytest.mark.anyio
async def test_fixture_grades(fx_id):
    fx = FIXTURES[fx_id]
    rep = await orchestrator.run_review(fx["text"], fx["content_type"],
                                        fx["language"], fx["product_facts"])
    assert rep["grade"] == fx["expected_grade"], f"score={rep['score']} findings={[f['rule_id'] for f in rep['rule_findings']]}"


@pytest.mark.anyio
async def test_demo_flow_fix_application_raises_score():
    """데모 시나리오: 위반 광고 → 수정안 전체 적용 → 점수 상승·통과/주의 전환."""
    fx = FIXTURES["FX-01"]
    before = await orchestrator.run_review(fx["text"], fx["content_type"],
                                           product_facts=fx["product_facts"])
    assert before["grade"] == "danger"

    fixes = [f["fix"] for f in before["rule_findings"] if f["fix"]]
    fixed_text = orchestrator.apply_fixes(fx["text"], fixes)
    after = await orchestrator.run_review(fixed_text, fx["content_type"],
                                          product_facts=fx["product_facts"])
    assert after["score"] > before["score"] + 20
    assert after["counts"]["high"] == 0


@pytest.mark.anyio
async def test_simulator_flags_senior_guarantee_misreading():
    fx = FIXTURES["FX-01"]
    rep = await orchestrator.run_review(fx["text"], fx["content_type"],
                                        product_facts=fx["product_facts"])
    sim = rep["simulation"]
    assert sim["misreading_risk"] == "high"
    senior = next(p for p in sim["personas"] if p["persona_id"] == "senior")
    assert senior["misunderstandings"], "72세 페르소나는 원금보장 오해를 가져야 함"
    assert senior["misunderstandings"][0]["trigger_phrase"] == "원금 보장"


@pytest.mark.anyio
async def test_multilingual_naive_translation_caught_by_rereview():
    """승인본 직역(폴백)에 'Guaranteed'가 생기면 영문 재심의가 잡아내야 함 (§10.3)."""
    result = await orchestrator.translate_and_rereview(
        "확정 연 5%! 안심예금으로 노후를 준비하세요.", "deposit", "en")
    assert "guaranteed" in result["translation"].lower()
    flagged = [f["rule_id"] for f in result["report"]["rule_findings"]]
    assert "R-101" in flagged and "R-102" in flagged


def test_retrieval_cites_only_corpus_articles():
    out = retrieve("확정 연 5% 원금 보장 예금", "deposit")
    assert out["sufficient"]
    ids = {a["id"] for a in out["articles"]}
    assert ids, "근거 조항이 검색되어야 함"
    # 단정 표현 질의에는 금소법 단정적 판단 조항이 상위에 와야 함
    assert any(a["id"].startswith("FCPA") or a["id"].startswith("ADREV") for a in out["articles"])


def test_retrieval_expands_cross_references():
    """법률 교차참조 — 검색된 조항이 참조하는 조항이 맥락으로 확장되어야 함."""
    out = retrieve("확정 연 5% 원금 보장 예금", "deposit")
    assert any(a.get("linked_from") for a in out["articles"]), "참조 그래프 확장이 일어나야 함"


@pytest.mark.anyio
async def test_short_input_skipped():
    rep = await orchestrator.run_review("짧")          # 1자 미만만 스킵 (MIN_TEXT_LEN=2)
    assert rep["skipped"] is True


@pytest.mark.anyio
async def test_short_risky_phrase_reviewed():
    rep = await orchestrator.run_review("원금 보장", "deposit")   # 5자 — 이제 검사됨
    assert rep["skipped"] is False
    assert any(f["rule_id"] == "R-002" for f in rep["rule_findings"])
