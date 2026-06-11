"""Orchestrator — 명시적 파이썬 파이프라인 (설계 문서 §5·§6).

①유형분류 → (②RAG ∥ ③룰엔진) → (④LLM심의 ∥ ⑤오인시뮬레이터) → ⑥리포트 종합
"""
from __future__ import annotations

import asyncio

from . import llm_reviewer, multilingual, report, simulator
from .classifier import classify
from .retriever import retrieve
from .rules_engine import run_rules

MIN_TEXT_LEN = 8


async def run_review(text: str, content_type: str | None = None, language: str = "ko",
                     product_facts: str = "") -> dict:
    text = (text or "").strip()
    if len(text) < MIN_TEXT_LEN:
        return {"skipped": True,
                "reason": f"검사하기에 너무 짧은 입력입니다 ({MIN_TEXT_LEN}자 이상 필요)."}

    # ① 유형 분류 (수동 지정 시 분류기는 참고 정보로만)
    classification = classify(text)
    ctype = content_type or classification["content_type"]

    # ②③ 병렬: 규제 근거 검색 + 룰엔진
    retrieval, rule_findings = await asyncio.gather(
        asyncio.to_thread(retrieve, text, ctype),
        asyncio.to_thread(run_rules, text, ctype, language),
    )

    # ④⑤ 병렬: LLM 심의 + 오인 시뮬레이터
    llm_review, simulation = await asyncio.gather(
        llm_reviewer.review(text, ctype, retrieval, rule_findings),
        simulator.simulate(text, product_facts, rule_findings),
    )

    # ⑥ 리포트 종합
    result = report.compose(text, ctype, language, classification,
                            retrieval, rule_findings, llm_review, simulation)
    result["skipped"] = False
    return result


def apply_fixes(text: str, fixes: list[dict]) -> str:
    """F7 — 수정안 적용: replace는 본문 치환, append는 고지문 말미 추가."""
    appended = []
    for fix in fixes:
        if fix.get("type") == "replace" and fix.get("original"):
            text = text.replace(fix["original"], fix.get("replacement", ""))
        elif fix.get("type") == "append" and fix.get("text"):
            appended.append(fix["text"])
    for note in appended:
        if note not in text:
            text = text.rstrip() + "\n" + note
    return text


async def translate_and_rereview(text: str, content_type: str, target_lang: str = "en",
                                 product_facts: str = "") -> dict:
    """F10 — 타깃언어 생성 + 동일 파이프라인 재심의."""
    translated = await multilingual.translate(text, target_lang)
    rereview = await run_review(translated["text"], content_type,
                                language=target_lang, product_facts=product_facts)
    return {"translation": translated["text"], "engine": translated["engine"],
            "target_lang": target_lang, "report": rereview}
