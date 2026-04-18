import re
from typing import Any

MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15


def normalize_phone_number(value: Any | None) -> str | None:
    if value is None:
        return None

    normalized = re.sub(r"\D+", "", str(value))
    return normalized or None


def parse_phone_number(value: Any | None) -> str | None:
    normalized = normalize_phone_number(value)
    if normalized is None:
        return None

    if not (MIN_PHONE_DIGITS <= len(normalized) <= MAX_PHONE_DIGITS):
        return None

    return normalized
