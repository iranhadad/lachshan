from trigger_engine.triggers.information_question import definition as information_question_definition
from trigger_engine.triggers.information_question import evaluate as information_question_evaluate


TRIGGER_REGISTRY = [
    {
        "definition": information_question_definition,
        "evaluate": information_question_evaluate,
    }
]