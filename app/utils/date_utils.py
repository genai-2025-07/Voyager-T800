from datetime import datetime, timedelta
import re


def preprocess_dates(user_input: str) -> dict:
    today = datetime.today().date()
    hints = {}

    # "for X days"
    match = re.search(r"for\s+(\d+)\s+day", user_input, re.IGNORECASE)
    if match:
        days = int(match.group(1))
        hints["start_date"] = today
        hints["end_date"] = today + timedelta(days=days)

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
