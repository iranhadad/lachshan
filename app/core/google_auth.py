# -*- coding: utf-8 -*-
"""
ניהול מרכזי של Google credentials דרך Service Account עם Impersonation.
תומך בשני חשבונות:
  - ארגוני: info@irondt.co.il (ברירת מחדל)
  - אישי:   iran.hadad@gmail.com
"""
import json
import os

from google.oauth2 import service_account

_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ברירת מחדל — חשבון ארגוני
DEFAULT_ACCOUNT = "info@irondt.co.il"
PERSONAL_ACCOUNT = "iran.hadad@gmail.com"

# cache נפרד לכל חשבון
_creds_cache: dict = {}


def get_credentials(account: str = DEFAULT_ACCOUNT) -> service_account.Credentials:
    """
    מחזיר Service Account Credentials עם impersonation לחשבון הנתון.
    
    Args:
        account: כתובת המייל שה-Service Account מתחזה אליה.
                 ברירת מחדל: info@irondt.co.il
    """
    global _creds_cache

    # החזר מ-cache אם קיים ותקף
    if account in _creds_cache and _creds_cache[account].valid:
        return _creds_cache[account]

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise FileNotFoundError(
            "משתנה סביבה GOOGLE_SERVICE_ACCOUNT_JSON לא מוגדר."
        )

    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=_SCOPES,
        subject=account,  # ← זה ה-impersonation
    )

    _creds_cache[account] = creds
    return creds


def get_org_credentials() -> service_account.Credentials:
    """מחזיר credentials לחשבון הארגוני info@irondt.co.il"""
    return get_credentials(DEFAULT_ACCOUNT)


def get_personal_credentials() -> service_account.Credentials:
    """מחזיר credentials לחשבון האישי iran.hadad@gmail.com"""
    return get_credentials(PERSONAL_ACCOUNT)
