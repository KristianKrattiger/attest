"""Veeam Backup for Microsoft 365 user data: `Get-VBOEntityData -Type User`, selected and ConvertTo-Json.

The field names (Email, IsMailboxBackedUp, MailboxBackedUpTime) come from
Veeam's published PowerShell examples, not its reference documentation; the
documented REST form of this data has no backup timestamps, so it cannot
prove a daily backup. Check them against the first real export before any
paid check relies on this reader. A missing field stops the run, and so does a
backup time with no UTC offset (see parse_time): read as UTC, a server east of
UTC would look fresher than it is. An `Email` with leading or trailing
whitespace stops the run too, as do two rows for one `Email` in any case: a
padded or repeated address would pass as another mailbox, or let row order
decide.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from attest.readers._json import load_records, parse_time, refuse_duplicates, require, require_address, require_bool


@dataclass(frozen=True)
class VeeamUser:
    email: str
    mailbox_backed_up: bool
    mailbox_backed_up_time: Optional[datetime]
    cite: str


def _backed_up_time(value: object, file: str, row: int) -> Optional[datetime]:
    """The backup time as UTC; None for "never backed up". A time with no UTC offset is refused."""
    if value in (None, ""):
        return None
    return parse_time(value, file, row, "MailboxBackedUpTime")


def read(path: Path) -> tuple[VeeamUser, ...]:
    file = Path(path).name
    users = []
    for row, r in enumerate(load_records(path), start=1):
        when = _backed_up_time(require(r, "MailboxBackedUpTime", file, row), file, row)
        users.append(VeeamUser(
            email=require_address(r, "Email", file, row),
            mailbox_backed_up=require_bool(r, "IsMailboxBackedUp", file, row),
            mailbox_backed_up_time=when,
            cite=f"{file}:{row}",
        ))
    refuse_duplicates((u.email for u in users), "Email", file, fold_case=True)
    return tuple(users)
