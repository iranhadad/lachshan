from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional


LatencyMode = Literal["low_latency", "delayed"]

WhisperStyle = Literal[
    "brief_direct_helpful",
    "corrective_neutral",
    "memory_reminder",
    "timing_alert",
]


@dataclass
class InputScope:
    source_window_turns: int
    source_window_chars: int
    use_conversation_context: bool
    use_recent_memory: bool
    use_entity_detection: bool


@dataclass
class TriggerConditions:
    requires_direct_question: bool = False
    requires_factual_intent: bool = False
    requires_unresolved_question: bool = False
    requires_time_reference_conflict: bool = False
    requires_high_correction_confidence: bool = False

    disallow_if_joke_context: bool = False
    disallow_if_answer_already_given_recently: bool = False
    disallow_if_recently_whispered_same_topic: bool = False
    disallow_if_high_ambiguity: bool = False


@dataclass
class OutputPolicy:
    max_whisper_chars: int
    style: WhisperStyle
    allow_uncertain_output: bool
    require_answer_or_hint: bool


@dataclass
class LoggingPolicy:
    log_reasoning_summary: bool
    log_detected_entities: bool
    log_feature_scores: bool
    log_context_snapshot: bool


@dataclass
class TriggerDefinition:
    id: str
    version: str
    label: str
    description: str
    enabled: bool

    latency_mode: LatencyMode
    priority: int

    cooldown_ms: int
    min_confidence: float
    min_intervention_score: float

    input_scope: InputScope
    conditions: TriggerConditions
    output_policy: OutputPolicy
    logging: LoggingPolicy


@dataclass
class WhisperCandidate:
    text: str
    style: WhisperStyle
    estimated_chars: int
    source_trigger_id: str
    target_topic: Optional[str] = None


@dataclass
class TriggerEvaluationResult:
    trigger_id: str
    trigger_version: str

    matched: bool
    confidence: float
    intervention_score: float

    feature_scores: Dict[str, float]
    reasoning_summary: str

    candidate_whisper: Optional[WhisperCandidate]

    blocked_by: List[str] = field(default_factory=list)
    decision: Literal["emit", "skip"] = "skip"