# ⚖ JB 준법 코파일럿 — 소비자 오인 방지 중심 준법자문 AI Agent

JB금융그룹 Fin:AI Challenge 지정주제2 (Compliance AI) MVP.
대고객 금융 콘텐츠를 **작성 시점부터** 심의하고, **소비자가 어떻게 오해하는지 시뮬레이션**하며,
**규제 근거와 함께 수정안**을 제시하고, 준법관리자는 **검토·승인만** 하는 **온프레미스 AI Agent**.

> 설계 문서: [`docs/superpowers/specs/2026-05-28-jb-compliance-ai-agent-design.html`](docs/superpowers/specs/2026-05-28-jb-compliance-ai-agent-design.html)

---

## 빠른 시작 (LLM 없이도 전 기능 테스트 가능)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://localhost:8000 접속
```

**Ollama가 없어도 바로 동작합니다.** LLM 미연결 시 룰엔진 + 결정적 시뮬레이션 폴백 모드로
전체 데모 플로우(심의 → 오인 시뮬레이터 → 수정안 적용 → 승인 → 다국어 재심의 → 감사로그)를
재현할 수 있습니다. 헤더 우측 배지에서 현재 엔진 모드를 확인하세요.

### LLM(권장) 연결 — Ollama + Qwen2.5

```bash
ollama pull qwen2.5:7b-instruct
ollama serve   # http://localhost:11434
# 환경변수로 변경 가능: OLLAMA_URL, OLLAMA_MODEL (기본 qwen2.5:7b-instruct)
```

서버 재접속(또는 새 심의) 시 자동으로 LLM 모드로 전환됩니다.
LLM 모드에서는 ④ LLM 심의(뉘앙스 리스크)와 ⑤ 오인 시뮬레이터(페르소나 1인칭 역할극 + 오해 판정기)가
실제 LLM 추론으로 동작합니다.

### (선택) RAG 임베딩 검색 업그레이드

기본은 의존성 없는 어휘 검색입니다. `pip install sentence-transformers` 후 재시작하면
BGE-m3 임베딩 코사인 검색으로 자동 전환됩니다 (최초 1회 모델 다운로드 ~2GB).

---

## 90초 데모 시나리오 (설계 문서 §10.4)

앱을 열면 **메인 데모가 자동 로드**됩니다 (첫인상).

1. **★ 헤드라인 「👥 소비자는 이렇게 오해합니다」** (점수 바로 아래): 👵 72세 은퇴자·🧑 20대 초보·🌏 외국인이
   각자 1인칭으로 오해 → 🔴 위험 오해 + ⟵ 유발 문구(클릭 시 본문 이동) + 금소법 조항
2. 그 오해의 근거: 좌측 에디터 위험 문구 자동 밑줄, 검토 결과에 규제 출처 인용, 🔴 점수
3. **[🚀 준법 통과까지 자동 개선]** → 점수 게이지 자율 상승 🔴→🟢 (통과까지, 미수렴 시 사람 에스컬레이션)
4. 제목 입력 후 **[준법관리자 검토로 전송]** → 검토 탭에서 **승인** → **[📤 마케팅 채널 자동 배포]**
   (푸시·SMS·이메일·SNS·CRM) → 감사로그에 *AI 자동개선 → 사람 승인 → 시스템 배포* 분리 기록
5. **[🌏 영문 버전 생성 + 재심의]** → 직역 시 생기는 `guaranteed` 같은 보장성 오역을 영문 룰셋이 검출

추가 데모: **[📋 내부 심의기준]** 평문 내규 → AI 룰 변환 · **[🛰 규제 모니터]** 규제 변경 감지·룰 제안 ·
**상품코드 선택** → 코어뱅킹 상품조건 자동 주입. 타이핑을 멈추면 즉시 룰 검사 → LLM 보강 (F11 실시간).

---

## 테스트

```bash
python -m pytest tests/ -v
```

- `tests/test_rules.py` — TDD 정답셋: 픽스처(알려진 위반) → 기대 룰 플래그 회귀 테스트
- `tests/test_classifier.py` — 콘텐츠 유형 분류 정확도
- `tests/test_pipeline.py` — 통합 시나리오 (데모 플로우 end-to-end, 폴백 모드 고정으로 결정적)
- `tests/test_autopilot.py` — 준법 오토파일럿(자율 개선) 수렴·종료보장·합격무결성·폴백
- `tests/test_internal_rules.py` · `test_regwatch.py` · `test_enterprise.py` — 내규 변환·규제 추적·배포·상품DB·다국어 신뢰도

> 총 **57개 테스트** 전체 통과 (LLM 폴백 모드로 고정해 결정적).

---

## 아키텍처

```
Frontend (정적 SPA — app/static/index.html, FastAPI가 서빙)
  심의 워크스페이스 · 오인 시뮬레이터 패널 · 준법관리자 승인 뷰 · 감사로그
        │ REST (JSON)
