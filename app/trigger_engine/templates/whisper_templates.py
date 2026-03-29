def build_information_question_whisper(answer: str, entity: str | None = None) -> str:
    answer = answer.strip()

    if entity:
        entity = entity.strip()
        if entity:
            return f"{entity}: {answer}"

    return answer