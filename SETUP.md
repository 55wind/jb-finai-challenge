# 설치 및 실행 가이드 — JB 준법 코파일럿

GitHub에서 이 프로젝트를 처음 받은 분이 **내려받기부터 실행(Ollama 포함)까지** 순서대로 따라 할 수 있는 안내서입니다.

> **핵심: LLM(Ollama) 없이도 전 기능이 동작합니다.**
> Ollama가 없으면 자동으로 **룰엔진 + 결정적 시뮬레이션 폴백 모드**로 돌아가 전체 데모(심의 → 오인 시뮬레이터 → 오토파일럿 → 승인 → 배포 → 다국어 → 감사로그)를 재현합니다.
> Ollama를 연결하면 ④LLM 심의(뉘앙스)와 ⑤오인 시뮬레이터(페르소나 1인칭 역할극)가 실제 LLM 추론으로 동작합니다.
>
> **바쁘면 [2단계]까지만 하면 바로 실행됩니다.** Ollama는 선택(권장)입니다.

---

## 0. 사전 준비물

| 필요 | 버전 | 확인 명령 |
|---|---|---|
| **Python** | 3.11 이상 | `python --version` |
| **Git** | 아무 버전 | `git --version` |
| **Ollama** (선택·권장) | 최신 | `ollama --version` |

- Python이 없으면: https://www.python.org/downloads/ (Windows 설치 시 **"Add python.exe to PATH"** 체크)
- Git이 없으면: https://git-scm.com/downloads

---

## 1. 프로젝트 내려받기

```bash
git clone https://github.com/55wind/jb-finai-challenge.git
cd jb-finai-challenge
```

---

## 2. 파이썬 환경 + 의존성 설치

프로젝트 폴더 안에서 가상환경을 만들고 패키지를 설치합니다.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> PowerShell에서 `Activate.ps1` 실행이 막히면(빨간 오류) 한 번만:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 후 다시 시도하세요.
> 또는 활성화 없이 `.\.venv\Scripts\python.exe -m uvicorn ...` 처럼 직접 호출해도 됩니다.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

설치되는 패키지: `fastapi`, `uvicorn`, `pyyaml`, `httpx`, `pytest` (의존성 최소).

---

## 3. 바로 실행 (LLM 없이 — 폴백 모드)

```bash
uvicorn app.main:app --reload
```

브라우저에서 **http://localhost:8000** 접속 → 메인 데모가 자동으로 뜹니다.

- 화면 우측 하단 배지에서 현재 엔진 모드를 확인할 수 있습니다.
  - `폴백 모드 · 룰엔진` → Ollama 미연결 (지금 상태)
  - `LLM` 표기 → Ollama 연결됨
- 여기까지만 해도 심의·오토파일럿·승인·배포·다국어·규제모니터·내규 등 **전 기능이 동작**합니다.

> 포트를 바꾸려면: `uvicorn app.main:app --reload --port 8137`

---

## 4. (권장) Ollama 설치 → LLM 모드로 실행

LLM을 연결하면 오인 시뮬레이터의 페르소나 1인칭 역할극과 뉘앙스 심의가 실제 추론으로 동작합니다. **오픈모델만 사용**하며 전 과정 온프레미스(로컬)입니다.

### 4-1. Ollama 설치

- **공식 사이트**: https://ollama.com/download (Windows / macOS / Linux 설치 파일 제공)
- Windows: 설치 후 Ollama가 백그라운드 서비스로 자동 실행됩니다.
- macOS: 앱 실행. Linux: `curl -fsSL https://ollama.com/install.sh | sh`

설치 확인:
```bash
ollama --version
```

### 4-2. 모델 내려받기 (최초 1회, 약 4.7GB)

```bash
ollama pull qwen2.5:7b-instruct
```

### 4-3. Ollama 서버 실행

```bash
ollama serve
```

> 이미 백그라운드로 떠 있으면 `address already in use`가 뜰 수 있는데, **정상입니다**(이미 실행 중이라는 뜻). 기본 주소는 `http://localhost:11434`.
> 확인: 브라우저에서 http://localhost:11434 접속 시 `Ollama is running` 표시.

### 4-4. 앱 (재)실행 → 자동으로 LLM 모드 전환

앱은 주기적으로 Ollama 가용성을 재확인하므로, Ollama를 켠 뒤 **새 심의를 실행하거나 페이지를 새로고침**하면 자동으로 LLM 모드로 전환됩니다.

