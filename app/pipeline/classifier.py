"""① 콘텐츠 유형 분류기 (F1) — 예금/투자/대출 키워드 기반 결정적 분류."""
from __future__ import annotations

import re

TYPE_LABELS = {"deposit": "예금·적금", "investment": "투자(펀드)", "loan": "대출"}

_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "deposit": [
        (r"예금|적금|예치|만기|이자율|예금자\s*보호", 2),
        (r"(?i)savings|deposit|interest\s+rate", 2),
        (r"정기|입출금|세전|세후", 1),
    ],
    "investment": [
        (r"펀드|투자|수익률|운용|주식|채권|ETF|집합투자", 2),
        (r"(?i)fund|invest|portfolio|returns?", 2),
        (r"원금\s*손실|위험등급", 1),
    ],
    "loan": [
        (r"대출|융자|한도|상환|금리\s*인하|연체", 2),
        (r"(?i)loan|credit|borrow|repay", 2),
        (r"승인|신용\s*(?:점수|등급)|중도상환", 1),
    ],
}


def classify(text: str) -> dict:
    """초안 텍스트 → {content_type, confidence, scores}."""
    scores = {t: 0 for t in _KEYWORDS}
    for ctype, pats in _KEYWORDS.items():
        for pat, weight in pats:
            scores[ctype] += weight * len(re.findall(pat, text))
    total = sum(scores.values())
    if total == 0:
        return {"content_type": "deposit", "confidence": 0.0, "scores": scores}
    best = max(scores, key=lambda t: scores[t])
    return {"content_type": best, "confidence": round(scores[best] / total, 2), "scores": scores}
