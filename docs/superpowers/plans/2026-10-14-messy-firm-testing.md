# Messy-Firm Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test the check against messy, realistic Microsoft 365 exports: operators that each make one real-world mess and declare its effect, run alone and in seeded combinations over a seed firm, judged for no false backed, identical inert runs, promised stops and no undecided stops; then replace the stand-in seed with real captures from a lab tenant.

**Architecture:** A test package, `tests/messy/`, holds a firm's exports in memory (`firm.py`), a catalog of operators by area (`mfa.py`, `edr.py`, `backup.py`, `formats.py`, gathered in `catalog.py`), and a judge (`compose.py`) that applies operators, writes a firm folder, runs `attest.compare.check`, and checks four properties. The seed is the dev firm healed of its planted gaps until the lab's clean capture, `firm/lab/seed-clean`, is committed. Real captures come from a Business Premium trial tenant (`docs/engineering/lab.md`, `scripts/lab_capture.ps1`), are scrubbed by `scripts/scrub_lab_capture.py`, and calibrate the operators through a fidelity check.

**Tech Stack:** Python 3.12+, PyYAML, pytest; Windows PowerShell 5.1 and PowerShell 7 with Microsoft Graph PowerShell for the captures.

**Spec:** `docs/superpowers/specs/2026-10-14-messy-firm-testing-design.md`

## Global Constraints

- Python `>=3.12` (`pyproject.toml`). Run the tests as `docs/engineering/using.md` says: `venv/Scripts/python.exe -m pytest`. If `venv/` is missing, create it first: `py -3.12 -m venv venv` then `venv/Scripts/python.exe -m pip install -r requirements.txt`.
- Under Python 3.14 two tests fail before any change: `tests/test_evidence.py::test_a_malformed_manifest_stops_the_run[...a\x00b...]` and `tests/test_profile_and_tags.py::test_a_document_path_with_a_nul_is_refused`. They are not this work's; every "expected" count below leaves them out.
- No new dependency: PyYAML and pytest only (spec decision).
- No change under `attest/` (spec non-goal). A false backed the suite finds is recorded on its operator with `known` and fixed in its own change.
- House style: module docstrings in plain prose, `from __future__ import annotations` in library modules, lines of at most 120 characters, UTF-8 with LF line endings.
- Tests import the new package as `messy.*`, the way they import `builders` today (pytest puts `tests/` on the path).
- Commit messages are one plain sentence in the repo's style (for example "Add the made-up dev firm with planted gaps, and record its results"), ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Nothing committed names the lab tenant or its owner. Raw captures and `deny.txt` live in `firm/lab/raw/`, which is gitignored. The guard test (Task 11) enforces it.
- Work continues on the branch `spec/messy-firm-testing`.

## Decisions made while planning

The plan was prototyped before it was written. Every Python and YAML block below ran, task by task in this order on a clean copy of the repository, and every "expected" output in Tasks 1 to 12 is that run's. The capture script was only parse-checked, and the runbook's commands were not run: both need the tenant. These points refine or depart from the spec, each for the reason given.

1. **A known false backed, found by the prototype.** A shared mailbox is a disabled user object. `attest/rules/backup.py` counts a disabled account only when Veeam lists it, so a shared mailbox the backup job never covered drops out of the population and backup comes out **backed** (both `app-4.5` and `wisp-backup`). The operator "shared mailbox Veeam never saw" carries `known`: its alone test is a strict expected failure, it is left out of combinations, and its fidelity test asserts the false backed is still there. When the rule is fixed in its own change, those tests fail until `known` is cleared. Task 6 records it in `using.md`'s known limitations.
2. **Break-glass accounts are also a backup false gap.** They hold no mailbox, but every enabled member is counted. This is the known limit "Unlicensed or service accounts are permanent backup gaps" in `using.md`; the operator's `alone` pins it.
3. **The nameless discovered device keeps its refusal for now.** The Defender reader stops on a null `computerDnsName`. The operator carries `may_stop` provisionally, until a real capture shows whether Defender writes one (`lab.md`, section 4).
4. **Twins carry their own `before`.** Each twin is `firm/lab/<twin>/before/exports` and `after/exports`, not a single capture compared with seed-clean: captures taken days apart drift (a `lastSeen`, an OS build), and the drift would read as a mismatch.
5. **The deny-list lives in `firm/lab/raw/deny.txt`, not in the test.** The spec kept it in the test; that would commit the owner's address. The scrub script writes it, and the guard test reads it when it is there.
6. **Nine members and a former employee, not ten members.** The former employee keeps a licensed mailbox, which Veeam counts; ten mailboxes is Community Edition's limit.
7. **"A Veeam export of one user, written as one object" is dropped** from the catalog and from the PowerShell 5.1 archetype: on a seed with more than one mailbox it cannot be made without changing the truth.
8. **`needs` and `touches` are not declared fields.** An operator's edit returns False when the firm has nothing it needs (it is then skipped), and it marks what it edits through `take()`, so two operators never edit one entity.
9. **Operators live in one module per area**, gathered in `catalog.py`, so each file stays small and each task adds one.
10. **Archetype truth is per seed:** `tests/messy/archetypes/<seed>/<name>.yaml`. Entities differ between the dev firm and the lab, and a person hand-checks each.
11. **Noise cost is charged to every "holds" operator that declares the scope** in a run where that scope left the seed's status and no applied "breaks" operator breaks it. Co-applied "holds" operators share the charge; the summary says so.

## File map

| File | Responsibility |
|---|---|
| `tests/messy/__init__.py` | Makes `messy` a package |
| `tests/messy/heal.py` | The dev firm's healing edits, shared with `tests/test_dev_firm.py` |
| `tests/messy/firm.py` | A firm's exports in memory: load, copy, edit, write as a firm folder; the seed |
| `tests/messy/operators.py` | `Operator`, the effects, the scope sets, and the helpers operators share |
| `tests/messy/mfa.py`, `edr.py`, `backup.py`, `formats.py` | The operators, one module per area |
| `tests/messy/catalog.py` | `CATALOG`, `BY_NAME`, `COMBINABLE` |
| `tests/messy/compose.py` | Apply operators, run the check, judge the four properties, combine, shrink, tally |
| `tests/messy/fidelity.py` | Compare an operator's mess with a twin capture's |
| `tests/messy/conftest.py` | The session fixture `seeded` |
| `tests/messy/test_*.py` | The tests |
| `tests/messy/archetypes/<seed>/*.yaml` | Hand-checked truth for the four archetypes |
| `scripts/scrub_lab_capture.py` | Scrub a raw capture into `firm/lab/`, keeping its bytes' form |
| `scripts/lab_capture.ps1` | Take the lab's exports exactly as `exports.md` gives them |
| `docs/engineering/lab.md` | The lab runbook |
| `firm/lab/` | Scrubbed captures and `messy-summary.md`; `raw/` is gitignored |

---

### Task 1: Share the healing edits

**Files:**
- Create: `tests/messy/__init__.py` (empty)
- Create: `tests/messy/heal.py`
- Modify: `tests/test_dev_firm.py` (imports at the top; delete `DOMAIN`, `_edit`, `_row`, `_machine` and `HEAL`)

**Interfaces:**
- Produces, in `messy.heal`: `DOMAIN: str`; `edit(file: str, change: Callable[[Any], None]) -> Callable[[Path], None]`; `row(rows: list[dict], key: str, value) -> dict`; `machine(name, health="Active", aad=None, last_seen="2026-10-01T09:30:00Z") -> dict`; `HEAL: tuple[Callable[[Path], None], ...]`, each applied to a firm's `exports/` folder.

- [ ] **Step 1: Run the dev firm tests for a baseline**

Run: `venv/Scripts/python.exe -m pytest tests/test_dev_firm.py -q`
Expected: `16 passed`

- [ ] **Step 2: Create the package and move the healing edits into it**

Create `tests/messy/__init__.py` as an empty file. Create `tests/messy/heal.py`:

```python
"""The dev firm healed of every planted gap: the seed the messy-firm suite uses until a real capture replaces it.

Each edit takes a firm's exports folder and changes one file in place. tests/test_dev_firm.py uses the same edits
for its single mutations.
"""
import json

DOMAIN = "harborpine.example"


def edit(file, change):
    """An edit of one export: change(data) alters the parsed JSON in place."""
    def apply(exports):
        path = exports / file
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return apply


def row(rows, key, value):
    (found,) = [r for r in rows if r[key] == value]
    return found


def machine(name, health="Active", aad=None, last_seen="2026-10-01T09:30:00Z"):
    return {"id": name.split(".")[0].ljust(40, "0")[:40], "computerDnsName": f"{name}.{DOMAIN}", "aadDeviceId": aad,
            "osPlatform": "Windows11", "onboardingStatus": "Onboarded", "healthStatus": health, "lastSeen": last_seen}


HEAL = (
    edit("ca-policies.json", lambda ca: ca["value"][0]["conditions"]["users"].update(excludeUsers=[])),  # Dana
    edit("registration.json", lambda reg: row(reg["value"], "id", "a0000000-0000-4000-8000-000000000012").update(
        isMfaRegistered=True)),  # Ivan registered
    edit("defender-machines.json", lambda mde: mde["value"].append(
        machine("hp-lt-12", aad="d0000000-0000-4000-8000-000000000012"))),  # Ivan's laptop onboarded
    edit("veeam-users.json", lambda rows: row(rows, "Email", f"carmen.diaz@{DOMAIN}").update(
        IsMailboxBackedUp=True, MailboxBackedUpTime="2026-10-01T02:10:00Z")),  # Carmen's mailbox backed up
)
```

- [ ] **Step 3: Point `tests/test_dev_firm.py` at it**

Replace the import block at the top:

```python
import json
import shutil
from pathlib import Path

import pytest
import yaml

from attest.__main__ import main
from attest.compare import check, run
from attest.model import AttestError
from attest.report import attestations, combined_status, render
```

with:

```python
import shutil
from pathlib import Path

import pytest
import yaml

from attest.__main__ import main
from attest.compare import check, run
from attest.model import AttestError
from attest.report import attestations, combined_status, render
from messy.heal import DOMAIN, HEAL
from messy.heal import edit as _edit
from messy.heal import machine as _machine
from messy.heal import row as _row
```

Then delete these definitions, which now come from `messy.heal`. The line:

```python
DOMAIN = "harborpine.example"
```

The function `_edit`:

```python
def _edit(file, change):
    """An edit of one export: change(data) alters the parsed JSON in place."""
    def apply(exports):
        path = exports / file
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return apply
```

The functions `_row` and `_machine`:

```python
def _row(rows, key, value):
    (row,) = [r for r in rows if r[key] == value]
    return row


def _machine(name, health="Active", aad=None, last_seen="2026-10-01T09:30:00Z"):
    return {"id": name.split(".")[0].ljust(40, "0")[:40], "computerDnsName": f"{name}.{DOMAIN}", "aadDeviceId": aad,
            "osPlatform": "Windows11", "onboardingStatus": "Onboarded", "healthStatus": health, "lastSeen": last_seen}
```

And the tuple `HEAL = ( ... )` (the four edits ending with `# Carmen's mailbox backed up`). Keep `_policy_1_users`, `_manifest`, `_copy`, `_by_id` and everything else.

- [ ] **Step 4: Run the dev firm tests again**

Run: `venv/Scripts/python.exe -m pytest tests/test_dev_firm.py -q`
Expected: `16 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/messy/__init__.py tests/messy/heal.py tests/test_dev_firm.py
git commit -m "Move the dev firm's healing edits into tests/messy, where the messy-firm tests share them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The in-memory firm

**Files:**
- Create: `tests/messy/firm.py`
- Test: `tests/messy/test_firm.py`

**Interfaces:**
- Consumes: `messy.heal.HEAL`; `attest.readers._json.parse_time`.
- Produces, in `messy.firm`: `ROOT`, `DEV`, `LAB`, `SEED_CLEAN: Path`; `Writer = Callable[[Any], bytes]`; `utf8_json(data) -> bytes`; `decode(raw: bytes) -> str`; `records(data) -> list[dict]`; `class Firm(data: dict[str, Any], manifest: list[dict], writers: dict[str, Writer] = {}, touched: set[str] = set())` with `Firm.load(exports: Path) -> Firm`, `copy() -> Firm`, `file(reader: str) -> str`, `rows(reader: str) -> list[dict]` (live records an operator may edit), `exported_at(reader: str) -> datetime`, `write(folder: Path) -> Path`; `assemble(folder: Path, exports: Path | None = None) -> Path`; `healed_dev() -> Firm`; `seed() -> tuple[str, Firm]` (`"seed-clean"` once `firm/lab/seed-clean/exports/manifest.yaml` exists, else `"dev"`).

- [ ] **Step 1: Write the failing test**

Create `tests/messy/test_firm.py`:

```python
from attest.compare import check
from messy.firm import DEV, Firm, decode, healed_dev, records, seed, utf8_json

PROVABLE = {"mfa.email", "mfa.all_users", "mfa.admins", "edr.all_endpoints", "backup.m365_mailboxes"}


def test_decode_reads_utf16_utf8_with_a_bom_and_plain_utf8():
    text = '{"a": "é"}'
    assert decode(b"\xff\xfe" + text.encode("utf-16-le")) == text
    assert decode(b"\xef\xbb\xbf" + text.encode("utf-8")) == text
    assert decode(text.encode("utf-8")) == text


def test_records_are_a_page_s_value_a_list_or_one_object():
    assert records({"@odata.context": "x", "value": [{"id": 1}]}) == [{"id": 1}]
    assert records([{"id": 1}, {"id": 2}]) == [{"id": 1}, {"id": 2}]
    assert records({"id": 1}) == [{"id": 1}]


def test_a_firm_written_out_loads_back_the_same(tmp_path):
    firm = Firm.load(DEV / "exports")
    again = Firm.load(firm.write(tmp_path / "firm") / "exports")
    assert again.data == firm.data
    assert [e["file"] for e in again.manifest] == [e["file"] for e in firm.manifest]
    assert again.exported_at("entra_users") == firm.exported_at("entra_users")


def test_a_copy_is_independent_of_its_original():
    firm = Firm.load(DEV / "exports")
    copied = firm.copy()
    copied.rows("entra_users")[0]["displayName"] = "Changed"
    copied.touched.add("user:x")
    assert firm.rows("entra_users")[0]["displayName"] != "Changed" and not firm.touched


def test_a_writer_decides_how_a_file_is_written(tmp_path):
    firm = Firm.load(DEV / "exports")
    firm.writers["users.json"] = lambda data: b"\xef\xbb\xbf" + utf8_json(data)
    folder = firm.write(tmp_path / "firm")
    assert (folder / "exports" / "users.json").read_bytes().startswith(b"\xef\xbb\xbf{")
    assert not (folder / "exports" / "registration.json").read_bytes().startswith(b"\xef\xbb\xbf")


def test_the_healed_dev_firm_is_backed_wherever_a_scope_can_be_proven(tmp_path):
    for tag, verdict in check(healed_dev().write(tmp_path / "firm")):
        assert verdict.status == ("backed" if f"{tag.control}.{tag.scope}" in PROVABLE else "unchecked"), tag.id


def test_the_seed_is_the_healed_dev_firm_until_seed_clean_is_committed():
    name, firm = seed()
    assert name in ("dev", "seed-clean")
    if name == "dev":
        assert firm.data == healed_dev().data
```

- [ ] **Step 2: Run it to see it fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_firm.py -q`
Expected: `ImportError while importing test module`, with `ModuleNotFoundError: No module named 'messy.firm'`

- [ ] **Step 3: Write the in-memory firm**

Create `tests/messy/firm.py`:

```python
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
```

- [ ] **Step 4: Run it to see it pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_firm.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/messy/firm.py tests/messy/test_firm.py
git commit -m "Hold a firm's exports in memory, write them out as a firm folder, and seed from the healed dev firm" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The judge

**Files:**
- Create: `tests/messy/operators.py`
- Create: `tests/messy/catalog.py` (empty catalog for now)
- Create: `tests/messy/compose.py`
- Create: `tests/messy/conftest.py`
- Test: `tests/messy/test_harness.py`

