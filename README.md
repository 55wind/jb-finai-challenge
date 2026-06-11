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

1. 워크스페이스에서 **"📋 예금 — 단정·원금보장 (메인 데모)"** 픽스처 클릭
   → 자동 심의: 위험 문구 밑줄 + 우측 규제 출처 인용 + 준법점수 🔴
2. 하단 **소비자 오인 시뮬레이터**: 72세 은퇴자·20대 금융초보·외국인 거주자가
   각자 1인칭으로 오해 → 위험 오해 + 유발 문구 + 금소법 조항
3. **[수정안 전체 적용]** → 재심의 → 점수 🟢 90+
4. 제목 입력 후 **[준법관리자 검토로 전송]** → 검토 탭에서 **승인** → 배포가능 + 감사로그
5. 승인된 콘텐츠에서 **[🌏 영문 버전 생성 + 재심의]** → 직역 시 생기는
   `guaranteed` 같은 보장성 오역·필수고지 누락을 영문 룰셋이 검출

직접 입력도 가능: 텍스트를 붙여넣거나 타이핑을 멈추면 자동 심의됩니다 (F11 실시간 검사).

---

## 테스트

```bash
python -m pytest tests/ -v
```

- `tests/test_rules.py` — TDD 정답셋: 픽스처(알려진 위반) → 기대 룰 플래그 회귀 테스트
- `tests/test_classifier.py` — 콘텐츠 유형 분류 정확도
- `tests/test_pipeline.py` — 통합 시나리오 (데모 플로우 end-to-end, 폴백 모드 고정으로 결정적)

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
   다국어 생성+재심의         multilingual.py (F10)
  LLM 서버: Ollama (Qwen2.5-7B-Instruct) — 미연결 시 룰 기반 폴백
```

### 설계 문서 대비 구현 노트

| 항목 | 설계 | MVP 구현 | 사유 |
|---|---|---|---|
| 프론트 | Next.js + React + Tailwind | 정적 SPA (바닐라 JS, 빌드 불필요) | 하드마감(6/12) 내 1-커맨드 실행·테스트 우선. UI 와이어프레임(§10)은 동일 재현 |
| 벡터DB | Chroma + BGE-m3 | 어휘 검색 기본, BGE-m3 선택 설치 | 의존성 0으로 즉시 구동. 인터페이스 분리로 교체 용이 |
| 그 외 F1–F11 | — | 설계대로 전부 구현 | 폴백 전략(§15)·인용 제한·TDD 정답셋(§16) 포함 |

## 주요 파일

```
app/
  main.py                 FastAPI 앱 + API 엔드포인트
  store.py                승인 워크플로(F8)·감사로그(F9) — SQLite
  pipeline/               ①~⑥ 파이프라인 모듈
  data/
    regulations.json      규제 지식베이스 (금소법 §22, 심사지침, 표시광고법 등 + 가상 내부기준)
    rules.yaml            룰엔진 정의 (KO 8종 + EN 재심의 2종)
    personas.json         오인 시뮬레이터 페르소나 3종 (프로필 + 폴백 템플릿)
    fixtures.json         테스트 픽스처 = 데모 입력 = TDD 정답셋
  static/index.html       프론트 (워크스페이스 + 승인 뷰)
tests/                    24개 테스트 (룰·분류·통합 시나리오)
```
