"""가독성 참고지표 (피드백 #6) — 오토파일럿 자동수정 결과의 부가 지표.

⚠ 이것은 '마케팅 효과 예측'이 아니라 **결정적 가독성 참고지표**다.
준법 통과만 추구하면 문장이 경직·과밀해지는 부작용을 작성자가 인지하도록
'문장 길이'와 '전문용어 밀도' 두 객관적 신호만으로 0~100 점을 계산해 1회 보조 표시한다.
준법 점수(rule 권위)와 혼동하지 않도록 명칭·표기를 '참고지표'로 한정한다.

근거(설정값 사유):
· 평균 문장 길이 40자 — 국내 금융 광고 카피 권장 한 문장 길이(읽기 부담 임계). 초과분에 비례 감점.
· 전문용어 — 소비자가 사전 지식 없이 이해하기 어려운 금융 용어. 등장당 4점 감점(밀도 신호).
두 신호 모두 '낮을수록 쉬움'이며, 가중치는 데모 가독성 직관에 맞춰 보수적으로 잡았다.
"""
from __future__ import annotations

import re

# 소비자가 사전 지식 없이는 오해하기 쉬운 금융 전문용어 (가독성 부담 신호)
JARGON_TERMS = [
    "세전", "세후", "원천징수", "비과세", "과세이연",
    "우대금리", "기본금리", "가산금리", "변동금리", "고정금리", "연복리", "복리", "단리",
    "중도해지", "약정이율", "만기", "거치식", "적립식", "우대조건", "예금자보호",
]

# 감점 가중치 (모듈 상단 사유 참조)
_IDEAL_SENTENCE_LEN = 40
_LEN_WEIGHT = 1.2          # 평균 문장 길이 1자 초과당 감점
_LEN_CAP = 40             # 길이 감점 상한
_JARGON_WEIGHT = 4        # 전문용어 1개당 감점
_JARGON_CAP = 32         # 용어 감점 상한
_FLOOR = 10              # 최저 점수 (지표는 0점까지 떨어뜨리지 않음)

_SENTENCE_SPLIT = re.compile(r"[.!?\n。]+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]


def score(text: str) -> dict:
    """텍스트 → 가독성 참고지표 dict (결정적). 준법 점수와 별개의 보조 신호."""
    sentences = _sentences(text)
    if not sentences:
        return {"score": None, "label": "—", "avg_sentence_len": 0,
                "long_sentences": 0, "jargon_count": 0, "jargon_terms": [],
                "note": "본문이 없어 가독성 참고지표를 계산할 수 없습니다."}

    lengths = [len(s) for s in sentences]
    avg_len = sum(lengths) / len(lengths)
    long_sentences = sum(1 for n in lengths if n > _IDEAL_SENTENCE_LEN + 20)

    found_terms = sorted({t for t in JARGON_TERMS if t in text})
    jargon_count = sum(text.count(t) for t in found_terms)

    len_penalty = min(max(avg_len - _IDEAL_SENTENCE_LEN, 0) * _LEN_WEIGHT, _LEN_CAP)
    jargon_penalty = min(jargon_count * _JARGON_WEIGHT, _JARGON_CAP)
    pts = max(round(100 - len_penalty - jargon_penalty), _FLOOR)

    label = "쉬움" if pts >= 80 else ("보통" if pts >= 60 else "어려움")
    return {
        "score": pts,
        "label": label,
        "avg_sentence_len": round(avg_len, 1),
        "long_sentences": long_sentences,
        "jargon_count": jargon_count,
        "jargon_terms": found_terms,
        "note": ("참고지표 — 준법 점수와 별개의 가독성 신호입니다. "
                 "문장 길이·전문용어 밀도만 반영하며 마케팅 효과를 예측하지 않습니다."),
    }