**Interfaces:**
- Consumes: `messy.firm` (Task 2); `attest.compare.check`; `attest.model.AttestError`.
- Produces, in `messy.operators`: `Effect`; `PROVABLE: tuple[str, ...]`; scope sets `ALL_USERS`, `ADMINS`, `ALL_MFA`, `EDR`, `BACKUP: frozenset[str]`; `GLOBAL_ADMIN`, `EXCHANGE_ADMIN: str`; `Operator(name: str, effect: Effect, edit: Callable[[Firm], bool], alone: Mapping[str, str] = {}, scopes: frozenset[str] = frozenset(), why: str = "", stop: str = "", may_stop: str = "", twin: str = "", known: str = "")` (equal and hashed by `name` and `effect` only); helpers `new_id(label) -> str`, `machine_id(label) -> str`, `utc_text(moment) -> str`, `take(firm, key) -> bool`, `members(firm) -> list[dict]`, `domain(firm) -> str`, `admin_ids(firm) -> set[str]`, `member(firm, admin: bool, mailbox: bool = False) -> dict | None`, `paired(firm) -> tuple[dict, dict] | None`, `clone(rows, **changes) -> dict`, `veeam_fresh(firm) -> str`, `add_account(firm, label, name, *, enabled=True, registered: bool | None = True, mailbox: tuple[bool, str | None] | None = None) -> dict`, `assign_role(firm, label, principal: dict, role=GLOBAL_ADMIN) -> None`.
- Produces, in `messy.catalog`: `CATALOG: tuple[Operator, ...]`, `BY_NAME: dict[str, Operator]`, `COMBINABLE: tuple[Operator, ...]` (the catalog without `known` operators).
- Produces, in `messy.compose`: `Verdicts = dict[str, tuple[str, str, tuple[str, ...]]]` (tag id to scope, status, sorted entities); `Outcome(applied, skipped, verdicts, stopped: str)`; `apply(seed: Firm, ops) -> tuple[Firm, tuple[Operator, ...], tuple[Operator, ...]]`; `run(seed: Firm, ops) -> Outcome`; `violations(outcome: Outcome, seed: Outcome) -> list[str]`; `degraded(outcome, seed) -> dict[str, set[str]]`; `combinations(seed_number: int, count: int, most: int = 4, catalog=COMBINABLE) -> list[tuple[Operator, ...]]`; `shrink(ops, fails: Callable[[tuple[Operator, ...]], bool]) -> tuple[Operator, ...]`.
- Produces, in `tests/messy/conftest.py`: the session fixture `seeded -> Seeded(name: str, firm: Firm, outcome: Outcome)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/messy/conftest.py`:

```python
from typing import NamedTuple

import pytest

from messy.compose import Outcome, run
from messy.firm import Firm, seed


class Seeded(NamedTuple):
    name: str  # "seed-clean" once the real capture is committed, else "dev"
    firm: Firm
    outcome: Outcome  # the check on the seed with no operator applied


@pytest.fixture(scope="session")
def seeded() -> Seeded:
    name, firm = seed()
    return Seeded(name, firm, run(firm, ()))
```

Create `tests/messy/test_harness.py`. Each test plants a lie and shows the judge catches it, because a judge that never fails proves nothing:

```python
"""The judge itself: a harness that never fails proves nothing, so each property is shown to catch a planted lie."""
from messy.compose import combinations, degraded, run, shrink, violations
from messy.operators import PROVABLE, Operator


def _all_users_scopes(outcome):
    return {status for scope, status, _ in outcome.verdicts.values() if scope == "mfa.all_users"}


def test_the_seed_is_backed_wherever_a_scope_can_be_proven(seeded):
    assert seeded.outcome.stopped == ""
    for tag, (scope, status, _) in seeded.outcome.verdicts.items():
        assert status == ("backed" if scope in PROVABLE else "unchecked"), tag


def test_a_breaks_operator_that_breaks_nothing_is_a_false_backed(seeded):
    lie = Operator("claims to break MFA but edits nothing", "breaks", lambda firm: True,
                   scopes=frozenset({"mfa.all_users"}))
    outcome = run(seeded.firm, (lie,))
    assert _all_users_scopes(outcome) == {"backed"}
    assert violations(outcome, seeded.outcome) == [
        f"false backed: {tag} (mfa.all_users) after 'claims to break MFA but edits nothing'"
        for tag, (scope, _, _) in outcome.verdicts.items() if scope == "mfa.all_users"]


def test_an_inert_operator_that_changes_a_verdict_is_caught(seeded):
    def drop_registration(firm):
        firm.rows("entra_registration").pop(0)  # the first member's row
        return True
    outcome = run(seeded.firm, (Operator("claims to be inert", "inert", drop_registration),))
    assert any(problem.startswith("inert changed ") for problem in violations(outcome, seeded.outcome))


def test_a_promised_stop_that_does_not_happen_is_caught(seeded):
    outcome = run(seeded.firm, (Operator("claims to stop", "stops", lambda firm: True, stop="never said"),))
    assert violations(outcome, seeded.outcome) == ["did not stop, though claims to stop must stop it"]


def test_a_stop_no_operator_allows_is_caught(seeded):
    def pad(firm):
        firm.rows("entra_users")[0]["userPrincipalName"] += " "
        return True
    outcome = run(seeded.firm, (Operator("pads an address", "holds", pad, scopes=frozenset(PROVABLE), why="x"),))
    assert violations(outcome, seeded.outcome) == [f"undecided stop: {outcome.stopped}"]
    assert "leading or trailing whitespace" in outcome.stopped


def test_a_holds_operator_is_charged_only_for_its_own_scopes(seeded):
    def drop_registration(firm):
        firm.rows("entra_registration").pop(0)  # the first member's row
        return True
    edr_only = Operator("touches EDR only", "holds", drop_registration, scopes=frozenset({"edr.all_endpoints"}),
                        why="x")
    mfa = Operator("touches MFA", "holds", drop_registration, scopes=frozenset({"mfa.all_users"}), why="x")
    assert degraded(run(seeded.firm, (edr_only,)), seeded.outcome) == {}
    assert degraded(run(seeded.firm, (mfa,)), seeded.outcome) == {"touches MFA": {"unchecked"}}


FAKES = tuple(Operator(name, "inert", lambda firm: True) for name in "abcdefgh")


def test_combinations_are_the_same_for_the_same_seed_number():
    assert combinations(7, 20, catalog=FAKES) == combinations(7, 20, catalog=FAKES)
    assert combinations(7, 20, catalog=FAKES) != combinations(8, 20, catalog=FAKES)
    assert all(1 <= len(combo) <= 4 and len(set(combo)) == len(combo)
               for combo in combinations(7, 200, catalog=FAKES))


def test_shrinking_keeps_only_the_operators_the_failure_needs():
    a, b, c, d = FAKES[:4]
    assert shrink((a, b, c, d), lambda ops: b in ops and d in ops) == (b, d)
    assert shrink((a,), lambda ops: True) == (a,)
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_harness.py -q`
Expected: `ImportError while loading conftest`, with `ModuleNotFoundError: No module named 'messy.compose'`

- [ ] **Step 3: Write the operator model**

Create `tests/messy/operators.py`:

```python
"""What an operator is, and the helpers operators share to find and add records (spec 2026-10-14, Operators).

An operator edits a firm's exports in memory to make one real-world mess, and declares what that mess does to the
truth:

- "breaks": the truth fails for the scopes in `scopes`; no tag of those scopes may come out backed.
- "holds": the truth is unchanged for the scopes in `scopes`, the ones the mess is about; `why` says why. The rules
  may still lose sight of it there, which the long run measures as noise cost.
- "inert": serialization only; every verdict must equal the seed's.
- "stops": a refusal the docs promise; the run must stop with `stop` in its message.

`alone` is the status of each provable scope that changes when the operator is the only one applied to the seed;
every other provable scope stays backed. For a "holds" operator it pins today's behaviour, false gaps included, so a
change is noticed. `may_stop` is set only once a stop on realistic data has been decided and the refusal kept.
`twin` names the real capture under firm/lab that shows the same mess. A "breaks" operator with `known` set is a
false backed found and not yet fixed: its alone test is a strict expected failure and it is left out of
combinations, until the rule is fixed in its own change.

An operator that adds a record clones a seed record of the same kind and changes what the mess changes, so the
fields stay the ones the real export has. It edits only entities no earlier operator touched (`take`), and returns
False when the firm has nothing left for it; it is then skipped.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, Mapping, Optional

from messy.firm import Firm

Effect = Literal["breaks", "holds", "inert", "stops"]
PROVABLE = ("mfa.email", "mfa.all_users", "mfa.admins", "edr.all_endpoints", "backup.m365_mailboxes")
ALL_USERS = frozenset({"mfa.all_users", "mfa.email"})
ADMINS = frozenset({"mfa.admins"})
ALL_MFA = ALL_USERS | ADMINS
EDR = frozenset({"edr.all_endpoints"})
BACKUP = frozenset({"backup.m365_mailboxes"})
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


@dataclass(frozen=True)
class Operator:
    name: str
    effect: Effect
    edit: Callable[[Firm], bool] = field(repr=False, compare=False)
    alone: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    scopes: frozenset[str] = field(default=frozenset(), repr=False, compare=False)
    why: str = field(default="", repr=False, compare=False)
    stop: str = field(default="", repr=False, compare=False)
    may_stop: str = field(default="", repr=False, compare=False)
    twin: str = field(default="", repr=False, compare=False)
    known: str = field(default="", repr=False, compare=False)


def new_id(label: str) -> str:
    """A GUID that is the same on every run and cannot collide with a seed's."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"attest-messy:{label}"))


def machine_id(label: str) -> str:
    """A Defender machine ID: 40 hex digits, the same on every run."""
    return new_id(label).replace("-", "") + "00000000"


def utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def take(firm: Firm, key: str) -> bool:
    """Mark an entity touched; False when an earlier operator already touched it."""
    if key in firm.touched:
        return False
    firm.touched.add(key)
    return True


def members(firm: Firm) -> list[dict]:
    """Enabled accounts that are not guests, in export order."""
    return [u for u in firm.rows("entra_users") if u["accountEnabled"] and (u.get("userType") or "") != "Guest"]


def domain(firm: Firm) -> str:
    return members(firm)[0]["userPrincipalName"].split("@")[1]


def admin_ids(firm: Firm) -> set[str]:
    return {a["principalId"] for a in firm.rows("entra_role_assignments")
            if a["principal"]["@odata.type"] == "#microsoft.graph.user"}


def member(firm: Firm, admin: bool, mailbox: bool = False) -> Optional[dict]:
    """The first untouched enabled member that holds an admin role or not, with a Veeam row when asked; now touched."""
    admins = admin_ids(firm)
    veeam = {r["Email"].lower() for r in firm.rows("veeam_users")}
    for u in members(firm):
        if (u["id"] in admins) == admin and (not mailbox or u["userPrincipalName"].lower() in veeam):
            if take(firm, f"user:{u['id']}"):
                return u
    return None


def paired(firm: Firm) -> Optional[tuple[dict, dict]]:
    """The first untouched Intune device and the one Defender machine that shares its Entra device ID; now touched."""
    machines = firm.rows("defender_machines")
    for device in firm.rows("intune_devices"):
        aad = (device.get("azureADDeviceId") or "").lower()
        matching = [m for m in machines if (m.get("aadDeviceId") or "").lower() == aad]
        if aad and len(matching) == 1 and take(firm, f"device:{device['id']}"):
            return device, matching[0]
    return None


def clone(rows: list[dict], **changes) -> dict:
    """A copy of the first record with these changes, appended to rows."""
    record = copy.deepcopy(rows[0])
    record.update(changes)
    rows.append(record)
    return record


def veeam_fresh(firm: Firm) -> str:
    """A backup time 10 hours before the Veeam export: fresh."""
    return utc_text(firm.exported_at("veeam_users") - timedelta(hours=10))


def add_account(firm: Firm, label: str, name: str, *, enabled: bool = True, registered: Optional[bool] = True,
                mailbox: Optional[tuple[bool, Optional[str]]] = None) -> dict:
    """A new account cloned from the seed's first: its user row; its registration row, unless registered is None (no
    row yet); and its Veeam row, unless mailbox is None, else (backed up, backup time)."""
    upn = f"{label}@{domain(firm)}"
    uid = new_id(label)
    user = clone(firm.rows("entra_users"), id=uid, userPrincipalName=upn, displayName=name, accountEnabled=enabled,
                 userType="Member")
    if registered is not None:
        row = clone(firm.rows("entra_registration"), id=uid, userPrincipalName=upn, userDisplayName=name,
                    isMfaRegistered=registered, isMfaCapable=registered, isAdmin=False)
        if not registered:
            row["methodsRegistered"] = []
    if mailbox is not None:
        backed_up, when = mailbox
        clone(firm.rows("veeam_users"), Email=upn, DisplayName=name, IsMailboxBackedUp=backed_up,
              MailboxBackedUpTime=when)
    return user


def assign_role(firm: Firm, label: str, principal: dict, role: str = GLOBAL_ADMIN) -> None:
    """A tenant-wide role assignment to this principal (the expanded `principal` object Graph returns)."""
    clone(firm.rows("entra_role_assignments"), id=new_id(f"assignment:{label}"), principalId=principal["id"],
          roleDefinitionId=role, directoryScopeId="/", principal=principal)
```

- [ ] **Step 4: Write the catalog, still empty**

Create `tests/messy/catalog.py`:

```python
"""Every operator, by area. A new real-world mess gets a new operator, not an edit to an old one."""
from messy.operators import Operator

CATALOG: tuple[Operator, ...] = ()
BY_NAME = {op.name: op for op in CATALOG}
COMBINABLE = tuple(op for op in CATALOG if not op.known)  # a known false backed would fail every combination
```

- [ ] **Step 5: Write the judge**

Create `tests/messy/compose.py`:

```python
"""Apply operators to the seed, run the check, and judge the result against what the operators declare.

Properties, for every run (spec 2026-10-14, The harness):
1. No false backed: no scope an applied operator breaks comes out backed.
2. Inert is identical: when every applied operator is inert, each tag's status and entities equal the seed's.
3. Promised stops happen: when an applied operator is "stops", the run stops with that operator's text.
4. No undecided stops: a run stops only when an applied operator declares `stop` or `may_stop`.
"""
from __future__ import annotations

import random
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from attest.compare import check
from attest.model import AttestError
from messy.catalog import COMBINABLE
from messy.firm import Firm
from messy.operators import Operator

Verdicts = dict[str, tuple[str, str, tuple[str, ...]]]  # tag id -> (control.scope, status, sorted entities)


@dataclass(frozen=True)
class Outcome:
    applied: tuple[Operator, ...]
    skipped: tuple[Operator, ...]
    verdicts: Verdicts  # empty when the run stopped
    stopped: str  # the AttestError message, or "" when the run finished


def apply(seed: Firm, ops: Sequence[Operator]) -> tuple[Firm, tuple[Operator, ...], tuple[Operator, ...]]:
    """A copy of the seed with each operator applied; inert operators go last, so they reshape whatever the others
    wrote. Returns the firm, the operators that applied, and those skipped for want of anything to edit."""
    firm = seed.copy()
    applied, skipped = [], []
    for op in sorted(ops, key=lambda op: op.effect == "inert"):
        (applied if op.edit(firm) else skipped).append(op)
    return firm, tuple(applied), tuple(skipped)


def _outcome(folder: Path, applied: tuple[Operator, ...], skipped: tuple[Operator, ...]) -> Outcome:
    try:
        results = check(folder)
    except AttestError as e:
        return Outcome(applied, skipped, {}, str(e))
    verdicts = {tag.id: (f"{tag.control}.{tag.scope}", v.status, tuple(sorted(v.entities))) for tag, v in results}
    return Outcome(applied, skipped, verdicts, "")


def run(seed: Firm, ops: Sequence[Operator]) -> Outcome:
    """The check on a copy of the seed with these operators applied."""
    firm, applied, skipped = apply(seed, ops)
    with tempfile.TemporaryDirectory() as tmp:
        return _outcome(firm.write(Path(tmp) / "firm"), applied, skipped)


def violations(outcome: Outcome, seed: Outcome) -> list[str]:
    """Each property this run breaks, in words; [] when it holds them all."""
    ops = outcome.applied
    allowed = [op.stop or op.may_stop for op in ops if op.stop or op.may_stop]
    if outcome.stopped:
        if not allowed:
            return [f"undecided stop: {outcome.stopped}"]
        if not any(text in outcome.stopped for text in allowed):
            return [f"stopped for a reason no applied operator gives: {outcome.stopped}"]
        return []
    promised = [op.name for op in ops if op.effect == "stops"]
    if promised:
        return [f"did not stop, though {', '.join(promised)} must stop it"]
    problems = [f"false backed: {tag} ({scope}) after '{op.name}'"
                for op in ops if op.effect == "breaks"
                for tag, (scope, status, _) in outcome.verdicts.items() if scope in op.scopes and status == "backed"]
    if ops and all(op.effect == "inert" for op in ops):
        problems += [f"inert changed {tag}: {seed.verdicts[tag][1:]} -> {verdict[1:]}"
                     for tag, verdict in outcome.verdicts.items() if verdict != seed.verdicts[tag]]
    return problems


def degraded(outcome: Outcome, seed: Outcome) -> dict[str, set[str]]:
    """For each applied "holds" operator, the statuses its scopes dropped to, leaving out scopes an applied "breaks"
    operator breaks; an operator whose scopes all kept the seed's status is left out."""
    if outcome.stopped:
        return {}
    broken = {scope for op in outcome.applied if op.effect == "breaks" for scope in op.scopes}
    found = {}
    for op in outcome.applied:
        if op.effect == "holds":
            drops = {status for tag, (scope, status, _) in outcome.verdicts.items()
                     if scope in op.scopes - broken and status != seed.verdicts[tag][1]}
            if drops:
                found[op.name] = drops
    return found


def combinations(seed_number: int, count: int, most: int = 4,
                 catalog: Sequence[Operator] = COMBINABLE) -> list[tuple[Operator, ...]]:
    """`count` combinations of one to `most` distinct operators; the same seed number always gives the same ones.
    Known false backeds are left out, so each combination tests what is not yet known."""
    rng = random.Random(seed_number)
    return [tuple(rng.sample(list(catalog), rng.randint(1, most))) for _ in range(count)]


def shrink(ops: Sequence[Operator], fails: Callable[[tuple[Operator, ...]], bool]) -> tuple[Operator, ...]:
    """The smallest subset found, one removal at a time, that still fails."""
    ops = tuple(ops)
    shrunk = True
    while shrunk and len(ops) > 1:
        shrunk = False
        for i in range(len(ops)):
            candidate = ops[:i] + ops[i + 1:]
            if fails(candidate):
                ops, shrunk = candidate, True
                break
    return ops
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_harness.py -q`
Expected: `8 passed`

