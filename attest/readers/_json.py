"""Load an API export and pull required fields out of it, loudly.

Every reader goes through these helpers, so a missing field, a truncated page
or an unreadable time stops the run with the file and row named instead of
being guessed around.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from attest.model import AttestError

# Windows PowerShell 5.1's ConvertTo-Json writes a DateTime as "/Date(ms)/".
_MS_DATE = re.compile(r"^/Date\((-?\d+)(?:[+-]\d{4})?\)/$")

# Graph and Defender report a device that is not Entra-joined as null or this GUID.
ZERO_GUID = "00000000-0000-0000-0000-000000000000"


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


def require_address(record: dict, key: str, file: str, row: int) -> str:
    """A required string that is an account address (a UPN or SMTP address), refused when padded with whitespace.

    A real address cannot carry leading or trailing whitespace. Duplicate checks and the rules that match
    addresses compare them as written (folding case only), so a padded copy of an address would pass as a
    different account; refusing it here keeps one address one spelling.
    """
    value = require_str(record, key, file, row)
    if value != value.strip():
        raise AttestError(f"{file}: row {row} field {key!r} has leading or trailing whitespace: {value!r}")
    return value


def require_bool(record: dict, key: str, file: str, row: int) -> bool:
    value = require(record, key, file, row)
    if not isinstance(value, bool):
        raise AttestError(f"{file}: row {row} field {key!r} must be true or false, got {value!r}")
    return value


def refuse_duplicates(values: Iterable[str], field: str, file: str, fold_case: bool = False) -> None:
    """Stop the run when two rows share a key; values are the key of each row, in row order.

    Two records for one entity can disagree, and any rule that picked one of
    them would pick silently. fold_case compares keys without regard to case.
    """
    first: dict[str, int] = {}
    for row, value in enumerate(values, start=1):
        key = value.lower() if fold_case else value
        if key in first:
            raise AttestError(f"{file}: rows {first[key]} and {row} share {field} {value!r}")
        first[key] = row


def device_id(value: Any, file: str, row: int, field: str) -> Optional[str]:
    """A lower-case Entra device GUID, or None when the device is not joined (null, "" or the all-zero GUID).

    Anything else is refused, never kept as an ID or read as "not joined": a bad
    value must not change which device a row is matched to.
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            canonical = str(uuid.UUID(value))
        except ValueError:
            canonical = None
        if canonical is not None:
            return None if canonical == ZERO_GUID else canonical
    raise AttestError(f"{file}: row {row} field {field!r} must be a device GUID or null, got {value!r}")


def has_no_utc_offset(value: Any) -> bool:
    """Whether value is a time written without a UTC offset: a naive datetime, or an ISO string with none.

    parse_time reads such a time as UTC, which is wrong for any export written in local time, so a caller whose
    answer depends on the real moment refuses it first. Anything that is not a time, or that carries an offset
    (or is a "/Date(ms)/", which is UTC), is False here: parse_time names what is not a time.
    """
    if isinstance(value, dict) and "value" in value:  # PowerShell 5.1 can wrap a DateTime as {"value": ...}
        value = value["value"]
    if isinstance(value, datetime):
        return value.utcoffset() is None
    if isinstance(value, str) and not _MS_DATE.match(value.strip()):
        try:
            return datetime.fromisoformat(value.strip()).utcoffset() is None
        except ValueError:
            return False
    return False


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
