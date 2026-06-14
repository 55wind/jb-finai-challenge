"""⑤ ★소비자 오인 시뮬레이터 (F5) — 헤드라인 기능.

페르소나별로 광고를 1인칭으로 읽고 ①이해 ②행동 ③기대/오해를 생성한 뒤,
오해 판정기(judge)가 상품 실제 조건 + 규제상 '암시 금지' 항목과 대조해
위험 오해를 플래그하고 유발 문구를 역추적한다.

LLM 불가 시: 룰엔진 카테고리 → 페르소나 취약점 매핑 기반 결정적 시뮬레이션 폴백.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import llm_client

_PERSONAS_PATH = Path(__file__).resolve().parent.parent / "data" / "personas.json"
_personas_cache: list[dict] | None = None

# 오해 카테고리 → 금소법 근거 매핑 (judge가 인용)
_CATEGORY_BASIS = {
    "guarantee": "FCPA-22-3",
    "assertive": "FCPA-22-4",
    "rate": "ADREV-RATE",
    "notice": "FCPA-22-1",
    "superlative": "FAIRAD-3",
}

_RISK_ORDER = {"high": 2, "medium": 1, "none": 0}


def load_personas() -> list[dict]:
    global _personas_cache
    if _personas_cache is None:
        with open(_PERSONAS_PATH, encoding="utf-8") as f:
            _personas_cache = json.load(f)
    return _personas_cache


def _trigger_phrase(category: str, rule_findings: list[dict]) -> str | None:
    for f in rule_findings:
        if f["category"] == category and f["matched_text"]:
            return f["matched_text"]
    for f in rule_findings:
        if f["category"] == category:
            return "(고지 문구 자체가 없음)"
    return None


def _fallback_persona(persona: dict, rule_findings: list[dict]) -> dict:
    """룰엔진 결과 기반 결정적 시뮬레이션: 페르소나 취약 카테고리 중 가장 위험한 것 선택."""
    hit_categories = {f["category"] for f in rule_findings}
    candidates = [c for c in persona["vulnerabilities"] if c in hit_categories]
    template_key = candidates[0] if candidates else "safe"
    # 취약점 외 카테고리라도 페르소나 폴백 템플릿이 있으면 사용
    if template_key == "safe":
        extra = [c for c in hit_categories if c in persona["fallback"]]
        if extra:
            template_key = extra[0]
    tpl = persona["fallback"].get(template_key, persona["fallback"]["safe"])
    misread = tpl["misunderstanding"]
    return {
        "persona_id": persona["id"],
        "emoji": persona["emoji"],
        "name": persona["name"],
        "understanding": tpl["understanding"],
        "action": tpl["action"],
        "misunderstandings": [] if not misread else [{
            "text": misread,
            "risk": tpl["risk"],
            "trigger_phrase": _trigger_phrase(template_key, rule_findings),
            "basis_id": _CATEGORY_BASIS.get(template_key),
        }],
        "safe": misread is None,
        "engine": "fallback(rule-based)",
    }


# 3 페르소나의 역할극+오해 판정을 단 1콜로 생성 (로컬 7B 큐 적체·레이턴시 방지).
# 각 소비자가 1인칭으로 읽고, 실제 조건·규제상 암시 금지에 어긋나는 '오해'를 스스로 식별한다.
_SYSTEM_MULTI = """당신은 금융소비자 오인 시뮬레이터입니다. 아래 [소비자 프로필] 3인이 각자
자신의 프로필로 광고를 1인칭으로 읽고, 자신이 믿게 된 것 중 ⓐ상품의 실제 조건 또는
ⓑ규제상 암시 금지 항목(원금보장·확정수익·무심사 대출 등)과 어긋나는 '오해'를 스스로 식별합니다.
각 소비자는 프로필의 금융이해도를 벗어난 전문적 해석을 하지 않습니다.
실제 조건과 일치하는 올바른 이해는 misunderstandings에 넣지 마세요. 오해가 없으면 빈 배열.
광고가 외국어면 그 언어를 이해하는 소비자로서 읽되 서술은 한국어로 합니다.
반드시 JSON으로만 답하세요. 스키마:
{"personas": [{"id": "<프로필 id 그대로>", "understanding": "1인칭 이해(2문장 이내)",
  "action": "할 행동(1문장)",
  "misunderstandings": [{"text": "오해 내용", "risk": "high|medium",
    "trigger_phrase": "오해를 유발한 광고 원문 문구", "category": "guarantee|assertive|rate|notice|superlative"}]}]}"""


def _persona_result(persona: dict, pr: dict, text: str) -> dict:
    mis = pr.get("misunderstandings") if isinstance(pr.get("misunderstandings"), list) else []
    cleaned = []
    for m in mis:
        if not isinstance(m, dict) or not m.get("text"):
            continue
        if m.get("trigger_phrase") and m["trigger_phrase"] not in text:
            m["trigger_phrase"] = None
        cleaned.append({
            "text": m["text"],
            "risk": m.get("risk", "medium"),
            "trigger_phrase": m.get("trigger_phrase"),
            "basis_id": _CATEGORY_BASIS.get(m.get("category", ""), "FCPA-22-1"),
        })
    return {
        "persona_id": persona["id"], "emoji": persona["emoji"], "name": persona["name"],
        "understanding": pr.get("understanding", ""), "action": pr.get("action", ""),
        "misunderstandings": cleaned, "safe": len(cleaned) == 0, "engine": "llm",
    }


async def _llm_simulate_all(personas: list[dict], text: str, product_facts: str,
                            rule_findings: list[dict]) -> list[dict]:
    """3 페르소나 반응을 단일 LLM 호출로 생성. 누락·실패한 페르소나는 폴백 템플릿."""
    profiles = "\n".join(f"- id={p['id']} ({p['name']}): {p['profile']}" for p in personas)
    user = (f"[소비자 프로필 3인]\n{profiles}\n\n[광고]\n{text}\n\n"
            f"[상품의 실제 조건] {product_facts or '(미입력 — 규제상 암시 금지 항목 기준으로만 판정)'}")
    out = await llm_client.chat_json(_SYSTEM_MULTI, user)
    by_id = {}
    if isinstance(out, dict) and isinstance(out.get("personas"), list):
        for pr in out["personas"]:
            if isinstance(pr, dict) and pr.get("id") is not None:
                by_id[str(pr["id"])] = pr
    results = []
    for p in personas:
        pr = by_id.get(str(p["id"]))
        if isinstance(pr, dict) and "understanding" in pr:
            results.append(_persona_result(p, pr, text))
        else:
            results.append(_fallback_persona(p, rule_findings))
    return results


async def simulate(text: str, product_facts: str, rule_findings: list[dict],
                   force_fallback: bool = False) -> dict:
    """3 페르소나 → 종합 오인 리스크. force_fallback=True면 LLM 무시(빠른 검사용 결정적 폴백)."""
    personas = load_personas()
    if not force_fallback and await llm_client.is_available():
        results = await _llm_simulate_all(personas, text, product_facts, rule_findings)
    else:
        results = [_fallback_persona(p, rule_findings) for p in personas]

    risks = [m["risk"] for r in results for m in r["misunderstandings"]]
    n_high = sum(1 for r in risks if r == "high")
    level = "high" if n_high >= 2 else ("medium" if risks else "low")
    return {
        "personas": list(results),
        "misreading_risk": level,
        "misreading_risk_label": {"high": "높음", "medium": "중간", "low": "낮음"}[level],
        "total_misunderstandings": len(risks),
        "high_risk_count": n_high,
    }
