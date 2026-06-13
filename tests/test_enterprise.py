"""엔터프라이즈 연동 — 배포(F15)·상품DB(F16)·다국어 신뢰도 방어 테스트."""
import pytest

from app.pipeline import distribution, llm_client, orchestrator, product_db


@pytest.fixture(autouse=True)
def force_fallback(monkeypatch):
    async def _no(force_check=False):
        return False
    monkeypatch.setattr(llm_client, "is_available", _no)


def test_distribution_dispatch_filters_invalid_channels():
    r = distribution.dispatch(["push", "sms", "bogus"], "제목", "본문")
    assert [x["channel"] for x in r] == ["push", "sms"]
    assert all(x["status"] == "sent" for x in r)


def test_product_db_lookup():
    p = product_db.get("JB-DEP-001")
    assert p and p["content_type"] == "deposit" and "예금자보호" in p["facts"]
    assert product_db.get("없는코드") is None


@pytest.mark.anyio
async def test_low_confidence_language_flag():
    rep = await orchestrator.run_review("Đây là tiền gửi đảm bảo 5%/năm.", "deposit", language="vi")
    assert rep["language_confidence"] == "low"
    assert "베타" in rep["language_note"]


@pytest.mark.anyio
async def test_high_confidence_for_korean():
    rep = await orchestrator.run_review("확정 연 5% 원금 보장 예금", "deposit", language="ko")
    assert rep["language_confidence"] == "high"
    assert "language_note" not in rep
