"""Security defaults: Microsoft Graph `GET /policies/identitySecurityDefaultsEnforcementPolicy`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/identitysecuritydefaultsenforcementpolicy?view=graph-rest-1.0
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.model import AttestError
from attest.readers._json import load_records, require_bool


@dataclass(frozen=True)
class SecurityDefaults:
    enabled: bool
    cite: str


def read(path: Path) -> tuple[SecurityDefaults, ...]:
    file = Path(path).name
    records = load_records(path)
    if len(records) != 1:
        raise AttestError(f"{file}: expected one security-defaults policy, found {len(records)}")
    return (SecurityDefaults(enabled=require_bool(records[0], "isEnabled", file, 1), cite=f"{file}:1"),)
