# -*- coding: utf-8 -*-
"""
פעולת יומן – שולפת אירועי היום מ-Google Calendar ומחזירה סיכום עברי לקריאה בקול.

דרישות:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

הגדרה ראשונה:
    1. פתח https://console.cloud.google.com
    2. APIs & Services → Enable "Google Calendar API"
    3. Credentials → Create → OAuth 2.0 Client ID → Desktop App
    4. הורד את קובץ ה-JSON ושמור אותו בנתיב GOOGLE_CREDENTIALS_FILE (ברירת מחדל: credentials.json)
    5. בהרצה הראשונה תיפתח חלון דפדפן לאישור – לאחר מכן נשמר token.json אוטומטית.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from config import GOOGLE_CALENDAR_ID, OPENAI_API_KEY, LLM_MODEL

# ─── ייבוא אופציונלי של ספריות Google ────────────────────────────────────────
try:
    from googleapiclient.discovery import build
    from core.google_auth import get_credentials
    _GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    _GOOGLE_LIBS_AVAILABLE = False

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

# ─── שמות ימים בעברית ────────────────────────────────────────────────────────
_DAY_NAMES = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════════════════════

def _get_service():
    """
    מחזיר Google Calendar service מאומת.
    credentials מנוהלים ב-core.google_auth (singleton משותף עם Gmail).

    Raises:
        RuntimeError: אם ספריות Google לא מותקנות.
        FileNotFoundError: אם credentials.json לא נמצא.
    """
    if not _GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError(
            "ספריות Google לא מותקנות. "
            "הרץ: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


# ═══════════════════════════════════════════════════════════════════════════════
# Fetching events
# ═══════════════════════════════════════════════════════════════════════════════

def get_today_events() -> list:
    """
    מחזיר רשימת אירועי Google Calendar להיום (מחצות עד 23:59).
    ממוין לפי שעת התחלה.
    """
    service = _get_service()

    now = datetime.now().astimezone()
    day_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    day_end   = now.replace(hour=23, minute=59, second=59, microsecond=0)

    result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=10,
    ).execute()

    return result.get("items", [])


def get_upcoming_events(hours_ahead: int = 3) -> list:
    """
    מחזיר אירועים שמתחילים בשעות הקרובות (ברירת מחדל: 3 שעות).
    שימושי לתזכורת שוטפת.
    """
    service = _get_service()

    now = datetime.now().astimezone()
    until = now.replace(
        hour=min(now.hour + hours_ahead, 23),
        minute=now.minute,
        second=0,
        microsecond=0,
    )

    result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=until.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=5,
    ).execute()

    return result.get("items", [])


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_event_time(event: dict) -> Optional[datetime]:
    """מחלץ datetime מאירוע (תומך ב-dateTime ו-date)."""
    start = event.get("start", {})
    time_str = start.get("dateTime") or start.get("date")
    if not time_str:
        return None
    try:
        if "T" in time_str:
            return datetime.fromisoformat(time_str)
        # all-day event: "2024-03-10"
        return datetime.fromisoformat(time_str + "T00:00:00")
    except ValueError:
        return None


def _format_single_event(event: dict) -> str:
    """מחזיר תיאור קצר של אירוע בעברית."""
    summary  = event.get("summary", "אירוע ללא שם")
    location = event.get("location", "")
    dt       = _parse_event_time(event)

    if dt is None:
        return summary

    start_info = event.get("start", {})
    is_all_day = "date" in start_info and "dateTime" not in start_info

    if is_all_day:
        time_part = "כל היום"
    else:
        time_part = f"בשעה {dt.strftime('%H:%M')}"

    loc_part = f" ב{location}" if location else ""
    return f"{time_part}: {summary}{loc_part}"


def format_events_for_speech(events: list) -> str:
    """ממיר רשימת אירועים לטקסט עברי קצר לקריאה בקול."""
    if not events:
        return "אין אירועים מתוכננים להיום."

    count = len(events)
    noun  = "אירוע" if count == 1 else "אירועים"
    parts = [f"יש לך {count} {noun} היום."]

    for event in events[:4]:
        parts.append(_format_single_event(event))

    if count > 4:
        parts.append(f"ועוד {count - 4} נוספים.")

    return ". ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_event_details(instruction: str) -> dict:
    """שולח את ה-instruction ל-LLM ומחלץ פרטי אירוע כ-JSON."""
    if not _OPENAI_AVAILABLE:
        raise RuntimeError("openai לא מותקן")

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    day_name = _DAY_NAMES[today.weekday()]

    system_prompt = (
        f"היום הוא {day_name}, {today_str}. "
        "חלץ פרטי אירוע מהטקסט בעברית והחזר JSON בלבד, ללא טקסט נוסף:\n"
        '{"title": "...", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_minutes": 60}\n'
        "כללים:\n"
        "- 'מחר' = יום אחרי היום\n"
        "- 'היום' = היום\n"
        "- אם אין שעה, השתמש ב-09:00\n"
        "- אם אין משך, השתמש ב-60\n"
        "- date ו-time חייבים להיות בפורמט המדויק"
    )

    client = _OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instruction},
        ],
        temperature=0.0,
        max_tokens=100,
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


def add_event(instruction: str) -> str:
    """
    מחלץ פרטי אירוע מ-instruction בעברית חופשית, יוצר אירוע ב-Google Calendar
    ומחזיר אישור קצר בעברית.
    """
    try:
        details = _extract_event_details(instruction)
    except Exception as exc:
        return f"לא הצלחתי להבין את פרטי האירוע: {exc}"

    try:
        title: str = details.get("title", "אירוע")
        date_str: str = details["date"]
        time_str: str = details.get("time", "09:00")
        duration: int = int(details.get("duration_minutes", 60))

        start_dt = datetime.fromisoformat(f"{date_str}T{time_str}:00")
        end_dt = start_dt + timedelta(minutes=duration)

        tz = datetime.now().astimezone().tzname()
        # השג timezone offset בפורמט שGoogle מקבל
        import time as _time
        offset_sec = -_time.timezone if not _time.daylight else -_time.altzone
        sign = "+" if offset_sec >= 0 else "-"
        offset_h = abs(offset_sec) // 3600
        tz_str = f"{sign}{offset_h:02d}:00"

        event_body = {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat() + tz_str},
            "end":   {"dateTime": end_dt.isoformat() + tz_str},
        }

        service = _get_service()
        service.events().insert(calendarId="primary", body=event_body).execute()

        # אישור בעברית
        day_offset = (start_dt.date() - datetime.now().date()).days
        if day_offset == 0:
            day_word = "היום"
        elif day_offset == 1:
            day_word = "מחר"
        else:
            day_word = f"ב-{date_str}"

        return f"{title} נוספה {day_word} ב-{time_str}"

    except RuntimeError:
        return "ספריית Google Calendar לא מותקנת."
    except FileNotFoundError:
        return "לא הוגדרו הרשאות Google Calendar."
    except Exception as exc:
        return f"לא הצלחתי להוסיף את האירוע: {exc}"


def get_calendar_summary(date_offset_days: int = 0) -> str:
    """
    נקודת הכניסה הראשית: מחזיר סיכום יומן בעברית לקריאה בקול.
    date_offset_days: 0=היום, 1=מחר, -1=אתמול וכו'.
    מחזיר הודעת שגיאה נעימה אם היומן לא זמין.
    """
    try:
        service = _get_service()
        now = datetime.now().astimezone()
        target = now + timedelta(days=date_offset_days)
        day_start = target.replace(hour=0,  minute=0,  second=0,  microsecond=0)
        day_end   = target.replace(hour=23, minute=59, second=59, microsecond=0)
        result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()
        events = result.get("items", [])

        # התאם את טקסט "היום" בפורמט
        if date_offset_days == 0:
            day_label = "היום"
        elif date_offset_days == 1:
            day_label = "מחר"
        elif date_offset_days == -1:
            day_label = "אתמול"
        else:
            day_label = target.strftime("%d/%m")

        if not events:
            return f"אין אירועים מתוכננים ל{day_label}."

        count = len(events)
        noun  = "אירוע" if count == 1 else "אירועים"
        parts = [f"יש לך {count} {noun} ל{day_label}."]
        for event in events[:4]:
            parts.append(_format_single_event(event))
        if count > 4:
            parts.append(f"ועוד {count - 4} נוספים.")
        return ". ".join(parts)

    except RuntimeError:
        return "ספריית Google Calendar לא מותקנת. הרץ pip install google-api-python-client."

    except FileNotFoundError:
        return "לא הוגדרו הרשאות Google Calendar. צריך להוסיף קובץ credentials.json."

    except Exception:
        return "לא הצלחתי לגשת ליומן כרגע."
