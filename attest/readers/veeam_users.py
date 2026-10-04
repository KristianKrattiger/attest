"""Veeam Backup for Microsoft 365 user data: `Get-VBOEntityData -Type User`, selected and ConvertTo-Json.

The field names (Email, IsMailboxBackedUp, MailboxBackedUpTime) come from
Veeam's published PowerShell examples, not its reference documentation; the
documented REST form of this data has no backup timestamps, so it cannot
prove a daily backup. Check them against the first real export before any
paid check relies on this reader. A missing field stops the run.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from attest.readers._json import load_records, parse_time, require, require_bool, require_str


@dataclass(frozen=True)
class VeeamUser:
    email: str
    mailbox_backed_up: bool
    mailbox_backed_up_time: Optional[datetime]
    cite: str


def read(path: Path) -> tuple[VeeamUser, ...]:
    file = Path(path).name
    users = []
    for row, r in enumerate(load_records(path), start=1):
        when = require(r, "MailboxBackedUpTime", file, row)
        users.append(VeeamUser(
            email=require_str(r, "Email", file, row),
            mailbox_backed_up=require_bool(r, "IsMailboxBackedUp", file, row),
            mailbox_backed_up_time=None if when in (None, "") else parse_time(when, file, row, "MailboxBackedUpTime"),
            cite=f"{file}:{row}",
        ))
    return tuple(users)
