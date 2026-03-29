# -*- coding: utf-8 -*-
"""
ניהול מרכזי של Google OAuth credentials.
טוען token.json פעם אחת לזיכרון (singleton).
OAuth flow נפתח רק אם token.json לא קיים או פג תוקף ואין refresh_token.
"""

import os

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE

_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

_cached_creds: "Credentials | None" = None  # singleton – טוען פעם אחת בלבד


def get_credentials() -> Credentials:
    """
    מחזיר Google Credentials תקפים.
    סדר עדיפויות:
      1. cache בזיכרון (אם עדיין תקף)
      2. token.json קיים – טוען ומרענן אם צריך
      3. OAuth flow דרך דפדפן (רק אם אין ברירה)
    """
    global _cached_creds

    # 1. השתמש ב-cache אם תקף
    if _cached_creds and _cached_creds.valid:
        return _cached_creds

    creds: "Credentials | None" = None

    # 2. טען מ-token.json אם קיים
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, _SCOPES)

    # 3. רענן אם פג תוקף, או הרץ OAuth אם אין token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"קובץ {GOOGLE_CREDENTIALS_FILE} לא נמצא. "
                    "הורד אותו מ-Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE, _SCOPES
            )
            creds = flow.run_local_server(port=0)

        # שמור ל-token.json לשימוש עתידי
        with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    # שמור ב-cache לשימוש חוזר באותה הרצה
    _cached_creds = creds
    return _cached_creds
