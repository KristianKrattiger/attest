"""The exports a firm supplied, loaded through their readers (spec: Pipeline, step 2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from attest._yaml import read_yaml
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
    exports_dir = Path(exports_dir)
    loaded: dict[str, Export] = {}
    for i, entry in enumerate(_manifest_entries(exports_dir / "manifest.yaml"), start=1):
        file, name, exported_at = _checked_entry(entry, i)
        if name in loaded:
            raise AttestError(f"manifest.yaml: entry {i} repeats reader {name!r}")
        path = _export_path(exports_dir, file, i)
        loaded[name] = Export(file=file, exported_at=exported_at, items=READERS[name](path))
    return Evidence(**loaded)


def _manifest_entries(manifest: Path) -> list:
    """The raw entries of the manifest's 'exports' list; an empty manifest lists none."""
    data = read_yaml(manifest, "manifest.yaml")
    if data is None:
        return []
    if not isinstance(data, dict) or "exports" not in data:
        raise AttestError("manifest.yaml: expected a mapping with an 'exports' list")
    for key in data:
        if key != "exports":
            raise AttestError(f"manifest.yaml: unknown key {key!r}")
    if not isinstance(data["exports"], list):
        raise AttestError("manifest.yaml: expected a mapping with an 'exports' list")
    return data["exports"]


def _checked_entry(entry: object, i: int) -> tuple[str, str, datetime]:
    """One entry's file, reader name and export time, each of the right kind and the reader a known one."""
    if not isinstance(entry, dict):
        raise AttestError(f"manifest.yaml: entry {i} must be a mapping")
    for key in ("file", "reader", "exported_at"):
        if key not in entry:
            raise AttestError(f"manifest.yaml: entry {i} has no {key!r}")
    for key in ("file", "reader"):
        if not isinstance(entry[key], str) or not entry[key]:
            raise AttestError(f"manifest.yaml: entry {i} field {key!r} must be a non-empty string")
    if entry["reader"] not in READERS:
        raise AttestError(f"manifest.yaml: entry {i} names unknown reader {entry['reader']!r}")
    try:
        exported_at = parse_time(entry["exported_at"], "manifest.yaml", i, "exported_at")
    except (AttestError, OverflowError) as e:  # OverflowError: a year-9999 time with an offset leaves the UTC range
        raise AttestError(
            f"manifest.yaml: entry {i} field 'exported_at' is not a time: {entry['exported_at']!r}") from e
    return entry["file"], entry["reader"], exported_at


def _export_path(exports_dir: Path, file: str, i: int) -> Path:
    """The listed file, which must be an existing regular file inside the exports folder."""
    path = exports_dir / file
    try:
        inside = path.resolve().is_relative_to(exports_dir.resolve())
    except (OSError, ValueError) as e:  # e.g. a NUL in the name
        raise AttestError(f"manifest.yaml: entry {i} file {file!r} is not a usable path") from e
    if not inside:
        raise AttestError(f"manifest.yaml: entry {i} file {file!r} is outside the exports folder")
    if not path.exists():
        raise AttestError(f"manifest.yaml: entry {i} file {file!r} does not exist")
    if not path.is_file():
        raise AttestError(f"manifest.yaml: entry {i} file {file!r} is not a file")
    return path
