from langgraph.graph import StateGraph, END
from app.state import MunshiState
from app.models import IntentType
from app.agents.transcription import transcription_agent
from app.agents.intent_classifier import intent_classifier_agent
from app.agents.entity_extractor import entity_extractor_agent
from app.agents.memory_agent import memory_rag_agent
from app.agents.task_agent import task_agent
from app.agents.task_completion_agent import task_completion_agent
from app.agents.reminder_control_agent import reminder_control_agent
from app.agents.confirmation_agent import confirmation_agent
from app.agents.reply_drafter import reply_drafter_agent
from app.agents.report_agent import report_agent
from app.agents.reminder_agent import reminder_agent

# Module-level compiled graph — initialized at startup via init_graph()
_compiled_graph = None


async def reset_turn_state(state: MunshiState) -> dict:
    """
    First node in the graph. Runs at the start of every turn.

    The LangGraph checkpointer has already restored the PREVIOUS turn's full state.
    Our initial_state in webhook.py has overwritten per-turn input fields (phone,
    raw_message, etc.) but intentionally left cross-turn fields (conversation_history,
    last_entities, onboarding_step, pending_confirmation_id) untouched so the
    checkpoint values carry forward.

    This node resets all per-turn output fields to clean defaults.
    """
    return {
        "transcribed_text": None,
        "intent": None,
        "intent_confidence": None,
        "entities": {},
        "contact_context": None,
        "tasks_created": [],
        "reminder_scheduled": None,
        "draft_reply": None,
        "status_report": None,
        "final_response": "",
        "agent_errors": [],
        # language is NOT reset — keeps the user's preferred language across turns
        # onboarding_step, pending_confirmation_id, conversation_history, last_entities
        # are NOT reset — they live in the checkpoint and carry forward automatically
    }


async def save_to_history(state: MunshiState) -> dict:
    """
    Last node before END. Appends the current turn to conversation_history and
    saves the current entities as last_entities for the next turn's pronoun resolution.
    History is never trimmed — the full conversation is retained in checkpoints.sqlite.
    """
    user_msg = state.get("processed_text", "").strip()
    bot_response = state.get("final_response", "").strip()
    prev_history = state.get("conversation_history") or ""

    if user_msg and bot_response:
        new_entry = f"USER: {user_msg}\nMUNSHI: {bot_response}"
        history = (prev_history + "\n" + new_entry) if prev_history else new_entry
    else:
        history = prev_history

    return {
        "conversation_history": history,
        "last_entities": state.get("entities", {}),
    }


async def response_formatter(state: MunshiState) -> MunshiState:
    """Send final_response back to user via WAHA."""
    from app.waha_client import send_text_message
    response = state.get("final_response", "")
    if response:
        await send_text_message(state["phone"], response)
    return state


def route_by_intent(state: MunshiState) -> str:
    intent = state.get("intent", IntentType.UNKNOWN)
    routing = {
        IntentType.TASK: "task",
        IntentType.FOLLOW_UP: "task",
        IntentType.REPLY_DRAFT: "reply",
        IntentType.STATUS_QUERY: "report",
        IntentType.STORE_INFO: "task",
        IntentType.TASK_COMPLETE: "task_complete",
        IntentType.REMINDER_CONTROL: "reminder_control",
        IntentType.CONFIRMATION: "confirm",
        IntentType.UNKNOWN: "reply",
    }
    return routing.get(intent, "reply")


def build_munshi_graph(checkpointer=None):
    graph = StateGraph(MunshiState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    graph.add_node("reset", reset_turn_state)
    graph.add_node("transcribe", transcription_agent)
    graph.add_node("classify", intent_classifier_agent)
    graph.add_node("extract", entity_extractor_agent)
    graph.add_node("memory", memory_rag_agent)
    # Original action nodes
    graph.add_node("task", task_agent)
    graph.add_node("reply", reply_drafter_agent)
    graph.add_node("report", report_agent)
    graph.add_node("reminder", reminder_agent)
    # New action nodes
    graph.add_node("task_complete", task_completion_agent)
    graph.add_node("reminder_control", reminder_control_agent)
    graph.add_node("confirm", confirmation_agent)
    # Shared tail nodes
    graph.add_node("respond", response_formatter)
    graph.add_node("save_history", save_to_history)

    # ── Edges ──────────────────────────────────────────────────────────────────
    graph.set_entry_point("reset")
    graph.add_edge("reset", "transcribe")
    graph.add_edge("transcribe", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "memory")

    # Intent-based routing from memory
    graph.add_conditional_edges(
        "memory",
        route_by_intent,
        {
            "task": "task",
            "reply": "reply",
            "report": "report",
            "task_complete": "task_complete",
            "reminder_control": "reminder_control",
            "confirm": "confirm",
        },
    )

    # TASK path: create task → schedule reminder → respond
    graph.add_edge("task", "reminder")
    graph.add_edge("reminder", "respond")

    # All other paths go directly to respond
    graph.add_edge("reply", "respond")
    graph.add_edge("report", "respond")
    graph.add_edge("task_complete", "respond")
    graph.add_edge("reminder_control", "respond")
    graph.add_edge("confirm", "respond")

    # Shared tail
    graph.add_edge("respond", "save_history")
    graph.add_edge("save_history", END)

    return graph.compile(checkpointer=checkpointer)


def init_graph(checkpointer=None) -> None:
    """Called once at startup from main.py lifespan. Compiles the graph with checkpointer."""
    global _compiled_graph
    _compiled_graph = build_munshi_graph(checkpointer=checkpointer)


def get_compiled_graph():
    """Returns the compiled graph. Falls back to a no-checkpointer graph if not initialized."""
    if _compiled_graph is None:
        return build_munshi_graph()
    return _compiled_graph