- [ ] **Step 7: Commit**

```bash
git add tests/messy/operators.py tests/messy/catalog.py tests/messy/compose.py tests/messy/conftest.py tests/messy/test_harness.py
git commit -m "Judge a run of the check against what its operators declare, and show each property catches a planted lie" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The MFA operators

**Files:**
- Create: `tests/messy/mfa.py`
- Modify: `tests/messy/catalog.py`
- Test: `tests/messy/test_operators.py`

**Interfaces:**
- Consumes: `messy.operators` helpers (Task 3); `messy.compose.run`, `violations`; the `seeded` fixture.
- Produces: `messy.mfa.OPERATORS: tuple[Operator, ...]`, ten operators. Their names are what archetype files and `BY_NAME` use: `microsoft-managed admin-portals policy`, `break-glass accounts excluded`, `MFA exclusions group`, `all-users policy limited to Office 365`, `grant through an authentication strength`, `per-user MFA instead of Conditional Access`, `admin role held by a group`, `admin role held by a group with an unregistered member`, `admin role held by a service principal`, `user created after the registration report`.

- [ ] **Step 1: Write the test every operator must pass**

Create `tests/messy/test_operators.py`. It checks that each operator declares what its effect needs, and that alone on the seed it gives exactly the statuses it declares:

```python
import pytest

from messy.compose import run, violations
from messy.catalog import CATALOG
from messy.operators import PROVABLE


def test_every_operator_declares_what_its_effect_needs():
    assert len({op.name for op in CATALOG}) == len(CATALOG)
    for op in CATALOG:
        assert op.effect in ("breaks", "holds", "inert", "stops"), op.name
        assert bool(op.scopes) == (op.effect in ("breaks", "holds")), op.name
        assert op.scopes <= set(PROVABLE) and set(op.alone) <= set(PROVABLE), op.name
        assert bool(op.why) == (op.effect == "holds"), op.name  # review reads every "holds" justification
        assert bool(op.stop) == (op.effect == "stops"), op.name
        assert all(status in ("gap", "unchecked") for status in op.alone.values()), op.name
        assert not op.known or op.effect == "breaks", op.name


def _expected_to_fail_while_known(op):
    if not op.known:
        return op
    return pytest.param(op, marks=pytest.mark.xfail(strict=True, reason=f"known false backed: {op.known}"))


@pytest.mark.parametrize("op", [_expected_to_fail_while_known(op) for op in CATALOG], ids=lambda op: op.name)
def test_an_operator_alone_gives_the_verdicts_it_declares(seeded, op):
    outcome = run(seeded.firm, (op,))
    if outcome.skipped:
        pytest.skip(f"the {seeded.name} seed has nothing for this operator to edit")
    assert violations(outcome, seeded.outcome) == []
    if outcome.stopped:
        return  # violations() checked the stop is one this operator declares
    statuses: dict[str, set[str]] = {}
    for scope, status, _ in outcome.verdicts.values():
        statuses.setdefault(scope, set()).add(status)
    assert all(len(found) == 1 for found in statuses.values()), statuses
    changed = {scope: found.pop() for scope, found in statuses.items() if scope in PROVABLE and found != {"backed"}}
    assert changed == dict(op.alone)
```

- [ ] **Step 2: Add the MFA area to the catalog**

Replace `tests/messy/catalog.py` with:

```python
"""Every operator, by area. A new real-world mess gets a new operator, not an edit to an old one."""
from messy import mfa

CATALOG = mfa.OPERATORS
BY_NAME = {op.name: op for op in CATALOG}
COMBINABLE = tuple(op for op in CATALOG if not op.known)  # a known false backed would fail every combination
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `ImportError while loading conftest`, with `ImportError: cannot import name 'mfa' from 'messy'`

- [ ] **Step 4: Write the MFA operators**

Create `tests/messy/mfa.py`:

```python
"""MFA mess: Conditional Access policies, exclusions, role holders and registration (spec 2026-10-14, catalog)."""
from __future__ import annotations

from typing import Optional

from messy.firm import Firm
from messy.operators import (
    ADMINS, ALL_MFA, ALL_USERS, BACKUP, EXCHANGE_ADMIN, GLOBAL_ADMIN, Operator, add_account, assign_role, clone, new_id,
    take, veeam_fresh)

MFA_STRENGTH = "00000000-0000-0000-0000-000000000002"  # the built-in "Multifactor authentication" strength


def _requires_mfa(policy: dict) -> bool:
    grant = policy["grantControls"] or {}
    return ("mfa" in [c.lower() for c in grant.get("builtInControls") or []]
            or (grant.get("authenticationStrength") or {}).get("id") == MFA_STRENGTH)


def _all_users_policy(firm: Firm) -> Optional[dict]:
    """The enabled policy that requires MFA, through builtInControls, of every user on every app."""
    for p in firm.rows("entra_ca_policies"):
        users, apps = p["conditions"]["users"], p["conditions"]["applications"]
        if (p["state"] == "enabled" and "All" in (users.get("includeUsers") or [])
                and "All" in (apps.get("includeApplications") or [])
                and "mfa" in [c.lower() for c in (p["grantControls"] or {}).get("builtInControls") or []]):
            return p
    return None


def _admin_portals(firm: Firm) -> bool:
    policies = firm.rows("entra_ca_policies")
    if any((p.get("displayName") or "").startswith("Multifactor authentication for admins accessing")
           for p in policies):
        return False  # a real capture has it already
    policy = clone(policies, id=new_id("policy:admin-portals"), state="enabledForReportingButNotEnforced",
                   displayName="Multifactor authentication for admins accessing Microsoft Admin Portals")
    policy["conditions"]["users"] = {**policy["conditions"]["users"], "includeUsers": [], "excludeUsers": [],
                                     "includeGroups": [], "excludeGroups": [], "includeRoles": [GLOBAL_ADMIN],
                                     "excludeRoles": []}
    policy["conditions"]["applications"] = {**policy["conditions"]["applications"],
                                            "includeApplications": ["MicrosoftAdminPortals"]}
    policy["grantControls"] = {**policy["grantControls"], "operator": "OR", "builtInControls": ["mfa"]}
    return True


def _break_glass(firm: Firm) -> bool:
    for n in (1, 2):
        account = add_account(firm, f"break.glass{n}", f"Break Glass {n}")
        assign_role(firm, f"break.glass{n}", {"@odata.type": "#microsoft.graph.user", "id": account["id"],
                                              "userPrincipalName": account["userPrincipalName"],
                                              "displayName": account["displayName"]})
        for p in firm.rows("entra_ca_policies"):
            users = p["conditions"]["users"]
            users["excludeUsers"] = [*(users.get("excludeUsers") or []), account["id"]]
    return True


def _exclusion_group(firm: Firm) -> bool:
    policy = _all_users_policy(firm)
    if policy is None:
        return False
    users = policy["conditions"]["users"]
    users["excludeGroups"] = [*(users.get("excludeGroups") or []), new_id("group:mfa-exclusions")]
    return True


def _office365_only(firm: Firm) -> bool:
    policy = _all_users_policy(firm)
    if policy is None or not take(firm, f"policy-apps:{policy['id']}"):
        return False
    policy["conditions"]["applications"]["includeApplications"] = ["Office365"]
    return True


def _authentication_strength(firm: Firm) -> bool:
    policy = _all_users_policy(firm)
    if policy is None or not take(firm, f"policy-grant:{policy['id']}"):
        return False
    grant = policy["grantControls"]
    grant["builtInControls"] = []
    grant["authenticationStrength@odata.context"] = (
        "https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies('x')/grantControls/"
        "authenticationStrength/$entity")
    grant["authenticationStrength"] = {
        "id": MFA_STRENGTH, "displayName": "Multifactor authentication", "policyType": "builtIn",
        "requirementsSatisfied": "mfa",
        "allowedCombinations": ["windowsHelloForBusiness", "fido2", "password,microsoftAuthenticatorPush",
                                "password,softwareOath", "password,sms"]}
    return True


def _per_user_mfa(firm: Firm) -> bool:
    policies = [p for p in firm.rows("entra_ca_policies") if _requires_mfa(p) and p["state"] == "enabled"]
    if not policies or not all(take(firm, f"policy-state:{p['id']}") for p in policies):
        return False
    for p in policies:
        p["state"] = "disabled"
    return True


def _group_admin(firm: Firm, unregistered_member: bool) -> bool:
    label = "admins-group-unregistered" if unregistered_member else "admins-group"
    assign_role(firm, label, {"@odata.type": "#microsoft.graph.group", "id": new_id(f"group:{label}"),
                              "displayName": "Tenant Admins", "mail": None, "securityEnabled": True,
                              "isAssignableToRole": True})
    if unregistered_member:
        add_account(firm, "new.admin", "New Admin", registered=False, mailbox=(True, veeam_fresh(firm)))
    return True


def _service_principal_admin(firm: Firm) -> bool:
    assign_role(firm, "backup-connector", {"@odata.type": "#microsoft.graph.servicePrincipal",
                                           "id": new_id("sp:backup-connector"), "displayName": "Backup Connector",
                                           "appId": new_id("app:backup-connector")}, role=EXCHANGE_ADMIN)
    return True


def _registration_lag(firm: Firm) -> bool:
    add_account(firm, "new.hire", "New Hire", registered=None, mailbox=None)
    return True


OPERATORS = (
    Operator("microsoft-managed admin-portals policy", "holds", _admin_portals, scopes=ALL_MFA,
             why="a report-only policy enforces nothing and excludes no one"),
    Operator("break-glass accounts excluded", "breaks", _break_glass,
             # Backup is a false gap: break-glass accounts hold no mailbox, but every enabled member is counted.
             alone={"mfa.all_users": "gap", "mfa.email": "gap", "mfa.admins": "gap", "backup.m365_mailboxes": "gap"},
             scopes=ALL_MFA, twin="real-messy-break-glass"),
    Operator("MFA exclusions group", "breaks", _exclusion_group,
             alone={"mfa.all_users": "gap", "mfa.email": "gap"}, scopes=ALL_USERS, twin="real-messy-exclusion-group"),
    Operator("all-users policy limited to Office 365", "breaks", _office365_only,
             alone={"mfa.all_users": "gap"}, scopes=frozenset({"mfa.all_users"})),
    Operator("grant through an authentication strength", "holds", _authentication_strength, scopes=ALL_USERS,
             why="the built-in Multifactor authentication strength requires MFA, as builtInControls mfa does"),
    Operator("per-user MFA instead of Conditional Access", "holds", _per_user_mfa,
             alone={"mfa.all_users": "gap", "mfa.email": "gap", "mfa.admins": "gap"}, scopes=ALL_MFA,
             why="per-user MFA prompts every account on every sign-in; no export in this set shows it"),
    Operator("admin role held by a group", "holds", lambda firm: _group_admin(firm, unregistered_member=False),
             alone={"mfa.admins": "unchecked"}, scopes=ADMINS,
             why="the group's members are existing accounts, registered and covered like everyone else"),
    Operator("admin role held by a group with an unregistered member", "breaks",
             lambda firm: _group_admin(firm, unregistered_member=True),
             alone={"mfa.all_users": "gap", "mfa.email": "gap", "mfa.admins": "unchecked"}, scopes=ALL_MFA),
    Operator("admin role held by a service principal", "holds", _service_principal_admin, scopes=ADMINS,
             why="a service principal signs in with a secret or a certificate; MFA does not apply to it"),
    Operator("user created after the registration report", "breaks", _registration_lag,
             alone={"mfa.all_users": "unchecked", "mfa.email": "unchecked", "backup.m365_mailboxes": "gap"},
             scopes=ALL_USERS | BACKUP, twin="real-messy-new-user"),
)
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/messy/mfa.py tests/messy/catalog.py tests/messy/test_operators.py
git commit -m "Add the MFA mess: break-glass and group exclusions, narrowed and strength-based policies, per-user MFA, unusual role holders, a new hire" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The EDR operators

**Files:**
- Create: `tests/messy/edr.py`
- Modify: `tests/messy/catalog.py`

**Interfaces:**
- Consumes: `messy.operators` helpers, including `paired` and `machine_id`.
- Produces: `messy.edr.OPERATORS`, eight operators: `laptop re-imaged`, `VM off for 8 days`, `sensor cut off`, `discovered printer`, `discovered unmanaged PC`, `discovered device with no DNS name`, `device renamed after onboarding`, `Intune device with no primary user`.

- [ ] **Step 1: Add the EDR area to the catalog**

Replace `tests/messy/catalog.py` with:

```python
"""Every operator, by area. A new real-world mess gets a new operator, not an edit to an old one."""
from messy import edr, mfa

CATALOG = mfa.OPERATORS + edr.OPERATORS
BY_NAME = {op.name: op for op in CATALOG}
COMBINABLE = tuple(op for op in CATALOG if not op.known)  # a known false backed would fail every combination
```

- [ ] **Step 2: Run the operator tests to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `ImportError while loading conftest`, with `ImportError: cannot import name 'edr' from 'messy'`

- [ ] **Step 3: Write the EDR operators**

Create `tests/messy/edr.py`. The re-image marks its new Intune ID touched as well, or a later operator would pick the same laptop again under its new ID:

```python
"""EDR mess: re-imaged, stale, cut-off, renamed and discovered devices (spec 2026-10-14, catalog)."""
from __future__ import annotations

import copy
from datetime import timedelta

from messy.firm import Firm
from messy.operators import EDR, Operator, clone, domain, machine_id, new_id, paired, take, utc_text


