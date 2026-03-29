# -*- coding: utf-8 -*-
"""
setup_google_credentials.py
============================
סקריפט חד-פעמי שמגדיר הרשאות Google (Calendar + Gmail) לפרויקט נרי.

הרצה:
    python setup_google_credentials.py

מה הסקריפט עושה:
    1. מדריך שלב-אחר-שלב איך ליצור פרויקט ב-Google Cloud Console
    2. מריץ OAuth flow (פותח דפדפן לאישור)
    3. שומר token.json לשימוש חוזר
    4. בודק שהגישה ל-Calendar ול-Gmail אכן עובדת
"""

import os
import sys


# ─── ספריות Google (בדיקת התקנה) ────────────────────────────────────────────
def _check_google_libs() -> None:
    missing = []
    for pkg in ("google.oauth2.credentials", "google_auth_oauthlib.flow", "googleapiclient.discovery"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg.split(".")[0])

    if missing:
        print("\n[שגיאה] חסרות ספריות Google. הרץ:")
        print("  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib\n")
        sys.exit(1)


_check_google_libs()

# ייבוא לאחר בדיקה
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ─── הגדרות ──────────────────────────────────────────────────────────────────
_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
_TOKEN_FILE       = os.getenv("GOOGLE_TOKEN_FILE",       "token.json")

# הרשאות נדרשות: Calendar מלא + Gmail modify
_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]


# ─── הדרכה ───────────────────────────────────────────────────────────────────
_GUIDE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              הגדרת הרשאות Google לפרויקט נרי                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

לפני שמריצים את ה-OAuth flow, יש להוריד קובץ credentials.json מ-Google.
בצע את השלבים הבאים פעם אחת בלבד:

┌─ שלב 1: פרויקט ב-Google Cloud Console ─────────────────────────────────────┐
│  1. פתח: https://console.cloud.google.com                                   │
│  2. לחץ על תפריט הפרויקטים (בראש העמוד) → "New Project"                   │
│  3. שם הפרויקט: nari-assistant  (או כל שם אחר)                             │
│  4. לחץ "Create" והמתן                                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ שלב 2: הפעלת APIs ────────────────────────────────────────────────────────┐
│  בתוך הפרויקט שיצרת:                                                       │
│  1. APIs & Services → Library                                               │
│  2. חפש "Google Calendar API" → Enable                                     │
│  3. חזור ל-Library, חפש "Gmail API" → Enable                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ שלב 3: יצירת OAuth Credentials ──────────────────────────────────────────┐
│  1. APIs & Services → Credentials → "+ Create Credentials"                 │
│  2. בחר "OAuth 2.0 Client ID"                                               │
│  3. Application type: "Desktop app"                                         │
│  4. שם: nari-desktop  (לא חשוב)                                             │
│  5. לחץ "Create"                                                             │
│  6. בחלון שנפתח לחץ "Download JSON"                                         │
│  7. שמור את הקובץ בשם: credentials.json                                    │
│     בתיקייה: {creds_dir}
└─────────────────────────────────────────────────────────────────────────────┘

┌─ שלב 4: OAuth Consent Screen ──────────────────────────────────────────────┐
│  אם נשאלת על Consent Screen:                                               │
│  1. User Type: External → Create                                            │
│  2. App name: נרי  |  User support email: המייל שלך                        │
│  3. בשדה "Test users" הוסף את כתובת ה-Gmail שלך                           │
│  4. שמור והמשך                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
"""


def _print_guide() -> None:
    creds_dir = os.path.abspath(os.path.dirname(_CREDENTIALS_FILE))
    print(_GUIDE.format(creds_dir=creds_dir))


# ─── OAuth Flow ───────────────────────────────────────────────────────────────
def _run_oauth_flow() -> Credentials:
    """
    מריץ OAuth flow ומחזיר Credentials.
    משתמש ב-token.json קיים אם אפשר.
    """
    creds = None

    # נסה לטעון token קיים
    if os.path.exists(_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(_TOKEN_FILE, _SCOPES)

    # רענן אם פג תוקף
    if creds and creds.expired and creds.refresh_token:
        print("[*] מרענן token קיים...")
        try:
            creds.refresh(Request())
            print("[v] Token רוּנן בהצלחה.")
            return creds
        except Exception as exc:
            print(f"[!] כישלון ברענון: {exc}  – יבצע OAuth מחדש.")
            creds = None

    # בדוק שקובץ credentials קיים
    if not os.path.exists(_CREDENTIALS_FILE):
        print(f"\n[שגיאה] הקובץ '{_CREDENTIALS_FILE}' לא נמצא.")
        print("        בצע את השלבים בהדרכה למעלה ואז הרץ שוב.\n")
        sys.exit(1)

    # OAuth flow חדש
    print("\n[*] פותח דפדפן לאישור Google...")
    print("    כנס עם חשבון ה-Gmail שלך ואשר את ההרשאות.\n")

    flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_FILE, _SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    # שמור token
    with open(_TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())

    print(f"[v] token.json נשמר: {os.path.abspath(_TOKEN_FILE)}")
    return creds


# ─── בדיקת Calendar ───────────────────────────────────────────────────────────
def _test_calendar(creds: Credentials) -> bool:
    """בודק גישה ל-Google Calendar ומדפיס את שם הלוח הראשי."""
    try:
        service = build("calendar", "v3", credentials=creds)
        cal = service.calendars().get(calendarId="primary").execute()
        summary = cal.get("summary", "לא ידוע")
        print(f"[v] Google Calendar: גישה תקינה  (לוח: '{summary}')")
        return True
    except Exception as exc:
        print(f"[x] Google Calendar: שגיאה – {exc}")
        return False


# ─── בדיקת Gmail ─────────────────────────────────────────────────────────────
def _test_gmail(creds: Credentials) -> bool:
    """בודק גישה ל-Gmail API ומדפיס את כתובת המייל."""
    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "לא ידוע")
        print(f"[v] Gmail: גישה תקינה  (חשבון: {email})")
        return True
    except Exception as exc:
        print(f"[x] Gmail: שגיאה – {exc}")
        return False


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n" + "=" * 78)
    print("  הגדרת הרשאות Google לנרי")
    print("=" * 78)

    # הצג הדרכה רק אם credentials.json לא קיים עדיין
    if not os.path.exists(_CREDENTIALS_FILE) and not os.path.exists(_TOKEN_FILE):
        _print_guide()
        input("לאחר שהורדת את credentials.json ושמרת אותו בתיקייה הנכונה,\nלחץ Enter להמשך...")

    creds = _run_oauth_flow()

    print("\n── בדיקת חיבורים ──────────────────────────────────────────────────────────")
    cal_ok   = _test_calendar(creds)
    gmail_ok = _test_gmail(creds)

    print("\n── סיכום ──────────────────────────────────────────────────────────────────")
    if cal_ok and gmail_ok:
        print("[v] הכל מוגדר! אפשר להריץ:  python nari_main.py")
    else:
        if not cal_ok:
            print("[!] Google Calendar לא עובד. ודא שה-API מופעל ושה-scope נכון.")
        if not gmail_ok:
            print("[!] Gmail לא עובד. ודא שה-API מופעל ושה-scope נכון.")
        print("    תקן את הבעיות ואז הרץ את הסקריפט שוב.\n")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
