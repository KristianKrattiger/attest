"""Defender for Endpoint machines: Defender API `GET /api/machines`.

Fields: https://learn.microsoft.com/en-us/defender-endpoint/api/machine
The reference table spells the onboarding field `onboardingstatus`; the API's
JSON uses `onboardingStatus`. Either is accepted. `lastSeen` is the last full
device report, which a device sends about every 24 hours.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from attest.readers._json import load_records, parse_time, require, require_str
from attest.readers.intune_devices import normalize_device_id


@dataclass(frozen=True)
class Machine:
    id: str
    name: str
    aad_device_id: Optional[str]
    onboarding: str
    health: str
    last_seen: Optional[datetime]
    cite: str


def read(path: Path) -> tuple[Machine, ...]:
    file = Path(path).name
    machines = []
    for row, r in enumerate(load_records(path), start=1):
        onboarding_key = "onboardingStatus" if "onboardingStatus" in r or "onboardingstatus" not in r \
            else "onboardingstatus"
        id_ = require_str(r, "id", file, row)
        name = require_str(r, "computerDnsName", file, row)
        onboarding = require_str(r, onboarding_key, file, row)
        health = require_str(r, "healthStatus", file, row)
        last_seen = require(r, "lastSeen", file, row)
        machines.append(Machine(
            id=id_,
            name=name,
            aad_device_id=normalize_device_id(r.get("aadDeviceId")),
            onboarding=onboarding,
            health=health,
            last_seen=None if last_seen is None else parse_time(last_seen, file, row, "lastSeen"),
            cite=f"{file}:{row}",
        ))
    return tuple(machines)
