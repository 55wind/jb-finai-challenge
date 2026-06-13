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


# 역할극 + 오해 판정을 1콜로 병합 (지연 절반). 페르소나가 1인칭으로 읽으면서
# 자신의 믿음 중 실제 조건·규제상 암시 금지에 어긋나는 '오해'를 스스로 식별한다.
_SYSTEM_PERSONA = """당신은 아래 프로필의 실제 한국 금융소비자입니다. 금융 전문가가 아닙니다.
광고가 외국어면 그 언어를 이해하는 소비자로서 읽으세요(서술은 한국어로).
광고를 1인칭으로 읽고, 당신이 믿게 된 것 중 ⓐ상품의 실제 조건 또는
ⓑ규제상 암시 금지 항목(원금보장·확정수익·무심사 대출 등)과 어긋나는 '오해'를 스스로 식별하세요.
실제 조건과 일치하는 올바른 이해는 misunderstandings에 넣지 마세요. 오해가 없으면 빈 배열.
프로필의 금융이해도를 벗어난 전문적 해석을 하지 마세요.
반드시 JSON으로만 답하세요. 스키마:
{"understanding": "광고에서 이해한 내용(1인칭, 2문장 이내)",
 "action": "이 광고를 보고 할 행동(1인칭, 1문장)",
 "misunderstandings": [{"text": "오해 내용", "risk": "high|medium",
   "trigger_phrase": "오해를 유발한 광고 원문 문구", "category": "guarantee|assertive|rate|notice|superlative"}]}"""


async def _llm_persona(persona: dict, text: str, product_facts: str, rule_findings: list[dict]) -> dict:
    user = (f"[당신의 프로필]\n{persona['profile']}\n\n[광고]\n{text}\n\n"
            f"[상품의 실제 조건] {product_facts or '(미입력 — 규제상 암시 금지 항목 기준으로만 판정)'}")
    out = await llm_client.chat_json(_SYSTEM_PERSONA, user)
    if not isinstance(out, dict) or "understanding" not in out:
        return _fallback_persona(persona, rule_findings)

    mis = out.get("misunderstandings") if isinstance(out.get("misunderstandings"), list) else []
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
        "persona_id": persona["id"],
        "emoji": persona["emoji"],
        "name": persona["name"],
        "understanding": out.get("understanding", ""),
        "action": out.get("action", ""),
        "misunderstandings": cleaned,
        "safe": len(cleaned) == 0,
        "engine": "llm",
    }


async def simulate(text: str, product_facts: str, rule_findings: list[dict],
                   force_fallback: bool = False) -> dict:
    """페르소나별 병렬 추론 → 종합 오인 리스크. force_fallback=True면 LLM 무시(빠른 검사용)."""
    personas = load_personas()
    if not force_fallback and await llm_client.is_available():
        results = await asyncio.gather(
            *(_llm_persona(p, text, product_facts, rule_findings) for p in personas)
        )
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
