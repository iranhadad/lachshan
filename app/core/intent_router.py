# -*- coding: utf-8 -*-
from dataclasses import dataclass
from enum import Enum
from openai import OpenAI
import json
from config import OPENAI_API_KEY, LLM_MODEL


class Intent(Enum):
    ENABLE_LACHSHAN  = "enable_lachshan"
    DISABLE_LACHSHAN = "disable_lachshan"
    CALENDAR         = "calendar"
    ADD_EVENT        = "add_event"
    EMAIL            = "email"
    READ_EMAIL       = "read_email"
    CONVERSATION     = "conversation"
    STOP             = "stop"
    UNKNOWN          = "unknown"


@dataclass
class IntentResult:
    intent: Intent
    command_text: str
    confidence: float


_SYSTEM_PROMPT = """\
אתה מסווג פקודות קוליות בעברית לעוזרת אישית בשם נרי.
החזר JSON בלבד, ללא טקסט נוסף:
{"intent": "...", "confidence": 0.0-1.0}
אפשרויות intent:
- read_email: כל בקשה לקרוא/לבדוק/לסכם/להקריא מיילים
- email: לכתוב/לשלוח מייל
- calendar: כל בקשה לבדוק יומן/לוז/פגישות/אירועים קיימים
- add_event: לקבוע/להוסיף/לתאם פגישה או אירוע חדש
- enable_lachshan: להפעיל מצב לחשן
- disable_lachshan: לכבות מצב לחשן
- conversation: שיחה, שאלת ידע, ייעוץ, חשיבה משותפת
- stop: לעצור/להשתיק את נרי
- unknown: לא ברור בכלל
כללים חשובים:
1. כל שאלה על "מה יש לי היום/מחר/השבוע" = calendar
2. כל בקשה "תבדקי יומן / תראי פגישות" = calendar
3. כל בקשה "תקבעי / תאמי / תוסיפי פגישה" = add_event
4. כל שאלת ידע כללי = conversation
5. ספק בין calendar ל-conversation? → calendar
דוגמאות:
"מה יש לי היום" → calendar
"את יכולה לבדוק את היומן שלי" → calendar
"יש לי פגישות מחר?" → calendar
"תקבעי פגישה עם יניב מחר ב-10" → add_event
"מה הם עקרונות ניהול פרויקט" → conversation
"תקריאי מיילים" → read_email
"עצרי" → stop
"די" → stop
"תפסיקי" → stop
"שקט" → stop"""

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def route_intent(command_text: str) -> IntentResult:
    """שולח ל-LLM לסיווג ומחזיר IntentResult."""
    try:
        response = _get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": command_text},
            ],
            temperature=0.0,
            max_tokens=60,
            timeout=3,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        intent_str = data.get("intent", "unknown")
        confidence = float(data.get("confidence", 0.5))
        intent = Intent(intent_str)
        return IntentResult(intent=intent, command_text=command_text, confidence=confidence)
    except (json.JSONDecodeError, KeyError, ValueError):
        return IntentResult(intent=Intent.CONVERSATION, command_text=command_text, confidence=0.5)
    except Exception:
        return IntentResult(intent=Intent.CONVERSATION, command_text=command_text, confidence=0.5)
