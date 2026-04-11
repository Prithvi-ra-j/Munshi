import os
from typing import List, Optional
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

_client: Optional[chromadb.PersistentClient] = None
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def get_or_create_collection(name: str = "contacts"):
    client = get_chroma_client()
    return client.get_or_create_collection(name=name, embedding_function=_ef)


def upsert_contact(user_phone: str, contact_name: str, context: str) -> None:
    collection = get_or_create_collection()
    doc_id = f"{user_phone}_{contact_name.lower().replace(' ', '_')}"
    collection.upsert(
        ids=[doc_id],
        documents=[f"{contact_name} - {context}"],
        metadatas=[{"user_phone": user_phone, "contact_name": contact_name}],
    )


def search_contact(user_phone: str, query: str, n_results: int = 3) -> List[str]:
    collection = get_or_create_collection()
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_phone": user_phone},
        )
        return results["documents"][0] if results["documents"] else []
    except Exception:
        return []
