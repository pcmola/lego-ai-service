# 레고 창작 AI Agent (Multi-Agent + RAG + Streamlit)

<img src="./images/01.InitResult.png" width="1007">

**[그림 1] 레고 창작 Agent의 초기 생성 결과 화면**

레고 창작 설계용 Multi-Agent 기반 에이전트 프로젝트입니다.  
사용자가 만들고 싶은 레고 작품의 컨셉·크기·용도 등을 입력하면, 여러 에이전트가 협업하여 <br/>
**요구사항 분석 → 구조 설계 → 최종 가이드 생성**까지 자동으로 수행합니다.

---

## ⭐ 주요 특징

- **Multi-Agent + LangGraph** 기반 워크플로우
- **RAG 기반 지식검색**(레고 관련 기초 문서)
- **Streamlit UI**로 간단한 브라우저 실행
- **Azure OpenAI GPT-4o / GPT-4o-mini** 활용

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

다음 단계로 구성됩니다:

1. 사용자 입력
2. 요구사항 분석(Requirements Agent)
3. 설계 제안(Design Agent)
4. RAG 기반 지식 강화
5. 최종 결과 정리(Refiner Agent)
6. Streamlit UI 출력

---

## 📌 2. 사용자 흐름 (User Flow)

```mermaid
flowchart TD
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

    %% ===================== 플로우 =====================
    Input --> Start --> A1 --> A2 --> A3 --> P --> Rb --> T --> Out

    A1 --> RAG
    A2 --> RAG
    A3 --> RAG

```

- 사용자가 사이드바 + 자유 텍스트로 아이디어를 입력합니다.
- LangGraph가 Requirements → Design → Refiner 에이전트를 순차 실행합니다.
- Refiner 결과 안의 "브릭/부품 제안"”" 섹션을 main.py에서 따로 파싱합니다.
- 각 행의 부품 번호를 기준으로 Rebrickable API 를 호출해 이미지·영문명 등을 채웁니다.
- brick_table.py에서 HTML 테이블을 생성해 Streamlit에서 스크롤 가능한 표로 렌더링합니다.

---

## 📌 3. 서비스 아키텍처

```mermaid
%%{init: {
  "theme": "neutral",
  "flowchart": { "nodeSpacing": 20, "rankSpacing": 25 },
  "themeVariables": {
    "primaryColor": "#e3f2fd",
    "primaryTextColor": "#111111",
    "lineColor": "#555555",
    "tertiaryColor": "#ffffff",
    "fontSize": "12px"
  }
}}%%
flowchart TB

    U([사용자 브라우저]):::client
    UI([Streamlit 앱<br/>app/main.py<br/>+ components/*]):::ui
    G([LangGraph App<br/>workflow/graph.py]):::orchestrator

    R([RequirementsAgent]):::agent
    D([DesignAgent]):::agent
    F([RefinerAgent]):::agent

    E([Azure OpenAI<br/>Embeddings]):::service
    LLM([Azure OpenAI<br/>LLM<br/>gpt-4.1-mini · gpt-4.1]):::service

    VS([Chroma VectorStore<br/>app/retrieval/vector_store.py]):::store
    K["레고 지식 문서<br/>app/retrieval/knowledge/*.md"]:::knowledge

    RB([Rebrickable API<br/>app/utils/rebrickable_client.py]):::service
    BT([브릭/부품 HTML 표<br/>app/components/brick_table.py]):::ui
    LOG([로그 파일<br/>app/logs/app.log]):::store

    U --> UI --> G
    G --> R --> E
    R --> VS
    G --> D --> LLM
    D --> VS
    G --> F --> LLM
    VS --> K
    UI -- "최종 답변 중 5번 섹션 파싱" --> RB --> BT --> UI
    UI --> LOG

    classDef client fill:#ffffff,stroke:#777;
    classDef ui fill:#e3f2fd,stroke:#1e88e5;
    classDef orchestrator fill:#ede7f6,stroke:#8e24aa;
    classDef agent fill:#e8f5e9,stroke:#43a047;
    classDef service fill:#ffebee,stroke:#e53935;
    classDef store fill:#fff8e1,stroke:#f9a825;
    classDef knowledge fill:#e0f7fa,stroke:#00838f;

```

- **프론트엔드**: Streamlit UI + HTML 브릭 표(components/brick_table.py)
- **워크플로우**: LangGraph 기반 Multi-Agent (workflow/graph.py)
- **백엔드**: Azure OpenAI LLM/Embeddings, Chroma VectorStore, Rebrickable API 연동
- **로깅**: 콘솔 + app/logs/app.log 파일 (UTC+9, 순환 로그)

---

## 📌 4. 프로젝트 구조(전체 트리)

```text
lego-ai-service/
├─ app/
│  ├─ main.py                      # Streamlit 엔트리 + 브릭 표 파싱/렌더링
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
│     ├─ config.py                # Azure OpenAI LLM/Embedding 팩토리
│     └─ rebrickable_client.py    # Rebrickable API 클라이언트
│
├─ images/                        # README용 스크린샷/이미지
├─ mermaid/                       # (선택) 다이어그램 원본 .mmd 파일
│
├─ .env.example                   # 환경변수 템플릿
├─ .gitignore
├─ Dockerfile
├─ docker-compose.yml             # 로컬 개발용 docker-compose 설정
├─ requirements.txt
├─ test_azure_openai.py           # Azure OpenAI 연결 테스트 스크립트
└─ README.md
```