Backend (FastAPI — app/main.py)
  Orchestrator (명시적 파이썬 파이프라인 — app/pipeline/orchestrator.py)
   ① 콘텐츠 유형 분류        classifier.py   (예금/투자/대출)
   ② 규제 근거 검색 (RAG)    retriever.py    (어휘 검색, BGE-m3 선택) ┐ 병렬
   ③ 룰엔진 (결정적)         rules_engine.py (YAML+정규식, span 추출) ┘
   ④ LLM 심의 (뉘앙스)       llm_reviewer.py (인용은 검색된 조항으로 제한) ┐ 병렬
   ⑤ ★오인 시뮬레이터        simulator.py    (페르소나 역할극+오해 판정기) ┘
   ⑥ 리포트 종합             report.py       (준법점수·등급·하이라이트)
   ⑦⑧ 승인/감사로그          store.py        (SQLite)
   다국어 생성+재심의·신뢰도   multilingual.py (F10, 비-한/영 신뢰도 방어)
  ── 자율·엔터프라이즈 기능 ──────────────────────────────
   ★준법 오토파일럿(F12)      orchestrator.autopilot + remediator.py (통과까지 자율 개선)
   내부 심의기준 자연어→룰(F13) internal_rules.py (법규와 함께 적용, 〔내규〕)
   규제 자동 추적·룰 제안(F14) regwatch.py     (피드 변경 감지→영향분석→제안)
   마케팅 배포 Last-Mile(F15)  distribution.py (승인 콘텐츠 채널 자동 발송)
   상품 DB 연동(F16)          product_db.py   (상품코드→조건 자동 주입)
  LLM 서버: Ollama (Qwen2.5-7B-Instruct) — 미연결 시 룰 기반 폴백
```

> **핵심 차별점 — 소비자 오인 시뮬레이터(헤드라인):** 고령자·금융초보·외국인 페르소나가
> 광고를 1인칭으로 읽고 오해하는 과정을 작성 시점에 재현 → 위험 오해 + 유발 문구 + 규제 조항 연결.
> 외부 연동(규제 피드·발송 채널·상품 DB)은 어댑터로 분리되어 데모는 목/피드로 동작을 증명하고
> 운영에서 법제처 OpenAPI·FCM/SNS·코어뱅킹 API로 교체된다. 전 과정 온프레미스 + 휴먼인더루프.

### 설계 문서 대비 구현 노트

| 항목 | 설계 | MVP 구현 | 사유 |
|---|---|---|---|
| 프론트 | Next.js + React + Tailwind | 정적 SPA (바닐라 JS, 빌드 불필요) | 하드마감(6/12) 내 1-커맨드 실행·테스트 우선. UI 와이어프레임(§10)은 동일 재현 |
| 벡터DB | Chroma + BGE-m3 | 어휘 검색 기본, BGE-m3 선택 설치 | 의존성 0으로 즉시 구동. 인터페이스 분리로 교체 용이 |
| 그 외 F1–F16 | — | 설계대로 전부 구현 (+오토파일럿·내규·규제추적·배포·상품DB) | 폴백 전략(§15)·인용 제한·TDD 정답셋(§16) 포함 |

## 주요 파일

```
app/
  main.py                 FastAPI 앱 + API 엔드포인트
  store.py                승인(F8)·감사로그(F9)·내규·배포 로그 — SQLite
  pipeline/               파이프라인 + 엔터프라이즈 모듈
    orchestrator.py       명시적 파이프라인 + autopilot(F12) 루프
    remediator.py         오토파일럿 수정 에이전트(F12)
    internal_rules.py     내부 심의기준 자연어→룰(F13)
    regwatch.py           규제 자동 추적·룰 제안(F14)
    distribution.py       마케팅 배포 Last-Mile(F15)
    product_db.py         상품 DB 조회(F16)
  data/
    regulations.json      규제 지식베이스 (금소법 §22, 심사지침, 표시광고법 등 + 가상 내부기준)
    rules.yaml            룰엔진 정의 (KO 8종 + EN 재심의 2종)
    personas.json         오인 시뮬레이터 페르소나 3종 (프로필 + 폴백 템플릿)
    fixtures.json         테스트 픽스처 = 데모 입력 = TDD 정답셋
    reg_feed.json         규제 변경 피드 (시연용 · 운영: 법제처 OpenAPI)
    products.json         상품 카탈로그 (시연용 · 운영: 코어뱅킹 API)
  static/index.html       프론트 (헤드라인 시뮬레이터 + 워크스페이스 + 승인 뷰)
tests/                    57개 테스트 (룰·분류·통합·오토파일럿·엔터프라이즈)
```
