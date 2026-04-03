# שנה את השורות הבאות בלבד:

# שורה 13 — הוסף את account לייבוא:
from core.google_auth import get_credentials, DEFAULT_ACCOUNT, PERSONAL_ACCOUNT

# פונקציה _get_service — הוסף פרמטר account:
def _get_service(account: str = DEFAULT_ACCOUNT):
    if not _GOOGLE_LIBS_AVAILABLE:
        raise RuntimeError("ספריות Google לא מותקנות.")
    creds = get_credentials(account)
    return build("calendar", "v3", credentials=creds)

# פונקציה get_calendar_summary — הוסף פרמטר account:
def get_calendar_summary(date_offset_days: int = 0, account: str = DEFAULT_ACCOUNT) -> str:
    try:
        service = _get_service(account)
        # שאר הקוד זהה...
        calendar_id = account  # ← השתמש בחשבון כ-Calendar ID
        result = service.events().list(
            calendarId=calendar_id,
            ...
        )

# פונקציה add_event — הוסף פרמטר account:
def add_event(instruction: str, account: str = DEFAULT_ACCOUNT) -> str:
    ...
    service = _get_service(account)
    service.events().insert(calendarId=account, body=event_body).execute()
