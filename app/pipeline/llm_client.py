"""Ollama LLM 클라이언트 (온프레미스 · 오픈모델).

OLLAMA_URL(기본 http://localhost:11434)의 Qwen2.5 등 로컬 모델을 호출.
서버가 없으면 is_available()=False → 각 모듈이 룰엔진 기반 결정적 폴백으로 동작
(설계 문서 §15: "실패 시 룰엔진 결과만으로 폴백").
"""
from __future__ import annotations

import json
import os
import re
import time

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))
# 가용성 캐시 TTL(초). 이 시간이 지나면 재프로브 →
#  · 서버가 뒤늦게 뜨면 폴백→LLM 자동 전환(README "새 심의 시 자동 전환"을 실제로 보장)
#  · 서버가 죽으면 LLM→폴백 자동 강등(매 심의 120s 타임아웃 hang을 TTL로 제한)
# 상시 캐시는 stale(전환 못 감지), 매 요청 프로브는 과함 — 그 사이의 균형.
LLM_PROBE_TTL = float(os.environ.get("LLM_PROBE_TTL", "10"))

_available: bool | None = None
_checked_at: float = 0.0


async def is_available(force_check: bool = False) -> bool:
    global _available, _checked_at
    now = time.monotonic()
    fresh = _available is not None and (now - _checked_at) < LLM_PROBE_TTL
    if fresh and not force_check:
        return _available
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            _available = r.status_code == 200
    except Exception:
        _available = False
    _checked_at = now
    return _available


def _extract_json(raw: str):
    """LLM 출력에서 JSON 추출 (코드펜스/잡담 제거)."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=-1)
    if start > 0:
        raw = raw[start:]
    return json.loads(raw)


async def chat_json(system: str, user: str, retries: int = 1):
    """구조화 출력(JSON) 강제 + 파싱 실패 시 재시도. 실패하면 None (폴백 신호)."""
    if not await is_available():
        return None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                r = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.2},
                    },
                )
                r.raise_for_status()
                return _extract_json(r.json()["message"]["content"])
        except Exception:
            if attempt >= retries:
                return None
    return None
