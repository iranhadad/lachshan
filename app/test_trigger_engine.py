from trigger_engine.engine.evaluate_triggers import evaluate_triggers
from trigger_engine.logging.write_jsonl_log import write_jsonl_log
from trigger_engine.schemas.intervention_log import (
    ConversationContextSnapshot,
    EvaluationTrace,
    InterventionLogRecord,
)
from trigger_engine.schemas.runtime_context import ConversationContext, RuntimeContext
from trigger_engine.utils.id_utils import create_intervention_id
from trigger_engine.utils.time_utils import now_iso


def run_test() -> None:
    context = RuntimeContext(
        session_id="sess_200",
        timestamp=now_iso(),
        latency_mode="low_latency",
        latest_user_text="מי יודע מתי נולד רבין?",
        source_text_window="מי יודע מתי נולד רבין?",
        conversation_context=ConversationContext(
            current_topic="שאלה היסטורית",
            open_questions=["מתי נולד רבין"],
            facts_snapshot=[],
            recent_events=["information_question_detected"],
            recent_memory_snapshot=[],
        ),
        detected_entities=["רבין"],
        recent_interventions=[],
    )

    output = evaluate_triggers(context)

    print("=== DECISION ===")
    print(output.decision)
    print()
    print("=== RESULTS ===")
    print(output.results)
    print()

    if not output.decision.should_intervene or output.decision.selected_candidate is None:
        print("No intervention emitted.")
        return

    winner = None
    for result in output.results:
        if result.trigger_id == output.decision.selected_trigger_id:
            winner = result
            break

    log_record = InterventionLogRecord(
        session_id=context.session_id,
        intervention_id=create_intervention_id(),
        timestamp=now_iso(),
        trigger_type=output.decision.selected_trigger_id,
        trigger_version=output.decision.selected_trigger_version,
        latency_mode=context.latency_mode,
        source_text_window=context.source_text_window,
        conversation_context=ConversationContextSnapshot(
            current_topic=context.conversation_context.current_topic,
            open_questions=context.conversation_context.open_questions,
            facts_snapshot=context.conversation_context.facts_snapshot,
            recent_events=context.conversation_context.recent_events,
            recent_memory_snapshot=context.conversation_context.recent_memory_snapshot,
        ),
        detected_entities=context.detected_entities,
        intervention_score=output.decision.intervention_score or 0.0,
        confidence=output.decision.confidence or 0.0,
        reasoning_summary=winner.reasoning_summary if winner else "",
        whisper_text=output.decision.selected_candidate.text,
        was_played=True,
        audio_delivery_status="played",
        evaluation_trace=EvaluationTrace(
            feature_scores=winner.feature_scores if winner else {},
            blocked_by=winner.blocked_by if winner else [],
            candidate_count=len([r for r in output.results if r.candidate_whisper is not None]),
            competing_triggers=[r.trigger_id for r in output.results],
        ),
    )

    write_jsonl_log("logs/interventions_log.jsonl", log_record)

    print("=== LOG WRITTEN ===")
    print("logs/interventions_log.jsonl")


if __name__ == "__main__":
    run_test()