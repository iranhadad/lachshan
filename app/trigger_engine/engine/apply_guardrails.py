from trigger_engine.schemas.runtime_context import RuntimeContext
from trigger_engine.schemas.trigger_types import TriggerDefinition, TriggerEvaluationResult


def apply_guardrails(
    result: TriggerEvaluationResult,
    context: RuntimeContext,
    trigger_definition: TriggerDefinition,
) -> TriggerEvaluationResult:
    blocked_by = list(result.blocked_by)

    if result.candidate_whisper is not None:
        if result.candidate_whisper.estimated_chars > trigger_definition.output_policy.max_whisper_chars:
            blocked_by.append("candidate_too_long")

        recent_same_whisper = any(
            item.whisper_text == result.candidate_whisper.text
            for item in context.recent_interventions
        )
        if recent_same_whisper:
            blocked_by.append("repeat_whisper")

        if result.candidate_whisper.target_topic:
            recent_same_topic = any(
                item.target_topic == result.candidate_whisper.target_topic
                for item in context.recent_interventions
                if item.target_topic is not None
            )
            if recent_same_topic:
                blocked_by.append("topic_cooldown")

    recent_too_many = len(context.recent_interventions) >= 2
    if recent_too_many:
        blocked_by.append("too_many_recent_interventions")

    result.blocked_by = blocked_by
    result.decision = "emit" if result.matched and len(blocked_by) == 0 else "skip"

    return result