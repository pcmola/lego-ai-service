# 레고 창작 AI Agent (Multi-Agent + RAG + Streamlit)

<img src="./images/01.InitResult.png" width="1007">

레고 창작 설계용 Multi-Agent 기반 에이전트 프로젝트입니다.  
사용자가 만들고 싶은 레고 작품의 컨셉·크기·용도 등을 입력하면, 여러 에이전트가 협업하여 <br/>
**요구사항 분석 → 구조 설계 → 최종 가이드 생성**까지 자동으로 수행하고,<br/>
**완성 예상 이미지와 층별 조립 도안**까지 그려 줍니다.

---

## ⭐ 주요 특징

- **Multi-Agent + LangGraph** 워크플로우
- **RAG 기반 지식 검색** (레고 기초 문서)
- **Rebrickable API**로 브릭/부품 이미지 자동 조회
- **완성 예상 이미지** (gpt-image) + **층별 조립 도안** (구조화 출력 → 검증 → SVG 평면도)
- **Streamlit** 기반 웹 UI (로컬 브라우저 실행)
- **Azure OpenAI (Foundry)**
  - Chat: `gpt-5.6-luna` (기본), `gpt-6-sol` (고성능)
  - Embedding: `text-embedding-3-*`
  - Image: `gpt-image-2` (선택)

---

## 🆕 v0.3 변경 사항

