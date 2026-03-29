from dataclasses import dataclass
from typing import Optional

from trigger_engine.engine.evaluate_triggers import evaluate_triggers
from trigger_engine.knowledge.local_knowledge import get_canonical_entity_name
from trigger_engine.schemas.runtime_context import (
    ConversationContext,
    RecentIntervention,
    RuntimeContext,
)
from trigger_engine.utils.time_utils import now_iso


KNOWN_ENTITIES = [
    "יצחק רבין",
    "רבין",
    "מנחם בגין",
    "בגין",
    "דוד בן גוריון",
    "בן גוריון",
    "בנימין זאב הרצל",
    "הרצל",
]


def normalize_text(text: str) -> str:
    return " ".join(
        text.replace("?", " ").replace(",", " ").replace(".", " ").split()
    ).strip()


def extract_detected_entities(text: str) -> list[str]:
    normalized = normalize_text(text)
    found_entities: list[str] = []
    canonical_found: list[str] = []

    for entity in sorted(KNOWN_ENTITIES, key=len, reverse=True):
        if entity in normalized:
            canonical = get_canonical_entity_name(entity)
            if canonical and canonical not in canonical_found:
                canonical_found.append(canonical)
                found_entities.append(canonical)

    return found_entities


@dataclass
class TriggerEngineRunResult:
    output: object
    detected_entities: list[str]
    current_topic: Optional[str]


def run_trigger_engine_on_text(
    text: str,
    session_id: str = "live_session",
    current_topic: str | None = None,
    detected_entities: list[str] | None = None,
    recent_interventions: list[RecentIntervention] | None = None,
) -> TriggerEngineRunResult:
    resolved_entities = detected_entities or extract_detected_entities(text)

    context = RuntimeContext(
        session_id=session_id,
        timestamp=now_iso(),
        latency_mode="low_latency",
        latest_user_text=text,
        source_text_window=text,
        conversation_context=ConversationContext(
            current_topic=current_topic
        ),
        detected_entities=resolved_entities,
        recent_interventions=recent_interventions or [],
    )

    output = evaluate_triggers(context)

    return TriggerEngineRunResult(
        output=output,
        detected_entities=resolved_entities,
        current_topic=current_topic,
    )