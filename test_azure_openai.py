# test_azure_openai.py

from app.utils.config import get_llm, get_embeddings


def test_chat_models() -> None:
    print("=== 기본 LLM (gpt-4.1-mini 예상) 테스트 ===")
    llm_default = get_llm()
    resp1 = llm_default.invoke("Azure OpenAI 기본 모델 연결 테스트입니다. 한 줄로 답해주세요.")
    print("기본 모델 응답:", resp1)

    print("\n=== 고성능 LLM (gpt-4.1 예상, preference='gpt4o') 테스트 ===")
    llm_strong = get_llm("gpt4o")
    resp2 = llm_strong.invoke("고성능 모델 연결 테스트입니다. 한 줄로 답해주세요.")
    print("고성능 모델 응답:", resp2)


def test_embeddings() -> None:
    print("\n=== 임베딩 모델(text-embedding-3-large) 테스트 ===")
    embed = get_embeddings("large")
    vec = embed.embed_query("임베딩 벡터 생성이 잘 되는지 테스트합니다.")
    print("임베딩 벡터 길이:", len(vec))
    print("앞 5개 값:", vec[:5])


if __name__ == "__main__":
    test_chat_models()
    test_embeddings()