```bash
uvicorn app.main:app --reload
```

우측 하단 배지가 `LLM`으로 바뀌면 연결 성공입니다.

---

## 5. (선택) RAG 임베딩 검색 업그레이드

기본 규제 근거 검색은 의존성 0의 **어휘 검색**입니다. 더 정밀한 의미 검색을 원하면:

```bash
pip install sentence-transformers
```

설치 후 재시작하면 **BGE-m3 임베딩 코사인 검색**으로 자동 전환됩니다 (최초 1회 모델 다운로드 약 2GB). 설치돼 있지 않으면 그냥 어휘 검색으로 폴백하므로 없어도 무방합니다.

---

## 6. 환경변수 (선택)

기본값으로도 잘 동작합니다. 필요할 때만 설정하세요.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama 서버 주소 |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | 사용할 로컬 모델 |
| `LLM_TIMEOUT` | `120` | LLM 응답 대기 최대 초 |
| `LLM_PROBE_TTL` | `10` | LLM 가용성 재확인 주기(초). 서버 up/down 자동 감지 |
| `JB_DB_PATH` | `app/data/app.db` | SQLite DB 경로 (승인·감사로그·내규 저장) |

설정 예시:

```bash
# Windows (PowerShell)
$env:OLLAMA_MODEL = "qwen2.5:7b-instruct"; uvicorn app.main:app --reload

# macOS / Linux
OLLAMA_MODEL=qwen2.5:7b-instruct uvicorn app.main:app --reload
```

---

## 7. 테스트 실행

```bash
python -m pytest tests/ -v
```

- 룰 정답셋·분류·통합 데모 플로우·오토파일럿·엔터프라이즈(내규·규제추적·배포·상품DB·다국어) 회귀 테스트가 실행됩니다.
- 테스트는 LLM 폴백 모드로 고정되어 **결정적**으로 통과합니다(Ollama 없어도 됨).

---

## 8. 실행 후 데모 순서 (참고)

앱 접속 시 메인 데모가 자동 로드됩니다. 발표/시연 순서:

1. **오인 시뮬레이터** — 소비자 5인이 광고를 1인칭으로 오해하는 화면 (헤드라인)
2. **[🚀 준법 통과까지 자동 개선]** — 점수 자율 상승 (위험 → 통과)
3. 제목 입력 후 **[검토 전송]** → 검토 탭에서 **승인** → **[채널로 자동 배포]**
4. **[🌏 영문 버전 생성 + 재심의]** — 다국어 재심의
5. **[🛰 규제 모니터]** 규제 변경 감지 · **[📋 내부 심의기준]** 평문 내규 → 룰 변환

---

## 9. 문제 해결 (FAQ)

| 증상 | 해결 |
|---|---|
| **포트 8000이 이미 사용 중** | `--port 8137` 등 다른 포트로 실행 |
| **`ModuleNotFoundError`** | 가상환경 활성화 확인 후 `pip install -r requirements.txt` 재실행 |
| **배지가 계속 `폴백 모드`** | Ollama 실행 여부(`ollama serve`)·모델 다운로드(`ollama list`)·`OLLAMA_URL` 확인 후 페이지 새로고침 |
| **LLM 응답이 느림** | 로컬 7B 모델은 CPU에서 느릴 수 있음. 첫 호출은 모델 로딩으로 지연됨(정상). GPU 있으면 자동 활용 |
| **데모 데이터 초기화** | 서버 종료 후 `app/data/app.db` 삭제 → 재실행 시 빈 상태로 재생성 (기본 gitignore 대상이라 커밋 안 됨) |
| **Windows에서 한글 깨짐** | 브라우저 표시는 정상. 터미널 로그만 깨지면 무시해도 됨 |

---

## 요약 (복붙용)

```bash
# 1) 받기
git clone https://github.com/55wind/jb-finai-challenge.git
cd jb-finai-challenge

# 2) 환경 (Windows: python -m venv .venv; .\.venv\Scripts\Activate.ps1)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) 바로 실행 (LLM 없이도 동작)
uvicorn app.main:app --reload      # → http://localhost:8000

# 4) (권장) LLM 모드
ollama pull qwen2.5:7b-instruct
ollama serve                        # 다른 터미널
#   → 앱 새로고침 시 자동으로 LLM 모드 전환
```
