import json
from pathlib import Path

import pytest

from app.pipeline.classifier import classify

FIXTURES = json.loads(
    (Path(__file__).resolve().parent.parent / "app" / "data" / "fixtures.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("fx", FIXTURES, ids=[f["id"] for f in FIXTURES])
def test_fixture_type_classification(fx):
    assert classify(fx["text"])["content_type"] == fx["expected_type"]


def test_empty_text_low_confidence():
    result = classify("안녕하세요")
    assert result["confidence"] == 0.0
