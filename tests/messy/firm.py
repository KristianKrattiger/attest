"""A firm's exports held in memory, so operators can edit them and the harness can write them out as a firm folder.

The seed is the real clean capture, firm/lab/seed-clean, once it is committed; until then it is the dev firm healed
of its planted gaps. Every test firm takes its text and tags from firm/dev: the tags name controls and scopes, not
people, so the dev firm's sentences fit any seed's exports.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from attest.readers._json import parse_time
from messy.heal import HEAL

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "firm" / "dev"
LAB = ROOT / "firm" / "lab"
SEED_CLEAN = LAB / "seed-clean"

Writer = Callable[[Any], bytes]


def utf8_json(data: Any) -> bytes:
    """How the harness writes an export unless an operator says otherwise: UTF-8, no BOM, LF."""
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def decode(raw: bytes) -> str:
    """An export's text: UTF-16 when it opens with a UTF-16 byte-order mark, otherwise UTF-8 with or without one."""
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")


def records(data: Any) -> list[dict]:
    """The records of an export as parsed JSON: a page's "value", a list, or one object."""
    if isinstance(data, dict) and isinstance(data.get("value"), list):
        return data["value"]
    if isinstance(data, list):
        return data
    return [data]


@dataclass
class Firm:
    """One firm's exports: each file's parsed JSON, the manifest's entries, and how each file is written.

    `touched` holds the entities operators have already edited ("user:<id>", "device:<Intune id>", ...), so two
    operators never edit the same one.
    """

    data: dict[str, Any]
    manifest: list[dict]
    writers: dict[str, Writer] = field(default_factory=dict)
    touched: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, exports: Path) -> Firm:
        manifest = yaml.safe_load((exports / "manifest.yaml").read_text(encoding="utf-8"))["exports"]
        data = {e["file"]: json.loads(decode((exports / e["file"]).read_bytes())) for e in manifest}
        return cls(data, manifest)

    def copy(self) -> Firm:
        return Firm(json.loads(json.dumps(self.data)), [dict(e) for e in self.manifest], dict(self.writers),
                    set(self.touched))

    def file(self, reader: str) -> str:
        """The file the manifest reads with this reader."""
        (name,) = [e["file"] for e in self.manifest if e["reader"] == reader]
        return name

    def rows(self, reader: str) -> list[dict]:
        """The records of the export this reader reads, as live parsed JSON an operator may edit."""
        return records(self.data[self.file(reader)])

    def exported_at(self, reader: str) -> datetime:
        (entry,) = [e for e in self.manifest if e["reader"] == reader]
        return parse_time(entry["exported_at"], "manifest.yaml", 1, "exported_at", unit="entry")

    def write(self, folder: Path) -> Path:
        """This firm as a folder `attest check` reads: firm/dev's text and tags, and these exports."""
        exports = assemble(folder) / "exports"
        exports.mkdir()
        for name, data in self.data.items():
            (exports / name).write_bytes(self.writers.get(name, utf8_json)(data))
        lines = ["exports:"] + [f"  - {{file: {e['file']}, reader: {e['reader']}, exported_at: {_time(e)}}}"
                                for e in self.manifest]
        (exports / "manifest.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return folder


def assemble(folder: Path, exports: Path | None = None) -> Path:
    """A firm folder holding firm/dev's text and tags, and a verbatim copy of these exports when given."""
    shutil.copytree(DEV / "attest", folder / "attest")
    shutil.copy(DEV / "tags.yaml", folder / "tags.yaml")
    if exports is not None:
        shutil.copytree(exports, folder / "exports")
    return folder


def _time(entry: dict) -> str:
    value = entry["exported_at"]
    return value.isoformat() if isinstance(value, datetime) else str(value)


def healed_dev() -> Firm:
    """The dev firm with every planted gap healed (tests/messy/heal.py)."""
    with tempfile.TemporaryDirectory() as tmp:
        exports = Path(tmp) / "exports"
        shutil.copytree(DEV / "exports", exports)
        for apply in HEAL:
            apply(exports)
        return Firm.load(exports)


def seed() -> tuple[str, Firm]:
    """The seed's name and a fresh copy of it: seed-clean once it is committed, else the healed dev firm."""
    if (SEED_CLEAN / "exports" / "manifest.yaml").exists():
        return "seed-clean", Firm.load(SEED_CLEAN / "exports")
    return "dev", healed_dev()
