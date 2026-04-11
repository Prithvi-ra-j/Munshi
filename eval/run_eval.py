"""
Eval script: runs intent classification and entity extraction on test_messages.json
and calculates accuracy/precision metrics.
"""
import asyncio
import json
import time
import sys
from pathlib import Path
from collections import defaultdict

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.agents.intent_classifier import intent_classifier_agent
from app.agents.entity_extractor import entity_extractor_agent
from app.state import MunshiState


def make_state(message: str) -> MunshiState:
    return {
        "phone": "eval_test",
        "raw_message": message,
        "message_type": "text",
        "audio_url": None,
        "timestamp": "2026-04-04T00:00:00",
        "transcribed_text": None,
        "processed_text": message,
        "intent": None,
        "intent_confidence": None,
        "entities": {},
        "contact_context": None,
        "tasks_created": [],
        "reminder_scheduled": None,
        "draft_reply": None,
        "status_report": None,
        "final_response": "",
        "language": "en",
        # New fields — must be present to avoid KeyError in agents
        "conversation_history": None,
        "last_entities": None,
        "onboarding_step": None,
        "pending_confirmation_id": None,
        "trace_id": "eval",
        "agent_errors": [],
    }


def entity_precision(predicted: dict, expected: dict) -> float:
    """Calculate precision for entity extraction."""
    if not expected:
        return 1.0
    scores = []
    for key, exp_vals in expected.items():
        pred_vals = predicted.get(key, [])
        if not exp_vals:
            continue
        hits = sum(
            1 for ev in exp_vals
            if any(str(ev).lower() in str(pv).lower() or str(pv).lower() in str(ev).lower()
                   for pv in pred_vals)
        )
        scores.append(hits / len(exp_vals))
    return sum(scores) / len(scores) if scores else 1.0


async def run_evaluation() -> dict:
    test_path = Path(__file__).parent / "test_messages.json"
    with open(test_path) as f:
        test_cases = json.load(f)

    intent_correct = 0
    entity_scores = []
    latencies = []
    per_intent_correct = defaultdict(int)
    per_intent_total = defaultdict(int)
    failures = []

    for i, tc in enumerate(test_cases):
        if i > 0:
            await asyncio.sleep(2)   # Groq free tier ~30 RPM; 2s spacing keeps us safe
        state = make_state(tc["message"])
        start = time.time()

        state = await intent_classifier_agent(state)
        state = await entity_extractor_agent(state)

        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)

        predicted_intent = state["intent"].value if state["intent"] else "UNKNOWN"
        expected_intent = tc["expected_intent"]

        per_intent_total[expected_intent] += 1
        if predicted_intent == expected_intent:
            intent_correct += 1
            per_intent_correct[expected_intent] += 1
        else:
            failures.append({
                "id": tc["id"],
                "message": tc["message"],
                "expected": expected_intent,
                "got": predicted_intent,
            })

        ep = entity_precision(state["entities"], tc.get("expected_entities", {}))
        entity_scores.append(ep)

    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.5)]
    p95 = latencies[int(n * 0.95)]

    results = {
        "intent_accuracy": round(intent_correct / n, 3),
        "entity_precision": round(sum(entity_scores) / n, 3),
        "p50_latency_ms": round(p50, 1),
        "p95_latency_ms": round(p95, 1),
        "total_messages": n,
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== Munshi Eval Results ===")
    print(f"Intent Accuracy:    {results['intent_accuracy']:.1%}")
    print(f"Entity Precision:   {results['entity_precision']:.1%}")
    print(f"P50 Latency:        {results['p50_latency_ms']} ms")
    print(f"P95 Latency:        {results['p95_latency_ms']} ms")
    print(f"Total Messages:     {results['total_messages']}")
    print("==========================")

    print("\n--- Per-Intent Accuracy ---")
    for intent in sorted(per_intent_total):
        total = per_intent_total[intent]
        correct = per_intent_correct[intent]
        bar = "#" * correct + "." * (total - correct)
        print(f"  {intent:<22} {correct}/{total}  {bar}")

    if failures:
        print(f"\n--- Failures ({len(failures)}) ---")
        for f in failures:
            msg_preview = f['message'][:55].encode('ascii', errors='replace').decode('ascii')
            print(f"  [#{f['id']}] \"{msg_preview}\"")
            print(f"         expected={f['expected']}  got={f['got']}")

    print()
    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())
