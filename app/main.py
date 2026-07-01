"""JB 준법 코파일럿 — FastAPI 백엔드 (API + 정적 프론트 서빙).

실행:  uvicorn app.main:app --reload
접속:  http://localhost:8000
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import store
from .pipeline import (classifier, distribution, internal_rules, llm_client,
                       orchestrator, product_db, regwatch, rules_engine)

app = FastAPI(title="JB 준법 코파일럿", version="0.1.0")

# 내규(내부 심의기준) 로더 주입 — 심의 시 활성 내규를 법규와 함께 적용
orchestrator.set_internal_rules_loader(store.active_internal_rules)

_STATIC = Path(__file__).resolve().parent / "static"
_FIXTURES = Path(__file__).resolve().parent / "data" / "fixtures.json"


# ── 요청 모델 ──────────────────────────────────────────────

class ReviewRequest(BaseModel):
    text: str
    content_type: str | None = Field(default=None, description="deposit|investment|loan (없으면 자동분류)")
    language: str = "ko"
    product_facts: str = ""
    quick: bool = False


class ApplyFixesRequest(BaseModel):
    text: str
    fixes: list[dict]


class AutopilotRequest(BaseModel):
    text: str
    content_type: str | None = None
    language: str = "ko"
    product_facts: str = ""
    max_iter: int = Field(default=4, ge=1, le=6)


class InternalExtractRequest(BaseModel):
    text: str


class InternalSaveRequest(BaseModel):
    rules: list[dict]
    source_text: str = ""


class InternalTestRequest(BaseModel):
    rules: list[dict]
    text: str = ""
    content_type: str | None = None
    language: str = "ko"


class SubmissionRequest(BaseModel):
    title: str = "무제 콘텐츠"
    submitter: str = "마케팅팀"
    text: str
    content_type: str
    language: str = "ko"
    product_facts: str = ""
    report: dict
    autopilot_summary: str = ""


class DecisionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject|comment)$")
    actor: str = "준법관리자"
    comment: str = ""


class DistributeRequest(BaseModel):
    channels: list[str] = ["push", "sms", "email"]


class TranslateRequest(BaseModel):
    target_lang: str = "en"
    actor: str = "준법관리자"


# ── API ────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    llm_ok = await llm_client.is_available(force_check=True)
    return {
        "status": "ok",
        "llm_available": llm_ok,
        "llm_model": llm_client.OLLAMA_MODEL if llm_ok else None,
        "mode": "llm" if llm_ok else "fallback(rule-based) — Ollama 미연결, 룰엔진·결정적 시뮬레이션으로 동작",
    }


@app.get("/api/fixtures")
def fixtures():
    return json.loads(_FIXTURES.read_text(encoding="utf-8"))


@app.post("/api/review")
async def review(req: ReviewRequest):
    return await orchestrator.run_review(req.text, req.content_type, req.language,
                                         req.product_facts, req.quick)


@app.post("/api/apply-fixes")
def apply_fixes(req: ApplyFixesRequest):
    return {"text": orchestrator.apply_fixes(req.text, req.fixes)}


@app.post("/api/autopilot")
async def autopilot(req: AutopilotRequest):
    """준법 오토파일럿 — 통과/종료조건까지 자율 개선, 회차 trace 반환."""
    return await orchestrator.autopilot(req.text, req.content_type, req.language,
                                        req.product_facts, req.max_iter)


# ── 내부 심의기준(내규) ────────────────────────────────────

@app.post("/api/internal-rules/extract")
async def internal_extract(req: InternalExtractRequest):
    """자연어 내규 → 구조화 룰 미리보기 + 기존 법규 룰 충돌 탐지 (저장 안 함)."""
    rules = await internal_rules.extract(req.text)
    return {"rules": rules, "conflicts": internal_rules.detect_conflicts(rules)}


@app.post("/api/internal-rules/test")
def internal_test(req: InternalTestRequest):
    """적용 전 룰 검증 — 생성된 룰을 현재 초안에 돌려 과탐/미탐을 미리 보여준다(F13 신뢰)."""
    ctype = req.content_type or (classifier.classify(req.text)["content_type"] if req.text else "deposit")
    normalized = internal_rules.normalize(req.rules)
    out = []
    for rule in normalized:
        f = rules_engine._eval_rule(rule, req.text, ctype, req.language, "internal") if req.text else None
        out.append({
            "name": rule["name"], "kind": rule["kind"],
            "matched": f is not None,
            "matched_text": (f.get("matched_text") if f else None),
        })
    return {"results": out, "content_type": ctype,
            "conflicts": internal_rules.detect_conflicts(normalized)}


@app.post("/api/internal-rules")
def internal_save(req: InternalSaveRequest):
    """확인된 내규 룰 저장 → 이후 심의에 법규와 함께 적용."""
    return {"rules": store.add_internal_rules(req.rules, req.source_text)}


@app.get("/api/internal-rules")
def internal_list():
    return {"rules": store.list_internal_rules()}


@app.post("/api/internal-rules/{rule_id}/toggle")
def internal_toggle(rule_id: int, active: bool = True):
    store.set_internal_rule_active(rule_id, active)
    return {"rules": store.list_internal_rules()}


@app.delete("/api/internal-rules/{rule_id}")
def internal_delete(rule_id: int):
    store.delete_internal_rule(rule_id)
    return {"rules": store.list_internal_rules()}


# ── 규제 자동 추적 (F14) ───────────────────────────────────

@app.post("/api/regwatch/scan")
async def regwatch_scan():
    """규제 피드 스캔 → 변경 감지 + 영향분석 + 룰 제안 + 승인 콘텐츠 사후 재검사."""
    changes = await regwatch.scan(store.count_submissions_by_types)
    recheck = regwatch.recheck_approved(changes, store.approved_submissions_for_recheck())
    return {"changes": changes, "recheck": recheck}


# ── 마케팅 배포 Last-Mile (F15) ────────────────────────────

@app.get("/api/dist/channels")
def dist_channels():
    return {"channels": [{"id": k, "label": v} for k, v in distribution.CHANNELS.items()]}


@app.post("/api/submissions/{sid}/distribute")
def distribute(sid: int, req: DistributeRequest):
    sub = store.get_submission(sid)
    if not sub:
        raise HTTPException(404, "submission not found")
    if sub["status"] != "approved":
        raise HTTPException(409, "승인된 콘텐츠만 마케팅 채널로 배포할 수 있습니다 (휴먼인더루프).")
    results = distribution.dispatch(req.channels, sub["title"], sub["text"])
    store.log_distribution(sid, results)
    return {"results": results, "submission": store.get_submission(sid)}


# ── 상품 DB 조회 (F16) ─────────────────────────────────────

@app.get("/api/products")
def products():
    return {"products": [{k: p[k] for k in ("code", "name", "content_type")} for p in product_db.load()]}


@app.get("/api/products/{code}")
def product_detail(code: str):
    p = product_db.get(code)
    if not p:
        raise HTTPException(404, "product not found")
    return p


@app.post("/api/submissions")
def create_submission(req: SubmissionRequest):
    return store.create_submission(req.title, req.submitter, req.content_type,
                                   req.language, req.product_facts, req.text, req.report,
                                   req.autopilot_summary)


@app.get("/api/submissions")
def list_submissions():
    return store.list_submissions()


@app.get("/api/submissions/{sid}")
def get_submission(sid: int):
    sub = store.get_submission(sid)
    if not sub:
        raise HTTPException(404, "submission not found")
    return sub


@app.post("/api/submissions/{sid}/decision")
def decide(sid: int, req: DecisionRequest):
    if req.action == "comment":
        if not req.comment.strip():
            raise HTTPException(400, "comment required")
        store.add_comment(sid, req.actor, req.comment)
        return store.get_submission(sid)
    sub = store.decide(sid, req.action, req.actor, req.comment)
    if not sub:
        raise HTTPException(404, "submission not found")
    return sub


@app.post("/api/submissions/{sid}/translate")
async def translate(sid: int, req: TranslateRequest):
    sub = store.get_submission(sid)
    if not sub:
        raise HTTPException(404, "submission not found")
    if sub["status"] != "approved":
        raise HTTPException(409, "다국어 생성은 승인된 콘텐츠에서만 가능합니다 (설계: 승인 후 단계).")
    result = await orchestrator.translate_and_rereview(
        sub["text"], sub["content_type"], req.target_lang, sub.get("product_facts") or "")
    store.save_translation(sid, req.target_lang, result["translation"],
                           result["engine"], result["report"], req.actor)
    return store.get_submission(sid)


@app.get("/api/audit")
def audit(submission_id: int | None = None):
    return store.audit_trail(submission_id)


# ── 프론트 (정적 SPA) ──────────────────────────────────────

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(_STATIC / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC), name="static")
