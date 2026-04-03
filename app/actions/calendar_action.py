# -*- coding: utf-8 -*-
"""
פעולת יומן – שולפת אירועי היום מ-Google Calendar ומחזירה סיכום עברי לקריאה בקול.
תומך בשני חשבונות: ארגוני (info@irondt.co.il) ואישי (iran.hadad@gmail.com).
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from config import OPENAI_API_KEY, LLM_MODEL

try:
    from googleapiclient.discovery import build
    from core.google_auth import get_credentials, DEFAULT_ACCOUNT, PERSONAL_ACCOUNT
    _GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    _GOOGLE_LIBS_AVAILABLE = False

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

_DAY_NAMES = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def _get_service(account: str = None):
    if not _GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("ספריות Google לא מותקנות.")
    if account is None:
        account = DEFAULT_ACCOUNT
    creds = get_credentials(account)
    return build("calendar", "v3", credentials=creds), account


def _parse_event_time(event: dict) -> Optional[datetime]:
    start = event.get("start", {})
    time_str = start.get("dateTime") or start.get("date")
    if not time_str:
        return None
    try:
        if "T" in time_str:
            return datetime.fromisoformat(time_str)
        return datetime.fromisoformat(time_str + "T00:00:00")
    except ValueError:
        return None


def _format_single_event(event: dict) -> str:
    summary  = event.get("summary", "אירוע ללא שם")
    location = event.get("location", "")
    dt       = _parse_event_time(event)

    if dt is None:
        return summary

    start_info = event.get("start", {})
    is_all_day = "date" in start_info and "dateTime" not in start_info

    time_part = "כל היום" if is_all_day else f"בשעה {dt.strftime('%H:%M')}"
    loc_part  = f" ב{location}" if location else ""
    return f"{time_part}: {summary}{loc_part}"


def _extract_event_details(instruction: str) -> dict:
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


def add_event(instruction: str, account: str = None) -> str:
    if account is None:
        account = DEFAULT_ACCOUNT
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

        service, calendar_id = _get_service(account)
        service.events().insert(calendarId=calendar_id, body=event_body).execute()

        day_offset = (start_dt.date() - datetime.now().date()).days
        if day_offset == 0:
            day_word = "היום"
        elif day_offset == 1:
            day_word = "מחר"
        else:
            day_word = f"ב-{date_str}"

        account_label = "ביומן האישי" if account == PERSONAL_ACCOUNT else "ביומן הארגוני"
        return f"{title} נוספה {day_word} ב-{time_str} {account_label}"

    except RuntimeError:
        return "ספריית Google Calendar לא מותקנת."
    except FileNotFoundError:
        return "לא הוגדרו הרשאות Google Calendar."
    except Exception as exc:
        return f"לא הצלחתי להוסיף את האירוע: {exc}"


def get_calendar_summary(date_offset_days: int = 0, account: str = None) -> str:
    if account is None:
        account = DEFAULT_ACCOUNT
    try:
        service, calendar_id = _get_service(account)
        now = datetime.now().astimezone()
        target = now + timedelta(days=date_offset_days)
        day_start = target.replace(hour=0,  minute=0,  second=0,  microsecond=0)
        day_end   = target.replace(hour=23, minute=59, second=59, microsecond=0)

        result = service.events().list(
            calendarId=calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()
        events = result.get("items", [])

        if date_offset_days == 0:
            day_label = "היום"
        elif date_offset_days == 1:
            day_label = "מחר"
        elif date_offset_days == -1:
            day_label = "אתמול"
        else:
            day_label = target.strftime("%d/%m")

        account_label = "באישי" if account == PERSONAL_ACCOUNT else "בארגוני"

        if not events:
            return f"אין אירועים מתוכננים ל{day_label} {account_label}."

        count = len(events)
        noun  = "אירוע" if count == 1 else "אירועים"
        parts = [f"יש לך {count} {noun} ל{day_label} {account_label}."]
        for event in events[:4]:
            parts.append(_format_single_event(event))
        if count > 4:
            parts.append(f"ועוד {count - 4} נוספים.")
        return ". ".join(parts)

    except RuntimeError:
        return "ספריית Google Calendar לא מותקנת."
    except FileNotFoundError:
        return "לא הוגדרו הרשאות Google Calendar."
    except Exception as exc:
        return f"לא הצלחתי לגשת ליומן: {exc}"
