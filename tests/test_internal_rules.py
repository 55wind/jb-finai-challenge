"""내부 심의기준(내규) — 자연어 지침 → 룰 변환 + 법규와 동시 적용 테스트."""
import pytest

from app.pipeline import internal_rules, rules_engine, orchestrator, llm_client


def test_rule_preview_matches_and_no_overdetect():
    """B-2 룰 테스트·미리보기 — 룰을 초안에 돌려 과탐/미탐 사전 확인."""
    rule = internal_rules.normalize([{"name": "x", "kind": "forbidden",
        "patterns": [r"업계\s*최초"], "severity": "medium", "message": "m"}])[0]
    hit = rules_engine._eval_rule(rule, "저희는 업계 최초입니다", "deposit", "ko", "internal")
    assert hit and "최초" in hit["matched_text"]
    miss = rules_engine._eval_rule(rule, "평범한 정기예금 광고입니다", "deposit", "ko", "internal")
    assert miss is None   # 정상 광고엔 과탐 없음


@pytest.fixture(autouse=True)
def force_fallback(monkeypatch):
    async def _no(force_check=False):
        return False
    monkeypatch.setattr(llm_client, "is_available", _no)


def test_fallback_extracts_forbidden_rule():
    rules = internal_rules.extract_fallback("광고에 '업계 최초' 표현 금지")
    assert rules and rules[0]["kind"] == "forbidden"
    assert rules[0]["category"] == "internal" and rules[0]["basis"] == "INTERNAL"


def test_fallback_extracts_required_rule():
    rules = internal_rules.extract_fallback("모든 예금 광고에 '영업점 문의' 안내 필수")
    assert rules and rules[0]["kind"] == "required"


def test_normalize_drops_invalid_regex():
    out = internal_rules.normalize([
        {"name": "bad", "kind": "forbidden", "patterns": ["(("], "severity": "high"},
        {"name": "ok", "kind": "forbidden", "patterns": [r"업계\s*최초"], "severity": "medium"},
    ])
    assert len(out) == 1 and out[0]["name"] == "ok"


def test_normalize_defaults_all_types():
    out = internal_rules.normalize([{"name": "x", "kind": "forbidden", "patterns": ["테스트"]}])
    assert set(out[0]["types"]) == {"deposit", "investment", "loan"}


def test_run_rules_merges_internal_with_base():
    internal = internal_rules.normalize([{
        "name": "내규-최초금지", "kind": "forbidden", "patterns": [r"업계\s*최초"],
        "severity": "medium", "message": "내규: 업계 최초 표현 금지", "types": ["deposit"]}])
    findings = rules_engine.run_rules("저희는 업계 최초 안심예금입니다", "deposit", "ko",
                                      extra_rules=internal)
    internal_hits = [f for f in findings if f.get("source") == "internal"]
    assert internal_hits and "최초" in (internal_hits[0]["matched_text"] or "")


def test_base_findings_tagged_source_rule():
    findings = rules_engine.run_rules("확정 연 5% 원금 보장", "deposit", "ko")
    assert findings and all(f.get("source") == "rule" for f in findings)


@pytest.mark.anyio
async def test_review_applies_internal_via_loader(monkeypatch):
    internal = internal_rules.normalize([{
        "name": "내규-최초금지", "kind": "forbidden", "patterns": [r"업계\s*최초"],
        "severity": "high", "message": "내규: 업계 최초 표현 금지"}])
    monkeypatch.setattr(orchestrator, "_internal_rules_loader", lambda: internal)
    rep = await orchestrator.run_review("업계 최초 안심예금 가입하세요", "deposit")
    assert any(f.get("source") == "internal" for f in rep["rule_findings"])
