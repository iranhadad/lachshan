from dataclasses import dataclass, field
from typing import List, Literal, Optional

from .trigger_types import LatencyMode


SpeakerType = Literal["user", "assistant", "other"]


@dataclass
class RecentTurn:
    speaker: SpeakerType
    text: str
    timestamp: Optional[str] = None


@dataclass
class RecentIntervention:
    intervention_id: str
    trigger_type: str
    whisper_text: str
    timestamp: str
    target_topic: Optional[str] = None


@dataclass
class ConversationContext:
    current_topic: Optional[str] = None
    open_questions: List[str] = field(default_factory=list)
    facts_snapshot: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    recent_memory_snapshot: List[str] = field(default_factory=list)


@dataclass
class RuntimeContext:
    session_id: str
    timestamp: str
    latency_mode: LatencyMode

    latest_user_text: str
    source_text_window: str

    recent_turns: List[RecentTurn] = field(default_factory=list)
    conversation_context: ConversationContext = field(default_factory=ConversationContext)

    detected_entities: List[str] = field(default_factory=list)
    recent_interventions: List[RecentIntervention] = field(default_factory=list)