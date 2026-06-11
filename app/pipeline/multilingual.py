"""다국어 생성 + 재심의 (F10).

승인본(KO) → 타깃언어(EN) 생성 후, 영문 룰셋으로 전체 파이프라인 재심의.
LLM 불가 시: 데모용 구문 사전 직역 폴백 — 직역이 만들어내는 'guaranteed' 같은
보장성 오역을 재심의가 잡아내는 흐름(설계 문서 §10.3)을 그대로 재현한다.
"""
from __future__ import annotations

import re

from . import llm_client

# 폴백 직역 사전 (의도적으로 '순진한' 직역 → 오역 위험 시연)
_NAIVE_PHRASE_MAP = [
    (r"확정\s*연\s*([0-9.]+)\s*%", r"Guaranteed \1% annual rate"),
    (r"최대\s*연\s*([0-9.]+)\s*%", r"up to \1% per year"),
    (r"연\s*([0-9.]+)\s*%", r"\1% per year"),
    (r"\(세전,?\s*변동\s*가능\)", "(before tax, subject to change)"),
    (r"세전", "before tax"),
    (r"원금\s*보장", "principal guaranteed"),
    (r"예금자\s*보호법에\s*따라.*?보호(?:합니다|됩니다)?\.?", "Protected by the Depositor Protection Act up to KRW 50 million per person (KDIC)."),
    (r"우대조건\s*충족\s*시", "if preferential conditions are met"),
    (r"안심\s*(?:정기)?예금", "worry-free savings deposit"),
    (r"정기예금", "time deposit"),
    (r"예금", "deposit"),
    (r"적금", "installment savings"),
    (r"노후를?\s*준비하세요", "prepare for your retirement"),
    (r"지금\s*가입하면", "sign up now and"),
    (r"누구나", "anyone can get"),
    (r"최고\s*금리\s*혜택", "the best rate benefits"),
    (r"기본금리", "base rate"),
    (r"만기\s*전\s*해지\s*시", "in case of early termination,"),
    (r"중도해지이율이?\s*적용됩니다", "an early-termination rate applies"),
    (r"가입\s*전\s*상품설명서를\s*확인하세요", "please read the product description before signing up"),
]

_SYSTEM_TRANSLATE = """You translate Korean financial advertisements into natural English.
Respond ONLY in JSON: {"translation": "..."}.
Translate faithfully — do not add or remove disclosures yourself."""


async def translate(text: str, target_lang: str = "en") -> dict:
    result = await llm_client.chat_json(
        _SYSTEM_TRANSLATE, f"Translate to {target_lang}:\n{text}"
    )
    if isinstance(result, dict) and result.get("translation"):
        return {"text": result["translation"], "engine": "llm"}

    out = text
    for pat, repl in _NAIVE_PHRASE_MAP:
        out = re.sub(pat, repl, out)
    out = re.sub(r"\s+", " ", out).strip()
    return {"text": out, "engine": "fallback(naive-dictionary)"}
