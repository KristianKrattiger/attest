"""Load an API export and pull required fields out of it, loudly.

Every reader goes through these helpers, so a missing field, a truncated page
or an unreadable time stops the run with the file and row named instead of
being guessed around.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from attest.model import AttestError

# Windows PowerShell 5.1's ConvertTo-Json writes a DateTime as "/Date(ms)/".
_MS_DATE = re.compile(r"^/Date\((-?\d+)(?:[+-]\d{4})?\)/$")


def load_records(path: Path) -> list[dict]:
    """The records of a JSON export: a list, a Graph or Defender page {"value": [...]}, or one object.

    Windows PowerShell 5.1 writes UTF-16 by default; a UTF-16 byte-order mark is
    honoured, otherwise the file is read as UTF-8 with or without a BOM; a file
    that is neither is refused, not guessed at. A page that carries
    "@odata.nextLink" is one page of several and is refused: a truncated user or
    device list would shrink the population.
    """
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise AttestError(f"{path.name}: not UTF-8 or UTF-16 text ({e.reason})") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AttestError(f"{path.name}: not valid JSON ({e.msg} at line {e.lineno})") from e
    if isinstance(data, dict) and "@odata.nextLink" in data:
        raise AttestError(f"{path.name}: the export is one page of several (it has @odata.nextLink)")
    if isinstance(data, dict) and isinstance(data.get("value"), list):
        records = data["value"]
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        raise AttestError(f"{path.name}: expected a JSON list or object, got {type(data).__name__}")
    for row, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise AttestError(f"{path.name}: row {row} is not a JSON object")
    return records


def require(record: dict, key: str, file: str, row: int) -> Any:
    """The value of a field the export must carry; its absence stops the run."""
    if key not in record:
        raise AttestError(f"{file}: row {row} has no field {key!r}")
    return record[key]


def require_str(record: dict, key: str, file: str, row: int) -> str:
    value = require(record, key, file, row)
    if not isinstance(value, str) or not value:
        raise AttestError(f"{file}: row {row} field {key!r} must be a non-empty string, got {value!r}")
    return value


def require_bool(record: dict, key: str, file: str, row: int) -> bool:
    value = require(record, key, file, row)
    if not isinstance(value, bool):
        raise AttestError(f"{file}: row {row} field {key!r} must be true or false, got {value!r}")
    return value


def parse_time(value: Any, file: str, row: int, key: str) -> datetime:
    """An ISO 8601 time, a PowerShell 5.1 "/Date(ms)/", or a datetime YAML already parsed; always UTC-aware.

    A time with another UTC offset is converted to UTC; a time with no offset is taken as UTC.
    """
    if isinstance(value, dict) and "value" in value:  # PowerShell 5.1 can wrap a DateTime as {"value": ...}
        value = value["value"]
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and (match := _MS_DATE.match(value.strip())):
        try:
            return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as e:  # the ms count is beyond what a datetime can hold
            raise AttestError(f"{file}: row {row} field {key!r} is not a time: {value!r}") from e
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.strip())
        except ValueError as e:
            raise AttestError(f"{file}: row {row} field {key!r} is not a time: {value!r}") from e
    else:
        raise AttestError(f"{file}: row {row} field {key!r} is not a time: {value!r}")
    return moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
