import os
import glob
from functools import lru_cache
from typing import List, Dict, Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config import get_embeddings

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "retrieval", "knowledge")
PERSIST_DIR = os.path.join(BASE_DIR, "retrieval", "chroma_db")


def _load_lego_docs() -> List[Document]:
    docs: List[Document] = []
    pattern = os.path.join(KNOWLEDGE_DIR, "*.md")
    for path in glob.glob(pattern):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        name = os.path.basename(path)
        docs.append(Document(page_content=text, metadata={"source": name}))
    return docs


def _build_vectorstore():
    os.makedirs(PERSIST_DIR, exist_ok=True)
    embeddings = get_embeddings()
    docs = _load_lego_docs()
    if not docs:
        raise RuntimeError(f"지식 문서를 찾을 수 없습니다: {KNOWLEDGE_DIR}")
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    vs = Chroma.from_documents(
        chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )
    return vs


@lru_cache(maxsize=1)
def get_vectorstore():
    """벡터스토어는 프로세스당 한 번만 열고 재사용 (검색마다 Chroma/임베딩 클라이언트 재생성 방지)"""
    has_db = os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR)
    if not has_db:
        return _build_vectorstore()
    embeddings = get_embeddings()
    vs = Chroma(
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR,
    )
    return vs


def get_retriever():
    vs = get_vectorstore()
    return vs.as_retriever(search_kwargs={"k": 4})


def search_lego_info(query: str, k: int = 4) -> List[Document]:
    return get_vectorstore().similarity_search(query, k=k)


def format_retrieved_context(docs: List[Document]) -> str:
    if not docs:
        return ""
    parts = []
    for doc in docs:
        src = doc.metadata.get("source", "")
        parts.append(f"[{src}]\n{doc.page_content}")
    return "\n\n".join(parts)
