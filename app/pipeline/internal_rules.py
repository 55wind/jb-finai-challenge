"""내부 심의기준(내규) — 자연어 지침 → 룰엔진 룰 변환 (F13).

비개발자가 평문 한국어로 쓴 내부 심의기준을 LLM이 구조화 룰로 변환하고,
법규 룰(rules.yaml)과 함께 결정적 룰엔진이 적용한다.
LLM 불가/실패 시: '금지/필수' 키워드 휴리스틱 폴백.
변환된 룰의 실제 판정은 결정적 룰엔진이 수행 → 신뢰 모델 유지.
"""
from __future__ import annotations

import re

from . import llm_client

_TYPES = ("deposit", "investment", "loan")
_SEV = ("high", "medium", "low")
_QUOTES = "'\"‘’“”"

_SYSTEM = """당신은 은행 준법 룰 엔지니어입니다. 입력된 내부 심의기준(평문)을 룰엔진 룰로 변환하세요.
각 지침을 forbidden(금지 표현) 또는 required(필수 고지)로 분류합니다.
- forbidden: 금지할 표현을 잡는 정규식 patterns (한국어; 띄어쓰기는 \\s* 로 유연하게)
- required: 반드시 포함돼야 하는 문구의 정규식 requires_any (전부 부재 시 위반)
중요: patterns/requires_any에는 입력 지침에 실제로 나온 표현(따옴표 안 문구)을 그대로 사용하세요.
유사어로 바꾸거나(예: '최초'를 '최고/최신'으로) 새 표현을 지어내지 마세요.
반드시 JSON으로만 답하세요. 스키마:
{"rules":[{"name":"짧은 이름","kind":"forbidden|required","severity":"high|medium|low",
  "message":"위반 설명(한국어 1문장)",
  "patterns":["정규식", ...],          // kind=forbidden 일 때
  "requires_any":["정규식", ...],      // kind=required 일 때
  "types":["deposit","investment","loan"]   // 생략 시 전체 적용
}]}"""


async def extract(text: str) -> list[dict]:
    """자연어 내규 → 구조화 룰. LLM 우선, 실패 시 휴리스틱 폴백."""
    result = await llm_client.chat_json(_SYSTEM, f"[내부 심의기준]\n{text}")
    if isinstance(result, dict) and isinstance(result.get("rules"), list):
        norm = normalize(result["rules"])
        if norm:
            return norm
    return extract_fallback(text)


def _key_phrase(line: str) -> str | None:
    m = re.search(rf"[{_QUOTES}]([^{_QUOTES}]{{2,40}})[{_QUOTES}]", line)
    if m:
        return m.group(1).strip()
    # 따옴표가 없으면 조사·지시어를 제거한 핵심 어구를 추정
    stripped = re.sub(r"(표현|문구|단어|용어).*$", "", line)
    stripped = re.sub(r"(는|은|이|가|을|를|에|의|도)?\s*(금지|불가|필수|반드시|포함|명시|사용|안\s*됨|하지\s*마세요|해야\s*합니다).*$",
                      "", stripped).strip(" -·•\t")
    return stripped[:30] if len(stripped) >= 2 else None


def extract_fallback(text: str) -> list[dict]:
    """LLM 없이 '금지/필수' 키워드로 룰 추출 (데모·오프라인 폴백)."""
    rules: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip(" -·•\t")
        if not line:
            continue
        phrase = _key_phrase(line)
        if not phrase:
            continue
        pat = re.escape(phrase).replace(r"\ ", r"\s*")
        if re.search(r"금지|하지\s*마|안\s*됨|불가|쓰지\s*마|사용\s*금지", line):
            rules.append({"name": f"내규 금지: {phrase}", "kind": "forbidden", "severity": "medium",
                          "message": f"내부 심의기준에서 금지한 표현입니다: '{phrase}'", "patterns": [pat]})
        elif re.search(r"필수|반드시|포함|명시", line):
            rules.append({"name": f"내규 필수: {phrase}", "kind": "required", "severity": "medium",
                          "message": f"내부 심의기준상 필수 고지가 누락되었습니다: '{phrase}'", "requires_any": [pat]})
    return normalize(rules)


def _valid_regex(p: str) -> bool:
    try:
        re.compile(p)
        return True
    except re.error:
        return False


