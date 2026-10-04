"""The exports a firm supplied, loaded through their readers (spec: Pipeline, step 2)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from attest.model import AttestError, Export
from attest.readers import READERS
from attest.readers._json import parse_time
from attest.readers.defender_machines import Machine
from attest.readers.entra_ca_policies import CaPolicy
from attest.readers.entra_registration import Registration
from attest.readers.entra_role_assignments import RoleAssignment
from attest.readers.entra_security_defaults import SecurityDefaults
from attest.readers.entra_users import User
from attest.readers.intune_devices import IntuneDevice
from attest.readers.veeam_users import VeeamUser


@dataclass(frozen=True)
class Evidence:
    """One field per reader; None when the firm supplied no export of that kind."""

    entra_users: Optional[Export[User]] = None
    entra_registration: Optional[Export[Registration]] = None
    entra_ca_policies: Optional[Export[CaPolicy]] = None
    entra_security_defaults: Optional[Export[SecurityDefaults]] = None
    entra_role_assignments: Optional[Export[RoleAssignment]] = None
    intune_devices: Optional[Export[IntuneDevice]] = None
    defender_machines: Optional[Export[Machine]] = None
    veeam_users: Optional[Export[VeeamUser]] = None


def load_evidence(exports_dir: Path) -> Evidence:
    """Every export the manifest lists, each read by its named reader and stamped with its time."""
    manifest = Path(exports_dir) / "manifest.yaml"
    if not manifest.is_file():
        raise AttestError(f"{manifest} not found")
    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    loaded: dict[str, Export] = {}
    for i, entry in enumerate(data.get("exports") or [], start=1):
        for key in ("file", "reader", "exported_at"):
            if key not in entry:
                raise AttestError(f"manifest.yaml: entry {i} has no {key!r}")
        name = entry["reader"]
        if name not in READERS:
            raise AttestError(f"manifest.yaml: entry {i} names unknown reader {name!r}")
        if name in loaded:
            raise AttestError(f"manifest.yaml: reader {name!r} appears twice")
        path = Path(exports_dir) / entry["file"]
        if not path.is_file():
            raise AttestError(f"manifest.yaml: entry {i} file {entry['file']!r} does not exist")
        loaded[name] = Export(
            file=entry["file"],
            exported_at=parse_time(entry["exported_at"], "manifest.yaml", i, "exported_at"),
            items=READERS[name](path),
        )
    return Evidence(**loaded)
