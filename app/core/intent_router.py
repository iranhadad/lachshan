# -*- coding: utf-8 -*-
from dataclasses import dataclass
from enum import Enum
from openai import OpenAI
import json
from config import OPENAI_API_KEY, LLM_MODEL

DEFAULT_ACCOUNT  = "info@irondt.co.il"
PERSONAL_ACCOUNT = "iran.hadad@gmail.com"

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
    account: str = DEFAULT_ACCOUNT  # ← חדש

_SYSTEM_PROMPT = """\
אתה מסווג פקודות קוליות בעברית לעוזרת אישית בשם נרי.
החזר JSON בלבד, ללא טקסט נוסף:
{"intent": "...", "confidence": 0.0-1.0, "account": "..."}

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

אפשרויות account:
- "info@irondt.co.il" — ברירת מחדל, חשבון ארגוני
- "iran.hadad@gmail.com" — אם המשתמש אומר "אישי" / "gmail" / "פרטי"

כללים חשובים:
1. כל שאלה על "מה יש לי היום/מחר/השבוע" = calendar
2. כל בקשה "תבדקי יומן / תראי פגישות" = calendar
3. כל בקשה "תקבעי / תאמי / תוסיפי פגישה" = add_event
4. כל שאלת ידע כללי = conversation
5. ספק בין calendar ל-conversation? → calendar
6. אם המשתמש אומר "אישי" / "gmail" / "פרטי" → account = iran.hadad@gmail.com
7. אחרת → account = info@irondt.co.il

דוגמאות:
"מה יש לי היום" → calendar, info@irondt.co.il
"מה יש לי היום ביומן האישי" → calendar, iran.hadad@gmail.com
"תקבעי פגישה עם יניב מחר ב-10" → add_event, info@irondt.co.il
"תקבעי פגישה ביומן האישי" → add_event, iran.hadad@gmail.com
"תקריאי מיילים" → read_email, info@irondt.co.il
"תקריאי מיילים מהג'ימייל" → read_email, iran.hadad@gmail.com
"עצרי" → stop, info@irondt.co.il"""

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
            max_tokens=80,
            timeout=3,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        intent_str = data.get("intent", "unknown")
        confidence = float(data.get("confidence", 0.5))
        account    = data.get("account", DEFAULT_ACCOUNT)

        # וידוא שה-account תקין
        if account not in (DEFAULT_ACCOUNT, PERSONAL_ACCOUNT):
            account = DEFAULT_ACCOUNT

        intent = Intent(intent_str)
        return IntentResult(
            intent=intent,
            command_text=command_text,
            confidence=confidence,
            account=account,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return IntentResult(intent=Intent.CONVERSATION, command_text=command_text, confidence=0.5)
    except Exception:
        return IntentResult(intent=Intent.CONVERSATION, command_text=command_text, confidence=0.5)

# -*- coding: utf-8 -*-
from dataclasses import dataclass
from enum import Enum
from openai import OpenAI
import json
from config import OPENAI_API_KEY, LLM_MODEL

DEFAULT_ACCOUNT  = "info@irondt.co.il"
PERSONAL_ACCOUNT = "iran.hadad@gmail.com"

class Intent(Enum):
    ENABLE_LACHSHAN  = "enable_lachshan"
    DISABLE_LACHSHAN = "disable_lachshan"
    CALENDAR         = "calendar"
    ADD_EVENT        = "add_event"
    EMAIL            = "email"
    READ_EMAIL       = "read_email"
    LAST_EMAIL       = "last_email"
    CONVERSATION     = "conversation"
    STOP             = "stop"
    UNKNOWN          = "unknown"

@dataclass
class IntentResult:
    intent: Intent
    command_text: str
    confidence: float
    account: str = DEFAULT_ACCOUNT

_SYSTEM_PROMPT = """\
אתה מסווג פקודות קוליות בעברית לעוזרת אישית בשם נרי.
החזר JSON בלבד, ללא טקסט נוסף:
{"intent": "...", "confidence": 0.0-1.0, "account": "..."}

אפשרויות intent:
- read_email: לקרוא/לבדוק/לסכם מספר מיילים
- last_email: לקרוא רק את המייל האחרון / הכי חדש
- email: לכתוב/לשלוח מייל
- calendar: לבדוק יומן/פגישות/אירועים קיימים
- add_event: לקבוע/להוסיף/לתאם פגישה או אירוע חדש
- enable_lachshan: להפעיל מצב לחשן
- disable_lachshan: לכבות מצב לחשן
- conversation: שיחה, שאלת ידע, ייעוץ, שאלות המשך
- stop: לעצור/להשתיק את נרי
- unknown: לא ברור בכלל

אפשרויות account:
- "info@irondt.co.il" — ברירת מחדל, חשבון ארגוני
- "iran.hadad@gmail.com" — אם המשתמש אומר "אישי" / "gmail" / "פרטי"

כללים:
1. "מה יש לי היום/מחר/השבוע" = calendar
2. "תקבעי/תאמי/תוסיפי פגישה" = add_event
3. "מה המייל האחרון/הכי חדש/קיבלתי לאחרונה" = last_email
4. "תקריאי מיילים/מה יש לי במייל" = read_email
5. שאלות המשך כמו "מה הנושא שלו/מי שלח/ספרי עוד" = conversation (עם היסטוריה)
6. "אישי/gmail/פרטי" → account = iran.hadad@gmail.com
7. אחרת → account = info@irondt.co.il"""

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client

def route_intent(command_text: str) -> IntentResult:
    try:
        response = _get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": command_text},
            ],
            temperature=0.0,
            max_tokens=80,
            timeout=3,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        intent_str = data.get("intent", "unknown")
        confidence = float(data.get("confidence", 0.5))
        account    = data.get("account", DEFAULT_ACCOUNT)

        if account not in (DEFAULT_ACCOUNT, PERSONAL_ACCOUNT):
            account = DEFAULT_ACCOUNT

        intent = Intent(intent_str)
        return IntentResult(
            intent=intent,
            command_text=command_text,
            confidence=confidence,
            account=account,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return IntentResult(intent=Intent.CONVERSATION, command_text=command_text, confidence=0.5)
    except Exception:
        return IntentResult(intent=Intent.CONVERSATION, command_text=command_text, confidence=0.5)
