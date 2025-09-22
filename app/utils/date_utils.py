from datetime import datetime, timedelta
import re


def preprocess_dates(user_input: str) -> dict:
    today = datetime.today().date()
    hints = {}

    # Trip duration extraction: supports multiple phrasings
    duration_days = None

    # for X days
    m = re.search(r"\bfor\s+(\d+)\s+days?\b", user_input, re.IGNORECASE)
    if m:
        duration_days = int(m.group(1))

    # for X nights (convert nights to days ~ nights + 1)
    if duration_days is None:
        m = re.search(r"\bfor\s+(\d+)\s+nights?\b", user_input, re.IGNORECASE)
        if m:
            duration_days = int(m.group(1)) + 1

    # X-day trip / X days trip
    if duration_days is None:
        m = re.search(r"\b(\d+)\s*-?\s*day(?:s)?(?:\s+trip)?\b", user_input, re.IGNORECASE)
        if m:
            duration_days = int(m.group(1))

    # stay X days
    if duration_days is None:
        m = re.search(r"\bstay\s+(\d+)\s+days?\b", user_input, re.IGNORECASE)
        if m:
            duration_days = int(m.group(1))

    # stay X nights
    if duration_days is None:
        m = re.search(r"\bstay\s+(\d+)\s+nights?\b", user_input, re.IGNORECASE)
        if m:
            duration_days = int(m.group(1)) + 1

    if duration_days is not None and "start_date" not in hints and "end_date" not in hints:
        hints["start_date"] = today
        hints["end_date"] = today + timedelta(days=duration_days)

    # "tomorrow"
    if re.search(r"\btomorrow\b", user_input, re.IGNORECASE):
        hints["start_date"] = today + timedelta(days=1)
        hints["end_date"] = today + timedelta(days=1)

    # "this weekend"
    if re.search(r"this weekend", user_input, re.IGNORECASE):
        days_ahead = (5 - today.weekday()) % 7  # Saturday
        start = today + timedelta(days=days_ahead)
        end = start + timedelta(days=1)
        hints["start_date"] = start
        hints["end_date"] = end

    # "next week"
    if re.search(r"next week", user_input, re.IGNORECASE):
        days_ahead = (7 - today.weekday()) % 7  # Next Monday
        start = today + timedelta(days=days_ahead)
        end = start + timedelta(days=6)
        hints["start_date"] = start
        hints["end_date"] = end

    return hints

def get_time_block(hour: int) -> str:
    if 8 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 23:
        return "evening"
    else:
        return None