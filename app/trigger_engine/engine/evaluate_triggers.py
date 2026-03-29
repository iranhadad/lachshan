from dataclasses import dataclass, field
from typing import List, Optional

from trigger_engine.engine.apply_guardrails import apply_guardrails
from trigger_engine.schemas.runtime_context import RuntimeContext
from trigger_engine.schemas.trigger_types import TriggerEvaluationResult, WhisperCandidate
from trigger_engine.triggers import TRIGGER_REGISTRY


@dataclass
class InterventionDecision:
    should_intervene: bool
    selected_trigger_id: Optional[str]
    selected_trigger_version: Optional[str]
    selected_candidate: Optional[WhisperCandidate]
    confidence: Optional[float]
    intervention_score: Optional[float]
    blocked_by: List[str] = field(default_factory=list)
    decision_reason: str = ""


@dataclass
class EvaluationOutput:
    decision: InterventionDecision
    results: List[TriggerEvaluationResult]


def evaluate_triggers(context: RuntimeContext) -> EvaluationOutput:
    eligible_triggers = [
        trigger
        for trigger in TRIGGER_REGISTRY
        if trigger["definition"].enabled
        and trigger["definition"].latency_mode == context.latency_mode
    ]

    trigger_map = {
        trigger["definition"].id: trigger["definition"]
        for trigger in eligible_triggers
    }

    raw_results = [
        trigger["evaluate"](context)
        for trigger in eligible_triggers
    ]

    passed_thresholds: List[TriggerEvaluationResult] = []
    for result in raw_results:
        trigger_definition = trigger_map.get(result.trigger_id)
        if trigger_definition is None:
            continue

        if (
            result.matched
            and result.candidate_whisper is not None
            and result.confidence >= trigger_definition.min_confidence
            and result.intervention_score >= trigger_definition.min_intervention_score
        ):
            passed_thresholds.append(result)

    guarded_results: List[TriggerEvaluationResult] = []
    for result in passed_thresholds:
        trigger_definition = trigger_map[result.trigger_id]
        guarded_result = apply_guardrails(result, context, trigger_definition)
        guarded_results.append(guarded_result)

    valid_results = [
        result for result in guarded_results
        if len(result.blocked_by) == 0
    ]

    if not valid_results:
        best_blocked_result: Optional[TriggerEvaluationResult] = None

        if guarded_results:
            best_blocked_result = sorted(
                guarded_results,
                key=lambda r: (
                    r.intervention_score,
                    r.confidence,
                    trigger_map[r.trigger_id].priority,
                ),
                reverse=True,
            )[0]

        if best_blocked_result is not None:
            return EvaluationOutput(
                decision=InterventionDecision(
                    should_intervene=False,
                    selected_trigger_id=None,
                    selected_trigger_version=None,
                    selected_candidate=None,
                    confidence=best_blocked_result.confidence,
                    intervention_score=best_blocked_result.intervention_score,
                    blocked_by=best_blocked_result.blocked_by,
                    decision_reason="A candidate was detected but blocked by guardrails",
                ),
                results=guarded_results,
            )

        return EvaluationOutput(
            decision=InterventionDecision(
                should_intervene=False,
                selected_trigger_id=None,
                selected_trigger_version=None,
                selected_candidate=None,
                confidence=None,
                intervention_score=None,
                blocked_by=["no_valid_candidate"],
                decision_reason="No trigger passed thresholds and guardrails",
            ),
            results=guarded_results if guarded_results else raw_results,
        )

    ranked = sorted(
        valid_results,
        key=lambda r: (
            r.intervention_score,
            r.confidence,
            trigger_map[r.trigger_id].priority,
        ),
        reverse=True,
    )

    winner = ranked[0]

    return EvaluationOutput(
        decision=InterventionDecision(
            should_intervene=True,
            selected_trigger_id=winner.trigger_id,
            selected_trigger_version=winner.trigger_version,
            selected_candidate=winner.candidate_whisper,
            confidence=winner.confidence,
            intervention_score=winner.intervention_score,
            blocked_by=[],
            decision_reason="Top-ranked candidate selected",
        ),
        results=guarded_results,
    )