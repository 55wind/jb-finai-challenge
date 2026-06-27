"""규제 자동 추적 + 영향분석 + 룰 제안 (F14).

외부 규제 피드(신규/개정 고시)를 받아 ① 현행 코퍼스와 비교해 변경을 감지하고,
② 영향받는 콘텐츠 유형/제출 건을 분석하며, ③ 변경 내용을 룰로 자동 '제안'한다.
사람이 검토·승인해야 실제 적용된다(휴먼인더루프).

데모 피드: app/data/reg_feed.json. 운영: 법제처 국가법령정보 공동활용 OpenAPI
(open.law.go.kr) 또는 금융위 고시 RSS를 같은 인터페이스로 교체하면 된다.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import internal_rules
from .retriever import load_corpus
from .rules_engine import run_rules

_FEED = Path(__file__).resolve().parent.parent / "data" / "reg_feed.json"


def load_feed() -> list[dict]:
    return json.loads(_FEED.read_text(encoding="utf-8"))


async def scan(affected_counter=None) -> list[dict]:
    """규제 피드를 훑어 변경 감지 → 영향분석 + 룰 제안 목록 반환.

    affected_counter(types: list[str]) -> int : 영향받는 제출 건수 산출(주입).
    """
    corpus_ids = {a["id"] for a in load_corpus()}
    changes = []
    for reg in load_feed():
        status = "개정" if reg["id"] in corpus_ids else "신규"
        # 변경 내용을 룰로 제안 (LLM, 실패 시 휴리스틱) — 근거는 이 규제 id로 인용
        proposed = internal_rules.extract(reg.get("guideline") or reg["text"])
        proposed = await proposed
        for r in proposed:
            r["basis"] = reg["id"]
            r["category"] = "regulation"
            r["name"] = f"[규제 {status}] {reg['title']} — " + r["name"].split(": ", 1)[-1]
            r["message"] = f"{reg['law']} {reg['article']}: {r['message']}"
        impact_types = reg.get("types", [])
        affected = affected_counter(impact_types) if affected_counter else 0
        changes.append({
            "regulation": {k: reg.get(k) for k in
                           ("id", "law", "article", "title", "text", "effective_date", "change_type")},
            "status": status,
            "impact_types": impact_types,
            "affected_count": affected,
            "proposed_rules": proposed,
        })
    return changes


def recheck_approved(changes: list[dict], submissions: list[dict]) -> list[dict]:
    """이미 승인·배포된 과거 콘텐츠 재검사 (피드백 #4 · 사후 관리).

    감지된 규제 변경의 '제안 룰'을 기존 승인 콘텐츠에 결정적으로 돌려,
    새 규제에 걸리는 건을 찾아 '재심의 필요'로 표시한다. 룰엔진 판정이므로
    환각 없이 사후 영향만 잡아낸다. 실제 수정/회수는 사람이 결정.
    """
    flagged: list[dict] = []
    for ch in changes:
        rules = ch.get("proposed_rules") or []
        if not rules:
            continue
        reg = ch["regulation"]
        for sub in submissions:
            findings = run_rules(sub["text"], sub["content_type"],
                                 sub.get("language", "ko"), extra_rules=rules)
            new_hits = [f for f in findings if f.get("source") == "internal"]
            if not new_hits:
                continue
            flagged.append({
                "submission_id": sub["id"],
                "title": sub["title"],
                "content_type": sub["content_type"],
                "regulation_id": reg["id"],
                "regulation_title": reg["title"],
                "hits": [{"rule_name": f["rule_name"], "matched_text": f.get("matched_text"),
                          "severity": f["severity"]} for f in new_hits],
            })
    return flagged
