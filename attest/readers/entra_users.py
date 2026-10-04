"""Entra users: Microsoft Graph `GET /users?$select=id,userPrincipalName,displayName,accountEnabled,userType`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.readers._json import load_records, require_bool, require_str


@dataclass(frozen=True)
class User:
    id: str
    upn: str
    display_name: str
    enabled: bool
    user_type: str  # "Member", "Guest", or "" when Graph returned null
    cite: str


def read(path: Path) -> tuple[User, ...]:
    file = Path(path).name
    return tuple(
        User(
            id=require_str(r, "id", file, row),
            upn=require_str(r, "userPrincipalName", file, row),
            display_name=r.get("displayName") or "",
            enabled=require_bool(r, "accountEnabled", file, row),
            user_type=r.get("userType") or "",
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path), start=1)
    )
