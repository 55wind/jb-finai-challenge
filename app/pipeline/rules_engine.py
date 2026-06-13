"""③ 룰엔진 (F3) — YAML 규칙 + 정규식 기반 결정적 심의.

forbidden 룰: 패턴 매치 시 위반 (매치 위치 span 포함 → 에디터 밑줄 하이라이트).
required 룰: requires_any 패턴이 전부 부재하면 위반 (fix_append로 고지문 추가 제안).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "rules.yaml"
_rules_cache: list[dict] | None = None

SEVERITY_LABEL = {"high": "위반", "medium": "주의", "low": "참고"}


def load_rules() -> list[dict]:
    global _rules_cache
    if _rules_cache is None:
        with open(_RULES_PATH, encoding="utf-8") as f:
            _rules_cache = yaml.safe_load(f)["rules"]
    return _rules_cache


def _suggestion_for(rule: dict, matched: str) -> str:
    # "확정 연 5%" 형태는 숫자를 보존한 구체적 치환안을 생성
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", matched)
    for tmpl_from, tmpl_to in (rule.get("suggestion_map") or {}).items():
        if "{n}" in tmpl_from and m:
            return tmpl_to.replace("{n}", m.group(1))
    if rule["id"] == "R-002":
        return "예금자보호법에 따라 1인당 최고 5천만원까지 보호"
    if rule["id"] == "R-101":
        return re.sub(r"(?i)guaranteed?\s*", "", matched).strip() or "(삭제)"
    return ""


def _eval_rule(rule: dict, text: str, content_type: str, language: str, source: str) -> dict | None:
    """단일 룰 평가 → 위반 finding 또는 None. 법규 룰·내규 룰 공용."""
    if content_type not in rule["types"] or language not in rule.get("languages", ["ko"]):
        return None

    base = {
        "rule_id": rule["id"],
        "rule_name": rule["name"],
        "severity": rule["severity"],
        "severity_label": SEVERITY_LABEL[rule["severity"]],
        "category": rule["category"],
        "basis_id": rule["basis"],
        "message": rule["message"],
        "suggestion": rule.get("suggestion", ""),
        "source": source,   # "rule"(법규) | "internal"(내규)
    }

    if rule["kind"] == "required":
        if any(re.search(p, text) for p in rule["requires_any"]):
            return None
        return {**base, "matched_text": None, "spans": [],
                "fix": {"type": "append", "text": rule["fix_append"]} if rule.get("fix_append") else None}

    # forbidden: condition_absent_any가 있으면 그 패턴이 이미 본문에 있을 때 룰 면제
    if rule.get("condition_absent_any") and any(re.search(p, text) for p in rule["condition_absent_any"]):
        return None
    spans = []
    for pat in rule["patterns"]:
        spans += [{"start": m.start(), "end": m.end(), "text": m.group()} for m in re.finditer(pat, text)]
    if not spans:
        return None
    spans.sort(key=lambda s: s["start"])
    matched = spans[0]["text"]
    replacement = _suggestion_for(rule, matched)
    return {**base, "matched_text": matched, "spans": spans,
            "fix": {"type": "replace", "original": matched, "replacement": replacement} if replacement else None}


def run_rules(text: str, content_type: str, language: str = "ko",
              extra_rules: list[dict] | None = None) -> list[dict]:
    """초안 + 유형 → 위반 룰 리스트. extra_rules(내규)를 법규 룰과 함께 적용."""
    findings: list[dict] = []
    for rule in load_rules():
        f = _eval_rule(rule, text, content_type, language, source="rule")
        if f:
            findings.append(f)
    for rule in (extra_rules or []):
        f = _eval_rule(rule, text, content_type, language, source="internal")
        if f:
            findings.append(f)
    return findings
