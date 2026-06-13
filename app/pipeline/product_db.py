"""상품 DB 조회 (F16) — 상품코드로 전체 상품조건을 자동 주입.

실무에서 상품 약관·조건은 방대해 매번 수기 입력은 비현실적이다. 상품코드를 넣으면
오인 시뮬레이터가 대조에 쓰는 product_facts가 자동으로 채워진다.
데모: app/data/products.json. 운영: 코어뱅킹(계정계) 상품 DB API로 어댑터 교체.
"""
from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"


def load() -> list[dict]:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def get(code: str) -> dict | None:
    return next((p for p in load() if p["code"] == code), None)
