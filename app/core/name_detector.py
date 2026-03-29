# -*- coding: utf-8 -*-
"""
מזהה האם דיבור מכוון לנרי בכל מקום במשפט, ומחלץ את הפקודה שאחרי השם.
"""

from config import ASSISTANT_NAME_HE, ASSISTANT_NAME_EN

_PREFIXES: list[str] = [
    ASSISTANT_NAME_HE,          # "נרי"
    ASSISTANT_NAME_EN,          # "nari"
    ASSISTANT_NAME_EN.lower(),
]


def _levenshtein(a: str, b: str) -> int:
    """חישוב מרחק Levenshtein בין שתי מחרוזות."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            ))
        prev = curr
    return prev[len(b)]


def _find_name_word_index(words: list[str]) -> int:
    """
    מחזיר את האינדקס של המילה הראשונה שמוכרת כשם נרי
    (מרחק Levenshtein ≤ 1). מחזיר -1 אם לא נמצא.
    """
    for i, word in enumerate(words):
        normalized = word.lower().strip(" ,.-")
        for prefix in _PREFIXES:
            if _levenshtein(normalized, prefix.lower()) <= 1:
                return i
    return -1


def is_addressed_to_nari(text: str) -> bool:
    """
    מחזיר True אם השם נרי (או וריאנט fuzzy) מופיע בכל מקום בטקסט.
    דוגמאות:
      "נרי תבדקי" → True
      "צהריים טובים נרי, מה יש לי" → True
      "היי נרית תקבעי פגישה" → True
      "נורבי תבדוק" → False  (מרחק 2)
    """
    if not text or not text.strip():
        return False
    return _find_name_word_index(text.strip().split()) >= 0


def strip_name_prefix(text: str) -> str:
    """
    מחזיר את הטקסט שאחרי המופע הראשון של שם נרי במשפט.
    דוגמאות:
      "נרי, תפעיל לחשן"              → "תפעיל לחשן"
      "צהריים טובים נרי, מה יש לי"  → "מה יש לי"
      "היי נרית תקבעי פגישה"         → "תקבעי פגישה"
    """
    stripped = text.strip()
    words = stripped.split()
    idx = _find_name_word_index(words)
    if idx < 0:
        return stripped
    remainder = " ".join(words[idx + 1:])
    return remainder.lstrip(" ,.-")
