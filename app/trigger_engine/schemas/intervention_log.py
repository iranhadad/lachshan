from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from .trigger_types import LatencyMode


TriggerQuality = Literal[
    "correct",
    "incorrect",
    "too_early",
    "too_late",
    "wrong_trigger",
    "unclear",
]

WhisperQuality = Literal[
    "very_helpful",
    "partly_helpful",
    "not_helpful",
    "inaccurate",
    "too_long",
    "too_short",
    "wrong_framing",
]


@dataclass
class EvaluationTrace:
    feature_scores: Dict[str, float] = field(default_factory=dict)
    blocked_by: List[str] = field(default_factory=list)
    candidate_count: int = 0
    competing_triggers: List[str] = field(default_factory=list)


@dataclass
class FeedbackRecord:
    trigger_quality: Optional[TriggerQuality] = None
    whisper_quality: Optional[WhisperQuality] = None
    notes: Optional[str] = None


@dataclass
class ConversationContextSnapshot:
    current_topic: Optional[str] = None
    open_questions: List[str] = field(default_factory=list)
    facts_snapshot: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    recent_memory_snapshot: List[str] = field(default_factory=list)


@dataclass
class InterventionLogRecord:
    session_id: str
    intervention_id: str
    timestamp: str

    trigger_type: str
    trigger_version: str
    latency_mode: LatencyMode

    source_text_window: str
    conversation_context: ConversationContextSnapshot

    detected_entities: List[str] = field(default_factory=list)

    intervention_score: float = 0.0
    confidence: float = 0.0
    reasoning_summary: str = ""

    whisper_text: str = ""
    was_played: bool = False
    audio_delivery_status: Literal["played", "failed", "skipped"] = "skipped"

    evaluation_trace: Optional[EvaluationTrace] = None
    feedback: FeedbackRecord = field(default_factory=FeedbackRecord)