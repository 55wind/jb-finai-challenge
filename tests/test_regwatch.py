"""규제 자동 추적 + 영향분석 + 룰 제안 테스트 (폴백 모드)."""
import pytest

from app.pipeline import llm_client, regwatch


@pytest.fixture(autouse=True)
def force_fallback(monkeypatch):
    async def _no(force_check=False):
        return False
    monkeypatch.setattr(llm_client, "is_available", _no)


@pytest.mark.anyio
async def test_scan_detects_changes_and_proposes_rules():
    changes = await regwatch.scan(lambda types: 3)
    assert changes, "피드에서 변경이 감지되어야 함"
    assert all(c["proposed_rules"] for c in changes), "각 변경은 제안 룰을 가져야 함"


@pytest.mark.anyio
async def test_proposed_rule_cites_the_regulation():
    changes = await regwatch.scan(lambda types: 0)
    new = [c for c in changes if c["status"] == "신규"]
    assert new, "신규 규제가 감지되어야 함"
    r = new[0]["proposed_rules"][0]
    assert r["basis"] == new[0]["regulation"]["id"], "제안 룰은 해당 규제를 근거로 인용"
    assert r["category"] == "regulation"


@pytest.mark.anyio
async def test_impact_analysis_counts_affected():
    changes = await regwatch.scan(lambda types: 7)
    assert any(c["affected_count"] == 7 for c in changes), "영향분석 건수가 반영되어야 함"
