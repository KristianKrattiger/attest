"""Entra users: Microsoft Graph `GET /users?$select=id,userPrincipalName,displayName,accountEnabled,userType`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
This list is the account population, so a single object (a `GET /users/{id}`
response) is refused rather than read as a firm of one.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.readers._json import (
    load_records, object_id, optional_text, refuse_duplicates, require, require_address, require_bool)


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
    users = tuple(
        User(
            id=object_id(require(r, "id", file, row), file, row, "id"),
            upn=require_address(r, "userPrincipalName", file, row),
            display_name=optional_text(r.get("displayName"), file, row, "displayName"),
            enabled=require_bool(r, "accountEnabled", file, row),
            user_type=optional_text(r.get("userType"), file, row, "userType"),
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path, allow_single=False), start=1)
    )
    refuse_duplicates((u.id for u in users), "id", file)
    refuse_duplicates((u.upn for u in users), "userPrincipalName", file, fold_case=True)
    return users
