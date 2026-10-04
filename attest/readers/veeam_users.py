"""Veeam Backup for Microsoft 365 user data: `Get-VBOEntityData -Type User`, selected and ConvertTo-Json.

The field names (Email, IsMailboxBackedUp, MailboxBackedUpTime) come from
Veeam's published PowerShell examples, not its reference documentation; the
documented REST form of this data has no backup timestamps, so it cannot
prove a daily backup. Check them against the first real export before any
paid check relies on this reader. A missing field stops the run, and so does a
backup time with no UTC offset: the reader would take it as UTC, and a server
east of UTC would then look fresher than it is.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from attest.model import AttestError
from attest.readers._json import load_records, parse_time, require, require_bool, require_str


@dataclass(frozen=True)
class VeeamUser:
    email: str
    mailbox_backed_up: bool
    mailbox_backed_up_time: Optional[datetime]
    cite: str


def _backed_up_time(value: object, file: str, row: int) -> Optional[datetime]:
    """The backup time as UTC; None for "never backed up". An ISO time with no offset is refused."""
    if value in (None, ""):
        return None
    iso = value["value"] if isinstance(value, dict) and "value" in value else value
    if isinstance(iso, str):  # "/Date(ms)/" is UTC epoch milliseconds and does not parse here
        try:
            naive = datetime.fromisoformat(iso.strip()).tzinfo is None
        except ValueError:
            naive = False  # parse_time names a string that is not a time
        if naive:
            raise AttestError(
                f"{file}: row {row} field 'MailboxBackedUpTime' has no UTC offset: {iso!r}; "
                "export it as UTC (see docs/exports.md)")
    return parse_time(value, file, row, "MailboxBackedUpTime")


def read(path: Path) -> tuple[VeeamUser, ...]:
    file = Path(path).name
    users = []
    for row, r in enumerate(load_records(path), start=1):
        when = _backed_up_time(require(r, "MailboxBackedUpTime", file, row), file, row)
        users.append(VeeamUser(
            email=require_str(r, "Email", file, row),
            mailbox_backed_up=require_bool(r, "IsMailboxBackedUp", file, row),
            mailbox_backed_up_time=when,
            cite=f"{file}:{row}",
        ))
    return tuple(users)
