import random
import string
import time


def create_intervention_id() -> str:
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"int_{int(time.time() * 1000)}_{rand}"