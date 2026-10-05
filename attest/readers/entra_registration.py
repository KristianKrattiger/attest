"""MFA registration: Microsoft Graph `GET /reports/authenticationMethods/userRegistrationDetails`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/userregistrationdetails?view=graph-rest-1.0
`isMfaRegistered` is what the rules read: the user has registered a strong
authentication method. It says nothing about whether MFA is enforced.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.readers._json import load_records, object_id, refuse_duplicates, require, require_bool, require_str


@dataclass(frozen=True)
class Registration:
    user_id: str
    upn: str
    mfa_registered: bool
    cite: str


def read(path: Path) -> tuple[Registration, ...]:
    file = Path(path).name
    registrations = tuple(
        Registration(
            user_id=object_id(require(r, "id", file, row), file, row, "id"),
            upn=require_str(r, "userPrincipalName", file, row),
            mfa_registered=require_bool(r, "isMfaRegistered", file, row),
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path), start=1)
    )
    refuse_duplicates((r.user_id for r in registrations), "id", file)
    return registrations
