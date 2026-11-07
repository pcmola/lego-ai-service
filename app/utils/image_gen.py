"""완성 예상 이미지 생성 (Azure OpenAI gpt-image)

최종 설계 가이드 → (기본 LLM) 짧은 영어 이미지 프롬프트 → (이미지 모델) PNG
※ 실제 부품 구성과 일치하지 않는 '분위기용 예상 이미지'입니다.
"""
import base64
import logging
from typing import Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from openai import AzureOpenAI

from utils.config import get_image_settings, get_llm

logger = logging.getLogger(__name__)

_PROMPT_WRITER = """You write prompts for an image generator.
Read the LEGO-style build guide (Korean) and describe the FINISHED model in English, max 80 words:
overall shape, approximate size/scale, main colors, 3-5 distinctive features.
Describe only the physical model. Do not mention brand names, logos, printed text or licensed characters.
Output only the description."""

_STYLE_SUFFIX = (
    " Style: realistic product photo of a finished model built from plastic toy construction bricks "
    "with visible studs, three-quarter view, soft studio lighting, plain light background. "
    "No logos, no brand marks, no text, no stickers."
)


def is_enabled() -> bool:
    return get_image_settings() is not None


def build_image_prompt(answer: str) -> str:
    llm = get_llm()
    resp = llm.invoke(
        [SystemMessage(content=_PROMPT_WRITER), HumanMessage(content=answer[:8000])]
    )
    desc = (resp.content or "").strip().replace("\n", " ")
    return desc + _STYLE_SUFFIX


def generate_image(prompt: str) -> bytes:
    cfg = get_image_settings()
    if not cfg:
        raise RuntimeError("AOAI_DEPLOY_IMAGE 가 설정되지 않았습니다.")
    client = AzureOpenAI(
        azure_endpoint=cfg["endpoint"],
        api_key=cfg["api_key"],
        api_version=cfg["api_version"],
    )
    result = client.images.generate(
        model=cfg["deployment"],
        prompt=prompt,
        size=cfg["size"],
        quality=cfg["quality"],
        n=1,
    )
    return base64.b64decode(result.data[0].b64_json)


def generate_preview(answer: str) -> Tuple[bytes, str]:
    """최종 가이드로부터 완성 예상 이미지 생성 → (PNG bytes, 사용한 프롬프트)"""
    prompt = build_image_prompt(answer)
    logger.info("[image] prompt: %s", prompt)
    return generate_image(prompt), prompt