## 📌 5. 주요 모듈 설명

### `app/main.py`

Streamlit 메인 실행 파일.  
사용자 입력을 받아 LangGraph 워크플로우를 실행하고,  
결과 중 “5. 브릭/부품 제안” 섹션을 파싱하여 HTML 표로 렌더링합니다.

### `app/components/sidebar.py`

규모/용도/난이도/보유 부품 등 사용자 입력을 받는 사이드바 UI 구성.

### `app/components/brick_table.py`

브릭/부품 제안 리스트를 HTML 테이블로 생성.  
Rebrickable API로 부품명·이미지 보완, 중복 제거, 불명확한 번호는 검색으로 자동 보정.

### `app/workflow/graph.py`

Requirements → Design → Refiner 에이전트를 순차 실행하는 LangGraph 정의.

### `app/workflow/state.py`

에이전트 간 공유되는 상태(LegoState)와 역할(AgentRole) 정의.

### `app/workflow/agents/*`

- `requirements_agent.py`: 요구사항 분석
- `design_agent.py`: 구조·부품 설계 제안
- `refiner_agent.py`: 최종 문서 정리
- `base_agent.py`: 공통 LLM 호출/프롬프트 처리 로직

### `app/retrieval/vector_store.py`

레고 지식 문서를 임베딩하여 Chroma DB에 저장하고  
에이전트가 RAG 검색을 수행할 수 있도록 지원.

### `app/utils/config.py`

Azure OpenAI LLM·Embedding 설정 및 모델 선택 로직.

### `app/utils/rebrickable_client.py`

Rebrickable API 클라이언트.  
부품 조회(번호·검색), 대체 번호 매핑, 캐싱, 호출 제한 관리.

## 📌 6. 환경변수 설정 (.env 예시)

Azure OpenAI를 사용하기 위한 환경변수입니다.  
`.env.example`을 복사하여 `.env` 파일을 만들고, 실제 값으로 수정해 주세요.

```bash
# == Azure Foundry 리소스 ==
AOAI_ENDPOINT=https://{your-resource-name}.openai.azure.com/
AOAI_API_KEY=YOUR_AOAI_KEY
AOAI_API_VERSION=2024-02-01

# == Chat 모델 배포 ==
# 기본 모델 (mini)
AOAI_DEPLOY_GPT4O_MINI=gpt-4.1-mini
# 고성능 모델
AOAI_DEPLOY_GPT4O=gpt-4.1

# == Embedding 모델 배포 ==
AOAI_DEPLOY_EMBED_3_LARGE=text-embedding-3-large
AOAI_DEPLOY_EMBED_3_SMALL=
AOAI_DEPLOY_EMBED_ADA=

# == Rebrickable API ==
REBRICKABLE_API_KEY=YOUR_REBRICKABLE_KEY
REBRICKABLE_API_BASE=https://rebrickable.com/api/v3
```

---

## 📌 7. 실행 방법

### 1) 로컬(가상환경) 실행

```bash
git clone https://github.com/pcmola/lego-ai-service.git
cd lego-ai-service

python -m venv .venv
# Windows PowerShell
#   .venv\Scripts\Activate.ps1
# macOS / Linux
#   source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# .env 파일을 열어 Azure OpenAI / Rebrickable 설정값 수정

streamlit run app/main.py
```

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

    ```

    ```

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
  - 기본 LLM 테스트 (gpt-4.1-mini)
  - 간단한 질문을 보내 응답이 정상적으로 반환되는지 확인
- 고성능 LLM 테스트 (gpt-4.1)
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
  - AOAI_DEPLOY_GPT4O_MINI, AOAI_DEPLOY_GPT4O
  - AOAI_DEPLOY_EMBED_3_LARGE
- 네트워크 또는 방화벽 정책
- Azure OpenAI 리소스 모델 배포명 오타 여부

문제가 지속되면 `app/logs/app.log` 파일에서 상세 오류 원인을 확인할 수 있습니다.

## 📌 9. TODO (향후 개선 예정)

- [ ] RAG 지식 문서 확장
- [ ] LEGO 브릭(Parts) 리스트 자동 생성 기능
- [ ] 결과물 Markdown / PDF Export 기능
- [ ] 다중 설계안(옵션 A/B/C) 생성 기능
- [ ] 이미지 기반 설계 보조 기능 (예: 사진 입력 → 구조 분석)
- [ ] Streamlit UI 고도화 (단계별 화면, 히스토리 관리 등)

## 📌 10. 문의

프로젝트 관련 문의 또는 협업 제안은 아래 연락처를 통해 가능합니다.

- **Author:** 메이커 꾸러기 (Jongyoon Won)
- **GitHub:** https://github.com/pcmola
- **Blog:** http://pcmola.com
- **Email:** pcmola@naver.com

## 📌 11. 결과 예시

### 🔹레고 창작 Agent 결과 화면

<img src="./images/03.AI-Result2.png" width="1232">

**[그림 2] AI가 생성한 최종 레고 설계 결과 화면**

<img src="./images/04.AI-Result3.png" width="1232">

**[그림 3] 리브리커블과 연동하여 레고 부품 정보 표시**
