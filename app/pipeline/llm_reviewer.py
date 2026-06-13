"""④ LLM 심의기 (F4) — RAG 근거 + 룰엔진 결과를 받아 뉘앙스 위반·표현리스크·수정안 도출.

인용 제한: LLM이 조항번호를 창작하지 못하도록 retrieved 코퍼스의 id만 인용 허용 (§15).
LLM 불가 시: 룰엔진 결과를 심의 의견 형태로 결정적 변환 (폴백).
"""
from __future__ import annotations

from . import llm_client
from .classifier import TYPE_LABELS

_SYSTEM = """당신은 한국 금융지주의 준법감시인(컴플라이언스 심의역)입니다.
대고객 광고 초안을 금융소비자보호법 등 제공된 규제 근거에 따라 심의합니다.
광고가 외국어(영어·중국어·베트남어·일본어 등)로 작성된 경우에도 의미를 이해하여 심의하고,
한국 규제 근거로 평가하세요. explanation은 한국어로 작성하고, quote는 원문(외국어) 그대로 인용하세요.
반드시 JSON으로만 답하세요. 스키마:
{"issues": [{"quote": "문제 문구(원문 그대로)", "risk": "high|medium|low",
  "title": "지적 제목", "explanation": "위반가능성·표현리스크 설명(한국어, 2문장 이내)",
  "suggestion": "수정안 문구", "basis_id": "근거 조항 id"}],
 "overall_comment": "총평(2문장 이내)"}
중요: basis_id는 아래 [규제 근거] 목록에 있는 id만 사용하세요. 목록에 없는 조항을 인용하지 마세요.
quote는 반드시 초안 원문에 실제로 존재하는 문구여야 합니다.
초안이 규제를 준수하면 issues를 빈 배열([])로 두세요. 지적할 것이 없으면 억지로 만들지 마세요.
'누락·미표시·부재' 지적은 해당 고지·문구가 초안에 실제로 존재하지 않을 때만 하세요.
초안에 이미 포함된 고지(예: 예금자보호 한도, 기본금리·우대금리 구분, 변동·세전 표기)를 누락으로 지적하지 마세요."""


def _fallback_issues(rule_findings: list[dict]) -> dict:
    issues = []
    for f in rule_findings:
        issues.append({
            "quote": f["matched_text"] or "",
            "risk": f["severity"],
            "title": f"[{f['rule_name']}] " + (f["matched_text"] or "필수 문구 누락"),
            "explanation": f["message"],
            "suggestion": (f["fix"] or {}).get("replacement") or (f["fix"] or {}).get("text") or f["suggestion"],
            "basis_id": f["basis_id"],
            "source": "rule",
        })
    n_high = sum(1 for i in issues if i["risk"] == "high")
    comment = (
        f"룰엔진 기준 위반 {n_high}건을 포함해 총 {len(issues)}건이 지적되었습니다. 수정안 적용 후 재심의를 권장합니다."
        if issues else "룰엔진 기준 지적 사항이 없습니다."
    )
    return {"issues": issues, "overall_comment": comment, "engine": "fallback(rule-based)"}


async def review(text: str, content_type: str, retrieval: dict, rule_findings: list[dict]) -> dict:
    allowed_ids = {a["id"] for a in retrieval["articles"]} | {f["basis_id"] for f in rule_findings}

    basis_block = "\n".join(
        f"- id={a['id']} | {a['law']} {a['article']} | {a['text']}" for a in retrieval["articles"]
    ) or "(검색된 근거 없음 — 근거 불충분 시 무리하게 인용하지 말 것)"
    rules_block = "\n".join(
        f"- {f['rule_id']} {f['rule_name']}: {f['matched_text'] or '누락'} ({f['message']})"
        for f in rule_findings
    ) or "(룰엔진 지적 없음)"

    user = f"""[콘텐츠 유형] {TYPE_LABELS.get(content_type, content_type)}
[광고 초안]
{text}

[규제 근거 (RAG 검색 결과 — 인용은 이 목록의 id로만)]
{basis_block}

[룰엔진 1차 지적]
{rules_block}

위 초안을 심의하세요. 실제 오인을 유발하는 표현이 있을 때만 룰엔진이 놓친 뉘앙스 리스크(맥락상 오인 유발, 조건 축약, 과장 분위기)를 지적하세요.
초안이 규제를 준수하고 필수고지가 이미 포함돼 있으면 issues를 빈 배열([])로 답하세요."""

    result = await llm_client.chat_json(_SYSTEM, user, retries=1)
    if result is None or not isinstance(result, dict) or "issues" not in result:
        return _fallback_issues(rule_findings)

    # 환각 인용 차단: 허용 목록 밖 basis_id 제거, 원문에 없는 quote는 비표시 처리
    issues = []
    for i in result.get("issues", []):
        if not isinstance(i, dict):
            continue
        if i.get("basis_id") not in allowed_ids:
            i["basis_id"] = None
        if i.get("quote") and i["quote"] not in text:
            i["quote"] = ""
        i.setdefault("risk", "medium")
        i["source"] = "llm"
        issues.append(i)
    return {"issues": issues, "overall_comment": result.get("overall_comment", ""), "engine": "llm"}
