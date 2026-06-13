"""준법 오토파일럿 (자율 개선 루프) 테스트 — 폴백 모드 기준(결정적).

설계: docs/superpowers/specs/2026-06-13-compliance-autopilot-design.html §11
"""
import json
from pathlib import Path

import pytest

from app.pipeline import llm_client, orchestrator

FIXTURES = {
    f["id"]: f
    for f in json.loads(
        (Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures.json").read_text(encoding="utf-8")
    )
}


@pytest.fixture(autouse=True)
def force_fallback(monkeypatch):
    """결정성을 위해 LLM을 폴백 모드로 고정 — 룰엔진 자동치환만으로 루프 검증."""
    async def _no(force_check=False):
        return False
    monkeypatch.setattr(llm_client, "is_available", _no)


@pytest.mark.anyio
async def test_autopilot_improves_danger_fixture():
    """위반 초안 → 자율 개선으로 점수 상승, 회차 단조 비감소."""
    fx = FIXTURES["FX-01"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    its = res["iterations"]
    assert its, "최소 1회차는 있어야 함"
    assert res["final"]["score"] > res["initial"]["score"], "점수가 개선되어야 함"
    scores = [it["score"] for it in its]
    assert scores == sorted(scores), f"회차 점수는 단조 비감소여야 함: {scores}"


@pytest.mark.anyio
async def test_autopilot_terminates_within_max_iter():
    """어떤 입력도 max_iter를 넘지 않고 종료."""
    for fid in ("FX-01", "FX-02", "FX-03"):
        fx = FIXTURES[fid]
        res = await orchestrator.autopilot(fx["text"], fx["content_type"],
                                           product_facts=fx["product_facts"], max_iter=3)
        assert len(res["iterations"]) <= 3, f"{fid}: max_iter 초과"
        assert res["stop_reason"] in {"passed", "plateau", "no_change", "regressed", "max_iter"}


@pytest.mark.anyio
async def test_autopilot_converged_only_when_rule_engine_passes():
    """합격 무결성 — converged는 룰엔진 grade==pass일 때만(환각 합격 불가)."""
    fx = FIXTURES["FX-01"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    if res["converged"]:
        assert res["final"]["grade"] == "pass"


@pytest.mark.anyio
async def test_autopilot_clean_fixture_converges_immediately():
    """이미 준법인 초안은 1회차에서 즉시 수렴(통과)."""
    fx = FIXTURES["FX-04"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    assert res["converged"] is True
    assert res["final"]["grade"] == "pass"
    assert len(res["iterations"]) == 1


def test_dedup_disclosures_keeps_one():
    txt = ("연 5% 안심예금.\n"
           "※ 이 예금은 예금보험공사가 1인당 최고 5천만원까지 보호합니다.\n"
           "※ 이 예금은 예금자보호법에 따라 예금보험공사가 1인당(원금과 이자를 합하여) 최고 5천만원까지 보호합니다.")
    out = orchestrator._dedup_disclosures(txt)
    assert out.count("5천만원") == 1, "예금자보호 고지는 하나만 남아야 함"
    assert "예금자보호법에 따라" in out, "더 완전한 고지가 유지되어야 함"


@pytest.mark.anyio
async def test_autopilot_no_duplicate_disclosure():
    fx = FIXTURES["FX-01"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    final = res["final"]["text"]
    # 예금자보호 고지문(예금보험공사+5천만원)이 두 번 이상 들어가면 안 됨
    assert final.count("예금보험공사") <= 1, f"중복 고지: {final}"


@pytest.mark.anyio
async def test_autopilot_trace_has_changes_and_basis():
    """회차 trace는 무엇을·왜 고쳤는지(근거) 담아야 함 — 설명가능성."""
    fx = FIXTURES["FX-01"]
    res = await orchestrator.autopilot(fx["text"], fx["content_type"], product_facts=fx["product_facts"])
    first = res["iterations"][0]
    assert first["changes"], "첫 회차는 수정 내역이 있어야 함"
    assert any(c.get("basis_id") for c in first["changes"]), "수정에는 규제 근거가 연결돼야 함"
