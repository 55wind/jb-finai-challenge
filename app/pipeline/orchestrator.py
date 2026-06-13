"""Orchestrator — 명시적 파이썬 파이프라인 (설계 문서 §5·§6).

①유형분류 → (②RAG ∥ ③룰엔진) → (④LLM심의 ∥ ⑤오인시뮬레이터) → ⑥리포트 종합
"""
from __future__ import annotations

import asyncio

from . import llm_reviewer, multilingual, remediator, report, simulator
from .classifier import classify
from .retriever import retrieve
from .rules_engine import run_rules

MIN_TEXT_LEN = 8
AUTOPILOT_MAX_ITER = 4

# 내부 심의기준(내규) 로더 — 앱 기동 시 store에서 활성 내규를 읽도록 주입(main.py).
# 기본은 빈 리스트라 파이프라인이 저장소와 분리되고 테스트가 결정적으로 유지된다.
_internal_rules_loader = lambda: []  # noqa: E731


def set_internal_rules_loader(fn) -> None:
    global _internal_rules_loader
    _internal_rules_loader = fn


async def run_review(text: str, content_type: str | None = None, language: str = "ko",
                     product_facts: str = "") -> dict:
    text = (text or "").strip()
    if len(text) < MIN_TEXT_LEN:
        return {"skipped": True,
                "reason": f"검사하기에 너무 짧은 입력입니다 ({MIN_TEXT_LEN}자 이상 필요)."}

    # ① 유형 분류 (수동 지정 시 분류기는 참고 정보로만)
    classification = classify(text)
    ctype = content_type or classification["content_type"]

    # 내규(내부 심의기준) — 법규 룰과 함께 적용
    internal = _internal_rules_loader() or None

    # ②③ 병렬: 규제 근거 검색 + 룰엔진(법규 + 내규)
    retrieval, rule_findings = await asyncio.gather(
        asyncio.to_thread(retrieve, text, ctype),
        asyncio.to_thread(run_rules, text, ctype, language, internal),
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


def _rule_fix_changes(rule_findings: list[dict]) -> list[dict]:
    """결정적 룰 치환·고지추가를 데모용 변경내역으로 변환."""
    out = []
    for f in rule_findings:
        fix = f.get("fix")
        if not fix:
            continue
        if fix.get("type") == "replace":
            out.append({"before": fix.get("original", ""), "after": fix.get("replacement", ""),
                        "basis_id": f.get("basis_id"), "rationale": f.get("message", ""), "engine": "rule"})
        elif fix.get("type") == "append":
            out.append({"before": "(고지 없음)", "after": fix.get("text", ""),
                        "basis_id": f.get("basis_id"), "rationale": f.get("message", ""), "engine": "rule"})
    return out


def _summary(report_: dict, text: str) -> dict:
    return {"score": report_["score"], "grade": report_["grade"],
            "grade_label": report_["grade_label"], "grade_emoji": report_["grade_emoji"],
            "text": text}


async def autopilot(text: str, content_type: str | None = None, language: str = "ko",
                    product_facts: str = "", max_iter: int = AUTOPILOT_MAX_ITER) -> dict:
    """준법 오토파일럿 — 심의→고쳐쓰기→재심의를 통과/종료조건까지 자율 반복 (설계 §4).

    합격 판정은 결정적 룰엔진(run_review의 grade)만 — LLM이 통과를 위장할 수 없음.
    """
    current = (text or "").strip()
    iterations: list[dict] = []
    converged = False
    stop_reason = "max_iter"
    prev_score: int | None = None

    for i in range(max_iter):
        report_ = await run_review(current, content_type, language, product_facts)
        ctype = report_["content_type"]
        score = report_["score"]

        # 발산 방지: 직전보다 나빠지면 이 회차를 버리고 직전 결과 유지 후 종료
        if prev_score is not None and score < prev_score:
            stop_reason = "regressed"
            break

        iterations.append({"iter": i, "draft": current, "report": report_,
                           "score": score, "grade": report_["grade"], "changes": []})

        if report_["grade"] == "pass":          # 종료조건 — 목표 달성
            converged = True
            stop_reason = "passed"
            break
        if prev_score is not None and score == prev_score:  # 정체 — 진전 없음
            stop_reason = "plateau"
            break
        prev_score = score

        # ── 행동: (a) 결정적 룰 치환 먼저 → (b) 잔여 비정형 위반만 LLM 재작성 ──
        det_fixes = [f["fix"] for f in report_["rule_findings"] if f.get("fix")]
        fixed = apply_fixes(current, det_fixes)
        residual = [f for f in report_["rule_findings"] if not f.get("fix")] + report_.get("llm_issues", [])
        rem = await remediator.remediate(fixed, residual, report_["retrieval"], ctype)

        iterations[-1]["changes"] = _rule_fix_changes(report_["rule_findings"]) + rem["changes"]

        nxt = rem["text"].strip()
        if nxt == current:                       # 텍스트 불변 — 더 개선 불가
            stop_reason = "no_change"
            break
        current = nxt

    initial = _summary(iterations[0]["report"], iterations[0]["draft"])
    final = _summary(iterations[-1]["report"], iterations[-1]["draft"])
    return {"iterations": iterations, "initial": initial, "final": final,
            "converged": converged, "stop_reason": stop_reason,
            "content_type": iterations[-1]["report"]["content_type"], "language": language}


async def translate_and_rereview(text: str, content_type: str, target_lang: str = "en",
                                 product_facts: str = "") -> dict:
    """F10 — 타깃언어 생성 + 동일 파이프라인 재심의."""
    translated = await multilingual.translate(text, target_lang)
    rereview = await run_review(translated["text"], content_type,
                                language=target_lang, product_facts=product_facts)
    return {"translation": translated["text"], "engine": translated["engine"],
            "target_lang": target_lang, "report": rereview}
