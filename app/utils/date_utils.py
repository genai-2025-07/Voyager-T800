from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple


ISO_DATE_RE = re.compile(r"(\d{4})[-/](\d{2})[-/](\d{2})")


def _safe_parse(date_str: str) -> Optional[datetime]:
    """Try multiple common date formats and ISO-8601.

    Returns None if nothing matches, keeping the caller simple.
    """
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return None


def extract_date_range(text: str) -> Tuple[datetime, datetime]:
    """Extract a best-effort [start_date, end_date] from free text.

    Heuristics:
      - Look for two ISO-like dates (YYYY-MM-DD or YYYY/MM/DD). If found, sort them.
      - Look for patterns like "from <date> to <date>".
      - Fallback: today .. today+2 (3-day window) so we at least have a range.

    Always returns valid datetimes in increasing order.
    """
    if not isinstance(text, str):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return today, today + timedelta(days=2)

    # 1) Two explicit dates anywhere
    matches = ISO_DATE_RE.findall(text)
    if len(matches) >= 2:
        parsed = []
        for y, m, d in matches[:2]:
            dt = _safe_parse(f"{y}-{m}-{d}")
            if dt:
                parsed.append(dt)
        if len(parsed) == 2:
            parsed.sort()
            return parsed[0], parsed[1]

    # 2) from X to Y pattern (with tolerant separators)
    span = re.search(r"from\s+([^\n]+?)\s+to\s+([^\n]+)", text, flags=re.IGNORECASE)
    if span:
        start_candidate = _safe_parse(span.group(1))
        end_candidate = _safe_parse(span.group(2))
        if start_candidate and end_candidate:
            start, end = sorted([start_candidate, end_candidate])
            return start, end

    # Fallback: 3 days starting today
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today, today + timedelta(days=2)


def derive_city_from_text(text: str) -> Optional[str]:
    """Best-effort city extraction: last capitalized token of length >= 3.

    This is intentionally simple and deterministic for a minimal UI/chain hint.
    A real system should rely on a proper NER/location parser.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    tokens = [t.strip(",. ") for t in text.split()]
    candidates = [t for t in tokens if len(t) >= 3 and t[0].isupper()]
    return candidates[-1] if candidates else None


