# -*- coding: utf-8 -*-
"""
פעולת מייל – קריאת inbox, יצירת טיוטה ואישור קולי לפני שליחה.

זרימה (שליחה):
  1. compose_draft(instruction) → EmailDraft
  2. draft_to_speech_preview(draft) → טקסט לקריאה בקול
  3. המשתמש אומר "כן" / "אישור" / "שלחי" → send_draft(draft)  [stub]
  4. המשתמש אומר "לא" / "ביטול"            → מבטל

TODO: חבר ל-Gmail API ב-send_draft.
"""

import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from config import OPENAI_API_KEY, LLM_MODEL

_client = OpenAI(api_key=OPENAI_API_KEY)

_CONFIRM_WORDS = {"כן", "אישור", "שלחי", "שלח", "yes", "confirm", "send"}
_CANCEL_WORDS  = {"לא", "ביטול", "בטל", "cancel", "no", "stop"}


@dataclass
class EmailDraft:
    to: str
    subject: str
    body: str
    approved: bool = False


def compose_draft(instruction: str) -> Optional[EmailDraft]:
    """
    יוצר טיוטת מייל מהוראה בעברית.
    מחזיר EmailDraft או None אם יצירה נכשלה.
    """
    prompt = (
        "אתה עוזר אישי. צור טיוטת מייל לפי ההוראה הבאה.\n"
        "החזר בפורמט המדויק הזה (שלושה שורות, בדיוק):\n"
        "TO: <כתובת מייל או UNKNOWN>\n"
        "SUBJECT: <נושא>\n"
        "BODY: <גוף המייל>\n\n"
        f"הוראה: {instruction}"
    )
    try:
        resp = _client.responses.create(model=LLM_MODEL, input=prompt)
        text = resp.output_text.strip()
    except Exception:
        return None

    to_val = "UNKNOWN"
    subject_val = ""
    body_lines: list[str] = []
    in_body = False

    for line in text.splitlines():
        if line.startswith("TO:"):
            to_val = line[3:].strip()
        elif line.startswith("SUBJECT:"):
            subject_val = line[8:].strip()
        elif line.startswith("BODY:"):
            in_body = True
            body_lines.append(line[5:].strip())
        elif in_body:
            body_lines.append(line)

    return EmailDraft(
        to=to_val,
        subject=subject_val,
        body="\n".join(body_lines).strip(),
    )


def draft_to_speech_preview(draft: EmailDraft) -> str:
    """ממיר טיוטה לטקסט קריאה בקול לאישור."""
    preview_body = draft.body[:80] + ("..." if len(draft.body) > 80 else "")
    to_part = f"ל-{draft.to}" if draft.to != "UNKNOWN" else ""
    return (
        f"הכנתי טיוטת מייל {to_part}. "
        f"נושא: {draft.subject}. "
        f"תוכן: {preview_body}. "
        "האם לשלוח? אמור כן או לא."
    )


def is_confirmation(text: str) -> bool:
    """מחזיר True אם הטקסט מביע אישור שליחה."""
    lower = text.strip().lower()
    return any(w in lower for w in _CONFIRM_WORDS)


def is_cancellation(text: str) -> bool:
    """מחזיר True אם הטקסט מביע ביטול."""
    lower = text.strip().lower()
    return any(w in lower for w in _CANCEL_WORDS)


def send_draft(draft: EmailDraft) -> str:
    """
    שולח את הטיוטה.
    כרגע stub – מחזיר אישור מילולי.
    TODO: חבר ל-Gmail API (google-auth + googleapiclient).
    """
    # stub
    return f"המייל בנושא '{draft.subject}' נשלח."


def read_inbox() -> str:
    """
    קורא עד 5 מיילים לא נקראים מה-inbox ומחזיר סיכום בעברית.
    מסתמך על core.google_auth (singleton משותף עם Calendar).
    """
    try:
        from googleapiclient.discovery import build
        from core.google_auth import get_credentials
    except ImportError as exc:
        return f"חסרה תלות: {exc}. נא להתקין google-auth-oauthlib ו-google-api-python-client."

    try:
        creds = get_credentials()
        service = build("gmail", "v1", credentials=creds)
        result = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=5
        ).execute()
        messages = result.get("messages", [])

        if not messages:
            return "אין מיילים לא נקראים בתיבת הדואר."

        lines: list[str] = []
        for msg in messages:
            data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"],
            ).execute()
            headers = {h["name"]: h["value"] for h in data["payload"]["headers"]}
            sender  = headers.get("From", "שולח לא ידוע")
            subject = headers.get("Subject", "ללא נושא")
            # חלץ שם שולח בלבד אם כתוב בפורמט "שם <email>"
            if "<" in sender:
                sender = sender[: sender.index("<")].strip().strip('"')
            lines.append(f"{sender}: {subject}")

        count = len(messages)
        items = ". ".join(lines)
        return f"יש לך {count} מיילים לא נקראים: {items}."

    except Exception as exc:
        return f"לא הצלחתי לקרוא את המיילים: {exc}"
