import json
from pathlib import Path

import pytest

from app.pipeline.rules_engine import run_rules

FIXTURES = json.loads(
    (Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("fx", FIXTURES, ids=[f["id"] for f in FIXTURES])
def test_fixture_expected_flags(fx):
    """TDD 정답셋: 알려진 위반 입력 → 기대 룰 플래그 (회귀 방지)."""
    findings = run_rules(fx["text"], fx["content_type"], fx["language"])
    assert sorted(f["rule_id"] for f in findings) == sorted(fx["expected_rule_ids"])


def test_forbidden_rule_has_spans_for_highlight():
    findings = run_rules("확정 연 5%! 원금 보장 예금", "deposit")
    r001 = next(f for f in findings if f["rule_id"] == "R-001")
    assert r001["spans"] and r001["spans"][0]["text"] == "확정 연 5%"
    assert r001["fix"]["type"] == "replace"
    assert "5" in r001["fix"]["replacement"]


def test_required_rule_provides_append_fix():
    findings = run_rules("그냥 평범한 예금 광고", "deposit")
    r005 = next(f for f in findings if f["rule_id"] == "R-005")
    assert r005["fix"]["type"] == "append"
    assert "5천만원" in r005["fix"]["text"]


def test_rate_rule_exempt_when_tax_notation_present():
    findings = run_rules("연 3.0%(세전) 정기예금. 예금자보호 안내 포함", "deposit")
    assert all(f["rule_id"] != "R-007" for f in findings)
