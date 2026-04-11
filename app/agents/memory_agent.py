from app.state import MunshiState
from app.db.chroma_client import search_contact, upsert_contact


async def memory_rag_agent(state: MunshiState) -> MunshiState:
    """Retrieve and update contact memory from ChromaDB."""
    phone = state["phone"]
    entities = state.get("entities", {})
    names = entities.get("names", [])
    text = state.get("processed_text", "")

    context_parts = []

    for name in names:
        results = search_contact(phone, name)
        if results:
            context_parts.extend(results)
        # Upsert contact with current interaction context
        if text:
            upsert_contact(phone, name, text[:200])

    state["contact_context"] = "\n".join(context_parts) if context_parts else None
    return state
