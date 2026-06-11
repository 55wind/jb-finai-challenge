"""⑥ 리포트 종합기 (F6) — 룰·LLM·시뮬레이터 결과를 통합 리스크 리포트 + 준법점수로."""
from __future__ import annotations

from .classifier import TYPE_LABELS
from .retriever import get_article

_RULE_PENALTY = {"high": 12, "medium": 4, "low": 1}
_LLM_PENALTY = {"high": 5, "medium": 2, "low": 1}
_SIM_PENALTY = {"high": 4, "medium": 2}
_SIM_CAP = 12

GRADE_LABEL = {"pass": "통과", "caution": "주의", "danger": "위험"}
GRADE_EMOJI = {"pass": "🟢", "caution": "🟡", "danger": "🔴"}


def _citation(basis_id: str | None) -> dict | None:
    if not basis_id:
        return None
    a = get_article(basis_id)
    if not a:
        return None
    return {"id": a["id"], "law": a["law"], "article": a["article"],
            "title": a["title"], "source_url": a["source_url"]}


def compose(text: str, content_type: str, language: str, classification: dict,
            retrieval: dict, rule_findings: list[dict], llm_review: dict, simulation: dict) -> dict:
    # LLM 고유 지적: 룰엔진과 같은 근거+문구 중복은 제외
    rule_keys = {(f["basis_id"], f["matched_text"]) for f in rule_findings}
    llm_only = [
        i for i in llm_review["issues"]
        if i.get("source") == "llm" and (i.get("basis_id"), i.get("quote") or None) not in rule_keys
    ]

    score = 100
    for f in rule_findings:
        score -= _RULE_PENALTY.get(f["severity"], 2)
    for i in llm_only:
        score -= _LLM_PENALTY.get(i.get("risk", "medium"), 2)
    sim_penalty = sum(
        _SIM_PENALTY.get(m["risk"], 2)
        for p in simulation["personas"] for m in p["misunderstandings"]
    )
    score -= min(sim_penalty, _SIM_CAP)
    score = max(score, 5)

    n_high = sum(1 for f in rule_findings if f["severity"] == "high") \
        + sum(1 for i in llm_only if i.get("risk") == "high")
    n_medium = sum(1 for f in rule_findings if f["severity"] == "medium") \
        + sum(1 for i in llm_only if i.get("risk") == "medium")

    if score >= 85 and n_high == 0:
        grade = "pass"
    elif score < 60 or (n_high >= 1 and score < 75):
        grade = "danger"
    else:
        grade = "caution"

    # 에디터 하이라이트: 룰 span + LLM quote 위치 + 오인 유발 문구
    highlights = []
    for f in rule_findings:
        for s in f["spans"]:
            highlights.append({**s, "severity": f["severity"], "rule_id": f["rule_id"]})
    for i in llm_only:
        q = i.get("quote")
        if q and q in text:
            start = text.index(q)
            highlights.append({"start": start, "end": start + len(q),
                               "text": q, "severity": i.get("risk", "medium"), "rule_id": "LLM"})
    highlights.sort(key=lambda h: (h["start"], -h["end"]))

    findings_out = [{**f, "citation": _citation(f["basis_id"])} for f in rule_findings]
    llm_out = [{**i, "citation": _citation(i.get("basis_id"))} for i in llm_only]
    for p in simulation["personas"]:
        for m in p["misunderstandings"]:
            m["citation"] = _citation(m.get("basis_id"))

    return {
        "score": score,
        "grade": grade,
        "grade_label": GRADE_LABEL[grade],
        "grade_emoji": GRADE_EMOJI[grade],
        "counts": {"high": n_high, "medium": n_medium,
                   "misunderstandings": simulation["total_misunderstandings"]},
        "content_type": content_type,
        "content_type_label": TYPE_LABELS.get(content_type, content_type),
        "language": language,
        "classification": classification,
        "rule_findings": findings_out,
        "llm_issues": llm_out,
        "llm_overall_comment": llm_review.get("overall_comment", ""),
        "review_engine": llm_review.get("engine", ""),
        "simulation": simulation,
        "retrieval": {
            "backend": retrieval["backend"],
            "sufficient": retrieval["sufficient"],
            "articles": retrieval["articles"],
        },
        "highlights": highlights,
        "text": text,
    }
