"""Intune managed devices: Microsoft Graph `GET /deviceManagement/managedDevices`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice?view=graph-rest-1.0
This list is the EDR population: the devices the firm manages, independent of
what Defender happens to know about.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from attest.readers._json import device_id, load_records, refuse_duplicates, require, require_str


@dataclass(frozen=True)
class IntuneDevice:
    id: str
    name: str
    aad_device_id: Optional[str]
    os: str
    cite: str


def read(path: Path) -> tuple[IntuneDevice, ...]:
    file = Path(path).name
    devices = tuple(
        IntuneDevice(
            id=require_str(r, "id", file, row),
            name=require_str(r, "deviceName", file, row),
            aad_device_id=device_id(require(r, "azureADDeviceId", file, row), file, row, "azureADDeviceId"),
            os=require(r, "operatingSystem", file, row) or "",
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path), start=1)
    )
    refuse_duplicates((d.id for d in devices), "id", file)
    return devices
