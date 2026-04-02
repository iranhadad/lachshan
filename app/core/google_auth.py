# -*- coding: utf-8 -*-
"""
ניהול מרכזי של Google credentials דרך Service Account.
קורא את ה-JSON מ-Environment Variable: GOOGLE_SERVICE_ACCOUNT_JSON
"""
import json
import os

from google.oauth2 import service_account

_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

_cached_creds = None  # singleton


def get_credentials() -> service_account.Credentials:
    global _cached_creds

    if _cached_creds and _cached_creds.valid:
        return _cached_creds

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise FileNotFoundError(
            "משתנה סביבה GOOGLE_SERVICE_ACCOUNT_JSON לא מוגדר."
        )

    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=_SCOPES
    )

    _cached_creds = creds
    return _cached_creds
