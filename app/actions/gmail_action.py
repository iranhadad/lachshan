# -*- coding: utf-8 -*-
"""
פעולת מייל – קריאת inbox, יצירת טיוטה ואישור קולי לפני שליחה.
תומך בשני חשבונות: ארגוני (info@irondt.co.il) ואישי (iran.hadad@gmail.com).

זרימה (שליחה):
  1. compose_draft(instruction) → EmailDraft
  2. draft_to_speech_preview(draft) → טקסט לקריאה בקול
  3. המשתמש אומר "כן" / "אישור" / "שלחי" → send_draft(draft)
  4. המשתמש אומר "לא" / "ביטול" → מבטל
"""

import base64
import os
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Optional

from openai import OpenAI

from config import OPENAI_API_KEY, LLM_MODEL

_client = OpenAI(api_key=OPENAI_API_KEY)

_CONFIRM_WORDS = {"כן", "אישור", "שלחי", "שלח", "yes", "confirm", "send"}
_CANCEL_WORDS  = {"לא", "ביטול", "בטל", "cancel", "no", "stop"}

DEFAULT_ACCOUNT  = "info@irondt.co.il"
PERSONAL_ACCOUNT = "iran.hadad@gmail.com"


@dataclass
class EmailDraft:
    to: str
    subject: str
    body: str
    account: str = DEFAULT_ACCOUNT
    approved: bool = False


def compose_draft(instruction: str, account: str = DEFAULT_ACCOUNT) -> Optional[EmailDraft]:
    """יוצר טיוטת מייל מהוראה בעברית."""
    prompt = (
        "אתה עוזר אישי. צור טיוטת מייל לפי ההוראה הבאה.\n"
        "החזר בפורמט המדויק הזה (שלושה שורות, בדיוק):\n"
        "TO: <כתובת מייל או UNKNOWN>\n"
        "SUBJECT: <נושא>\n"
        "BODY: <גוף המייל>\n\n"
        f"הוראה: {instruction}"
    )
    try:
        resp = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()
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
        account=account,
    )


def draft_to_speech_preview(draft: EmailDraft) -> str:
    """ממיר טיוטה לטקסט קריאה בקול לאישור."""
    preview_body = draft.body[:80] + ("..." if len(draft.body) > 80 else "")
    to_part = f"ל-{draft.to}" if draft.to != "UNKNOWN" else ""
    account_label = "מהמייל האישי" if draft.account == PERSONAL_ACCOUNT else "מהמייל הארגוני"
    return (
        f"הכנתי טיוטת מייל {to_part} {account_label}. "
        f"נושא: {draft.subject}. "
        f"תוכן: {preview_body}. "
        "האם לשלוח? אמור כן או לא."
    )


def is_confirmation(text: str) -> bool:
    return any(w in text.strip().lower() for w in _CONFIRM_WORDS)


def is_cancellation(text: str) -> bool:
    return any(w in text.strip().lower() for w in _CANCEL_WORDS)


def send_draft(draft: EmailDraft) -> str:
    """שולח את הטיוטה דרך Gmail API."""
    try:
        from googleapiclient.discovery import build
        from core.google_auth import get_credentials
    except ImportError as exc:
        return f"חסרה תלות: {exc}."

    try:
        creds = get_credentials(draft.account)
        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(draft.body)
        message["to"] = draft.to
        message["from"] = draft.account
        message["subject"] = draft.subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        return f"המייל בנושא '{draft.subject}' נשלח מ-{draft.account}."

    except Exception as exc:
        return f"לא הצלחתי לשלוח את המייל: {exc}"


def read_inbox(account: str = DEFAULT_ACCOUNT) -> str:
    """קורא עד 5 מיילים לא נקראים מה-inbox ומחזיר סיכום בעברית."""
    try:
        from googleapiclient.discovery import build
        from core.google_auth import get_credentials
    except ImportError as exc:
        return f"חסרה תלות: {exc}."

    try:
        creds = get_credentials(account)
        service = build("gmail", "v1", credentials=creds)
        result = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=5
        ).execute()
        messages = result.get("messages", [])

        account_label = "האישי" if account == PERSONAL_ACCOUNT else "הארגוני"

        if not messages:
            return f"אין מיילים לא נקראים בתיבת הדואר {account_label}."

        lines: list[str] = []
        for msg in messages:
            data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"],
            ).execute()
            headers = {h["name"]: h["value"] for h in data["payload"]["headers"]}
            sender  = headers.get("From", "שולח לא ידוע")
            subject = headers.get("Subject", "ללא נושא")
            if "<" in sender:
                sender = sender[: sender.index("<")].strip().strip('"')
            lines.append(f"{sender}: {subject}")

        count = len(messages)
        items = ". ".join(lines)
        return f"יש לך {count} מיילים לא נקראים ב{account_label}: {items}."

    except Exception as exc:
        return f"לא הצלחתי לקרוא את המיילים: {exc}"
