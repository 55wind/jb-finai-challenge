"""수정 전/후 비교 뷰(diff) (피드백 #2) — AI가 무엇을 바꿨는지 한눈에.

오토파일럿 초안(수정 전)과 최종본(수정 후)을 어절 단위로 비교해
삭제(빨강)·추가(초록)·유지 세그먼트로 분해한다. 준법감시인·마케터의
'AI 수정 내역 파악'과 감사 추적을 돕는다(결정적, LLM 불필요).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# 공백 토큰을 보존해 비교 후 원래 띄어쓰기를 복원
_TOKEN = re.compile(r"\s+|[^\s]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text or "")


def word_diff(before: str, after: str) -> list[dict]:
    """before→after 어절 단위 diff. [{op: equal|delete|insert, text}] 세그먼트."""
    a, b = _tokens(before), _tokens(after)
    sm = SequenceMatcher(None, a, b, autojunk=False)
    segments: list[dict] = []

    def _emit(op: str, text: str) -> None:
        if not text:
            return
        if segments and segments[-1]["op"] == op:
            segments[-1]["text"] += text
        else:
            segments.append({"op": op, "text": text})

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            _emit("equal", "".join(a[i1:i2]))
        elif tag == "delete":
            _emit("delete", "".join(a[i1:i2]))
        elif tag == "insert":
            _emit("insert", "".join(b[j1:j2]))
        elif tag == "replace":
            _emit("delete", "".join(a[i1:i2]))
            _emit("insert", "".join(b[j1:j2]))
    return segments


def change_stats(before: str, after: str) -> dict:
    """변경 요약 — 삭제/추가 어절 수, 변경 여부."""
    segs = word_diff(before, after)
    deleted = sum(len(_TOKEN.findall(s["text"])) for s in segs if s["op"] == "delete")
    inserted = sum(len(_TOKEN.findall(s["text"])) for s in segs if s["op"] == "insert")
    return {"deleted": deleted, "inserted": inserted, "changed": bool(deleted or inserted)}