def _literal_sample(pattern: str) -> str:
    """정규식 패턴 → 대표 리터럴 문자열 (충돌 비교 전용, 판정용 아님).

    내규 룰은 시스템 프롬프트상 '실제 표현 그대로 + \\s* 유연화'만 쓰므로
    \\s*/\\s+ 를 공백으로, 나머지 메타문자를 제거하면 원 표현이 복원된다.
    """
    s = re.sub(r"\\s[*+]", " ", pattern)      # \s* \s+ → 공백
    s = re.sub(r"\\[a-zA-Z]", "", s)          # 그 외 문자클래스(\d 등) 제거
    s = re.sub(r"[()\[\]{}?*+.^$|]", "", s)    # 메타문자 제거
    s = s.replace("\\", "")                     # 이스케이프된 리터럴(\%→%)
    return re.sub(r"\s+", " ", s).strip()


def detect_conflicts(new_rules: list[dict], law_rules: list[dict] | None = None) -> list[dict]:
    """내규 룰 ↔ 기존 법규 룰 충돌 탐지 (피드백 #5 · 거버넌스).

    · 내규 required(필수)가 요구하는 표현을 기존 법규 forbidden(금지)이 막는 경우
    · 내규 forbidden(금지)이 막는 표현을 기존 법규 required(필수)가 요구하는 경우
    겹침이 보이면 경고를 반환한다. 실제 수정/예외 여부는 사람이 판단(휴먼인더루프).
    """
    if law_rules is None:
        from .rules_engine import load_rules
        law_rules = load_rules()
    conflicts: list[dict] = []

    for nr in new_rules or []:
        kind = nr.get("kind")
        name = nr.get("name", "내규 룰")
        if kind == "required":
            for pat in nr.get("requires_any", []):
                sample = _literal_sample(pat)
                if len(sample) < 2:
                    continue
                for lr in law_rules:
                    if lr.get("kind") != "forbidden":
                        continue
                    if any(re.search(p, sample) for p in lr.get("patterns", [])):
                        conflicts.append({
                            "new_rule": name, "new_kind": "required",
                            "law_rule_id": lr["id"], "law_rule_name": lr["name"],
                            "overlap": sample,
                            "message": (f"내규 「{name}」가 필수로 요구하는 표현('{sample}')을 "
                                        f"기존 법규 {lr['id']}({lr['name']})가 금지합니다. "
                                        f"내규를 수정하거나 예외 적용 여부를 검토하세요."),
                        })
        elif kind == "forbidden":
            for pat in nr.get("patterns", []):
                if not _valid_regex(pat):
                    continue
                for lr in law_rules:
                    if lr.get("kind") != "required":
                        continue
                    for rp in lr.get("requires_any", []):
                        sample = _literal_sample(rp)
                        if len(sample) >= 2 and re.search(pat, sample):
                            conflicts.append({
                                "new_rule": name, "new_kind": "forbidden",
                                "law_rule_id": lr["id"], "law_rule_name": lr["name"],
                                "overlap": sample,
                                "message": (f"내규 「{name}」가 금지하는 표현('{sample}')을 "
                                            f"기존 법규 {lr['id']}({lr['name']})가 필수 고지로 요구합니다. "
                                            f"내규를 수정하거나 예외 적용 여부를 검토하세요."),
                            })
                            break
    return conflicts


def normalize(rules) -> list[dict]:
    """LLM/휴리스틱 산출 룰을 룰엔진 스키마로 검증·정규화. 잘못된 정규식은 폐기."""
    out: list[dict] = []
    for i, r in enumerate(rules or []):
        if not isinstance(r, dict) or r.get("kind") not in ("forbidden", "required"):
            continue
        kind = r["kind"]
        key = "patterns" if kind == "forbidden" else "requires_any"
        pats = [p for p in (r.get(key) or []) if isinstance(p, str) and _valid_regex(p)]
        if not pats:
            continue
        types = [t for t in (r.get("types") or _TYPES) if t in _TYPES] or list(_TYPES)
        rule = {
            "id": f"INT-{i + 1}",
            "name": (r.get("name") or "내규 룰")[:60],
            "kind": kind,
            "types": types,
            "languages": ["ko"],
            "severity": r.get("severity") if r.get("severity") in _SEV else "medium",
            "category": "internal",
            "basis": "INTERNAL",
            "message": (r.get("message") or "내부 심의기준 위반")[:200],
            key: pats,
        }
        out.append(rule)
    return out
