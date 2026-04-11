import json
import re
from typing import Any
from app.state import MunshiState
from app.llm_client import call_llm

ENTITY_PROMPT = """Extract entities from this message. Return JSON only.

Recent conversation history (use this to resolve pronouns like 'him', 'her', 'usse', 'wahi', 'the same person'):
{history}

Entities mentioned in the PREVIOUS turn (use these if the current message uses pronouns like 'him'/'her'/'usse'):
{last_entities}

Latest message to extract from: {message}

Extract:
- names: list of person/company names mentioned (resolve pronouns using history above)
- dates: list of dates/times (normalize to YYYY-MM-DD if possible)
- amounts: list of monetary amounts in INR (as numbers)
- action: the main action/task described in one line

IMPORTANT: If the message uses a pronoun like 'him', 'her', 'usse', 'wahi' and the history
shows a person was recently mentioned, include that person's name in 'names'.

JSON format:
{{
  "names": [],
  "dates": [],
  "amounts": [],
  "action": ""
}}"""

_nlp: Any = None


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            _nlp = None
    return _nlp


async def entity_extractor_agent(state: MunshiState) -> MunshiState:
    """Extract entities using spaCy + Groq hybrid approach."""
    text = state.get("processed_text", "")
    if not text:
        state["entities"] = {"names": [], "dates": [], "amounts": [], "action": ""}
        return state

    # spaCy extraction for names and dates
    spacy_names = []
    spacy_dates = []
    nlp = get_nlp()
    if nlp:
        doc = nlp(text)
        spacy_names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        spacy_dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]

    # Groq extraction for amounts and action — with conversation context for pronoun resolution
    history = state.get("conversation_history") or "(no prior conversation)"
    last_entities = state.get("last_entities") or {}
    prompt = ENTITY_PROMPT.format(message=text, history=history, last_entities=last_entities)
    response = await call_llm(prompt, max_tokens=300)

    groq_names, groq_dates, amounts, action = [], [], [], ""
    try:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            groq_names = data.get("names", [])
            groq_dates = data.get("dates", [])
            amounts = data.get("amounts", [])
            action = data.get("action", "")
    except Exception as e:
        state["agent_errors"].append(f"entity_extractor groq error: {e}")

    # Merge results, deduplicate
    all_names = list(dict.fromkeys(spacy_names + groq_names))
    all_dates = list(dict.fromkeys(spacy_dates + groq_dates))

    state["entities"] = {
        "names": all_names,
        "dates": all_dates,
        "amounts": amounts,
        "action": action,
    }
    return state
