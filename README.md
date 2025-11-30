# 레고 창작 AI Agent (Multi-Agent + RAG + Streamlit)

레고 창작 설계용 Multi-Agent 에이전트입니다.

## 사용자 흐름 다이어그램

<img src="./images/01. UserFlowDiagram.png" width="411">

## 서비스 아키텍처 다이어그램

<img src="./images/02. ServiceArchitectureDiagram.png" width="1394">

## 구조

- app/main.py : Streamlit 진입점
- app/components/sidebar.py : 사이드바 입력 UI
- app/workflow/state.py : LegoState, AgentRole 정의
- app/workflow/graph.py : LangGraph Multi-Agent 워크플로우
- app/workflow/agents/
  - base_agent.py : 공통 에이전트 로직
  - requirements_agent.py : 요구사항 분석 에이전트
  - design_agent.py : 설계 생성 에이전트
  - refiner_agent.py : 최종 정리 에이전트
- app/retrieval/vector_store.py : Chroma 기반 RAG
- app/retrieval/knowledge/\*.md : 레고 관련 기초 지식 문서
- app/utils/config.py : Azure OpenAI LLM/임베딩 설정
- .env : AOAI 환경변수

## 실행

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

또는 Docker:

```bash
docker build -t lego-agent .
docker run -it --rm -p 8501:8501 --env-file .env lego-agent
```

# 레고 창작 Agent 최초 실행 화면

<img src="./images/03. InitResult.png" width="1007">

# 레고 창작 Agent 결과 화면

<img src="./images/04. AI-Result.png" width="976">
