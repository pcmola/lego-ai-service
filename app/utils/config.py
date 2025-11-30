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


def get_llm(model_preference: str | None = None) -> AzureChatOpenAI:
    """
    Azure OpenAI LLM 생성

    - model_preference=None  -> AOAI_DEPLOY_GPT4O_MINI 사용 (기본: gpt-4.1-mini)
    - model_preference="gpt4o" -> AOAI_DEPLOY_GPT4O 사용 (기본: gpt-4.1)
    """
    endpoint, api_key, api_version = _get_azure_base()

    if model_preference == "gpt4o":
        # 고성능 모델 우선, 없으면 mini fallback
        deployment = _get_env("AOAI_DEPLOY_GPT4O") or _get_env("AOAI_DEPLOY_GPT4O_MINI")
    else:
        # 기본은 mini, 없으면 고성능
        deployment = _get_env("AOAI_DEPLOY_GPT4O_MINI") or _get_env("AOAI_DEPLOY_GPT4O")

    if not deployment:
        raise RuntimeError(
            "LLM 배포명이 설정되지 않았습니다.\n"
            "AOAI_DEPLOY_GPT4O_MINI 또는 AOAI_DEPLOY_GPT4O 를 확인하세요."
        )

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        openai_api_key=api_key,
        api_version=api_version,
        temperature=0.7,
    )


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
