import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

# 현재 작업 폴더(.env) 로드
load_dotenv()


def _get_azure_base() -> tuple[str, str, str]:
    """기본 Azure OpenAI 설정(AOAI_ENDPOINT, AOAI_API_KEY, AOAI_API_VERSION) 가져오기"""
    endpoint = os.getenv("AOAI_ENDPOINT")
    api_key = os.getenv("AOAI_API_KEY")
    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure OpenAI 환경변수가 올바르게 설정되지 않았습니다.\n"
            "AOAI_ENDPOINT, AOAI_API_KEY를 확인하세요."
        )

    api_version = os.getenv("AOAI_API_VERSION") or "2024-02-01"
    return endpoint, api_key, api_version


def _get_env(name: str) -> str | None:
    """환경변수 공백 제거해서 가져오기"""
    value = os.getenv(name)
    return value.strip() if value else None


def _chat_deployment(pro: bool) -> str | None:
    """Chat 배포명 조회. (구 변수명 AOAI_DEPLOY_GPT4O[_MINI] 도 하위호환으로 인식)"""
    default = _get_env("AOAI_DEPLOY_CHAT") or _get_env("AOAI_DEPLOY_GPT4O_MINI")
    pro_dep = _get_env("AOAI_DEPLOY_CHAT_PRO") or _get_env("AOAI_DEPLOY_GPT4O")
    # 원하는 쪽이 없으면 다른 쪽으로 fallback
    return (pro_dep or default) if pro else (default or pro_dep)


def get_llm(tier: str | None = None) -> AzureChatOpenAI:
    """
    Azure OpenAI LLM 생성

    - tier=None   -> AOAI_DEPLOY_CHAT     (기본 모델: 빠르고 저렴, 예: gpt-5.6-luna)
    - tier="pro"  -> AOAI_DEPLOY_CHAT_PRO (고성능 모델, 예: gpt-6-sol)
    """
    endpoint, api_key, api_version = _get_azure_base()

    pro = tier in ("pro", "gpt4o")  # "gpt4o" 는 구버전 호출 호환용
    deployment = _chat_deployment(pro)

    if not deployment:
        raise RuntimeError(
            "LLM 배포명이 설정되지 않았습니다.\n"
            "AOAI_DEPLOY_CHAT 또는 AOAI_DEPLOY_CHAT_PRO 를 확인하세요."
        )

    # AOAI_TEMPERATURE 미설정/빈 값이면 temperature를 넘기지 않음
    # (gpt-5.x 등 추론형 모델은 기본값(1) 외의 temperature를 거부함)
    kwargs = {}
    temperature = _get_env("AOAI_TEMPERATURE")
    if temperature:
        kwargs["temperature"] = float(temperature)

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        openai_api_key=api_key,
        api_version=api_version,
        **kwargs,
    )


def get_image_settings() -> dict | None:
    """
    이미지 생성(완성 예상 이미지) 설정. 별도 리소스일 수 있어 엔드포인트/키를 따로 받음.
    AOAI_DEPLOY_IMAGE 가 비어 있으면 None → 이미지 기능 비활성화.
    엔드포인트/키를 비우면 기본 AOAI_ENDPOINT / AOAI_API_KEY 사용.
    """
    deployment = _get_env("AOAI_DEPLOY_IMAGE")
    if not deployment:
        return None
    return {
        "endpoint": _get_env("AOAI_IMAGE_ENDPOINT") or _get_env("AOAI_ENDPOINT"),
        "api_key": _get_env("AOAI_IMAGE_API_KEY") or _get_env("AOAI_API_KEY"),
        "api_version": _get_env("AOAI_IMAGE_API_VERSION") or "2025-04-01-preview",
        "deployment": deployment,
        "quality": _get_env("AOAI_IMAGE_QUALITY") or "low",  # low | medium | high
        "size": _get_env("AOAI_IMAGE_SIZE") or "1024x1024",
    }


def get_llm_for_agent(role: str) -> AzureChatOpenAI:
    """
    에이전트 역할별 LLM 선택

    AOAI_PRO_AGENTS 에 쉼표로 나열한 역할만 고성능(pro) 모델 사용, 나머지는 기본 모델.
    역할: REQUIREMENTS, DESIGN, REFINER  (대소문자 무관, 예: AOAI_PRO_AGENTS=DESIGN)
    """
    pro_agents = {r.strip().upper() for r in (_get_env("AOAI_PRO_AGENTS") or "").split(",") if r.strip()}
    return get_llm("pro" if role.upper() in pro_agents else None)


def get_embeddings(embed_preference: str | None = None) -> AzureOpenAIEmbeddings:
    """
    Azure OpenAI 임베딩 모델 생성

    - embed_preference="large" -> AOAI_DEPLOY_EMBED_3_LARGE 강제
    - 그 외 -> SMALL/ADA/3_LARGE 순으로 fallback
    """
    endpoint, api_key, api_version = _get_azure_base()

    if embed_preference == "large" and _get_env("AOAI_DEPLOY_EMBED_3_LARGE"):
        deployment = _get_env("AOAI_DEPLOY_EMBED_3_LARGE")
    else:
        deployment = (
            _get_env("AOAI_DEPLOY_EMBED_3_SMALL")
            or _get_env("AOAI_DEPLOY_EMBED_ADA")
            or _get_env("AOAI_DEPLOY_EMBED_3_LARGE")
        )

    if not deployment:
        raise RuntimeError(
            "임베딩 배포명이 설정되지 않았습니다.\n"
            "AOAI_DEPLOY_EMBED_3_LARGE (또는 SMALL/ADA)을 확인하세요."
        )

    return AzureOpenAIEmbeddings(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        openai_api_key=api_key,
        api_version=api_version,
    )