> 이전 버전(v0.2 계열)은 [`release/v0.2`](https://github.com/pcmola/lego-ai-service/tree/release/v0.2) 브랜치에 보존되어 있습니다.

| 구분 | 내용 |
| --- | --- |
| 모델 | Chat 기본 `gpt-4.1-mini` → **`gpt-5.6-luna`**, 고성능 `gpt-4.1` → **`gpt-6-sol`** |
| 모델 설정 | 변수명을 용도 기준으로 변경 (`AOAI_DEPLOY_CHAT` / `AOAI_DEPLOY_CHAT_PRO`, 구 변수명도 인식)<br/>`AOAI_PRO_AGENTS` 로 에이전트별 고성능 모델 지정 (예: `DESIGN,BLUEPRINT`)<br/>`AOAI_TEMPERATURE` 신설 — gpt-5.x 이상 추론형 모델은 비워 둘 것 (0.7 등 지정 시 400 오류) |
| 신규 기능 | **완성 예상 이미지** (gpt-image) · **층별 조립 도안** (구조화 출력 → 범위/겹침/지지 검증 → SVG 평면도 + 부품 수량표) |
| 응답성 | 에이전트 단계별 진행 표시 + 최종 정리 답변 **실시간 스트리밍**<br/>이미지·도안을 부품 표(Rebrickable 조회)와 **병렬 생성**<br/>**⏹ 중지 버튼** (어느 단계에서든 1초 내 중지, 직전 결과 유지) |
| 성능 | 벡터스토어 재사용(검색마다 재생성 X), Rebrickable 404 부품 재조회 방지 |
| 의존성 | 미사용 `langchain`, `langchain-community`, `chromadb`(직접 명시) 제거, `langchain-core`, `requests` 명시 |
| 실행 | `run.ps1` / `run.bat` / `run.sh` 가 `.venv` 생성 + `requirements.txt` 변경 시 자동 설치 후 실행 (전역 Python 미사용) |

---

## 📑 Table of Contents

- [1. 기능 개요](#-1-기능-개요)
- [2. 사용자 흐름 (User Flow)](#-2-사용자-흐름-user-flow)
- [3. 서비스 아키텍처](#-3-서비스-아키텍처)
- [4. 프로젝트 구조(전체 트리)](#-4-프로젝트-구조전체-트리)
- [5. 주요 모듈 설명](#-5-주요-모듈-설명)
- [6. 환경변수 설정 (.env 예시)](#-6-환경변수-설정-env-예시)
- [7. 실행 방법](#-7-실행-방법)
- [8. Azure OpenAI 연결 테스트](#-8-azure-openai-연결-테스트)
- [9. TODO (향후 개선 예정)](#-9-todo-향후-개선-예정)
- [10. 문의](#-10-문의)
- [11. 결과 예시](#-11-결과-예시)

---

## 📌 1. 기능 개요

에이전트들은 아래 단계로 협업합니다.

1. **사용자 입력**
   - 작품명, 용도(전시/놀이), 목표 크기, 난이도, 추가 제약 조건 등
2. **요구사항 분석 (RequirementsAgent)**
   - 입력을 구조화(요구/제약/우선순위 등)
3. **설계 제안 (DesignAgent)**
   - 구조, 모듈 분리, 색상/브릭 종류, 안정성 고려사항 등 제안
4. **RAG 기반 지식 보강**
   - 준비된 레고 지식 문서를 검색해 설계를 보완
5. **최종 결과 정리 (RefinerAgent)**
   - 사람이 읽기 좋은 가이드/체크리스트/빌드 팁 등으로 정리
6. **브릭/부품 제안 표 생성**
   - Refiner 결과 중 “브릭/부품 제안” 섹션을 파싱
   - Rebrickable API로 각 부품의 이름·이미지를 조회 후 HTML 표로 렌더링
7. **완성 예상 이미지 생성** (선택, `app/utils/image_gen.py`)
   - 최종 가이드 → 영어 이미지 프롬프트 → gpt-image 로 완성 예상 이미지 생성
   - ※ 분위기용 예상 이미지이며 실제 부품 구성과 다를 수 있음
8. **층별 조립 도안 생성** (`app/utils/blueprint.py`)
   - LLM 구조화 출력으로 층별 브릭 좌표/크기/색/부품 번호 생성 (바닥 16x16 · 8층 · 150개 이내)
   - 격자 밖·겹침 브릭 제외, 아래층에 받쳐지지 않은 브릭은 빨간 점선으로 표시
   - 층별 SVG 평면도(아래층 위치 음영 표시) + 부품 수량 요약표
9. **Streamlit UI 출력**
   - 단계별 진행 상태 + 최종 답변 실시간 스트리밍, 실행 중 ⏹ 중지 가능
   - 최종 텍스트 + 브릭/부품 표 + (탭) 조립 도안 / 완성 예상 이미지

---

## 📌 2. 사용자 흐름 (User Flow)

```mermaid
%%{init: {
  "theme": "neutral",
  "background": "white",
  "flowchart": {
    "nodeSpacing": 10,
    "rankSpacing": 40
  },
  "themeVariables": {
    "primaryColor": "#e3f2fd",
    "primaryTextColor": "#111111",
    "lineColor": "#555555",
    "tertiaryColor": "#ffffff",
    "fontSize": "14px"
  }
}}%%
flowchart TB

    %% ===================== 스타일 정의 =====================
    classDef input fill:#E3F2FD,stroke:#1E88E5,stroke-width:1px,color:#0D47A1;
    classDef agent fill:#FFE0B2,stroke:#FB8C00,stroke-width:1px,color:#E65100;
    classDef rag fill:#E1BEE7,stroke:#8E24AA,stroke-width:1px,color:#4A148C;
    classDef output fill:#E8F5E9,stroke:#43A047,stroke-width:1px,color:#1B5E20;

    %% ===================== 노드 정의 =====================
    Input["🟦 사용자 입력<br/>- 사이드바 옵션<br/>- 레고 아이디어 텍스트"]:::input
    Start["🔥 LangGraph 시작"]:::agent

    A1["📘 요구사항 분석 에이전트<br/>(RequirementsAgent)"]:::agent
    A2["📗 설계 생성 에이전트<br/>(DesignAgent)"]:::agent
    A3["📙 정리 에이전트<br/>(RefinerAgent)"]:::agent

    RAG["🔍 레고 지식 검색 (RAG)<br/>(app/retrieval/vector_store.py)"]:::rag
    P["🧩 브릭/부품 제안 섹션 파싱<br/>(app/main.py)"]:::rag
    Rb["🔧 Rebrickable API 호출<br/>(app/utils/rebrickable_client.py)"]:::rag
    T["🧱 브릭/부품 HTML 표 렌더링<br/>(app/components/brick_table.py)"]:::rag

    Out["✅ 최종 설계 결과 + 브릭 제안 표 출력<br/>(Streamlit 화면)"]:::output
    IMG["🖼️ 완성 예상 이미지<br/>(app/utils/image_gen.py)"]:::output
    BP["📐 층별 조립 도안<br/>(app/utils/blueprint.py)"]:::output

    %% ===================== 플로우 =====================
    Input --> Start --> A1 --> A2 --> A3 --> P --> Rb --> T --> Out
    A3 -. 병렬 .-> IMG --> Out
    A3 -. 병렬 .-> BP --> Out

    A1 --> RAG
    A2 --> RAG
    A3 --> RAG
```

- 사용자가 사이드바 + 자유 텍스트로 아이디어를 입력합니다.
- LangGraph가 Requirements → Design → Refiner 에이전트를 순차 실행합니다.
- Refiner 결과 안의 "브릭/부품 제안"”" 섹션을 main.py에서 따로 파싱합니다.
- 각 행의 부품 번호를 기준으로 Rebrickable API 를 호출해 이미지·영문명 등을 채웁니다.
- brick_table.py에서 HTML 테이블을 생성해 Streamlit에서 스크롤 가능한 표로 렌더링합니다.
- 최종 답변이 나오는 즉시 **완성 예상 이미지**와 **층별 조립 도안** 생성을 백그라운드로 시작하여, 부품 표 조회와 병렬로 진행합니다.

---

## 📌 3. 서비스 아키텍처

### 3.1. 어른용

```mermaid
%%{init: {
  "theme": "neutral",
  "background": "white",
  "flowchart": { "nodeSpacing": 10, "rankSpacing": 40 },
  "themeVariables": {
    "primaryColor": "#F5F7FB",
    "primaryTextColor": "#1F2933",
    "lineColor": "#B0BEC5",
    "tertiaryColor": "#FFFFFF",
    "fontSize": "14px"
  }
}}%%
flowchart TB

  %% ───────── 클라이언트 / UI ─────────
  U([사용자 브라우저]):::client

  subgraph UI_LAYER[ ]
    direction TB
    UI([Streamlit 앱<br/>app/main.py<br/>+ components/*]):::ui
    BT([브릭/부품 HTML 표<br/>app/components/brick_table.py]):::ui
  end

  %% ───────── 오케스트레이터 & 에이전트 ─────────
  G([LangGraph App<br/>workflow/graph.py]):::orchestrator

  subgraph AGENTS[ ]
    direction TB
    R([RequirementsAgent]):::agent
    D([DesignAgent]):::agent
    F([RefinerAgent]):::agent
  end

  %% ───────── Azure OpenAI 서비스 ─────────
  subgraph AZURE[ ]
    direction TB
    E([Azure OpenAI<br/>Embeddings]):::service
    LLM([Azure OpenAI<br/>LLM<br/>gpt-5.6-luna · gpt-6-sol]):::service
  end

  %% ───────── 지식 / 저장소 ─────────
  subgraph STORAGE[ ]
    direction TB
    VS([Chroma VectorStore<br/>app/retrieval/vector_store.py]):::store
    K["레고 지식 문서<br/>app/retrieval/knowledge/*.md"]:::knowledge
    LOG([로그 파일<br/>app/logs/app.log]):::ops
  end

  %% ───────── 외부 API ─────────
  RB([Rebrickable API<br/>app/utils/rebrickable_client.py]):::service

  %% ───────── 연결 ─────────
  U --> UI
  UI --> G

  G --> R
  G --> D
  G --> F

  R --> E
  D --> LLM
  F --> LLM

  R --> VS
  D --> VS
  F --> VS
  VS --> K

  UI -- "최종 답변 중<br/>5번 섹션 파싱" --> RB
  RB --> BT
  BT --> UI

  UI --> LOG

  %% ───────── 스타일 정의 ─────────
  classDef client fill:#FFFFFF,stroke:#B0BEC5,color:#374151;
  classDef ui fill:#E3F2FD,stroke:#1D4ED8,color:#1E3A8A;
  classDef orchestrator fill:#F3E8FF,stroke:#8B5CF6,color:#4C1D95;
  classDef agent fill:#ECFDF3,stroke:#22C55E,color:#166534;
  classDef service fill:#FEF2F2,stroke:#F97373,color:#B91C1C;
  classDef store fill:#FFFBEB,stroke:#F59E0B,color:#92400E;
  classDef knowledge fill:#E0F2FE,stroke:#0EA5E9,color:#075985;

  %% 운영/로그 요소(배경화): 점선 + 회색 + 연한 배경
  classDef ops fill:#F8FAFC,stroke:#94A3B8,stroke-width:1px,stroke-dasharray:4 4,color:#64748B;

  linkStyle 5,6,7 stroke:#E11D48,stroke-width:1.6px,stroke-dasharray:6 3;

  %% LOG 연결선도 더 "배경" 느낌으로
  linkStyle 15 stroke:#94A3B8,stroke-width:1px,stroke-dasharray:4 4;
```

- **프론트엔드**: Streamlit UI + HTML 브릭 표(components/brick_table.py)
- **워크플로우**: LangGraph 기반 Multi-Agent (workflow/graph.py)
- **백엔드**: Azure OpenAI LLM/Embeddings, Chroma VectorStore, Rebrickable API 연동
- **로깅**: 콘솔 + app/logs/app.log 파일 (UTC+9, 순환 로그)

### 3.1. 어린이용

```mermaid
%%{init: {
  "theme": "neutral",
  "background": "white",
  "flowchart": { "nodeSpacing": 20, "rankSpacing": 55 },
  "themeVariables": {
    "primaryColor": "#F0F9FF",
    "primaryTextColor": "#1E293B",
    "lineColor": "#94A3B8",
    "tertiaryColor": "#FFFFFF",
    "fontSize": "16px"
  }
}}%%
flowchart TB

  %% 👦 사용자
  U(["👦 사용자"]):::user

  %% 🖥️ 화면 (Streamlit 같은 기술명 제거)
  UI(["🖥️ 레고 만드는 화면"]):::ui
  BT(["🧱 부품 표(목록)"]):::ui

  %% 🤖 로봇 친구들(에이전트)
  subgraph AI["🤖 생각하는 로봇 친구들"]
    direction TB
    R(["1) 무엇을 만들까?"]):::agent
    D(["2) 어떻게 만들까?"]):::agent
    F(["3) 더 보기 좋게 정리하기"]):::agent
  end

  %% 📚 레고 책장(지식)
  subgraph BOOKS["📚 레고 책장"]
    direction TB
    K(["레고 설명/규칙 모음"]):::book
    VS(["찾기 도우미(검색 상자)"]):::book
  end

  %% 🛒 부품 정보 가져오기(외부)
  SHOP(["🛒 부품 정보 가져오기"]):::shop

  %% 🧾 기록(로그)
  LOG(["🧾 작업 기록장"]):::log

  %% 🔗 연결
  U --> UI

  UI --> R
  R --> D
  D --> F
  F --> UI

  R --> VS
  D --> VS
  F --> VS
  VS --> K

  UI -- "부품 이름/사진 찾기" --> SHOP
  SHOP --> BT
  BT --> UI

  UI --> LOG

  %% 🎨 스타일
  classDef user fill:#FFF7ED,stroke:#FB923C,color:#7C2D12;
  classDef ui fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E;
  classDef agent fill:#ECFDF5,stroke:#22C55E,color:#14532D;
  classDef book fill:#EEF2FF,stroke:#6366F1,color:#312E81;
  classDef shop fill:#FEF2F2,stroke:#EF4444,color:#7F1D1D;
  classDef log fill:#F8FAFC,stroke:#94A3B8,stroke-width:1px,stroke-dasharray:4 4,color:#64748B;
```

---

## 📌 4. 프로젝트 구조(전체 트리)

```text
lego-ai-service/
├─ app/
│  ├─ main.py                     # Streamlit 엔트리 + 브릭 표 파싱/렌더링
│  ├─ components/
│  │  ├─ sidebar.py               # 사이드바 UI 구성
│  │  └─ brick_table.py           # 브릭/부품 HTML 테이블 생성
│  ├─ workflow/
│  │  ├─ state.py                 # LegoState / AgentRole 정의
│  │  ├─ graph.py                 # LangGraph 워크플로우 정의
│  │  └─ agents/
│  │     ├─ base_agent.py         # 공통 에이전트 베이스 클래스
│  │     ├─ requirements_agent.py # 요구사항 분석 에이전트
│  │     ├─ design_agent.py       # 설계 제안 에이전트
│  │     └─ refiner_agent.py      # 최종 정리/문서화 에이전트
│  ├─ retrieval/
│  │  ├─ vector_store.py          # Chroma 기반 RAG 벡터스토어
│  │  ├─ knowledge/               # 레고 지식 Markdown 문서들 (*.md)
│  │  └─ chroma_db/               # 최초 실행 시 자동 생성되는 벡터 DB
│  └─ utils/
│     ├─ config.py                # Azure OpenAI LLM/Embedding/Image 설정, 에이전트별 모델 선택
│     ├─ rebrickable_client.py    # Rebrickable API 클라이언트
│     ├─ image_gen.py             # 완성 예상 이미지 생성 (gpt-image)
│     └─ blueprint.py             # 층별 조립 도안 생성/검증/SVG 렌더링
│
├─ images/                        # README용 스크린샷/이미지
├─ mermaid/                       # (선택) 다이어그램 원본 .mmd 파일
│
├─ .streamlit/config.toml         # Streamlit 서버/브라우저 설정
│
├─ .env.example                   # 환경변수 템플릿
├─ .gitignore
├─ .gitattributes                 # *.sh 는 LF 고정
├─ run.ps1 / run.bat / run.sh     # .venv 준비 + 자동 설치 + 실행
├─ Dockerfile
├─ docker-compose.yml             # 로컬 개발용 docker-compose 설정
├─ requirements.txt
├─ test_azure_openai.py           # Azure OpenAI 연결 테스트 스크립트
└─ README.md
```

## 📌 5. 주요 모듈 설명

| 모듈 경로                     | 역할 요약                                                  |
| ----------------------------- | ---------------------------------------------------------- |
| `app/main.py`                 | Streamlit 메인 실행, LangGraph 스트리밍 호출/중지, 결과 & 브릭 표 렌더링, 이미지·도안 병렬 생성 |
| `components/sidebar.py`       | 사용자 입력 UI, 입력값을 LegoState로 변환                  |
| `components/brick_table.py`   | 브릭 제안 파싱, Rebrickable API 조회, HTML 표 생성         |
| `utils/rebrickable_client.py` | Rebrickable API 호출(부품 번호/이름/이미지 조회)           |
| `workflow/state.py`           | LangGraph 상태(LegoState) 정의                             |
| `workflow/graph.py`           | Multi-Agent 실행 플로우 구성 (Req → Design → Refiner)      |
| `workflow/agents/*`           | 세부 에이전트 구현 (요구/설계/정리)                        |
| `retrieval/vector_store.py`   | Chroma 기반 RAG 검색 엔진 구성                             |
| `utils/config.py`             | Azure OpenAI 설정 로드, LLM/Embeddings/Image 설정, 에이전트별 모델 선택 (`get_llm_for_agent`) |
| `utils/image_gen.py`          | 최종 가이드 → 이미지 프롬프트 → gpt-image 완성 예상 이미지 |
| `utils/blueprint.py`          | 층별 조립 도안: 구조화 출력 → 검증(범위/겹침/지지) → SVG 렌더링 |

## 📌 6. 환경변수 설정 (.env 예시)

Azure OpenAI를 사용하기 위한 환경변수입니다.  
`.env.example`을 복사하여 `.env` 파일을 만들고, 실제 값으로 수정해 주세요.

```bash
# == Azure Foundry 리소스 ==
AOAI_ENDPOINT=https://{your-resource-name}.openai.azure.com/
AOAI_API_KEY=YOUR_AOAI_KEY
AOAI_API_VERSION=2024-02-01

# == Chat 모델 배포 ==
# 기본 모델 (빠르고 저렴)
AOAI_DEPLOY_CHAT=gpt-5.6-luna
# 고성능 모델
AOAI_DEPLOY_CHAT_PRO=gpt-6-sol
# 고성능 모델을 쓸 에이전트 (쉼표 구분: REQUIREMENTS, DESIGN, REFINER, BLUEPRINT(조립 도안) / 비우면 전부 기본 모델)
AOAI_PRO_AGENTS=

# LLM temperature (비우면 모델 기본값 사용, gpt-5.x 이상은 비워 둘 것)
AOAI_TEMPERATURE=

# == Embedding 모델 배포 ==
AOAI_DEPLOY_EMBED_3_LARGE=text-embedding-3-large
AOAI_DEPLOY_EMBED_3_SMALL=
AOAI_DEPLOY_EMBED_ADA=

# == 이미지 생성 (완성 예상 이미지, 선택) ==
# 비우면 이미지 기능 비활성화. 엔드포인트/키를 비우면 AOAI_ENDPOINT / AOAI_API_KEY 사용
AOAI_DEPLOY_IMAGE=gpt-image-2
AOAI_IMAGE_ENDPOINT=https://<image-resource>.services.ai.azure.com/
AOAI_IMAGE_API_KEY=YOUR_KEY
AOAI_IMAGE_API_VERSION=2025-04-01-preview
AOAI_IMAGE_QUALITY=low

# == Rebrickable API ==
REBRICKABLE_API_KEY=YOUR_REBRICKABLE_KEY
REBRICKABLE_API_BASE=https://rebrickable.com/api/v3
```

---

## 📌 7. 실행 방법

사전 요구사항

- Python 3.10+ (권장: 3.11)
- Docker & Docker Compose (선택 사항, Docker 기반 실행 시)
- Azure OpenAI (Foundry) 리소스
- Rebrickable API Key (브릭 이미지/이름 조회 시 활용)

### 1) 로컬(가상환경) 실행

```bash
git clone https://github.com/pcmola/lego-ai-service.git
cd lego-ai-service

cp .env.example .env
# .env 파일을 열어 Azure OpenAI / Rebrickable 설정값 수정

# Windows (PowerShell / cmd)
./run.ps1        # 또는 run.bat
# Git Bash / macOS / Linux
./run.sh
```

- run 스크립트가 `.venv` 생성과 `requirements.txt` 설치를 자동으로 처리합니다.
  - `.venv` 가 없으면 새로 만들고, `requirements.txt` 가 바뀌면 다시 설치합니다.
  - 항상 `.venv` 의 Python 으로 실행하며 전역 Python 은 사용하지 않습니다.

- Streamlit 앱 실행 후 브라우저에서 아래 주소로 접속합니다.
  - ➡ <http://localhost:8501>
- 첫 실행 시
  - `app/retrieval/chroma_db/` 디렉터리가 생성되며, 지식 문서 임베딩이 저장됩니다.
  - `app/logs/app.log` 에 상세 로그가 남습니다.

### 2) Docker 단일 컨테이너 실행

```bash
docker build -t lego-agent .
docker run -it --rm -p 8501:8501 --env-file .env lego-agent
```

- 코드 변경 시에는 이미지를 다시 빌드해야 반영됩니다.

### 3) Docker Compose 실행 (개발용 hot reload)

`docker-compose.yml`을 이용하면 로컬 코드 변경이 컨테이너에 바로 반영됩니다.

```bash
docker-compose up --build
# 이후부터는 코드만 수정하고
# docker-compose up   # 으로 재시작하면 됨
```

- 주요 설정

  - 포트 매핑: `8501:8501`
  - 볼륨 마운트

    - `./app:/app/app`
    - `./retrieval:/app/retrieval`

  - 커맨드: `streamlit run app/main.py --server.port=8501 --server.address=0.0.0.0`

---

## 📌 8. Azure OpenAI 연결 테스트

이 프로젝트가 Azure OpenAI와 정상적으로 통신하는지 확인하려면  
아래 스크립트를 실행하여 LLM 및 Embedding 모델을 테스트할 수 있습니다.

```bash
python test_azure_openai.py
```

### 테스트 내용

- test_azure_openai.py는 다음 항목을 점검합니다:
  - 기본 LLM 테스트 (gpt-5.6-luna)
  - 간단한 질문을 보내 응답이 정상적으로 반환되는지 확인
- 고성능 LLM 테스트 (gpt-6-sol)
  - 모델 배포명이 .env와 일치하는지 검증
- Embedding 모델 테스트 (text-embedding-3-large)
  - 벡터 길이 및 생성 여부 확인

### 정상 출력 예시

- 각 모델에서 한 줄 요약 응답 출력
- Embedding 벡터 크기 출력 (예: 3072)

### 오류가 발생할 경우 확인할 사항

- .env에 설정된 아래 값이 올바른지 확인
  - AOAI_ENDPOINT
  - AOAI_API_KEY
  - AOAI_API_VERSION
  - AOAI_DEPLOY_CHAT, AOAI_DEPLOY_CHAT_PRO (구 변수명 AOAI_DEPLOY_GPT4O_MINI / AOAI_DEPLOY_GPT4O 도 인식)
  - AOAI_DEPLOY_EMBED_3_LARGE
- 네트워크 또는 방화벽 정책
- Azure OpenAI 리소스 모델 배포명 오타 여부

문제가 지속되면 `app/logs/app.log` 파일에서 상세 오류 원인을 확인할 수 있습니다.

## 📌 9. TODO (향후 개선 예정)

- [x] 최신 모델 적용 (gpt-5.6-luna / gpt-6-sol) 및 에이전트별 모델 지정
- [x] 응답 스트리밍 · 진행 표시 · 중지 버튼
- [x] 완성 예상 이미지 / 층별 조립 도안 (v1)
- [ ] 도안 부품 번호 ↔ 크기 일치 검증 (Rebrickable 데이터 활용)
- [ ] 최종 정리(Refiner) 출력 축소로 전체 응답 시간 단축
- [ ] 3D 뷰어 (LDraw + three.js) 검토
- [ ] `components.html` → `st.iframe` 전환 (Streamlit 사용 중지 예정 API)
- [ ] 브릭/부품 제안 파싱 정확도 개선
- [ ] Rebrickable API 캐싱 및 대체 파트 처리 강화 (404 재조회 방지는 반영)
- [ ] 브릭 표 기능 고도화 (색상/수량 인식)
- [ ] RAG 지식 문서 확장
- [ ] Streamlit UI 개선 (히스토리, Export 기능)
- [ ] 에이전트/파트 파싱 테스트 코드 보강

## 📌 10. 문의

### 🙋‍♂️ 문의 / 협업 제안

이 프로젝트와 관련된 이슈, 버그 리포트, 기능 제안 등은 아래 채널을 활용해주세요.

- GitHub 이슈: https://github.com/pcmola/lego-ai-service/issues
- Maintainer: **Jongyoon Won (메이커 꾸러기)**
- GitHub: https://github.com/pcmola
- Blog: http://pcmola.com
- Email: pcmola@naver.com

Pull Request / 코드 리뷰 / 아이디어 제안 모두 환영합니다. 🙂

---

### 🧱 LEGO 상표 관련 안내

- LEGO® 및 레고 로고는 The LEGO Group의 상표입니다.
- 본 프로젝트는 The LEGO Group과 공식적인 제휴·후원·승인을 받은 프로젝트가 아니며,  
  비상업적·팬 메이드(팬 프로젝트)로 운영됩니다.

## 📌 11. 결과 예시

<details>
<summary><strong>📂 클릭하여 결과 예시 펼치기 / 접기</strong></summary>
<br>

아래는 레고 창작 AI Agent가 실제로 생성하는 화면 예시입니다.  
사용자 입력 → 에이전트 협업 → 브릭/부품 표 생성까지의 전체 흐름을 확인할 수 있습니다.

---

### 1) 초기 생성 결과 화면

사용자가 아이디어(컨셉·크기·용도 등)를 입력하면,  
Multi-Agent Workflow가 자동으로 요구사항을 분석하고 설계를 시작합니다.

<img src="./images/01.InitResult.png" width="1007">

---

### 2) AI 설계 결과 (최종 요약 + 구조 가이드)

아래는 RefinerAgent가 생성한 최종 문서 예시입니다.

- 전체 설계 요약
- 구조적 고려사항
- 전시 안정성 팁
- 색상·모듈 구성 가이드 등이 포함됩니다.

<img src="./images/03.AI-Result2.png" width="1232">

---

### 3) 브릭/부품 제안 표 (Rebrickable API 연동)

AI가 생성한 “브릭/부품 제안 섹션”을 파싱하여  
각 부품 번호·이미지·공식 이름을 Rebrickable API에서 자동으로 조회합니다.

아래는 실제 Streamlit 화면에 표시되는 HTML 테이블 예시입니다.

<img src="./images/04.AI-Result3.png" width="1232">

- 부품 번호 → Rebrickable API로 검색
- 공식 영문 이름, 이미지 자동 삽입
- 설명/용도는 AI가 해석하여 자연어로 정리
- 스크롤 가능한 표 형태로 UI에 표시됨

---

이와 같은 방식으로  
**사용자 아이디어 → 구조 설계 → 브릭 제안 → 시각화**  
까지 전체 파이프라인이 자동 실행됩니다.

</details>
