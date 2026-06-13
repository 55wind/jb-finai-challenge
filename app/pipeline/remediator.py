"""수정 에이전트 (remediation agent) — 준법 오토파일럿의 '행동' 단계.

잔여(비정형) 위반을 규제 근거에 맞게 고쳐쓰되, 마케팅 효과(핵심 셀링포인트)는 보존한다.
인용은 검색된 조항으로 제한(환각 차단). LLM 불가 시: 변경 없이 그대로 반환(폴백) →
오토파일럿 루프가 '수렴 실패 → 사람 에스컬레이션'으로 종료한다.

설계: docs/superpowers/specs/2026-06-13-compliance-autopilot-design.html §5
"""
from __future__ import annotations

from . import llm_client
from .classifier import TYPE_LABELS

_SYSTEM = """당신은 은행 마케팅 카피라이터이자 준법 보조자입니다.
아래 [잔여 위반]만 규제 근거에 맞게 고쳐써서 광고 초안을 수정하세요. 제약:
· 상품의 핵심 셀링포인트(금리 수치·상품명·혜택)는 최대한 보존합니다.
· 새로운 위반이나 허위 고지를 만들지 마세요.
· 필수고지는 본문에 아직 없을 때만 추가합니다.
· 광고가 외국어면 해당 언어를 유지한 채 수정합니다.
반드시 JSON으로만 답하세요. 스키마:
{"revised_text": "수정된 전체 초안",
 "changes": [{"before": "고치기 전 문구", "after": "고친 문구",
              "basis_id": "근거 조항 id", "rationale": "수정 이유(한국어 1문장)"}]}
중요: basis_id는 아래 [규제 근거] 목록에 있는 id만 사용하세요."""


def _residual_block(residual: list[dict]) -> str:
    lines = []
    for f in residual:
        quote = f.get("matched_text") or f.get("quote") or "(필수 고지 누락)"
        why = f.get("message") or f.get("explanation") or ""
        hint = f.get("suggestion") or (f.get("fix") or {}).get("replacement") or ""
        lines.append(f"- 문구: {quote} | 사유: {why}" + (f" | 제안: {hint}" if hint else ""))
    return "\n".join(lines) or "(없음)"


async def remediate(text: str, residual: list[dict], retrieval: dict, content_type: str) -> dict:
    """잔여 위반을 고쳐쓴 새 초안 + 변경내역 반환. 실패/LLM불가 시 원문 그대로."""
    if not residual:
        return {"text": text, "changes": [], "engine": "noop"}

    allowed_ids = {a["id"] for a in retrieval.get("articles", [])} | {
        f.get("basis_id") for f in residual if f.get("basis_id")
    }
    basis_block = "\n".join(
        f"- id={a['id']} | {a['law']} {a['article']} | {a['text']}" for a in retrieval.get("articles", [])
    ) or "(검색된 근거 없음 — 무리하게 인용하지 말 것)"

    user = f"""[콘텐츠 유형] {TYPE_LABELS.get(content_type, content_type)}
[현재 초안]
{text}

[잔여 위반 (이것만 수정)]
{_residual_block(residual)}

[규제 근거 (인용은 이 목록의 id로만)]
{basis_block}"""

    result = await llm_client.chat_json(_SYSTEM, user, retries=1)
    if not isinstance(result, dict) or not result.get("revised_text"):
        return {"text": text, "changes": [], "engine": "fallback(no-llm)"}

    revised = str(result["revised_text"]).strip()
    changes = []
    for c in result.get("changes", []):
        if not isinstance(c, dict):
            continue
        bid = c.get("basis_id") if c.get("basis_id") in allowed_ids else None
        changes.append({
            "before": c.get("before", ""),
            "after": c.get("after", ""),
            "basis_id": bid,
            "rationale": c.get("rationale", ""),
            "engine": "llm",
        })
    return {"text": revised or text, "changes": changes, "engine": "llm"}
