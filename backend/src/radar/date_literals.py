from __future__ import annotations

import re
from datetime import date

ISO_DAY = re.compile(r"(?<!\d)(20\d{2})-(0[1-9]|1[0-2])-([012]\d|3[01])(?!\d)")
ZH_DAY = re.compile(r"(?<!\d)(20\d{2})年(1[0-2]|0?[1-9])月(3[01]|[12]\d|0?[1-9])日")
ISO_MONTH = re.compile(r"(?<!\d)(20\d{2})-(0[1-9]|1[0-2])(?!-?\d)")
ZH_MONTH = re.compile(r"(?<!\d)(20\d{2})年(1[0-2]|0?[1-9])月(?!\d)")
MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    )
    if name
}
EN_DAY = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+([012]?\d|3[01]),\s*(20\d{2})\b",
    re.IGNORECASE,
)


def explicit_dates(text: str, precision: str = "day") -> set[date]:
    found: set[date] = set()
    patterns = (ISO_DAY, ZH_DAY)
    for pattern in patterns:
        for match in pattern.finditer(text):
            try:
                found.add(date(*(int(value) for value in match.groups())))
            except ValueError:
                pass
    for match in EN_DAY.finditer(text):
        try:
            found.add(
                date(int(match.group(3)), MONTHS[match.group(1).casefold()], int(match.group(2)))
            )
        except ValueError:
            pass
    if precision == "month":
        for pattern in (ISO_MONTH, ZH_MONTH):
            for match in pattern.finditer(text):
                found.add(date(int(match.group(1)), int(match.group(2)), 1))
    return found
