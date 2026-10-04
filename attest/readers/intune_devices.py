"""Intune managed devices: Microsoft Graph `GET /deviceManagement/managedDevices`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice?view=graph-rest-1.0
This list is the EDR population: the devices the firm manages, independent of
what Defender happens to know about.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from attest.readers._json import load_records, require, require_str

ZERO_GUID = "00000000-0000-0000-0000-000000000000"


def normalize_device_id(value: object) -> Optional[str]:
    """A lower-case Entra device ID, or None when the field is empty or the all-zero GUID."""
    text = str(value or "").strip().lower()
    return None if text in ("", ZERO_GUID) else text


@dataclass(frozen=True)
class IntuneDevice:
    id: str
    name: str
    aad_device_id: Optional[str]
    os: str
    cite: str


def read(path: Path) -> tuple[IntuneDevice, ...]:
    file = Path(path).name
    return tuple(
        IntuneDevice(
            id=require_str(r, "id", file, row),
            name=require_str(r, "deviceName", file, row),
            aad_device_id=normalize_device_id(require(r, "azureADDeviceId", file, row)),
            os=r.get("operatingSystem") or "",
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path), start=1)
    )