def _reimaged(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    device, machine = pair
    new_aad = new_id(f"aad:reimaged:{device['id']}")
    old = copy.deepcopy(machine)
    old.update(healthStatus="Inactive", lastSeen=utc_text(firm.exported_at("defender_machines") - timedelta(days=10)))
    firm.rows("defender_machines").append(old)
    machine.update(id=machine_id(f"machine:reimaged:{device['id']}"), aadDeviceId=new_aad)
    device.update(id=new_id(f"intune:reimaged:{device['id']}"), azureADDeviceId=new_aad)
    firm.touched.add(f"device:{device['id']}")  # the new Intune record is the same laptop
    return True


def _vm_off(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    pair[1].update(healthStatus="Inactive",
                   lastSeen=utc_text(firm.exported_at("defender_machines") - timedelta(days=8)))
    return True


def _sensor_cut_off(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    pair[1]["healthStatus"] = "ImpairedCommunication"
    return True


def _discovered(firm: Firm, label: str, **changes) -> bool:
    if not take(firm, f"discovered:{label}"):
        return False
    clone(firm.rows("defender_machines"), id=machine_id(f"machine:{label}"), aadDeviceId=None,
          lastSeen=utc_text(firm.exported_at("defender_machines") - timedelta(hours=6)), **changes)
    return True


def _renamed(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    device, machine = pair
    machine["computerDnsName"] = f"renamed-{device['deviceName'].lower()}.{domain(firm)}"
    return True


def _no_primary_user(firm: Firm) -> bool:
    for device in firm.rows("intune_devices"):
        if take(firm, f"device-user:{device['id']}"):
            device["userPrincipalName"] = ""
            return True
    return False


OPERATORS = (
    Operator("laptop re-imaged", "holds", _reimaged, scopes=EDR, twin="real-messy-reimaged",
             why="the laptop is onboarded again under a new Entra device; the old Defender record is a ghost"),
    Operator("VM off for 8 days", "breaks", _vm_off,
             alone={"edr.all_endpoints": "gap"}, scopes=EDR, twin="real-messy-vm-off"),
    Operator("sensor cut off", "breaks", _sensor_cut_off,
             alone={"edr.all_endpoints": "gap"}, scopes=EDR, twin="real-messy-sensor-cut"),
    Operator("discovered printer", "holds",
             lambda firm: _discovered(firm, "printer", computerDnsName="hp-laserjet-01", osPlatform="Linux",
                                      onboardingStatus="Unsupported", healthStatus="Inactive"),
             scopes=EDR, why="a printer cannot run Defender; it is not an endpoint the claim is about"),
    Operator("discovered unmanaged PC", "breaks",
             lambda firm: _discovered(firm, "unmanaged-pc", computerDnsName="desktop-7q2k9", osPlatform="Windows11",
                                      onboardingStatus="CanBeOnboarded", healthStatus="Inactive"),
             alone={"edr.all_endpoints": "gap"}, scopes=EDR, twin="real-messy-discovered"),
    Operator("discovered device with no DNS name", "holds",
             lambda firm: _discovered(firm, "nameless", computerDnsName=None, osPlatform="Unknown",
                                      onboardingStatus="InsufficientInfo", healthStatus="Inactive"),
             scopes=EDR, why="a device known only by its network address is not shown to be a company endpoint",
             # Provisional: kept until a real capture shows whether Defender writes a null name.
             may_stop="field 'computerDnsName' must be a non-empty string, got None"),
    Operator("device renamed after onboarding", "holds", _renamed, scopes=EDR, twin="real-messy-renamed",
             why="the same device, paired by its Entra device ID"),
    Operator("Intune device with no primary user", "inert", _no_primary_user),
)
```

- [ ] **Step 4: Run the operator tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `19 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/messy/edr.py tests/messy/catalog.py
git commit -m "Add the EDR mess: a re-imaged laptop, stale and cut-off sensors, discovered devices, a renamed device" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The backup operators, and the known false backed

**Files:**
- Create: `tests/messy/backup.py`
- Modify: `tests/messy/catalog.py`
- Modify: `docs/engineering/using.md` (Known limitations)

**Interfaces:**
- Consumes: `messy.operators` helpers, including `member` and `add_account`.
- Produces: `messy.backup.OPERATORS`, five operators: `11th user over the Veeam limit`, `backup job paused for 2 days`, `shared mailbox listed but not backed up`, `shared mailbox Veeam never saw` (`known`), `Veeam Email is the primary SMTP address`.

- [ ] **Step 1: Add the backup area to the catalog**

Replace `tests/messy/catalog.py` with:

```python
"""Every operator, by area. A new real-world mess gets a new operator, not an edit to an old one."""
from messy import backup, edr, mfa

CATALOG = mfa.OPERATORS + edr.OPERATORS + backup.OPERATORS
BY_NAME = {op.name: op for op in CATALOG}
COMBINABLE = tuple(op for op in CATALOG if not op.known)  # a known false backed would fail every combination
```

- [ ] **Step 2: Run the operator tests to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `ImportError while loading conftest`, with `ImportError: cannot import name 'backup' from 'messy'`

- [ ] **Step 3: Write the backup operators**

Create `tests/messy/backup.py`:

```python
"""Backup mess: Veeam's user limit, a paused job, shared mailboxes, SMTP addresses (spec 2026-10-14, catalog)."""
from __future__ import annotations

from datetime import timedelta

from messy.firm import Firm
from messy.operators import BACKUP, Operator, add_account, domain, member, take, utc_text


def _over_limit(firm: Firm) -> bool:
    add_account(firm, "eleventh.user", "Eleventh User", registered=True, mailbox=None)
    return True


def _paused(firm: Firm) -> bool:
    if not take(firm, "veeam-times"):
        return False
    stale = utc_text(firm.exported_at("veeam_users") - timedelta(days=2))
    for r in firm.rows("veeam_users"):
        if r["IsMailboxBackedUp"]:
            r["MailboxBackedUpTime"] = stale
    return True


def _shared_mailbox(firm: Firm) -> bool:
    add_account(firm, "front.desk", "Front Desk (shared)", enabled=False, registered=False, mailbox=(False, None))
    return True


def _shared_mailbox_never_seen(firm: Firm) -> bool:
    add_account(firm, "front.desk", "Front Desk (shared)", enabled=False, registered=False, mailbox=None)
    return True


def _primary_smtp(firm: Firm) -> bool:
    account = member(firm, admin=False, mailbox=True)
    if account is None:
        return False
    upn = account["userPrincipalName"]
    (row,) = [r for r in firm.rows("veeam_users") if r["Email"].lower() == upn.lower()]
    row["Email"] = f"{upn.split('@')[0].split('.')[0]}@mail.{domain(firm)}"
    return True


OPERATORS = (
    Operator("11th user over the Veeam limit", "breaks", _over_limit,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP, twin="real-messy-over-limit"),
    Operator("backup job paused for 2 days", "breaks", _paused,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP, twin="real-messy-paused"),
    Operator("shared mailbox listed but not backed up", "breaks", _shared_mailbox,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP),
    Operator("shared mailbox Veeam never saw", "breaks", _shared_mailbox_never_seen,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP, twin="real-messy-shared-mailbox",
             known="a disabled account Veeam does not list is left out of the backup population "
                   "(attest/rules/backup.py), so a shared mailbox the job never covered is not counted"),
    Operator("Veeam Email is the primary SMTP address", "holds", _primary_smtp,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP,
             why="the mailbox is backed up; Veeam names it by its SMTP address, not its UPN"),
)
```

- [ ] **Step 4: Run the operator tests, and read the expected failure**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q -rx`
Expected: `23 passed, 1 xfailed`, the expected failure being `shared mailbox Veeam never saw` with the reason `known false backed: a disabled account Veeam does not list is left out of the backup population ...`

- [ ] **Step 5: Record the false backed as a known limitation**

In `docs/engineering/using.md`, under `## Known limitations`, add after the item that begins "Unlicensed or service accounts are permanent backup gaps":

```markdown
- A shared mailbox the backup job never covered is not counted. A shared
  mailbox is a disabled user object, and a disabled account joins the backup
  population only when the Veeam export lists it, so backup can come out
  backed while that mailbox holds unprotected mail. This is a known false
  backed (`tests/messy/backup.py`, "shared mailbox Veeam never saw"), to be
  fixed in the backup rule in its own change.
```

- [ ] **Step 6: Commit**

```bash
git add tests/messy/backup.py tests/messy/catalog.py docs/engineering/using.md
git commit -m "Add the backup mess, and record that a shared mailbox Veeam never saw comes out backed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The format and stop operators

**Files:**
- Create: `tests/messy/formats.py`
- Modify: `tests/messy/catalog.py`

**Interfaces:**
- Consumes: `messy.firm.records`, `Firm.writers`; `messy.operators.take`.
- Produces: `messy.formats.OPERATORS`, eight operators: `UTF-16 with CRLF`, `UTF-8 with a BOM and CRLF`, `rows and fields reordered`, `unknown fields added`, `Defender times with 7 fractional digits`, `Veeam times as PowerShell 5.1 DateTimes`, `users export is one page of several` (stops), `Veeam time with no UTC offset` (stops). The catalog is then complete: 31 operators.

- [ ] **Step 1: Add the format area to the catalog**

Replace `tests/messy/catalog.py` with:

```python
"""Every operator, by area. A new real-world mess gets a new operator, not an edit to an old one."""
from messy import backup, edr, formats, mfa

CATALOG = mfa.OPERATORS + edr.OPERATORS + backup.OPERATORS + formats.OPERATORS
BY_NAME = {op.name: op for op in CATALOG}
COMBINABLE = tuple(op for op in CATALOG if not op.known)  # a known false backed would fail every combination
```

- [ ] **Step 2: Run the operator tests to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `ImportError while loading conftest`, with `ImportError: cannot import name 'formats' from 'messy'`

- [ ] **Step 3: Write the format operators**

Create `tests/messy/formats.py`. An unknown field goes only at the top level of a policy, because an unknown key inside its conditions narrows it by design:

```python
"""Format mess: how PowerShell and the APIs write the same data, and the refusals the docs promise.

Inert operators run after every other operator in a combination (compose.apply), so they reshape whatever the others
wrote.
"""
from __future__ import annotations

import json
from datetime import datetime

from messy.firm import Firm, records
from messy.operators import Operator, take


def _write_all(firm: Firm, encode) -> bool:
    if not take(firm, "format:encoding"):
        return False
    for name in firm.data:
        firm.writers[name] = encode
    return True


def _utf16(data) -> bytes:
    """Windows PowerShell 5.1's Out-File default: UTF-16 LE with a byte-order mark, CRLF."""
    return ("﻿" + json.dumps(data, indent=2).replace("\n", "\r\n") + "\r\n").encode("utf-16-le")


def _utf8_bom_crlf(data) -> bytes:
    """Windows PowerShell 5.1's Out-File -Encoding utf8: UTF-8 with a byte-order mark, CRLF."""
    return ("﻿" + json.dumps(data, indent=4).replace("\n", "\r\n") + "\r\n").encode("utf-8")


def _reordered(firm: Firm) -> bool:
    if not take(firm, "format:order"):
        return False
    for data in firm.data.values():
        rows = records(data)
        rows.reverse()
        rows[:] = [dict(reversed(list(r.items()))) for r in rows]
    return True


UNKNOWN_FIELDS = {
    "entra_users": {"createdDateTime": "2025-01-06T16:00:00Z", "mail": None, "jobTitle": None},
    "entra_registration": {"isSsprRegistered": False, "lastUpdatedDateTime": "2026-10-01T03:00:00Z"},
    # Top-level only: an unknown key inside a policy's conditions narrows it, by design (entra_ca_policies.py).
    "entra_ca_policies": {"templateId": None, "createdDateTime": "2025-01-06T16:00:00Z", "modifiedDateTime": None,
                          "sessionControls": None},
    "intune_devices": {"enrolledDateTime": "2025-01-07T10:00:00Z", "complianceState": "compliant"},
    "defender_machines": {"firstSeen": "2025-01-07T10:05:00.1234567Z", "osProcessor": "x64",
                          "lastIpAddress": "192.0.2.10", "riskScore": "None", "machineTags": []},
    "veeam_users": {"IsArchiveBackedUp": False, "ArchiveBackedUpTime": None},
}


def _unknown_fields(firm: Firm) -> bool:
    if not take(firm, "format:fields"):
        return False
    for reader, fields in UNKNOWN_FIELDS.items():
        for r in firm.rows(reader):
            r.update({k: v for k, v in fields.items() if k not in r})
    return True


def _seven_digit_fractions(firm: Firm) -> bool:
    if not take(firm, "format:defender-times"):
        return False
    for m in firm.rows("defender_machines"):
        if isinstance(m.get("lastSeen"), str) and m["lastSeen"].endswith("Z") and "." not in m["lastSeen"]:
            m["lastSeen"] = m["lastSeen"][:-1] + ".1234567Z"
    return True


def _ps51_dates(firm: Firm) -> bool:
    if not take(firm, "format:veeam-dates"):
        return False
    for r in firm.rows("veeam_users"):
        when = r.get("MailboxBackedUpTime")
        # A time with no offset is left as it is: refusing it is another operator's promise.
        if isinstance(when, str) and datetime.fromisoformat(when).utcoffset() is not None:
            r["MailboxBackedUpTime"] = {"value": f"/Date({int(datetime.fromisoformat(when).timestamp() * 1000)})/",
                                        "DisplayHint": 2}
    return True


def _paged_users(firm: Firm) -> bool:
    page = firm.data[firm.file("entra_users")]
    if not isinstance(page, dict) or not take(firm, "users-page"):
        return False
    page["@odata.nextLink"] = "https://graph.microsoft.com/v1.0/users?$top=5&$skiptoken=X"
    return True


def _veeam_no_offset(firm: Firm) -> bool:
    if not take(firm, "veeam-times"):
        return False
    for r in firm.rows("veeam_users"):
        if isinstance(r.get("MailboxBackedUpTime"), str):
            r["MailboxBackedUpTime"] = r["MailboxBackedUpTime"].replace("Z", "").split("+")[0]
            return True
    return False


OPERATORS = (
    Operator("UTF-16 with CRLF", "inert", lambda firm: _write_all(firm, _utf16)),
    Operator("UTF-8 with a BOM and CRLF", "inert", lambda firm: _write_all(firm, _utf8_bom_crlf)),
    Operator("rows and fields reordered", "inert", _reordered),
    Operator("unknown fields added", "inert", _unknown_fields),
    Operator("Defender times with 7 fractional digits", "inert", _seven_digit_fractions),
    Operator("Veeam times as PowerShell 5.1 DateTimes", "inert", _ps51_dates),
    Operator("users export is one page of several", "stops", _paged_users,
             stop="the export is one page of several", twin="real-messy-paged"),
    Operator("Veeam time with no UTC offset", "stops", _veeam_no_offset, stop="has no UTC offset"),
)
```

- [ ] **Step 4: Run the operator tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_operators.py -q`
Expected: `31 passed, 1 xfailed`

- [ ] **Step 5: Commit**

```bash
git add tests/messy/formats.py tests/messy/catalog.py
git commit -m "Add the format mess PowerShell and the APIs make, and the refusals the export docs promise" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Combinations, and the long run's summary

**Files:**
- Modify: `tests/messy/compose.py` (imports; append `Tally`)
- Modify: `pyproject.toml` (`markers`, `addopts`)
- Test: `tests/messy/test_combinations.py`
- Create, by running: `firm/lab/messy-summary.md`

**Interfaces:**
- Consumes: `combinations`, `run`, `shrink`, `violations`, `degraded` (Task 3); `messy.firm.LAB`.
- Produces, in `messy.compose`: `Tally()` with `add(outcome: Outcome, seed: Outcome, problems: list[str]) -> None`, `markdown(seed_name: str, seed_number: int, today: date) -> str`, and the field `problems: list[str]`.

- [ ] **Step 1: Write the tests**

Create `tests/messy/test_combinations.py`:

```python
"""Seeded combinations of mess under the four properties (compose.py), and the long run that writes the summary."""
from datetime import date

import pytest

from messy.compose import Tally, combinations, run, shrink, violations
from messy.firm import LAB

SEED_NUMBER = 20261014
COMBINATIONS = combinations(SEED_NUMBER, 200)


@pytest.mark.parametrize("number", range(len(COMBINATIONS)))
def test_a_combination_of_mess_keeps_every_property(seeded, number):
    combo = COMBINATIONS[number]
    problems = violations(run(seeded.firm, combo), seeded.outcome)
    if problems:
        smallest = shrink(combo, lambda ops: bool(violations(run(seeded.firm, ops), seeded.outcome)))
        pytest.fail(f"{problems}; smallest failing set: {[op.name for op in smallest]}")


@pytest.mark.messy
def test_five_thousand_combinations_keep_every_property_and_write_the_summary(seeded):
    tally = Tally()
    for combo in combinations(SEED_NUMBER, 5000):
        outcome = run(seeded.firm, combo)
        problems = violations(outcome, seeded.outcome)
        if problems:
            smallest = shrink(combo, lambda ops: bool(violations(run(seeded.firm, ops), seeded.outcome)))
            problems = [f"{p}; smallest failing set: {[op.name for op in smallest]}" for p in problems]
        tally.add(outcome, seeded.outcome, problems)
    LAB.mkdir(parents=True, exist_ok=True)
    (LAB / "messy-summary.md").write_text(tally.markdown(seeded.name, SEED_NUMBER, date.today()), encoding="utf-8",
                                          newline="\n")
    assert tally.problems == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_combinations.py -q`
Expected: `ImportError while importing test module`, with `ImportError: cannot import name 'Tally' from 'messy.compose'`

- [ ] **Step 3: Add the tally to the judge**

In `tests/messy/compose.py`, replace the import block:

```python
import random
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
```

with:

```python
import random
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
```

and append at the end of the file, after `shrink`, separated by two blank lines:

```python
@dataclass
class Tally:
    """What a long run found: every property violation, every stop, and the noise cost of each "holds" operator."""

    runs: int = 0
    problems: list[str] = field(default_factory=list)
    stops: Counter = field(default_factory=Counter)
    applied: Counter = field(default_factory=Counter)
    degraded: Counter = field(default_factory=Counter)
    drops: defaultdict = field(default_factory=lambda: defaultdict(Counter))

    def add(self, outcome: Outcome, seed: Outcome, problems: list[str]) -> None:
        self.runs += 1
        self.problems += problems
        if outcome.stopped:
            self.stops[re.sub(r"rows? \d+( and \d+)?", "row N", outcome.stopped)] += 1
        for op in outcome.applied:
            if op.effect == "holds":
                self.applied[op.name] += 1
        for name, statuses in degraded(outcome, seed).items():
            self.degraded[name] += 1
            self.drops[name].update(statuses)

    def markdown(self, seed_name: str, seed_number: int, today: date) -> str:
        lines = [
            "# Messy-firm run", "",
            f"Run {today.isoformat()} on the {seed_name} seed: {self.runs} combinations of one to four operators "
            f"from tests/messy/catalog.py, random seed {seed_number}.", "",
            f"- Property violations: {len(self.problems)}",
            f"- Runs that stopped: {sum(self.stops.values())}", "",
        ]
        if self.problems:
            lines += ["## Violations", ""] + [f"- {p}" for p in self.problems] + [""]
        lines += ["## Stops", "", "| Reason | Runs |", "|---|---|"]
        lines += [f"| {reason} | {n} |" for reason, n in sorted(self.stops.items())]
        lines += ["", '## Noise cost of "holds" operators', "",
                  "A run counts against an operator when a scope it declares left the seed's status while it was "
                  'applied and no applied "breaks" operator breaks that scope. Every "holds" operator applied in '
                  "that run with the same scope is charged.", "",
                  "| Operator | Runs applied | Runs degraded | Degraded to |", "|---|---|---|---|"]
        for name in sorted(self.applied):
            to = ", ".join(f"{status} {n}" for status, n in sorted(self.drops.get(name, Counter()).items())) or "-"
            lines.append(f"| {name} | {self.applied[name]} | {self.degraded[name]} | {to} |")
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Keep the long run out of the default run**

In `pyproject.toml`, under `[tool.pytest.ini_options]`, add after `testpaths = ["tests"]`:

```toml
markers = ["messy: the long messy-firm run; writes firm/lab/messy-summary.md (run with: pytest -m messy)"]
addopts = "-m 'not messy'"
```

A `-m messy` on the command line overrides the default `-m 'not messy'`.

- [ ] **Step 5: Run the default tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_combinations.py -q`
Expected: `200 passed, 1 deselected` (about 10 to 15 seconds)

- [ ] **Step 6: Run the long run once on the dev seed**

Run: `venv/Scripts/python.exe -m pytest -m messy tests/messy -q`
Expected: `1 passed, ... deselected` after about 5 minutes, and a new `firm/lab/messy-summary.md` whose first lines read `Run <today> on the dev seed: 5000 combinations ...` and `- Property violations: 0`. Read its noise table. On the dev seed, per-user MFA, an admin role held by a group, and a Veeam `Email` that is the SMTP address cost the most.

- [ ] **Step 7: Run the whole suite**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: every test passes except the two Python 3.14 NUL-path tests named in Global Constraints; `1 deselected`, `1 xfailed`.

- [ ] **Step 8: Commit**

```bash
git add tests/messy/compose.py tests/messy/test_combinations.py pyproject.toml firm/lab/messy-summary.md
git commit -m "Run seeded combinations of mess under the four properties, and write the long run's summary on the dev seed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The pinned archetypes

**Files:**
- Test: `tests/messy/test_archetypes.py`
- Create: `tests/messy/archetypes/dev/msp-run-firm.yaml`, `reimaged-fleet.yaml`, `backup-over-its-limit.yaml`, `powershell-5-1-admin.yaml`

**Interfaces:**
- Consumes: `messy.catalog.BY_NAME`; `messy.compose.run`; the `seeded` fixture.
- Produces: the truth file format: `operators:` (a list of operator names) and `verdicts:` (tag id to `{status, entities}`, in tag order, as in `firm/dev/truth.yaml`).

- [ ] **Step 1: Write the test**

Create `tests/messy/test_archetypes.py`:

```python
"""Four named combinations whose every verdict a person checked by hand, one truth file per seed."""
from pathlib import Path

import pytest
import yaml

from messy.catalog import BY_NAME
from messy.compose import run

ARCHETYPES = Path(__file__).parent / "archetypes"
NAMES = ("msp-run-firm", "reimaged-fleet", "backup-over-its-limit", "powershell-5-1-admin")


@pytest.mark.parametrize("name", NAMES)
def test_an_archetype_gets_its_hand_checked_verdicts(seeded, name):
    path = ARCHETYPES / seeded.name / f"{name}.yaml"
    if not path.exists():
        pytest.fail(f"hand-check the {name} archetype on the {seeded.name} seed and write {path}")
    truth = yaml.safe_load(path.read_text(encoding="utf-8"))
    outcome = run(seeded.firm, [BY_NAME[op] for op in truth["operators"]])
    assert (outcome.skipped, outcome.stopped) == ((), "")
    assert list(outcome.verdicts) == list(truth["verdicts"])
    for tag, expected in truth["verdicts"].items():
        _, status, entities = outcome.verdicts[tag]
        assert (status, list(entities)) == (expected["status"], sorted(expected.get("entities", []))), tag
```

- [ ] **Step 2: Run it to see it fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_archetypes.py -q`
Expected: `4 failed`, each saying `hand-check the <name> archetype on the dev seed and write ...`

- [ ] **Step 3: Write the four hand-checked truth files**

Each verdict below was checked by hand against the operators' edits; the comment at the top of each file says why. Create `tests/messy/archetypes/dev/msp-run-firm.yaml`:

```yaml
# The MSP-run firm, on the healed dev firm (spec 2026-10-14, Pinned archetypes). Hand-checked 2026-10-14.
# The break-glass accounts are excluded from every policy and hold Global Administrator, so every MFA scope is a gap
# naming them. Backup names them too: they hold no mailbox, and every enabled member is counted (a false gap).
# The report-only admin-portals policy, the authentication-strength grant and the service principal change nothing.
operators:
  - microsoft-managed admin-portals policy
  - break-glass accounts excluded
  - grant through an authentication strength
  - admin role held by a service principal
verdicts:
  app-4.1: {status: gap, entities: [break.glass1@harborpine.example, break.glass2@harborpine.example]}
  app-4.2: {status: unchecked}
  app-4.3: {status: gap, entities: [break.glass1@harborpine.example, break.glass2@harborpine.example]}
  app-4.4: {status: backed}
  app-4.5: {status: gap, entities: [break.glass1@harborpine.example, break.glass2@harborpine.example]}
  app-4.6: {status: unchecked}
  wisp-mfa-all: {status: gap, entities: [break.glass1@harborpine.example, break.glass2@harborpine.example]}
  wisp-mfa-admins: {status: gap, entities: [break.glass1@harborpine.example, break.glass2@harborpine.example]}
  wisp-vpn: {status: unchecked}
  wisp-edr: {status: backed}
  wisp-edr-alerts: {status: unchecked}
  wisp-backup: {status: gap, entities: [break.glass1@harborpine.example, break.glass2@harborpine.example]}
  wisp-backup-files: {status: unchecked}
  wisp-immutable: {status: unchecked}
```

Create `tests/messy/archetypes/dev/reimaged-fleet.yaml`:

```yaml
# The re-imaged fleet, on the healed dev firm (spec 2026-10-14, Pinned archetypes). Hand-checked 2026-10-14.
# HP-LT-01 is re-imaged (its old Defender record, Inactive and 10 days old, sits outside the population), HP-LT-02 is
# renamed in Defender (still paired by Entra device ID), the printer is Unsupported and only listed, and HP-LT-03 has
# been off for 8 days: the one gap.
operators:
  - laptop re-imaged
  - device renamed after onboarding
  - discovered printer
  - VM off for 8 days
verdicts:
  app-4.1: {status: backed}
  app-4.2: {status: unchecked}
  app-4.3: {status: backed}
  app-4.4: {status: gap, entities: [HP-LT-03]}
  app-4.5: {status: backed}
  app-4.6: {status: unchecked}
  wisp-mfa-all: {status: backed}
  wisp-mfa-admins: {status: backed}
  wisp-vpn: {status: unchecked}
  wisp-edr: {status: gap, entities: [HP-LT-03]}
  wisp-edr-alerts: {status: unchecked}
  wisp-backup: {status: backed}
  wisp-backup-files: {status: unchecked}
  wisp-immutable: {status: unchecked}
```

Create `tests/messy/archetypes/dev/backup-over-its-limit.yaml`:

```yaml
# The backup over its limit, on the healed dev firm (spec 2026-10-14, Pinned archetypes). Hand-checked 2026-10-14.
# The job has been paused for 2 days, so every backed-up mailbox is stale; the 11th user has no Veeam row; the shared
# front-desk mailbox (a disabled account Veeam lists) was never backed up. Sam Lowe is disabled but listed by Veeam,
# so he is counted too.
operators:
  - 11th user over the Veeam limit
  - shared mailbox listed but not backed up
  - backup job paused for 2 days
verdicts:
  app-4.1: {status: backed}
  app-4.2: {status: unchecked}
  app-4.3: {status: backed}
  app-4.4: {status: backed}
  app-4.5:
    status: gap
    entities: &everyone
      - aisha.rahman@harborpine.example
      - ben.foster@harborpine.example
      - carmen.diaz@harborpine.example
      - dana.whitfield@harborpine.example
      - elena.kowalski@harborpine.example
      - eleventh.user@harborpine.example
      - felix.braun@harborpine.example
      - front.desk@harborpine.example
      - george.okafor@harborpine.example
      - hana.sato@harborpine.example
      - ivan.petrov@harborpine.example
      - marcus.chen@harborpine.example
      - priya.nair@harborpine.example
      - sam.lowe@harborpine.example
      - tom.reyes@harborpine.example
  app-4.6: {status: unchecked}
  wisp-mfa-all: {status: backed}
  wisp-mfa-admins: {status: backed}
  wisp-vpn: {status: unchecked}
  wisp-edr: {status: backed}
  wisp-edr-alerts: {status: unchecked}
  wisp-backup: {status: gap, entities: *everyone}
  wisp-backup-files: {status: unchecked}
  wisp-immutable: {status: unchecked}
```

Create `tests/messy/archetypes/dev/powershell-5-1-admin.yaml`:

```yaml
# The PowerShell 5.1 admin, on the healed dev firm (spec 2026-10-14, Pinned archetypes). Hand-checked 2026-10-14.
# UTF-16 files with CRLF, Veeam times wrapped as PowerShell 5.1 DateTimes, rows and fields in another order: every
# verdict is the seed's.
operators:
  - UTF-16 with CRLF
  - Veeam times as PowerShell 5.1 DateTimes
  - rows and fields reordered
verdicts:
  app-4.1: {status: backed}
  app-4.2: {status: unchecked}
  app-4.3: {status: backed}
  app-4.4: {status: backed}
  app-4.5: {status: backed}
  app-4.6: {status: unchecked}
  wisp-mfa-all: {status: backed}
  wisp-mfa-admins: {status: backed}
  wisp-vpn: {status: unchecked}
  wisp-edr: {status: backed}
  wisp-edr-alerts: {status: unchecked}
  wisp-backup: {status: backed}
  wisp-backup-files: {status: unchecked}
  wisp-immutable: {status: unchecked}
```

- [ ] **Step 4: Run the test to see it pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_archetypes.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/messy/test_archetypes.py tests/messy/archetypes
git commit -m "Pin four named archetypes of mess with hand-checked verdicts on the dev seed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The fidelity check

**Files:**
- Create: `tests/messy/fidelity.py`
- Modify: `tests/messy/compose.py` (add `run_capture`; import `assemble`)
- Test: `tests/messy/test_fidelity.py`

**Interfaces:**
- Consumes: `messy.firm.Firm`, `assemble`, `LAB`, `SEED_CLEAN`; `messy.compose.apply`, `Outcome`, `violations`; `messy.catalog.BY_NAME`, `CATALOG`.
- Produces, in `messy.fidelity`: `KEYS: dict[str, str]` (reader to record key); `json_type(value) -> str`; `Change(added: int, removed: int, changed_fields: frozenset[str], added_shape: frozenset[tuple[str, str]])`; `change(before: Firm, after: Firm, reader: str) -> Change`; `mismatches(before: Firm, synthetic: Firm, real: Firm) -> list[str]`.
- Produces, in `messy.compose`: `run_capture(exports: Path) -> Outcome`, the check on a capture exactly as written.

- [ ] **Step 1: Write the tests**

Create `tests/messy/test_fidelity.py`. The twin tests skip until their captures exist (Tasks 13 and 14):

```python
"""Operators against the real captures of the same mess, and the real captures against what the seed promises."""
import copy

import pytest

from messy.compose import Outcome, apply, run_capture, violations
from messy.fidelity import mismatches
from messy.firm import LAB, SEED_CLEAN, Firm
from messy.catalog import BY_NAME, CATALOG

TWINS = [op for op in CATALOG if op.twin]


def _made(firm, name):
    return apply(firm, (BY_NAME[name],))[0]


def test_an_operator_agrees_with_a_capture_that_made_the_same_mess(seeded):
    before = seeded.firm
    assert mismatches(before, _made(before, "VM off for 8 days"), _made(before, "VM off for 8 days")) == []


def test_a_capture_that_added_a_record_the_operator_did_not_is_a_mismatch(seeded):
    before = seeded.firm
    synthetic = _made(before, "sensor cut off")
    real = synthetic.copy()
    extra = copy.deepcopy(real.rows("defender_machines")[0])
    extra["id"] = "e" * 40
    real.rows("defender_machines").append(extra)
    assert mismatches(before, synthetic, real) == [
        "defender_machines: the operator adds 0 and removes 0 records; the capture adds 1 and removes 0"]


def test_an_operator_changing_a_field_the_capture_left_alone_is_a_mismatch(seeded):
    before = seeded.firm
    assert mismatches(before, _made(before, "sensor cut off"), before.copy()) == [
        "defender_machines: the operator changes healthStatus, which the capture does not"]


def test_added_records_with_other_fields_are_a_mismatch(seeded):
    before = seeded.firm
    synthetic = _made(before, "discovered unmanaged PC")
    real = synthetic.copy()
    del real.rows("defender_machines")[-1]["osPlatform"]
    assert mismatches(before, synthetic, real) == [
        "defender_machines: added records differ; only the operator's have ['osPlatform (string)'], "
        "only the capture's have []"]


@pytest.mark.parametrize("op", TWINS, ids=lambda op: op.name)
def test_an_operator_makes_its_mess_the_way_the_tenant_did(op):
    folder = LAB / op.twin
    if not folder.exists():
        pytest.skip(f"no twin capture yet: firm/lab/{op.twin} (docs/engineering/lab.md)")
    real = run_capture(folder / "after" / "exports")
    if op.effect == "stops":
        assert op.stop in real.stopped
        return
    before, after = Firm.load(folder / "before" / "exports"), Firm.load(folder / "after" / "exports")
    synthetic, applied, _ = apply(before, (op,))
    assert applied == (op,), f"the operator finds nothing to edit in firm/lab/{op.twin}/before"
    assert mismatches(before, synthetic, after) == []
    problems = violations(Outcome((op,), (), real.verdicts, real.stopped), run_capture(folder / "before" / "exports"))
    if op.known:
        assert problems, f"'{op.name}' no longer gives a false backed on its real capture: clear `known`"
        return
    assert problems == []


def test_the_seed_capture_as_written_gives_the_verdicts_the_harness_sees(seeded):
    if seeded.name != "seed-clean":
        pytest.skip("no seed-clean capture yet (docs/engineering/lab.md)")
    assert run_capture(SEED_CLEAN / "exports") == seeded.outcome


def test_the_powershell_5_1_capture_reads_as_the_powershell_7_one():
    ps51 = LAB / "seed-clean-ps51" / "exports"
    if not ps51.exists():
        pytest.skip("no PowerShell 5.1 capture yet (docs/engineering/lab.md)")
    ps7 = run_capture(SEED_CLEAN / "exports")
    assert ps7.stopped == ""
    assert run_capture(ps51) == ps7
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_fidelity.py -q`
Expected: `ImportError while importing test module`, with `ImportError: cannot import name 'run_capture' from 'messy.compose'`

- [ ] **Step 3: Add `run_capture` to the judge**

In `tests/messy/compose.py`, change `from messy.firm import Firm` to `from messy.firm import Firm, assemble`, and add this function after `run`:

```python
def run_capture(exports: Path) -> Outcome:
    """The check on a capture exactly as its files were written: encoding, byte-order mark and line endings kept."""
    with tempfile.TemporaryDirectory() as tmp:
        return _outcome(assemble(Path(tmp) / "firm", exports), (), ())
```

- [ ] **Step 4: Write the comparison**

Create `tests/messy/fidelity.py`:

```python
"""Whether an operator makes a mess the way the tenant really made it (spec 2026-10-14, Fidelity check).

Each twin capture holds the firm just before the mess (`before/exports`) and just after it (`after/exports`), so
drift between captures taken days apart (a Defender lastSeen, an OS build) is not mistaken for the mess. The operator
is applied to `before` and the change it makes is compared with the change the capture shows: the same number of
records added and removed per export, every field the operator changes also changed in the capture, and added
records with the same fields and JSON types. Values are not compared: IDs, times and addresses differ by nature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from messy.firm import Firm

# The field that identifies a record in each export; a record whose key changes counts as removed and added.
KEYS = {
    "entra_users": "id", "entra_registration": "id", "entra_ca_policies": "id", "entra_security_defaults": "id",
    "entra_role_assignments": "id", "intune_devices": "id", "defender_machines": "id", "veeam_users": "Email",
}


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "array" if isinstance(value, list) else "object"


@dataclass(frozen=True)
class Change:
    added: int
    removed: int
    changed_fields: frozenset[str]
    added_shape: frozenset[tuple[str, str]]  # (field, JSON type) over every added record


def change(before: Firm, after: Firm, reader: str) -> Change:
    key = KEYS[reader]
    old = {str(r.get(key)).lower(): r for r in before.rows(reader)}
    new = {str(r.get(key)).lower(): r for r in after.rows(reader)}
    added = [new[k] for k in new.keys() - old.keys()]
    changed = {f for k in new.keys() & old.keys() for f in set(new[k]) | set(old[k])
               if new[k].get(f) != old[k].get(f)}
    shape = {(f, json_type(v)) for r in added for f, v in r.items()}
    return Change(len(added), len(old.keys() - new.keys()), frozenset(changed), frozenset(shape))


def mismatches(before: Firm, synthetic: Firm, real: Firm) -> list[str]:
    """How the operator's mess (synthetic) differs from the capture's (real), both from `before`; [] when it agrees."""
    problems = []
    for reader in sorted(KEYS):
        if not any(e["reader"] == reader for e in before.manifest):
            continue
        made, seen = change(before, synthetic, reader), change(before, real, reader)
        if (made.added, made.removed) != (seen.added, seen.removed):
            problems.append(f"{reader}: the operator adds {made.added} and removes {made.removed} records; "
                            f"the capture adds {seen.added} and removes {seen.removed}")
        if missing := sorted(made.changed_fields - seen.changed_fields):
            problems.append(f"{reader}: the operator changes {', '.join(missing)}, which the capture does not")
        if made.added and seen.added and made.added_shape != seen.added_shape:
            only_made = sorted(f"{f} ({t})" for f, t in made.added_shape - seen.added_shape)
            only_seen = sorted(f"{f} ({t})" for f, t in seen.added_shape - made.added_shape)
            problems.append(f"{reader}: added records differ; only the operator's have {only_made}, "
                            f"only the capture's have {only_seen}")
    return problems
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_fidelity.py -q`
Expected: `4 passed, 14 skipped`

- [ ] **Step 6: Commit**

```bash
git add tests/messy/fidelity.py tests/messy/compose.py tests/messy/test_fidelity.py
git commit -m "Compare each operator's mess with the tenant's real capture of it, once the captures exist" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Scrubbing, and the guard

**Files:**
- Create: `scripts/scrub_lab_capture.py`
- Test: `tests/test_scrub_lab_capture.py`
- Test: `tests/messy/test_lab_guard.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces, in `scripts.scrub_lab_capture`: `DENY: Path` (`firm/lab/raw/deny.txt`); `LAB_DOMAIN = "harborlab.example"`; `LAB_TENANT_ID`; `decode(raw: bytes) -> tuple[str, str, bytes]` (text, codec, byte-order mark); `Scrubber(tenant_id, admin_name, admin_address, domains=())` with `scrub(text) -> str` and `denied -> list[str]`; `leaks(text, deny=()) -> list[str]`; `read_deny(path=DENY) -> list[str]`; `scrub_capture(raw, out, scrubber, deny_file=DENY) -> list[str]`; `main(argv=None, deny_file=DENY) -> int` (0 written, 1 refused, 2 the output exists).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scrub_lab_capture.py`:

```python
from scripts.scrub_lab_capture import Scrubber, decode, leaks, main

TENANT = "9f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f"
ARGS = ["--tenant-id", TENANT, "--admin-name", "Pat Example", "--admin-address", "pat@example.net"]


def _scrubber():
    return Scrubber(TENANT, "Pat Example", "pat@example.net")


def test_what_names_the_tenant_or_its_owner_is_replaced():
    text = ('{"userPrincipalName": "admin@contosolab.onmicrosoft.com", "mail": "pat@example.net", '
            '"displayName": "Pat Example", "tenantId": "9F1C2D3E-4B5A-4C6D-8E7F-0A1B2C3D4E5F", '
            '"proxy": "contosolab.mail.onmicrosoft.com"}')
    assert _scrubber().scrub(text) == (
        '{"userPrincipalName": "admin@harborlab.example", "mail": "lab.admin@harborlab.example", '
        '"displayName": "Lab Admin", "tenantId": "11111111-1111-4111-8111-111111111111", '
        '"proxy": "harborlab.example"}')


def test_each_address_becomes_one_documentation_address_and_nothing_else_moves():
    scrubber = _scrubber()
    text = ('{"lastIpAddress": "10.0.0.4", "lastExternalIpAddress": "203.45.67.89", "again": "203.45.67.89", '
            '"v6": "2606:4700::1111", "osVersion": "10.0.22631.4317", "lastSeen": "2026-10-01T09:30:00Z", '
            '"time": "09:30:00"}')
    assert scrubber.scrub(text) == (
        '{"lastIpAddress": "192.0.2.1", "lastExternalIpAddress": "192.0.2.2", "again": "192.0.2.2", '
        '"v6": "2001:db8::3", "osVersion": "10.0.22631.4317", "lastSeen": "2026-10-01T09:30:00Z", '
        '"time": "09:30:00"}')


def test_leaks_name_onmicrosoft_public_addresses_and_denied_values():
    assert leaks('{"a": "x.onmicrosoft.com", "b": "8.8.8.8", "c": "10.1.2.3", "d": "192.0.2.7", "e": "Pat"}',
                 ["pat"]) == ["an onmicrosoft.com domain", "public IP address 8.8.8.8", "denied value 'pat'"]


def test_a_capture_keeps_its_encoding_byte_order_mark_and_line_endings(tmp_path):
    raw = tmp_path / "raw"
    (raw / "exports").mkdir(parents=True)
    utf16 = b"\xff\xfe" + '{\r\n  "upn": "a@contosolab.onmicrosoft.com"\r\n}\r\n'.encode("utf-16-le")
    (raw / "exports" / "users.json").write_bytes(utf16)
    (raw / "exports" / "manifest.yaml").write_bytes(b"exports:\n  - {file: users.json}\n")
    deny = tmp_path / "deny.txt"
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=deny) == 0
    written = (tmp_path / "out" / "exports" / "users.json").read_bytes()
    assert written == b"\xff\xfe" + '{\r\n  "upn": "a@harborlab.example"\r\n}\r\n'.encode("utf-16-le")
    assert decode(written)[1:] == ("utf-16-le", b"\xff\xfe")
    assert (tmp_path / "out" / "exports" / "manifest.yaml").read_bytes() == b"exports:\n  - {file: users.json}\n"
    assert deny.read_text(encoding="utf-8").splitlines() == sorted([TENANT, "Pat Example", "pat@example.net"])


def test_a_capture_still_holding_a_denied_value_is_refused_and_removed(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "users.json").write_text('{"note": "an old tenant: oldlab"}', encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("oldlab\n", encoding="utf-8")
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=deny) == 1
    assert not (tmp_path / "out").exists()
    assert "users.json: denied value 'oldlab'" in capsys.readouterr().err


def test_a_file_that_is_not_an_export_is_refused(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "notes.txt").write_text("hello", encoding="utf-8")
    assert main([str(raw), str(tmp_path / "out"), *ARGS], deny_file=tmp_path / "deny.txt") == 1
    assert "notes.txt: not an export or a manifest" in capsys.readouterr().err
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_scrub_lab_capture.py -q`
Expected: `ImportError while importing test module`, with `ModuleNotFoundError: No module named 'scripts.scrub_lab_capture'`

- [ ] **Step 3: Write the scrub script**

Create `scripts/scrub_lab_capture.py`:

```python
#!/usr/bin/env python3
"""Copy a raw lab capture into firm/lab with everything that names the tenant or its owner replaced.

The replacement is made on the text, so each file keeps its encoding, byte-order mark and line endings: they are
part of what a PowerShell 5.1 or 7 capture shows. Replaced: every *.onmicrosoft.com domain and each --domain, the
--tenant-id, the --admin-name and --admin-address, every IPv4 address (to 192.0.2.N), and every JSON string that is
an IPv6 address (to 2001:db8::N). Random object GUIDs are kept: they identify nothing outside the lab.

The values replaced are added to firm/lab/raw/deny.txt, which is gitignored with the rest of raw/ and which the
guard test (tests/messy/test_lab_guard.py) reads. The copy is refused, and removed, if anything in it could still
name the tenant or its owner: an onmicrosoft.com domain, a public IP address, or a value deny.txt lists.

Run from the repo root:
  python scripts/scrub_lab_capture.py firm/lab/raw/seed-clean firm/lab/seed-clean \\
      --tenant-id <tenant GUID> --admin-name "<your name>" --admin-address <your sign-up address>
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DENY = ROOT / "firm" / "lab" / "raw" / "deny.txt"
LAB_DOMAIN = "harborlab.example"
LAB_TENANT_ID = "11111111-1111-4111-8111-111111111111"
CAPTURE_FILES = {".json", ".yaml"}
ONMICROSOFT = re.compile(r"[A-Za-z0-9-]+(?:\.mail)?\.onmicrosoft\.com", re.IGNORECASE)
IPV4 = re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])")
IPV6_STRING = re.compile(r'"([0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7})"')
BOMS = ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"), (b"\xef\xbb\xbf", "utf-8"))


def _ip(value: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def decode(raw: bytes) -> tuple[str, str, bytes]:
    """The text, the codec to write it back with, and the byte-order mark that went before it."""
    for bom, codec in BOMS:
        if raw.startswith(bom):
            return raw[len(bom):].decode(codec), codec, bom
    return raw.decode("utf-8"), "utf-8", b""


class Scrubber:
    """Replaces what names the tenant or its owner; one address always becomes the same documentation address."""

    def __init__(self, tenant_id: str, admin_name: str, admin_address: str, domains: tuple[str, ...] = ()):
        self.replacements = [(admin_address, f"lab.admin@{LAB_DOMAIN}"), (admin_name, "Lab Admin"),
                             (tenant_id, LAB_TENANT_ID), *((d, LAB_DOMAIN) for d in domains)]
        self.addresses: dict[str, str] = {}

    @property
    def denied(self) -> list[str]:
        return [old for old, _ in self.replacements if old]

    def scrub(self, text: str) -> str:
        for old, new in self.replacements:
            if old:
                text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
        text = ONMICROSOFT.sub(LAB_DOMAIN, text)
        text = IPV4.sub(lambda m: self._address(m.group(), "192.0.2.{}"), text)
        return IPV6_STRING.sub(lambda m: '"' + self._address(m.group(1), "2001:db8::{:x}") + '"', text)

    def _address(self, value: str, form: str) -> str:
        if _ip(value) is None:
            return value  # a version number or a time, not an address
        return self.addresses.setdefault(value, form.format(len(self.addresses) % 254 + 1))


def leaks(text: str, deny: list[str] | tuple[str, ...] = ()) -> list[str]:
    """What in this text could name the tenant or its owner."""
    found = ["an onmicrosoft.com domain"] if ONMICROSOFT.search(text) else []
    found += [f"public IP address {v}" for v in IPV4.findall(text) + IPV6_STRING.findall(text)
              if (ip := _ip(v)) is not None and ip.is_global]
    lowered = text.lower()
    return found + [f"denied value {v!r}" for v in deny if v and v.lower() in lowered]


def read_deny(path: Path = DENY) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line] if path.exists() else []


def scrub_capture(raw: Path, out: Path, scrubber: Scrubber, deny_file: Path = DENY) -> list[str]:
    """Write the scrubbed copy of raw to out and record the denied values; the problems, when the copy is refused."""
    deny = sorted(set(read_deny(deny_file)) | set(scrubber.denied))
    deny_file.parent.mkdir(parents=True, exist_ok=True)
    deny_file.write_text("".join(f"{v}\n" for v in deny), encoding="utf-8")
    problems = []
    for src in sorted(p for p in raw.rglob("*") if p.is_file()):
        name = src.relative_to(raw).as_posix()
        if src.suffix.lower() not in CAPTURE_FILES:
            problems.append(f"{name}: not an export or a manifest")
            continue
        text, codec, bom = decode(src.read_bytes())
        clean = scrubber.scrub(text)
        problems += [f"{name}: {leak}" for leak in leaks(clean, deny)]
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(bom + clean.encode(codec))
    if problems:
        shutil.rmtree(out, ignore_errors=True)
    return problems


def main(argv: list[str] | None = None, deny_file: Path = DENY) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("raw", type=Path, help="the raw capture folder, under firm/lab/raw/")
    parser.add_argument("out", type=Path, help="the folder to write, under firm/lab/")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--admin-name", required=True)
    parser.add_argument("--admin-address", required=True)
    parser.add_argument("--domain", action="append", default=[], help="a custom domain the tenant uses")
    args = parser.parse_args(argv)
    if args.out.exists():
        print(f"{args.out} already exists; remove it first", file=sys.stderr)
        return 2
    scrubber = Scrubber(args.tenant_id, args.admin_name, args.admin_address, tuple(args.domain))
    problems = scrub_capture(args.raw, args.out, scrubber, deny_file)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"refused: nothing written to {args.out}", file=sys.stderr)
        return 1
    print(f"scrubbed {args.raw} into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_scrub_lab_capture.py -q`
Expected: `6 passed`

- [ ] **Step 5: Add the guard and ignore the raw captures**

Create `tests/messy/test_lab_guard.py`:

```python
"""Nothing committed under firm/lab names the lab tenant or its owner (spec 2026-10-14, Scrubbing and storage)."""
from messy.firm import LAB
from scripts.scrub_lab_capture import decode, leaks, read_deny


def test_nothing_committed_under_firm_lab_names_the_tenant_or_its_owner():
    deny = read_deny()  # firm/lab/raw/deny.txt, on the machine that took the captures; absent elsewhere
    problems = []
    for path in sorted(LAB.rglob("*")) if LAB.exists() else []:
        relative = path.relative_to(LAB)
        if path.is_file() and relative.parts[0] != "raw":
            problems += [f"{relative.as_posix()}: {leak}" for leak in leaks(decode(path.read_bytes())[0], deny)]
    assert problems == []
```

Append to `.gitignore`:

```text
firm/lab/raw/
```

- [ ] **Step 6: Run the guard**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_lab_guard.py -q`
Expected: `1 passed` (it scans `firm/lab/messy-summary.md`, which names nothing)

- [ ] **Step 7: Commit**

```bash
git add scripts/scrub_lab_capture.py tests/test_scrub_lab_capture.py tests/messy/test_lab_guard.py .gitignore
git commit -m "Scrub lab captures into firm/lab without changing their bytes' form, and guard that nothing committed names the tenant" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: The capture script and the runbook

**Files:**
- Create: `scripts/lab_capture.ps1`
- Create: `docs/engineering/lab.md`
- Modify: `docs/engineering/using.md` (a section on testing against messy firms)
- Modify: `docs/README.md` (link the runbook)

**Interfaces:**
- Produces: `scripts/lab_capture.ps1 -Out <exports folder> -Part Graph|Defender|Veeam [-TenantId] [-AppId] [-Repository]`, which writes the export files and appends one manifest line per export.

- [ ] **Step 1: Write the capture script**

Create `scripts/lab_capture.ps1`. Every command is the one `docs/engineering/exports.md` gives; the Veeam part also writes every property of one user, the evidence for the reader's unconfirmed field names:

```powershell
<#
.SYNOPSIS
Take the lab tenant's exports exactly as docs/engineering/exports.md gives them, into one capture folder.

.DESCRIPTION
One part per run. Run -Part Graph and -Part Defender on the admin machine, in the PowerShell the capture is for
(pwsh for PowerShell 7, powershell.exe for Windows PowerShell 5.1). Run -Part Veeam on the Veeam server, then copy
veeam-users.json, veeam-user-properties.json and the manifest line it prints into the same folder.

Each part appends one manifest line per export to <Out>/manifest.yaml, with exported_at taken after that export
finished, in UTC with a Z (docs/engineering/exports.md, Recording exported_at). The lab procedure is
docs/engineering/lab.md.

.EXAMPLE
pwsh -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean/exports -Part Graph
#>
param(
    [Parameter(Mandatory)] [string] $Out,
    [Parameter(Mandatory)] [ValidateSet('Graph', 'Defender', 'Veeam')] [string] $Part,
    [string] $TenantId,
    [string] $AppId,
    [string] $Repository
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$manifest = Join-Path $Out 'manifest.yaml'
if (-not (Test-Path $manifest)) { Set-Content -Path $manifest -Value 'exports:' -Encoding ascii }

function Add-Entry([string] $File, [string] $Reader) {
    $at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $line = "  - {file: $File, reader: $Reader, exported_at: $at}"
    Add-Content -Path $manifest -Value $line -Encoding ascii
    Write-Output $line
}

function Save-Graph([string] $Uri, [string] $File, [string] $Reader) {
    Invoke-MgGraphRequest -Method GET -Uri $Uri -OutputType Json | Out-File (Join-Path $Out $File) -Encoding utf8
    Add-Entry $File $Reader
}

if ($Part -eq 'Graph') {
    Connect-MgGraph -NoWelcome -Scopes 'User.Read.All', 'AuditLog.Read.All', 'Policy.Read.All',
        'RoleManagement.Read.Directory', 'DeviceManagementManagedDevices.Read.All'
    Save-Graph 'v1.0/users?$select=id,userPrincipalName,displayName,accountEnabled,userType&$top=999' `
        'users.json' 'entra_users'
    Save-Graph 'v1.0/reports/authenticationMethods/userRegistrationDetails' 'registration.json' 'entra_registration'
    Save-Graph 'v1.0/identity/conditionalAccess/policies' 'ca-policies.json' 'entra_ca_policies'
    Save-Graph 'v1.0/policies/identitySecurityDefaultsEnforcementPolicy' 'security-defaults.json' `
        'entra_security_defaults'
    Save-Graph 'v1.0/roleManagement/directory/roleAssignments?$expand=principal' 'role-assignments.json' `
        'entra_role_assignments'
    Save-Graph ('v1.0/deviceManagement/managedDevices?$select=id,deviceName,azureADDeviceId,operatingSystem,' +
        'userPrincipalName') 'intune-devices.json' 'intune_devices'
}

if ($Part -eq 'Defender') {
    if (-not $TenantId -or -not $AppId) { throw '-Part Defender needs -TenantId and -AppId' }
    $secret = Read-Host -AsSecureString 'Client secret of the lab app registration'
    $plain = [System.Net.NetworkCredential]::new('', $secret).Password
    $token = (Invoke-RestMethod -Method Post -Uri "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token" `
        -Body @{ client_id = $AppId; client_secret = $plain; grant_type = 'client_credentials'
                 scope = 'https://api.securitycenter.microsoft.com/.default' }).access_token
    Invoke-RestMethod -Uri 'https://api.security.microsoft.com/api/machines' `
        -Headers @{ Authorization = "Bearer $token" } |
        ConvertTo-Json -Depth 6 | Out-File (Join-Path $Out 'defender-machines.json') -Encoding utf8
    Add-Entry 'defender-machines.json' 'defender_machines'
}

if ($Part -eq 'Veeam') {
    if (-not $Repository) { throw '-Part Veeam needs -Repository' }
    $repo = Get-VBORepository -Name $Repository
    Get-VBOEntityData -Type User -Repository $repo |
        Select-Object Email, DisplayName, IsMailboxBackedUp,
            @{ Name = 'MailboxBackedUpTime'; Expression = {
                if ($_.MailboxBackedUpTime) { $_.MailboxBackedUpTime.ToUniversalTime().ToString('o') } } } |
        ConvertTo-Json | Out-File (Join-Path $Out 'veeam-users.json') -Encoding utf8
    Add-Entry 'veeam-users.json' 'veeam_users'
    # Every property of one user as Veeam names them: the evidence for the reader's unconfirmed field names.
    Get-VBOEntityData -Type User -Repository $repo | Select-Object -First 1 -Property * |
        ConvertTo-Json -Depth 3 | Out-File (Join-Path $Out 'veeam-user-properties.json') -Encoding utf8
}
```

- [ ] **Step 2: Check that it parses in Windows PowerShell 5.1 and in PowerShell 7**

Run, in `powershell` and again in `pwsh` (where installed):

```powershell
$tokens = $null; $errors = $null; [System.Management.Automation.Language.Parser]::ParseFile("$PWD\scripts\lab_capture.ps1", [ref]$tokens, [ref]$errors) | Out-Null; if ($errors) { $errors } else { 'no parse errors' }
```

Expected: `no parse errors`

- [ ] **Step 3: Write the runbook**

Create `docs/engineering/lab.md`:

````markdown
# The lab tenant

The lab is a small Microsoft 365 tenant we control, set up as a clean firm, captured, then made messy one mess at a
time and captured again. Its captures are the seed and the twins of the messy-firm tests (`tests/messy/`). The design
is in [the spec](../superpowers/specs/2026-10-14-messy-firm-testing-design.md).

Nothing here is ever done in a client's tenant. Every step below is done by a person, in the lab tenant, from this
machine or the lab's Azure VMs.

## Cost and clock

- **Microsoft 365 Business Premium trial.** It is the stack the target firms run. Confirm the trial's length, whether
  it needs a card, and when billing starts at sign-up, and note them in the spec's open questions.
- **Azure.** A subscription in the same tenant pays for the VMs. Deallocate every VM when you are not using it.
- **The clock.** All of this happens inside the trial. [Teardown](#6-teardown) cancels everything before billing.

## Before you start, on this machine

- PowerShell 7 beside Windows PowerShell 5.1: `winget install --id Microsoft.PowerShell --source winget`
- The Graph module, once in each shell (`pwsh` and `powershell`):
  `Install-Module Microsoft.Graph.Authentication -Scope CurrentUser`
- The Python environment from [using.md](using.md).

Windows PowerShell may refuse to run scripts. Every command below passes `-ExecutionPolicy Bypass`, which applies to
that one process only.

## 1. The tenant

1. Sign up for the Business Premium trial with a new tenant. Record its tenant ID (Entra admin center, Overview). The
   account you sign up with is the first member and holds Global Administrator. Register MFA for it before step 7.
2. Connect for setup, in `pwsh`:

   ```powershell
   Connect-MgGraph -Scopes 'User.ReadWrite.All', 'Directory.ReadWrite.All', 'RoleManagement.ReadWrite.Directory',
       'Policy.ReadWrite.ConditionalAccess', 'Policy.Read.All', 'UserAuthenticationMethod.ReadWrite.All'
   function Send-Graph($Method, $Uri, $Body) {
       Invoke-MgGraphRequest -Method $Method -Uri $Uri -Body ($Body | ConvertTo-Json -Depth 8) -ContentType 'application/json'
   }
   ```

3. Turn security defaults off:

   ```powershell
   Send-Graph PATCH 'v1.0/policies/identitySecurityDefaultsEnforcementPolicy' @{ isEnabled = $false }
   ```

4. Create eight more members and a former employee, each licensed. With you, that is nine members and ten mailboxes,
   the most Veeam Community Edition backs up. The passwords are random and never kept: no one signs in as these
   accounts.

   ```powershell
   $domain = ((Invoke-MgGraphRequest GET 'v1.0/domains').value | Where-Object isDefault).id
   $sku = ((Invoke-MgGraphRequest GET 'v1.0/subscribedSkus').value | Where-Object skuPartNumber -eq 'SPB').skuId
   $names = 'Avery Lane', 'Blake Moss', 'Casey Hart', 'Drew Ellis', 'Emery Stone', 'Finley Park', 'Gray Holt',
       'Harper Quinn', 'Former Employee'
   $made = @{}
   foreach ($name in $names) {
       $nick = $name.ToLower().Replace(' ', '.')
       $user = Send-Graph POST 'v1.0/users' @{
           accountEnabled = $true; displayName = $name; mailNickname = $nick.Replace('.', '')
           userPrincipalName = "$nick@$domain"; usageLocation = 'US'
           passwordProfile = @{ forceChangePasswordAtNextSignIn = $true; password = "$([guid]::NewGuid())Aa1!" } }
       Send-Graph POST "v1.0/users/$($user.id)/assignLicense" @{ addLicenses = @(@{ skuId = $sku }); removeLicenses = @() }
       $made[$name] = $user.id
   }
   ```

5. Disable the former employee (the mailbox stays while the license does), and make Avery Lane an Exchange
   Administrator:

   ```powershell
   Send-Graph PATCH "v1.0/users/$($made['Former Employee'])" @{ accountEnabled = $false }
   Send-Graph POST 'v1.0/roleManagement/directory/roleAssignments' @{
       principalId = $made['Avery Lane']; roleDefinitionId = '29232cdf-9323-42fd-ade2-1d097af3e4de'; directoryScopeId = '/' }
   ```

6. A shared mailbox and a guest. Create the shared mailbox "Front Office" in the Exchange admin center (Recipients,
   Mailboxes, Add a shared mailbox); it appears in Entra as a disabled user. Invite the guest without sending mail
   (`example.com` delivers nothing):

   ```powershell
   Send-Graph POST 'v1.0/invitations' @{ invitedUserEmailAddress = 'auditor@example.com'
       inviteRedirectUrl = 'https://myapps.microsoft.com'; sendInvitationMessage = $false }
   ```

7. Register every member for MFA with a phone method. The numbers are in the fictional 555-0100 to 555-0199 range.
   Your own account may refuse a second phone; that is fine, it is registered already.

   ```powershell
   $n = 100
   $users = (Invoke-MgGraphRequest GET 'v1.0/users?$select=id,accountEnabled,userType').value
   foreach ($u in $users | Where-Object { $_.accountEnabled -and $_.userType -eq 'Member' }) {
       $n++
       try { Send-Graph POST "v1.0/users/$($u.id)/authentication/phoneMethods" @{
           phoneNumber = "+1 2065550$n"; phoneType = 'mobile' } } catch { Write-Warning $_ }
   }
   ```

8. The Conditional Access policies a clean firm has:

   ```powershell
   $ga = '62e90394-69f5-4237-9190-012177145e10'; $exchange = '29232cdf-9323-42fd-ade2-1d097af3e4de'
   $everyone = @{ includeUsers = @('All') }; $admins = @{ includeRoles = @($ga, $exchange) }
   $policies = @(
       @{ name = 'Require MFA for all users'; users = $everyone; clients = @('all'); grant = @('mfa') },
       @{ name = 'Require MFA for administrators'; users = $admins; clients = @('all'); grant = @('mfa') },
       @{ name = 'Block legacy authentication'; users = $everyone; clients = @('exchangeActiveSync', 'other')
          grant = @('block') })
   foreach ($p in $policies) {
       Send-Graph POST 'v1.0/identity/conditionalAccess/policies' @{ displayName = $p.name; state = 'enabled'
           conditions = @{ users = $p.users; applications = @{ includeApplications = @('All') }
                           clientAppTypes = $p.clients }
           grantControls = @{ operator = 'OR'; builtInControls = $p.grant } }
   }
   ```

   Microsoft may also have created its own managed policies in the tenant. Leave them: they are real noise.

## 2. Machines in Azure

1. Create an Azure subscription in this tenant (portal.azure.com, signed in as the tenant's admin), and one resource
   group, `attest-lab`, for everything below.
2. Intune automatic enrollment: Intune admin center, Devices, Windows, Enrollment, Automatic Enrollment: MDM user
   scope All.
3. **Before you build the endpoints**, settle the spec's open question on Windows 11 in Azure: the image asks you to
   confirm a license with multi-tenant hosting rights. If Business Premium seats do not carry it, build the endpoints
   from a Windows Server image instead, and note that in the spec.
4. Three endpoints, `lab-lt-01` to `lab-lt-03`: Windows 11 Enterprise, size Standard_B2s, in `attest-lab`. On the
   Management tab, turn on "Login with Microsoft Entra ID" and "Enroll the VM with Intune". Within an hour each should
   appear in Intune (Devices, Windows) with an Entra device ID.
5. Onboard them to Defender for Business through Intune:
   - Defender portal, Settings, Endpoints, Advanced features: Microsoft Intune connection On.
   - Intune admin center, Endpoint security, Microsoft Defender for Endpoint: connect Windows devices On.
   - Intune admin center, Endpoint security, Endpoint detection and response: a policy for Windows with the package
     type "Auto from connector", assigned to all devices.

   Within a day each VM should show in the Defender portal (Assets, Devices) as Onboarded and Active. If the policy
   does not take, onboard with the local script instead (Defender portal, Settings, Endpoints, Onboarding).
6. The Veeam server, `lab-veeam`: Windows Server 2022 Datacenter, Standard_D8s_v5 (Veeam's documented minimum is 8
   cores and 16 GB), a 128 GB data disk. Not Entra-joined, not enrolled, not onboarded: it is outside the firm's
   population. On it:
   - Install Veeam Backup for Microsoft 365 (from veeam.com). With no license installed it runs as the Community
     Edition, for up to 10 users.
   - Add the organization: Microsoft 365, modern app-only authentication, and let Veeam register a new Entra
     application (sign in as Global Administrator when it asks).
   - Add a repository on the data disk, and record its name.
   - A backup job: the entire organization, mailboxes and archives, daily at 02:00. Run it once now.
   - Confirm the job backed up ten users and the shared mailbox. If Veeam counts the shared mailbox against its ten,
     remove the license from the former employee, so it becomes a disabled account without a mailbox.
7. An app registration for the Defender API: Entra admin center, App registrations, New, `attest-lab-export`. API
   permissions: APIs my organization uses, WindowsDefenderATP, Application permissions, Machine.Read.All; grant admin
   consent. Certificates & secrets: a client secret that expires before the trial ends. Record the app ID. The secret
   is typed at each capture and stored nowhere.

## 3. Capturing seed-clean

Wait a day after the last change, so the registration report and Defender's `lastSeen` have caught up. Then take the
same capture from both shells, minutes apart:

```powershell
pwsh -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean/exports -Part Graph
pwsh -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean/exports -Part Defender -TenantId <tenant ID> -AppId <app ID>
powershell -ExecutionPolicy Bypass -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean-ps51/exports -Part Graph
powershell -ExecutionPolicy Bypass -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean-ps51/exports -Part Defender -TenantId <tenant ID> -AppId <app ID>
```

On `lab-veeam`, with a copy of `scripts/lab_capture.ps1`:

```powershell
powershell -ExecutionPolicy Bypass -File lab_capture.ps1 -Out C:\capture\exports -Part Veeam -Repository '<repository>'
```

Copy `veeam-users.json` and `veeam-user-properties.json` into both `firm/lab/raw/seed-clean/exports/` and
`firm/lab/raw/seed-clean-ps51/exports/`, and add the manifest line it printed to both `manifest.yaml` files.

**Confirm the Veeam fields.** `veeam-user-properties.json` lists every property of one user as Veeam names them.
Check that `Email`, `IsMailboxBackedUp` and `MailboxBackedUpTime` are among them, and that each `Email` in
`veeam-users.json` is the account's UPN. Write what you found into `exports.md` (Veeam section) and `using.md` (Known
limitations). This settles the strategy register's next step 1.

Scrub both captures into `firm/lab/` (the values you pass are added to the gitignored `firm/lab/raw/deny.txt`):

```bash
venv/Scripts/python.exe scripts/scrub_lab_capture.py firm/lab/raw/seed-clean firm/lab/seed-clean --tenant-id <tenant ID> --admin-name "<your display name>" --admin-address <the address you signed up with>
venv/Scripts/python.exe scripts/scrub_lab_capture.py firm/lab/raw/seed-clean-ps51 firm/lab/seed-clean-ps51 --tenant-id <tenant ID> --admin-name "<your display name>" --admin-address <the address you signed up with>
```

Once `firm/lab/seed-clean/exports/manifest.yaml` exists, the messy-firm tests use it as their seed.

## 4. The twins

Each twin is two captures: `before`, then the mess, then `after`. Capture `before` with all three parts into
`firm/lab/raw/<twin>/before/exports`, make the mess, wait as long as the table says, capture `after` into
`firm/lab/raw/<twin>/after/exports`, then undo the mess. Scrub `firm/lab/raw/<twin>` into `firm/lab/<twin>` with the
same arguments as above. One mess at a time: a twin whose `after` shows two messes cannot be compared with either
operator.

| Twin | Operator | Make the mess | Wait | Undo |
|---|---|---|---|---|
| `real-messy-break-glass` | break-glass accounts excluded | Two unlicensed accounts `break.glass1`, `break.glass2` with Global Administrator and a phone method each; add both IDs to `excludeUsers` of every policy | 1 day (registration) | Delete both, remove the exclusions |
| `real-messy-exclusion-group` | MFA exclusions group | A security group "MFA exclusions" with one member, in `excludeGroups` of the all-users policy | none | Remove the exclusion, delete the group |
| `real-messy-new-user` | user created after the registration report | A licensed member; capture `after` within the hour, before the report refreshes and before the next backup | none | Delete the user |
| `real-messy-reimaged` | laptop re-imaged | Reset `lab-lt-01` (Settings, System, Recovery, Reset this PC, Remove everything) and let it re-join, re-enroll and re-onboard; retire its old Intune record | 1 to 2 days | None: the re-imaged laptop is the new normal |
| `real-messy-vm-off` | VM off for 8 days | Deallocate `lab-lt-02` | 8 days | Start it |
| `real-messy-sensor-cut` | sensor cut off | A network security group rule on `lab-lt-03` that denies outbound traffic to the Internet service tag | 1 day | Remove the rule |
| `real-messy-discovered` | discovered unmanaged PC | An Ubuntu VM in the same virtual network, never onboarded; Defender's device discovery may find it | 1 to 2 days | Delete the VM |
| `real-messy-renamed` | device renamed after onboarding | `Rename-Computer -NewName lab-lt-03b -Restart` on `lab-lt-03` | 1 day | Rename it back |
| `real-messy-over-limit` | 11th user over the Veeam limit | An 11th licensed mailbox user; let the nightly job run | 1 day | Delete the user |
| `real-messy-paused` | backup job paused for 2 days | Disable the backup job | 2 days | Enable it |
| `real-messy-shared-mailbox` | shared mailbox Veeam never saw | A second shared mailbox "Front Desk", excluded from the backup job | 1 day | Delete it |
| `real-messy-paged` | users export is one page of several | No change in the tenant: copy `before` to `after`, then replace `after`'s `users.json` with the command below | none | none |

The paged users export, in `pwsh`, signed in with the scopes `scripts/lab_capture.ps1 -Part Graph` uses:

```powershell
Invoke-MgGraphRequest -Method GET -Uri 'v1.0/users?$select=id,userPrincipalName,displayName,accountEnabled,userType&$top=5' `
    -OutputType Json | Out-File firm/lab/raw/real-messy-paged/after/exports/users.json -Encoding utf8
```

What the twins can show that the operators guess:

- **The sensor cut.** The health status Defender reports for a sensor that cannot reach it may not be
  `ImpairedCommunication`. The fidelity check compares which fields change, not their values, and any status but
  Active is a gap.
- **Discovery.** It may find nothing in an Azure network. Then there is no `real-messy-discovered`, and the operator
  stays without a twin.
- **A nameless device.** If a discovered device comes back with a null `computerDnsName`, the reader stops the run.
  The "discovered device with no DNS name" operator keeps that refusal for now (`may_stop`); a real capture showing it
  is the prompt to decide whether the reader should read such a device instead.

## 5. When a capture disagrees

- **A run stops on a capture.** Decide, case by case, whether the reader is too strict for what the API really writes,
  or whether the refusal stays and `exports.md` changes the export so the firm avoids it.
- **A fidelity mismatch.** Fix the operator so it makes the mess the way the tenant did. Never edit the capture.
- **A false backed.** Fix the rule in its own change, with the operator as the regression test.

## 6. Teardown

1. Delete the `attest-lab` resource group. Cancel the Azure subscription if it was made for the lab.
2. Delete the `attest-lab-export` app registration.
3. Microsoft 365 admin center, Billing, Your products: cancel the Business Premium trial before it bills.
4. Keep `firm/lab/raw/deny.txt` so the guard test can keep checking for the tenant's names; delete the rest of
   `firm/lab/raw/`.
````

- [ ] **Step 4: Say how to run the messy-firm tests**

In `docs/engineering/using.md`, insert before `## Known limitations`:

```markdown
## Testing against messy firms

`tests/messy/` runs the check on a seed firm made messy by operators, alone
and in seeded combinations, and judges each run: no scope an operator breaks
comes out backed, serialization alone changes no verdict, every refusal the
docs promise happens, and no run stops on data nobody decided to refuse
(design: `../superpowers/specs/2026-10-14-messy-firm-testing-design.md`). The
seed is the lab's clean capture, `firm/lab/seed-clean`, once it is committed,
and the dev firm healed of its planted gaps until then. The default run
includes 200 combinations. The long run, 5,000 combinations, writes
`firm/lab/messy-summary.md`:

    venv/Scripts/python.exe -m pytest -m messy

How the lab tenant is built and captured: `lab.md`.
```

In `docs/README.md`, under the engineering register's links, add after `  - [Architecture of the check](engineering/architecture.md)`:

```markdown
  - [The lab tenant](engineering/lab.md)
```

- [ ] **Step 5: Run the whole suite**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: every test passes except the two Python 3.14 NUL-path tests; `16 skipped` or more (the twin and capture tests, and the two symlink tests), `1 deselected`, `1 xfailed`.

- [ ] **Step 6: Commit**

```bash
git add scripts/lab_capture.ps1 docs/engineering/lab.md docs/engineering/using.md docs/README.md
git commit -m "Add the lab runbook and the capture script that takes its exports as exports.md gives them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13 (by hand): Build the lab and capture seed-clean

A person does this in the lab tenant and the Azure portal. It needs the trial and an Azure subscription, and about two days of elapsed time.

**Files:**
- Create: `firm/lab/seed-clean/exports/*`, `firm/lab/seed-clean-ps51/exports/*` (scrubbed)
- Create: `tests/messy/archetypes/seed-clean/*.yaml`
- Modify: `docs/engineering/exports.md` and `docs/engineering/using.md` (the Veeam fields, confirmed)
- Modify: `docs/superpowers/specs/2026-10-14-messy-firm-testing-design.md` (answers to the open questions)
- Possibly modify: operators' `alone`, `may_stop` or `known` (see Step 4)

- [ ] **Step 1: Build the lab**

Follow `docs/engineering/lab.md`, sections 1 and 2. Record in the spec's "Open questions": the trial's terms, whether Business Premium seats carry Windows 11 on Azure, and whether Defender's machine list answers for Defender for Business (it does if Step 2's Defender part returns machines).

- [ ] **Step 2: Capture, confirm and scrub seed-clean**

Follow `docs/engineering/lab.md`, section 3. Write the Veeam field names and whether `Email` is the UPN into `exports.md` (Veeam section) and `using.md` (Known limitations), replacing "confirm them ... on the first real export".

- [ ] **Step 3: Run the suite on the new seed**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: the seed is now `seed-clean`. `test_the_seed_capture_as_written_gives_the_verdicts_the_harness_sees` and `test_the_powershell_5_1_capture_reads_as_the_powershell_7_one` now run. The four archetype tests fail with `hand-check the <name> archetype on the seed-clean seed`. Any other failure is a finding for Step 4.

- [ ] **Step 4: Settle every finding**

For each failure, decide and record why:
- **`test_the_seed_is_backed_wherever_a_scope_can_be_proven` fails.** Read the verdict's reason with `attest check` (Step 5's command, with no operator named). If the tenant is not yet clean, fix the tenant and recapture. If a reader stops on real data, decide as `lab.md` section 5 says.
- **An operator alone gives other statuses than its `alone`.**
  - A "holds" operator: update `alone` to the new behaviour, and say why in the commit.
  - A "breaks" operator that comes out backed: a false backed. Set `known` with the reason, and propose the rule fix as its own change.
  - A "breaks" operator that comes out with another non-backed status: update `alone`.
- **An operator skipped on seed-clean** (for example, the admin-portals policy when the tenant already has it): leave it. It shows as skipped.
- **`test_the_powershell_5_1_capture_reads_as_the_powershell_7_one` fails:** a serialization difference the readers mishandle. Decide as `lab.md` section 5 says.

- [ ] **Step 5: Hand-check the four archetypes on seed-clean**

For each archetype, write the firm and read every verdict's reason:

```bash
venv/Scripts/python.exe -c "import sys; sys.path[:0] = ['.', 'tests']; from pathlib import Path; from messy.catalog import BY_NAME; from messy.compose import apply; from messy.firm import seed; firm, applied, skipped = apply(seed()[1], [BY_NAME[n] for n in sys.argv[1:]]); print('skipped:', [op.name for op in skipped]); firm.write(Path('firm/lab/raw/archetype'))" "break-glass accounts excluded" "microsoft-managed admin-portals policy" "grant through an authentication strength" "admin role held by a service principal"
venv/Scripts/python.exe -m attest check firm/lab/raw/archetype
```

Check each verdict in `firm/lab/raw/archetype/report.md` against what the operators did, then write `tests/messy/archetypes/seed-clean/<name>.yaml` in the format of `tests/messy/archetypes/dev/`, with a comment saying what each operator touched. Delete `firm/lab/raw/archetype` before the next. Run `venv/Scripts/python.exe -m pytest tests/messy/test_archetypes.py -q` until it reports `4 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: every test passes except the two Python 3.14 NUL-path tests, and the guard test passes (nothing under `firm/lab/` names the tenant or its owner).

- [ ] **Step 7: Commit**

```bash
git add firm/lab/seed-clean firm/lab/seed-clean-ps51 tests/messy docs/engineering/exports.md docs/engineering/using.md docs/superpowers/specs/2026-10-14-messy-firm-testing-design.md
git commit -m "Seed the messy-firm tests from the lab tenant's clean capture, and confirm the Veeam fields against it" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14 (by hand): The twins

**Files:**
- Create: `firm/lab/real-messy-*/before/exports/*` and `after/exports/*` (scrubbed)
- Possibly modify: the operators the twins correct

- [ ] **Step 1: Capture the twins, one mess at a time**

Follow `docs/engineering/lab.md`, section 4, for each twin in its table. The VM that is off for 8 days and the paused job take days: start them first, and capture the others meanwhile.

- [ ] **Step 2: Run the fidelity tests after each twin is scrubbed**

Run: `venv/Scripts/python.exe -m pytest tests/messy/test_fidelity.py -q`
Expected: the twin's test runs instead of skipping. A mismatch names the export and what differs. Fix the operator so that it makes the mess the way the tenant did, never the capture, and rerun `tests/messy/test_operators.py`: an operator that changed may need its `alone` updated, which Task 13 Step 4 says how to judge. For `shared mailbox Veeam never saw`, the test passes while the capture still shows the false backed.

- [ ] **Step 3: Run the whole suite**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: every test passes except the two Python 3.14 NUL-path tests.

- [ ] **Step 4: Commit**

```bash
git add firm/lab tests/messy
git commit -m "Capture the lab's real messes and calibrate the operators against them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: The long run on seed-clean, and the register

**Files:**
- Modify: `firm/lab/messy-summary.md` (regenerated)
- Modify: `docs/engineering/README.md` (measured state)
- Modify: `docs/superpowers/specs/2026-10-14-messy-firm-testing-design.md` (status)

- [ ] **Step 1: Run the long run**

Run: `venv/Scripts/python.exe -m pytest -m messy tests/messy -q`
Expected: `1 passed` after about 5 minutes, and `firm/lab/messy-summary.md` now reads `on the seed-clean seed` with `- Property violations: 0`. If it reports violations, each is a false backed, a changed inert verdict or an undecided stop, with its smallest failing set: settle each as Task 13 Step 4 says before going on.

- [ ] **Step 2: Record the measurement in the engineering register**

In `docs/engineering/README.md`, section 3.4, after the `**Measured state (2026-10-05):**` list, add a dated list. Take every number from `firm/lab/messy-summary.md` and from the last full run of the suite:

```markdown
**Messy firms (<date of the summary>):**

- <N> automated tests pass, run against the lab tenant's clean capture (`firm/lab/seed-clean`).
- 5,000 combinations of one to four kinds of real-world mess, from `tests/messy/catalog.py`, give **no false "backed"**, no changed verdict from serialization alone, and no undecided stop. The summary is `firm/lab/messy-summary.md`.
- One false "backed" is known and not yet fixed: a shared mailbox the backup job never covered (`using.md`, Known limitations).
- The costliest realistic mess, in false gaps: <the three "holds" operators with the most degraded runs, from the summary>.
```

- [ ] **Step 3: Mark the spec as built**

In the spec, change `**Status:**` to `Built; seeded from the lab tenant (<date>)`.

- [ ] **Step 4: Commit**

```bash
git add firm/lab/messy-summary.md docs/engineering/README.md docs/superpowers/specs/2026-10-14-messy-firm-testing-design.md
git commit -m "Run 5,000 combinations of mess on the lab's clean capture, and record the measurement" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16 (by hand): Teardown

- [ ] **Step 1: Tear the lab down before any billing**

Follow `docs/engineering/lab.md`, section 6. Keep `firm/lab/raw/deny.txt`.

- [ ] **Step 2: Confirm the repository still passes without the raw captures**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: the same result as Task 15's last run. Nothing in the suite reads `firm/lab/raw/` except the guard's `deny.txt`.
