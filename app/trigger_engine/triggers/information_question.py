from trigger_engine.knowledge.local_knowledge import (
    get_canonical_entity_name,
    lookup_birth_year,
)
from trigger_engine.schemas.runtime_context import RuntimeContext
from trigger_engine.schemas.trigger_types import (
    InputScope,
    LoggingPolicy,
    OutputPolicy,
    TriggerConditions,
    TriggerDefinition,
    TriggerEvaluationResult,
    WhisperCandidate,
)
from trigger_engine.templates.whisper_templates import build_information_question_whisper


definition = TriggerDefinition(
    id="information_question",
    version="1.3",
    label="Information Question",
    description="Detect direct factual questions suitable for short assistive whispers",
    enabled=True,
    latency_mode="low_latency",
    priority=80,
    cooldown_ms=12000,
    min_confidence=0.72,
    min_intervention_score=7.5,
    input_scope=InputScope(
        source_window_turns=2,
        source_window_chars=220,
        use_conversation_context=True,
        use_recent_memory=True,
        use_entity_detection=True,
    ),
    conditions=TriggerConditions(
        requires_direct_question=True,
        requires_factual_intent=True,
        disallow_if_joke_context=True,
        disallow_if_answer_already_given_recently=True,
        disallow_if_recently_whispered_same_topic=True,
        disallow_if_high_ambiguity=True,
    ),
    output_policy=OutputPolicy(
        max_whisper_chars=80,
        style="brief_direct_helpful",
        allow_uncertain_output=False,
        require_answer_or_hint=True,
    ),
    logging=LoggingPolicy(
        log_reasoning_summary=True,
        log_detected_entities=True,
        log_feature_scores=True,
        log_context_snapshot=True,
    ),
)


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

QUESTION_WORDS = [
    "מה",
    "מתי",
    "מי",
    "כמה",
    "איפה",
    "למה",
    "איך",
    "איזה",
    "איזו",
    "באיזה",
]

FACTUAL_PATTERNS = [
    "מתי",
    "מי",
    "כמה",
    "איפה",
    "באיזה שנה",
    "באיזה תאריך",
    "מה השעה",
    "מה הגיל",
    "מה המרחק",
    "מתי נולד",
    "מתי נולדה",
    "מתי נפטר",
    "מה תאריך הלידה",
    "תאריך הלידה",
    "מתי הוא נולד",
    "מתי היא נולדה",
]

INDIRECT_QUESTION_PHRASES = [
    "הייתי רוצה לדעת",
    "אני לא יודע",
    "מעניין",
    "תוכל לבדוק",
    "תוכלי לבדוק",
    "את יכולה למצוא",
    "אתה יכול למצוא",
    "מי יודע",
]

JOKE_INDICATORS = [
    "חח",
    "חחח",
    "חחחח",
    "סתם",
    "בצחוק",
]


def normalize_text(text: str) -> str:
    replacements = {
        "?": " ",
        ",": " ",
        ".": " ",
        "!": " ",
        ":": " ",
        ";": " ",
    }

    normalized = text.strip()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    return " ".join(normalized.split())


def looks_like_direct_question(text: str) -> float:
    text = text.strip()
    if not text:
        return 0.0

    has_question_mark = "?" in text
    has_question_word = any(word in text for word in QUESTION_WORDS)

    if has_question_mark and has_question_word:
        return 0.95
    if has_question_word:
        return 0.82
    if has_question_mark:
        return 0.70
    if any(phrase in text for phrase in INDIRECT_QUESTION_PHRASES):
        return 0.72

    return 0.15


def looks_factual(text: str) -> float:
    text = text.strip()

    if any(pattern in text for pattern in FACTUAL_PATTERNS):
        return 0.88

    return 0.35


def joke_risk(text: str) -> float:
    text = text.strip()

    if any(item in text for item in JOKE_INDICATORS):
        return 0.75

    return 0.08


def extract_known_entity(text: str) -> str | None:
    normalized = normalize_text(text)

    for entity in sorted(KNOWN_ENTITIES, key=len, reverse=True):
        if entity in normalized:
            canonical = get_canonical_entity_name(entity)
            if canonical:
                return canonical

    return None


