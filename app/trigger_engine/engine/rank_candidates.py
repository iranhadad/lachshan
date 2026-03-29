from trigger_engine.schemas.trigger_types import TriggerEvaluationResult


def rank_trigger_results_desc(a: TriggerEvaluationResult, b: TriggerEvaluationResult, trigger_map: dict) -> int:
    if b.intervention_score != a.intervention_score:
        return 1 if b.intervention_score > a.intervention_score else -1

    if b.confidence != a.confidence:
        return 1 if b.confidence > a.confidence else -1

    trigger_a = trigger_map.get(a.trigger_id)
    trigger_b = trigger_map.get(b.trigger_id)

    priority_a = trigger_a.priority if trigger_a else 0
    priority_b = trigger_b.priority if trigger_b else 0

    if priority_b != priority_a:
        return 1 if priority_b > priority_a else -1

    return 0