def is_birth_question(text: str, entity: str | None) -> bool:
    normalized = normalize_text(text)

    strong_patterns = [
        "מה תאריך הלידה",
        "תאריך הלידה של",
        "מתי נולד",
        "מתי נולדה",
        "נולד מתי",
        "נולדה מתי",
    ]

    if any(pattern in normalized for pattern in strong_patterns):
        return True

    if entity is None:
        return False

    birth_words = ["נולד", "נולדה", "לידה", "נפטר", "נפטרה"]
    question_or_interest_words = ["מתי", "מה", "יודע", "לדעת", "לבדוק", "למצוא", "מעניין"]

    has_entity = entity in normalized or any(alias in normalized for alias in KNOWN_ENTITIES)
    has_birth_word = any(word in normalized for word in birth_words)
    has_question_signal = (
        "?" in text
        or any(word in normalized for word in question_or_interest_words)
    )

    return has_entity and has_birth_word and has_question_signal


def infer_simple_answer(text: str) -> tuple[str | None, str | None]:
    entity = extract_known_entity(text)

    if entity and is_birth_question(text, entity):
        birth_year = lookup_birth_year(entity)
        if birth_year:
            return birth_year, entity

    return None, entity


def evaluate(context: RuntimeContext) -> TriggerEvaluationResult:
    text = (context.latest_user_text or context.source_text_window or "").strip()

    direct_question_score = looks_like_direct_question(text)
    factual_intent_score = looks_factual(text)
    joke_risk_score = joke_risk(text)

    extracted_entity = extract_known_entity(text)
    entity_match_score = 0.90 if extracted_entity else 0.20

    ambiguity_penalty = 0.50 if len(text) < 4 else 0.10

    confidence = (
        0.35 * direct_question_score
        + 0.30 * factual_intent_score
        + 0.20 * entity_match_score
        + 0.15 * (1 - ambiguity_penalty)
    )

    raw_intervention_score = (
        0.35 * direct_question_score
        + 0.30 * factual_intent_score
        + 0.20 * entity_match_score
        + 0.15 * (1 - joke_risk_score)
    )

    intervention_score = raw_intervention_score * 10

    matched = direct_question_score >= 0.70 and factual_intent_score >= 0.60

    answer, entity = infer_simple_answer(text)

    candidate_whisper = None
    blocked_by: list[str] = []

    if joke_risk_score > 0.70:
        blocked_by.append("joke_context")

    if matched and answer:
        whisper_text = build_information_question_whisper(answer=answer, entity=entity)
        candidate_whisper = WhisperCandidate(
            text=whisper_text,
            style=definition.output_policy.style,
            estimated_chars=len(whisper_text),
            source_trigger_id=definition.id,
            target_topic=entity,
        )
    else:
        blocked_by.append("no_answer_available")

    if not matched:
        reasoning_summary = "לא זוהתה שאלה עובדתית ישירה ברמת ביטחון מספקת"
    elif matched and not answer:
        reasoning_summary = "זוהתה שאלה עובדתית, אך לא נמצאה תשובה במאגר המקומי"
    else:
        reasoning_summary = "זוהתה שאלה עובדתית ונמצאה תשובה במאגר המקומי"

    decision = "emit" if matched and len(blocked_by) == 0 else "skip"

    return TriggerEvaluationResult(
        trigger_id=definition.id,
        trigger_version=definition.version,
        matched=matched,
        confidence=round(confidence, 3),
        intervention_score=round(intervention_score, 2),
        feature_scores={
            "direct_question_score": round(direct_question_score, 3),
            "factual_intent_score": round(factual_intent_score, 3),
            "joke_risk_score": round(joke_risk_score, 3),
            "entity_match_score": round(entity_match_score, 3),
            "ambiguity_penalty": round(ambiguity_penalty, 3),
        },
        reasoning_summary=reasoning_summary,
        candidate_whisper=candidate_whisper,
        blocked_by=blocked_by,
        decision=decision,
    )