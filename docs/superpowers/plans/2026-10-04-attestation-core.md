# Attestation Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic core of the attestation check: given hand-confirmed tags on a firm's insurance application and WISP, and the firm's Microsoft 365 and Veeam API exports, report each attestation as **backed**, **gap** or **unchecked**, with the export rows cited, and never **backed** without proof that covers the whole attested scope.

**Architecture:** One reader per export format turns API JSON into frozen dataclasses (every record keeps a `file:row` cite). A manifest names which reader parses each file and when it was exported. A profile maps each control's scope to a proof rule. Rules are pure functions of the loaded evidence; populations always come from a source independent of the evidence. A CLI runs every tag through its rule and writes a Markdown report.

**Tech Stack:** Python 3.12, PyYAML, pytest. No network, no model, no GIN import.

**Spec:** `docs/superpowers/specs/2026-10-04-attestation-core-design.md`

**Planning dry run (2026-10-04):** every file this plan creates was extracted into a scratch copy and run as written. The generator wrote the dev firm, the full suite gave `150 passed` with each task's count as stated below, and the CLI printed `backed 2, gap 6, unchecked 4` for `firm/dev`. If a step's actual output differs from its stated expectation, the transcription has drifted from the plan: compare against the plan text before changing any test.

## Global Constraints

- Repo: `C:\Users\krist\Projects\attest`, branch `main`, local only. Never push and never add a remote.
- Python: `venv/Scripts/python.exe` (the venv is created from `py -3.12` in Task 1). Run every command from the repo root with the Bash tool.
- Third-party dependencies: PyYAML only, plus pytest for tests. Nothing else.
- No network access, no model calls, no import from GIN.
- LF line endings everywhere (`.gitattributes` from Task 1).
- Verdict statuses are exactly `"backed"`, `"gap"`, `"unchecked"`.
- Never report **backed** without proof computed from an export that covers the whole attested scope. Missing evidence → **unchecked**. Evidence showing a failure → **gap**. An empty population → **unchecked**.
- A population never comes from the export that supplies the evidence for the same verdict.
- Thresholds: an EDR device is stale when last seen more than 7 days before the Defender export's `exported_at`; a mailbox backup is stale when more than 24 hours before the Veeam export's `exported_at`.
- An input problem (bad tag, missing field, unknown reader) raises `AttestError` with the file and row or tag named; it is never guessed around.
- Commit messages: one plain imperative sentence as the subject, an optional body, and the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## File Structure

| File | Responsibility |
|---|---|
| `.gitattributes`, `.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`, `requirements.txt` | Repo setup |
| `attest/model.py` | `AttestError`, `Tag`, `Export[T]`, `Verdict` |
| `attest/readers/_json.py` | Loading API JSON and required fields, loudly |
| `attest/readers/entra_users.py`, `entra_registration.py`, `entra_security_defaults.py`, `entra_role_assignments.py`, `entra_ca_policies.py`, `intune_devices.py`, `defender_machines.py`, `veeam_users.py` | One reader per export format |
| `attest/readers/__init__.py` | `READERS`: reader name → read function |
| `attest/evidence.py` | `Evidence` (one field per reader) and `load_evidence` from the manifest |
| `profile/controls.yaml`, `attest/profile.py` | Control → scope → rule name |
| `attest/tags.py` | Load confirmed tags and ground each quote in its document |
| `attest/rules/common.py` | Account population, `unchecked`, `never` |
| `attest/rules/mfa.py`, `edr.py`, `backup.py` | Proof rules, one module per control |
| `attest/rules/__init__.py` | `RULES`: rule name → rule |
| `attest/compare.py`, `attest/report.py`, `attest/__main__.py` | Run tags through rules, render, CLI |
| `docs/exports.md` | How the firm produces each export |
| `scripts/build_dev_firm.py`, `firm/dev/...` | The made-up dev firm and its planted truth |
| `tests/...` | One test file per unit; `tests/builders.py` and `tests/conftest.py` hold shared helpers |

---

### Task 1: Repo setup, shared types and JSON helpers

**Files:**
- Create: `.gitattributes`, `.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`, `requirements.txt`
- Create: `attest/__init__.py`, `attest/model.py`, `attest/readers/__init__.py`, `attest/readers/_json.py`
- Test: `tests/test_json_helpers.py`

**Interfaces:**
- Produces:
  - `attest.model.AttestError(Exception)`
  - `attest.model.Tag(id: str, doc: str, quote: str, control: str, scope: str)` (frozen dataclass)
  - `attest.model.Export(file: str, exported_at: datetime, items: tuple[T, ...])` (frozen, generic)
  - `attest.model.Verdict(status, reason, entities=(), cited=(), population=None)` (frozen)
  - `attest.readers._json.load_records(path: Path) -> list[dict]`
  - `attest.readers._json.require(record, key, file, row) -> Any`, `require_str(...) -> str`, `require_bool(...) -> bool`
  - `attest.readers._json.parse_time(value, file, row, key) -> datetime` (always UTC-aware)

- [ ] **Step 1: Create the venv and repo files**

Run: `py -3.12 -m venv venv`

Create `.gitattributes`:

```
* text=auto eol=lf
```

Create `.gitignore`:

```
venv/
__pycache__/
.pytest_cache/
firm/*/report.md
```

Create `LICENSE`:

```
Copyright (c) 2026 Kristian Krattiger. All rights reserved.

This software is proprietary and confidential. No license to use, copy,
modify or distribute it is granted.
```

Create `requirements.txt`:

```
PyYAML>=6.0
pytest>=8.0
```

Create `pyproject.toml`:

```toml
[project]
name = "attest"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["PyYAML>=6.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create `README.md`:

```markdown
# attest

Checks a firm's insurance application and written information security plan
(WISP) against what its Microsoft 365 and Veeam exports show. Each attestation
comes out **backed**, **gap** or **unchecked**, with the export rows cited.

    py -3.12 -m venv venv
    venv/Scripts/python.exe -m pip install -r requirements.txt
    venv/Scripts/python.exe -m pytest
    venv/Scripts/python.exe -m attest check firm/dev

Design: `docs/superpowers/specs/2026-10-04-attestation-core-design.md`.
How the firm produces each export: `docs/exports.md`.
```

Create `attest/__init__.py`:

```python
"""attest: check a firm's security attestations against its system exports."""
```

Create `attest/readers/__init__.py`:

```python
"""One reader per export format; the READERS registry arrives with the readers (Task 5)."""
```

Run: `venv/Scripts/python.exe -m pip install -r requirements.txt`
Expected: ends with `Successfully installed ...` naming PyYAML and pytest (or "Requirement already satisfied").

- [ ] **Step 2: Write the failing tests**

Create `tests/test_json_helpers.py`:

```python
import json
from datetime import datetime, timezone

import pytest

from attest.model import AttestError
from attest.readers._json import load_records, parse_time, require, require_bool, require_str


def _write(tmp_path, data, encoding="utf-8"):
    path = tmp_path / "export.json"
    path.write_text(json.dumps(data), encoding=encoding)
    return path


def test_a_graph_page_yields_its_value_list(tmp_path):
    path = _write(tmp_path, {"@odata.context": "x", "value": [{"id": "1"}, {"id": "2"}]})
    assert load_records(path) == [{"id": "1"}, {"id": "2"}]


def test_a_bare_list_and_a_single_object_are_both_records(tmp_path):
    assert load_records(_write(tmp_path, [{"id": "1"}])) == [{"id": "1"}]
    assert load_records(_write(tmp_path, {"isEnabled": False})) == [{"isEnabled": False}]


def test_a_utf16_file_from_windows_powershell_is_read(tmp_path):
    path = _write(tmp_path, [{"Email": "a@x.example"}], encoding="utf-16")
    assert load_records(path) == [{"Email": "a@x.example"}]


def test_a_utf8_bom_is_ignored(tmp_path):
    path = _write(tmp_path, [{"id": "1"}], encoding="utf-8-sig")
    assert load_records(path) == [{"id": "1"}]


def test_one_page_of_several_stops_the_run(tmp_path):
    path = _write(tmp_path, {"value": [{"id": "1"}], "@odata.nextLink": "https://graph.microsoft.com/next"})
    with pytest.raises(AttestError, match="one page of several"):
        load_records(path)


def test_invalid_json_stops_the_run_naming_the_file(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(AttestError, match="broken.json: not valid JSON"):
        load_records(path)


def test_a_record_that_is_not_an_object_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="row 2 is not a JSON object"):
        load_records(_write(tmp_path, [{"id": "1"}, "oops"]))


def test_require_names_file_row_and_field():
    with pytest.raises(AttestError, match="users.json: row 3 has no field 'id'"):
        require({}, "id", "users.json", 3)


def test_require_str_and_require_bool_reject_the_wrong_type():
    with pytest.raises(AttestError, match="non-empty string"):
        require_str({"id": ""}, "id", "f.json", 1)
    with pytest.raises(AttestError, match="true or false"):
        require_bool({"accountEnabled": None}, "accountEnabled", "f.json", 1)
    assert require_bool({"accountEnabled": False}, "accountEnabled", "f.json", 1) is False


@pytest.mark.parametrize("value", [
    "2026-10-01T02:10:13Z",
    "2026-10-01T02:10:13.0000000Z",
    "/Date(1790820613000)/",
    {"value": "/Date(1790820613000)/", "DisplayHint": 2},
    datetime(2026, 10, 1, 2, 10, 13, tzinfo=timezone.utc),
])
def test_parse_time_accepts_iso_powershell_and_yaml_forms(value):
    assert parse_time(value, "f.json", 1, "t") == datetime(2026, 10, 1, 2, 10, 13, tzinfo=timezone.utc)


def test_a_naive_time_is_taken_as_utc():
    assert parse_time("2026-10-01T02:10:13", "f.json", 1, "t").tzinfo == timezone.utc


def test_an_unreadable_time_stops_the_run():
    with pytest.raises(AttestError, match="field 't' is not a time"):
        parse_time("yesterday", "f.json", 1, "t")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_json_helpers.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.model'`.

- [ ] **Step 4: Write the shared types**

Create `attest/model.py`:

```python
"""Shared types: a confirmed tag, one loaded export, and a verdict."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

Status = Literal["backed", "gap", "unchecked"]
T = TypeVar("T")


class AttestError(Exception):
    """An input problem that stops the run: a bad tag, a missing field, an unknown reader."""


@dataclass(frozen=True)
class Tag:
    """One attestation, confirmed by a reviewer: its words, where they are, and what they claim."""

    id: str
    doc: str
    quote: str
    control: str
    scope: str


@dataclass(frozen=True)
class Export(Generic[T]):
    """One export file's records, and when the firm took it."""

    file: str
    exported_at: datetime
    items: tuple[T, ...]


@dataclass(frozen=True)
class Verdict:
    """A rule's answer. `entities` names what failed; `cited` names the rows the verdict rests on."""

    status: Status
    reason: str
    entities: tuple[str, ...] = ()
    cited: tuple[str, ...] = ()
    population: Optional[str] = None
```

- [ ] **Step 5: Write the JSON helpers**

Create `attest/readers/_json.py`:

```python
"""Load an API export and pull required fields out of it, loudly.

Every reader goes through these helpers, so a missing field, a truncated page
or an unreadable time stops the run with the file and row named instead of
being guessed around.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from attest.model import AttestError

# Windows PowerShell 5.1's ConvertTo-Json writes a DateTime as "/Date(ms)/".
_MS_DATE = re.compile(r"^/Date\((-?\d+)(?:[+-]\d{4})?\)/$")


def load_records(path: Path) -> list[dict]:
    """The records of a JSON export: a list, a Graph or Defender page {"value": [...]}, or one object.

    Windows PowerShell 5.1 writes UTF-16 by default; a UTF-16 byte-order mark is
    honoured, otherwise the file is read as UTF-8 with or without a BOM. A page
    that carries "@odata.nextLink" is one page of several and is refused: a
    truncated user or device list would shrink the population.
    """
    path = Path(path)
    raw = path.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AttestError(f"{path.name}: not valid JSON ({e.msg} at line {e.lineno})") from e
    if isinstance(data, dict) and "@odata.nextLink" in data:
        raise AttestError(f"{path.name}: the export is one page of several (it has @odata.nextLink)")
    if isinstance(data, dict) and isinstance(data.get("value"), list):
        records = data["value"]
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        raise AttestError(f"{path.name}: expected a JSON list or object, got {type(data).__name__}")
    for row, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise AttestError(f"{path.name}: row {row} is not a JSON object")
    return records


def require(record: dict, key: str, file: str, row: int) -> Any:
    """The value of a field the export must carry; its absence stops the run."""
    if key not in record:
        raise AttestError(f"{file}: row {row} has no field {key!r}")
    return record[key]


def require_str(record: dict, key: str, file: str, row: int) -> str:
    value = require(record, key, file, row)
    if not isinstance(value, str) or not value:
        raise AttestError(f"{file}: row {row} field {key!r} must be a non-empty string, got {value!r}")
    return value


def require_bool(record: dict, key: str, file: str, row: int) -> bool:
    value = require(record, key, file, row)
    if not isinstance(value, bool):
        raise AttestError(f"{file}: row {row} field {key!r} must be true or false, got {value!r}")
    return value


def parse_time(value: Any, file: str, row: int, key: str) -> datetime:
    """An ISO 8601 time, a PowerShell 5.1 "/Date(ms)/", or a datetime YAML already parsed; always UTC-aware."""
    if isinstance(value, dict) and "value" in value:  # PowerShell 5.1 can wrap a DateTime as {"value": ...}
        value = value["value"]
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and (match := _MS_DATE.match(value.strip())):
        return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.strip())
        except ValueError as e:
            raise AttestError(f"{file}: row {row} field {key!r} is not a time: {value!r}") from e
    else:
        raise AttestError(f"{file}: row {row} field {key!r} is not a time: {value!r}")
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_json_helpers.py -q`
Expected: `16 passed`.

- [ ] **Step 7: Commit**

```bash
git add .gitattributes .gitignore LICENSE README.md pyproject.toml requirements.txt attest tests/test_json_helpers.py
git commit -F - <<'EOF'
Set up the repo with shared types and loud JSON export loading

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Entra readers for users, registration, security defaults and roles

**Files:**
- Create: `attest/readers/entra_users.py`, `attest/readers/entra_registration.py`, `attest/readers/entra_security_defaults.py`, `attest/readers/entra_role_assignments.py`
- Create: `tests/conftest.py`
- Test: `tests/test_readers_entra.py`

**Interfaces:**
- Consumes: `load_records`, `require`, `require_str`, `require_bool` (Task 1); `AttestError`.
- Produces (each module has `read(path: Path) -> tuple[<Type>, ...]`):
  - `entra_users.User(id: str, upn: str, display_name: str, enabled: bool, user_type: str, cite: str)`
  - `entra_registration.Registration(user_id: str, upn: str, mfa_registered: bool, cite: str)`
  - `entra_security_defaults.SecurityDefaults(enabled: bool, cite: str)`; `read` returns exactly one
  - `entra_role_assignments.RoleAssignment(principal_id: str, principal_kind: str, principal_name: str, role_id: str, scope: str, cite: str)`; `principal_kind` is `"user"`, `"group"`, `"servicePrincipal"` or the raw `@odata.type`
  - `tests/conftest.py` fixture `write_json(name, data) -> Path` (writes JSON into `tmp_path`)

- [ ] **Step 1: Write the shared test fixture**

Create `tests/conftest.py`:

```python
import json

import pytest


@pytest.fixture
def write_json(tmp_path):
    """write_json(name, data) -> path of a JSON file written into tmp_path."""
    def write(name, data):
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path
    return write
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_readers_entra.py`:

```python
import pytest

from attest.model import AttestError
from attest.readers import entra_registration, entra_role_assignments, entra_security_defaults, entra_users

GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


def test_users_are_read_from_a_graph_page(write_json):
    path = write_json("users.json", {"value": [
        {"id": "u1", "userPrincipalName": "ann@firm.example", "displayName": "Ann",
         "accountEnabled": True, "userType": "Member"},
        {"id": "u2", "userPrincipalName": "guest#EXT#@firm.example", "displayName": None,
         "accountEnabled": True, "userType": "Guest"},
    ]})
    users = entra_users.read(path)
    assert users[0] == entra_users.User("u1", "ann@firm.example", "Ann", True, "Member", "users.json:1")
    assert (users[1].display_name, users[1].user_type, users[1].cite) == ("", "Guest", "users.json:2")


def test_a_null_user_type_reads_as_empty_not_guest(write_json):
    path = write_json("users.json", [
        {"id": "u1", "userPrincipalName": "a@f.example", "accountEnabled": True, "userType": None},
    ])
    assert entra_users.read(path)[0].user_type == ""


def test_a_user_without_account_enabled_stops_the_run(write_json):
    path = write_json("users.json", [{"id": "u1", "userPrincipalName": "a@f.example", "userType": "Member"}])
    with pytest.raises(AttestError, match="users.json: row 1 has no field 'accountEnabled'"):
        entra_users.read(path)


def test_registration_reads_is_mfa_registered(write_json):
    path = write_json("reg.json", {"value": [
        {"id": "u1", "userPrincipalName": "ann@firm.example", "isMfaRegistered": True, "isAdmin": False},
        {"id": "u2", "userPrincipalName": "bob@firm.example", "isMfaRegistered": False},
    ]})
    assert [(r.user_id, r.mfa_registered, r.cite) for r in entra_registration.read(path)] == [
        ("u1", True, "reg.json:1"),
        ("u2", False, "reg.json:2"),
    ]


def test_registration_without_is_mfa_registered_stops_the_run(write_json):
    path = write_json("reg.json", [{"id": "u1", "userPrincipalName": "a@f.example", "isMfaCapable": True}])
    with pytest.raises(AttestError, match="no field 'isMfaRegistered'"):
        entra_registration.read(path)


def test_security_defaults_is_one_object(write_json):
    path = write_json("sd.json", {"@odata.context": "x", "id": "00000000-0000-0000-0000-000000000005",
                                  "isEnabled": True})
    assert entra_security_defaults.read(path) == (entra_security_defaults.SecurityDefaults(True, "sd.json:1"),)


def test_security_defaults_must_be_exactly_one_policy(write_json):
    path = write_json("sd.json", [{"isEnabled": True}, {"isEnabled": False}])
    with pytest.raises(AttestError, match="expected one security-defaults policy, found 2"):
        entra_security_defaults.read(path)


def test_role_assignments_read_the_expanded_principal(write_json):
    path = write_json("roles.json", {"value": [
        {"id": "ra1", "principalId": "u1", "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": "/",
         "principal": {"@odata.type": "#microsoft.graph.user", "id": "u1",
                       "userPrincipalName": "ann@firm.example", "displayName": "Ann"}},
        {"id": "ra2", "principalId": "g1", "roleDefinitionId": EXCHANGE_ADMIN,
         "directoryScopeId": "/administrativeUnits/x",
         "principal": {"@odata.type": "#microsoft.graph.group", "id": "g1", "displayName": "IT admins"}},
    ]})
    first, second = entra_role_assignments.read(path)
    assert (first.principal_kind, first.principal_name, first.role_id, first.scope, first.cite) == (
        "user", "ann@firm.example", GLOBAL_ADMIN, "/", "roles.json:1")
    assert (second.principal_kind, second.principal_name, second.scope) == (
        "group", "IT admins", "/administrativeUnits/x")


def test_role_assignments_without_expanded_principal_say_how_to_export(write_json):
    path = write_json("roles.json", [{"id": "ra1", "principalId": "u1", "roleDefinitionId": "r"}])
    with pytest.raises(AttestError, match=r"\$expand=principal"):
        entra_role_assignments.read(path)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_readers_entra.py -q`
Expected: collection error, `ImportError: cannot import name 'entra_registration' from 'attest.readers'`.

- [ ] **Step 4: Write the four readers**

Create `attest/readers/entra_users.py`:

```python
"""Entra users: Microsoft Graph `GET /users?$select=id,userPrincipalName,displayName,accountEnabled,userType`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.readers._json import load_records, require_bool, require_str


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
    return tuple(
        User(
            id=require_str(r, "id", file, row),
            upn=require_str(r, "userPrincipalName", file, row),
            display_name=r.get("displayName") or "",
            enabled=require_bool(r, "accountEnabled", file, row),
            user_type=r.get("userType") or "",
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path), start=1)
    )
```

Create `attest/readers/entra_registration.py`:

```python
"""MFA registration: Microsoft Graph `GET /reports/authenticationMethods/userRegistrationDetails`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/userregistrationdetails?view=graph-rest-1.0
`isMfaRegistered` is what the rules read: the user has registered a strong
authentication method. It says nothing about whether MFA is enforced.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.readers._json import load_records, require_bool, require_str


@dataclass(frozen=True)
class Registration:
    user_id: str
    upn: str
    mfa_registered: bool
    cite: str


def read(path: Path) -> tuple[Registration, ...]:
    file = Path(path).name
    return tuple(
        Registration(
            user_id=require_str(r, "id", file, row),
            upn=require_str(r, "userPrincipalName", file, row),
            mfa_registered=require_bool(r, "isMfaRegistered", file, row),
            cite=f"{file}:{row}",
        )
        for row, r in enumerate(load_records(path), start=1)
    )
```

Create `attest/readers/entra_security_defaults.py`:

```python
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
```

Create `attest/readers/entra_role_assignments.py`:

```python
"""Directory role assignments: Microsoft Graph `GET /roleManagement/directory/roleAssignments?$expand=principal`.

Fields: https://learn.microsoft.com/en-us/graph/api/resources/unifiedroleassignment?view=graph-rest-1.0
For built-in roles, `roleDefinitionId` is the role template ID that
Conditional Access lists in `includeRoles` and `excludeRoles`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from attest.model import AttestError
from attest.readers._json import load_records, require_str

_ODATA_PREFIX = "#microsoft.graph."


@dataclass(frozen=True)
class RoleAssignment:
    principal_id: str
    principal_kind: str  # "user", "group", "servicePrincipal", or the raw @odata.type
    principal_name: str
    role_id: str
    scope: str
    cite: str


def read(path: Path) -> tuple[RoleAssignment, ...]:
    file = Path(path).name
    assignments = []
    for row, r in enumerate(load_records(path), start=1):
        principal = r.get("principal")
        if not isinstance(principal, dict):
            raise AttestError(f"{file}: row {row} has no field 'principal' (export with $expand=principal)")
        odata_type = require_str(principal, "@odata.type", file, row)
        kind = odata_type[len(_ODATA_PREFIX):] if odata_type.startswith(_ODATA_PREFIX) else odata_type
        assignments.append(RoleAssignment(
            principal_id=require_str(r, "principalId", file, row),
            principal_kind=kind,
            principal_name=principal.get("userPrincipalName") or principal.get("displayName") or "",
            role_id=require_str(r, "roleDefinitionId", file, row),
            scope=r.get("directoryScopeId") or "/",
            cite=f"{file}:{row}",
        ))
    return tuple(assignments)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_readers_entra.py -q`
Expected: `9 passed`.

- [ ] **Step 6: Commit**

```bash
git add attest/readers tests/conftest.py tests/test_readers_entra.py
git commit -F - <<'EOF'
Read Entra users, MFA registration, security defaults and role assignments

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Conditional Access reader that decides "requires MFA" and "narrowing"

**Files:**
- Create: `attest/readers/entra_ca_policies.py`
- Test: `tests/test_readers_ca_policies.py`

**Interfaces:**
- Consumes: `load_records`, `require`, `require_str` (Task 1); `write_json` fixture (Task 2).
- Produces:
  - `CaPolicy(id, name, state, include_users, exclude_users, exclude_groups, include_roles, exclude_roles, include_apps, narrowing, requires_mfa, cite)`: strings, then `tuple[str, ...]` for the six lists and `narrowing`, `requires_mfa: bool`, `cite: str`
  - `requires_mfa(grant: dict | None) -> bool`
  - `narrowing_conditions(conditions: dict) -> tuple[str, ...]`
  - `read(path: Path) -> tuple[CaPolicy, ...]`
  - `MFA_STRENGTH_IDS: frozenset[str]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_readers_ca_policies.py`:

```python
import pytest

from attest.model import AttestError
from attest.readers.entra_ca_policies import CaPolicy, narrowing_conditions, read, requires_mfa

MFA_STRENGTH = {"id": "00000000-0000-0000-0000-000000000002", "displayName": "Multifactor authentication"}

BASE = {
    "clientAppTypes": ["all"],
    "applications": {"includeApplications": ["All"], "excludeApplications": []},
    "users": {"includeUsers": ["All"]},
    "locations": None,
    "platforms": None,
    "devices": None,
    "signInRiskLevels": [],
    "userRiskLevels": [],
    "servicePrincipalRiskLevels": [],
}


@pytest.mark.parametrize("grant, expected", [
    ({"operator": "OR", "builtInControls": ["mfa"]}, True),
    ({"operator": "AND", "builtInControls": ["mfa", "compliantDevice"]}, True),
    ({"operator": "OR", "builtInControls": ["mfa", "compliantDevice"]}, False),
    ({"operator": "OR", "builtInControls": [], "authenticationStrength": MFA_STRENGTH}, True),
    ({"operator": "OR", "builtInControls": [], "authenticationStrength": {"id": "custom-1"}}, False),
    ({"operator": "OR", "builtInControls": ["mfa"], "authenticationStrength": {"id": "custom-1"}}, False),
    ({"operator": "OR", "builtInControls": ["mfa"], "termsOfUse": ["tou-1"]}, False),
    ({"operator": "AND", "builtInControls": ["mfa"], "termsOfUse": ["tou-1"]}, True),
    ({"operator": "OR", "builtInControls": ["block"]}, False),
    ({"operator": "AND", "builtInControls": ["block", "mfa"]}, False),
    ({"operator": "OR", "builtInControls": ["compliantDevice"]}, False),
    ({"builtInControls": ["mfa", "domainJoinedDevice"]}, False),
    (None, False),
])
def test_requires_mfa_only_when_every_way_through_takes_mfa(grant, expected):
    assert requires_mfa(grant) is expected


def test_a_plain_all_users_all_apps_policy_has_no_narrowing():
    assert narrowing_conditions(BASE) == ()


def test_locations_that_include_all_without_exclusions_do_not_narrow():
    assert narrowing_conditions({**BASE, "locations": {"includeLocations": ["All"], "excludeLocations": []}}) == ()


def test_an_empty_devices_object_does_not_narrow():
    devices = {"@odata.type": "#microsoft.graph.conditionalAccessDevices",
               "deviceFilter": None, "includeDevices": [], "excludeDevices": []}
    assert narrowing_conditions({**BASE, "devices": devices}) == ()


@pytest.mark.parametrize("change, name", [
    ({"clientAppTypes": ["browser", "mobileAppsAndDesktopClients"]}, "clientAppTypes"),
    ({"locations": {"includeLocations": ["All"], "excludeLocations": ["AllTrusted"]}}, "locations"),
    ({"locations": {"includeLocations": ["loc-1"], "excludeLocations": []}}, "locations"),
    ({"platforms": {"includePlatforms": ["windows"], "excludePlatforms": []}}, "platforms"),
    ({"platforms": {"includePlatforms": ["all"], "excludePlatforms": ["iOS"]}}, "platforms"),
    ({"devices": {"deviceFilter": {"mode": "exclude", "rule": "device.isCompliant -eq True"}}}, "devices"),
    ({"signInRiskLevels": ["high"]}, "signInRiskLevels"),
    ({"userRiskLevels": ["medium"]}, "userRiskLevels"),
    ({"servicePrincipalRiskLevels": ["high"]}, "servicePrincipalRiskLevels"),
    ({"insiderRiskLevels": "elevated"}, "insiderRiskLevels"),
    ({"authenticationFlows": {"transferMethods": "deviceCodeFlow"}}, "authenticationFlows"),
    ({"applications": {"includeApplications": ["All"], "excludeApplications": ["app-1"]}},
     "applications.excludeApplications"),
    ({"applications": {"includeApplications": ["All"], "includeUserActions": ["urn:user:registersecurityinfo"]}},
     "applications.includeUserActions"),
])
def test_each_narrowing_condition_is_named(change, name):
    assert name in narrowing_conditions({**BASE, **change})


def test_read_builds_a_policy_from_graph_json(write_json):
    path = write_json("ca.json", {"value": [{
        "id": "p1", "displayName": "Require MFA for all users", "state": "enabled",
        "conditions": {**BASE, "users": {"includeUsers": ["All"], "excludeUsers": ["u9"], "excludeGroups": ["g1"],
                                         "includeRoles": [], "excludeRoles": ["r1"]}},
        "grantControls": {"operator": "OR", "builtInControls": ["mfa"]},
    }]})
    assert read(path) == (CaPolicy(
        id="p1", name="Require MFA for all users", state="enabled",
        include_users=("All",), exclude_users=("u9",), exclude_groups=("g1",),
        include_roles=(), exclude_roles=("r1",), include_apps=("All",),
        narrowing=(), requires_mfa=True, cite="ca.json:1"),)


def test_a_session_only_policy_with_null_grant_does_not_require_mfa(write_json):
    path = write_json("ca.json", [{"id": "p2", "displayName": "Sign-in frequency", "state": "enabled",
                                   "conditions": BASE, "grantControls": None}])
    assert read(path)[0].requires_mfa is False


def test_a_policy_without_conditions_stops_the_run(write_json):
    path = write_json("ca.json", [{"id": "p3", "state": "enabled", "grantControls": None}])
    with pytest.raises(AttestError, match="no field 'conditions'"):
        read(path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_readers_ca_policies.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.readers.entra_ca_policies'`.

- [ ] **Step 3: Write the reader**

Create `attest/readers/entra_ca_policies.py`:

```python
"""Conditional Access policies: Microsoft Graph `GET /identity/conditionalAccess/policies`.

Fields: conditionalAccessPolicy and its conditionalAccessConditionSet,
conditionalAccessUsers, conditionalAccessApplications and
conditionalAccessGrantControls, from
https://learn.microsoft.com/en-us/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0

Two judgments live here because both are about what the policy JSON says,
not about any firm: whether the grant requires MFA, and which conditions
narrow when the policy applies. Both err toward "does not count": a policy
wrongly counted could back an attestation that is false, while a policy
wrongly discounted can only cost a false gap.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from attest.model import AttestError
from attest.readers._json import load_records, require, require_str

# Microsoft's built-in authentication strengths that require MFA:
# Multifactor authentication, Passwordless MFA, Phishing-resistant MFA.
MFA_STRENGTH_IDS = frozenset({
    "00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000003",
    "00000000-0000-0000-0000-000000000004",
})


@dataclass(frozen=True)
class CaPolicy:
    id: str
    name: str
    state: str
    include_users: tuple[str, ...]
    exclude_users: tuple[str, ...]
    exclude_groups: tuple[str, ...]
    include_roles: tuple[str, ...]
    exclude_roles: tuple[str, ...]
    include_apps: tuple[str, ...]
    narrowing: tuple[str, ...]
    requires_mfa: bool
    cite: str


def requires_mfa(grant: dict | None) -> bool:
    """Whether every way of satisfying this grant takes MFA.

    With operator OR, any other control is an alternative that passes without
    MFA, so "MFA or a compliant device" does not require MFA. A grant that
    blocks does not prove MFA. A missing operator is read as OR.
    """
    if not grant:
        return False
    controls = list(grant.get("builtInControls") or [])
    if "block" in controls:
        return False
    strength = grant.get("authenticationStrength")
    strength_is_mfa = isinstance(strength, dict) and strength.get("id") in MFA_STRENGTH_IDS
    if "mfa" not in controls and not strength_is_mfa:
        return False
    alternatives = [c for c in controls if c != "mfa"]
    alternatives += list(grant.get("customAuthenticationFactors") or [])
    alternatives += list(grant.get("termsOfUse") or [])
    if strength and not strength_is_mfa:
        alternatives.append("authenticationStrength")
    return (grant.get("operator") or "OR").upper() == "AND" or not alternatives


def _is_set(value: Any) -> bool:
    """True when a condition carries anything, ignoring @odata annotations."""
    if isinstance(value, dict):
        return any(_is_set(v) for k, v in value.items() if not k.startswith("@odata"))
    return bool(value)


def _locations_narrow(locations: dict | None) -> bool:
    if not locations:
        return False
    include = [loc.lower() for loc in locations.get("includeLocations") or ["all"]]
    return include != ["all"] or bool(locations.get("excludeLocations"))


def _platforms_narrow(platforms: dict | None) -> bool:
    if not platforms:
        return False
    include = [p.lower() for p in platforms.get("includePlatforms") or ["all"]]
    return include != ["all"] or bool(platforms.get("excludePlatforms"))


def narrowing_conditions(conditions: dict) -> tuple[str, ...]:
    """Every condition that limits when the policy applies beyond its users and applications."""
    found: list[str] = []
    if [t.lower() for t in conditions.get("clientAppTypes") or ["all"]] != ["all"]:
        found.append("clientAppTypes")
    if _locations_narrow(conditions.get("locations")):
        found.append("locations")
    if _platforms_narrow(conditions.get("platforms")):
        found.append("platforms")
    for key in ("devices", "authenticationFlows", "clientApplications", "insiderRiskLevels",
                "signInRiskLevels", "userRiskLevels", "servicePrincipalRiskLevels"):
        if _is_set(conditions.get(key)):
            found.append(key)
    applications = conditions.get("applications") or {}
    for key in ("excludeApplications", "applicationFilter", "includeUserActions",
                "includeAuthenticationContextClassReferences"):
        if _is_set(applications.get(key)):
            found.append(f"applications.{key}")
    return tuple(found)


def read(path: Path) -> tuple[CaPolicy, ...]:
    file = Path(path).name
    policies = []
    for row, r in enumerate(load_records(path), start=1):
        conditions = require(r, "conditions", file, row)
        if not isinstance(conditions, dict):
            raise AttestError(f"{file}: row {row} field 'conditions' must be an object")
        users = conditions.get("users") or {}
        applications = conditions.get("applications") or {}
        policy_id = require_str(r, "id", file, row)
        policies.append(CaPolicy(
            id=policy_id,
            name=r.get("displayName") or policy_id,
            state=require_str(r, "state", file, row),
            include_users=tuple(users.get("includeUsers") or ()),
            exclude_users=tuple(users.get("excludeUsers") or ()),
            exclude_groups=tuple(users.get("excludeGroups") or ()),
            include_roles=tuple(users.get("includeRoles") or ()),
            exclude_roles=tuple(users.get("excludeRoles") or ()),
            include_apps=tuple(applications.get("includeApplications") or ()),
            narrowing=narrowing_conditions(conditions),
            requires_mfa=requires_mfa(require(r, "grantControls", file, row)),
            cite=f"{file}:{row}",
        ))
    return tuple(policies)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_readers_ca_policies.py -q`
Expected: `32 passed`.

- [ ] **Step 5: Commit**

```bash
git add attest/readers/entra_ca_policies.py tests/test_readers_ca_policies.py
git commit -F - <<'EOF'
Read Conditional Access policies, deciding strictly what requires MFA

A policy counts only when every way through its grant takes MFA and no
condition narrows when it applies; either way a doubtful policy does not
count, which can cost a false gap but never back a false attestation.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 4: Intune, Defender and Veeam readers, and how to export them

**Files:**
- Create: `attest/readers/intune_devices.py`, `attest/readers/defender_machines.py`, `attest/readers/veeam_users.py`
- Create: `docs/exports.md`
- Test: `tests/test_readers_devices_backup.py`

**Interfaces:**
- Consumes: Task 1 helpers including `parse_time`; `write_json` fixture.
- Produces:
  - `intune_devices.IntuneDevice(id: str, name: str, aad_device_id: str | None, os: str, cite: str)`; `intune_devices.normalize_device_id(value) -> str | None` (lower-case GUID; None for empty or all-zero)
  - `defender_machines.Machine(id: str, name: str, aad_device_id: str | None, onboarding: str, health: str, last_seen: datetime | None, cite: str)`
  - `veeam_users.VeeamUser(email: str, mailbox_backed_up: bool, mailbox_backed_up_time: datetime | None, cite: str)`
  - each module: `read(path: Path) -> tuple[...]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_readers_devices_backup.py`:

```python
from datetime import datetime, timezone

import pytest

from attest.model import AttestError
from attest.readers import defender_machines, intune_devices, veeam_users


def test_intune_devices_read_name_and_entra_device_id(write_json):
    path = write_json("intune.json", {"value": [
        {"id": "i1", "deviceName": "HP-LT-01", "azureADDeviceId": "D0000000-0000-4000-8000-000000000001",
         "operatingSystem": "Windows"},
        {"id": "i2", "deviceName": "PHONE-1", "azureADDeviceId": "00000000-0000-0000-0000-000000000000",
         "operatingSystem": "iOS"},
    ]})
    first, second = intune_devices.read(path)
    assert first == intune_devices.IntuneDevice(
        "i1", "HP-LT-01", "d0000000-0000-4000-8000-000000000001", "Windows", "intune.json:1")
    assert second.aad_device_id is None  # the all-zero GUID means "not joined"


def test_an_intune_device_without_the_azure_ad_device_id_field_stops_the_run(write_json):
    path = write_json("intune.json", [{"id": "i1", "deviceName": "HP-LT-01"}])
    with pytest.raises(AttestError, match="no field 'azureADDeviceId'"):
        intune_devices.read(path)


def test_defender_machines_read_health_onboarding_and_last_seen(write_json):
    path = write_json("mde.json", {"value": [
        {"id": "m1", "computerDnsName": "hp-lt-01.firm.example", "aadDeviceId": "d0000000-0000-4000-8000-000000000001",
         "onboardingStatus": "Onboarded", "healthStatus": "Active", "lastSeen": "2026-10-01T09:30:00.1234567Z"},
        {"id": "m2", "computerDnsName": "hp-fs01.firm.example", "aadDeviceId": None,
         "onboardingstatus": "CanBeOnboarded", "healthStatus": "Inactive", "lastSeen": None},
    ]})
    first, second = defender_machines.read(path)
    assert (first.name, first.aad_device_id, first.onboarding, first.health) == (
        "hp-lt-01.firm.example", "d0000000-0000-4000-8000-000000000001", "Onboarded", "Active")
    assert first.last_seen == datetime(2026, 10, 1, 9, 30, 0, 123456, tzinfo=timezone.utc)
    assert (second.aad_device_id, second.onboarding, second.last_seen) == (None, "CanBeOnboarded", None)


def test_a_defender_machine_without_health_status_stops_the_run(write_json):
    path = write_json("mde.json", [
        {"id": "m1", "computerDnsName": "x", "onboardingStatus": "Onboarded", "lastSeen": None},
    ])
    with pytest.raises(AttestError, match="no field 'healthStatus'"):
        defender_machines.read(path)


def test_veeam_users_read_mailbox_state_in_powershell_5_and_7_forms(write_json):
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "DisplayName": "Ann", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": "/Date(1790820613000)/"},
        {"Email": "bob@firm.example", "DisplayName": "Bob", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": "2026-10-01T02:10:13Z"},
        {"Email": "cy@firm.example", "DisplayName": "Cy", "IsMailboxBackedUp": False,
         "MailboxBackedUpTime": None},
    ])
    ann, bob, cy = veeam_users.read(path)
    when = datetime(2026, 10, 1, 2, 10, 13, tzinfo=timezone.utc)
    assert (ann.mailbox_backed_up_time, bob.mailbox_backed_up_time) == (when, when)
    assert (cy.email, cy.mailbox_backed_up, cy.mailbox_backed_up_time, cy.cite) == (
        "cy@firm.example", False, None, "veeam.json:3")


def test_a_veeam_export_without_mailbox_backup_time_stops_the_run(write_json):
    path = write_json("veeam.json", [{"Email": "ann@firm.example", "IsMailboxBackedUp": True}])
    with pytest.raises(AttestError, match="no field 'MailboxBackedUpTime'"):
        veeam_users.read(path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_readers_devices_backup.py -q`
Expected: collection error, `ImportError: cannot import name 'defender_machines' from 'attest.readers'`.

- [ ] **Step 3: Write the three readers**

Create `attest/readers/intune_devices.py`:

```python
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
```

Create `attest/readers/defender_machines.py`:

```python
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
```

Create `attest/readers/veeam_users.py`:

```python
"""Veeam Backup for Microsoft 365 user data: `Get-VBOEntityData -Type User`, selected and ConvertTo-Json.

The field names (Email, IsMailboxBackedUp, MailboxBackedUpTime) come from
Veeam's published PowerShell examples, not its reference documentation; the
documented REST form of this data has no backup timestamps, so it cannot
prove a daily backup. Check them against the first real export before any
paid check relies on this reader. A missing field stops the run.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from attest.readers._json import load_records, parse_time, require, require_bool, require_str


@dataclass(frozen=True)
class VeeamUser:
    email: str
    mailbox_backed_up: bool
    mailbox_backed_up_time: Optional[datetime]
    cite: str


def read(path: Path) -> tuple[VeeamUser, ...]:
    file = Path(path).name
    users = []
    for row, r in enumerate(load_records(path), start=1):
        when = require(r, "MailboxBackedUpTime", file, row)
        users.append(VeeamUser(
            email=require_str(r, "Email", file, row),
            mailbox_backed_up=require_bool(r, "IsMailboxBackedUp", file, row),
            mailbox_backed_up_time=None if when in (None, "") else parse_time(when, file, row, "MailboxBackedUpTime"),
            cite=f"{file}:{row}",
        ))
    return tuple(users)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_readers_devices_backup.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Write the export instructions**

Create `docs/exports.md`:

````markdown
# Producing the exports

The firm runs these read-only while the reviewer watches. Write each file into
the firm's `exports/` folder and record the UTC time it was taken as its
`exported_at` in `exports/manifest.yaml`:

```yaml
exports:
  - {file: users.json, reader: entra_users, exported_at: 2026-10-01T15:00:00Z}
```

Every reader stops the run on a missing field, so a wrong export fails loudly.

## Microsoft Graph (Entra ID and Intune)

Use Microsoft Graph PowerShell and sign in with read-only scopes:

```powershell
Connect-MgGraph -Scopes "User.Read.All","AuditLog.Read.All","Policy.Read.All","RoleManagement.Read.Directory","DeviceManagementManagedDevices.Read.All"
```

`Invoke-MgGraphRequest -OutputType Json` returns the API's JSON unchanged.
Write it with `-Encoding utf8`. If a response carries `@odata.nextLink`, it is
one page of several and the reader refuses it, because v1 does not page.

| Reader | Command | Fields documented at |
|---|---|---|
| `entra_users` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/users?$select=id,userPrincipalName,displayName,accountEnabled,userType&$top=999' -OutputType Json \| Out-File users.json -Encoding utf8` | [user](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0) |
| `entra_registration` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/reports/authenticationMethods/userRegistrationDetails' -OutputType Json \| Out-File registration.json -Encoding utf8` | [userRegistrationDetails](https://learn.microsoft.com/en-us/graph/api/resources/userregistrationdetails?view=graph-rest-1.0) |
| `entra_ca_policies` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/identity/conditionalAccess/policies' -OutputType Json \| Out-File ca-policies.json -Encoding utf8` | [conditionalAccessPolicy](https://learn.microsoft.com/en-us/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0) |
| `entra_security_defaults` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/policies/identitySecurityDefaultsEnforcementPolicy' -OutputType Json \| Out-File security-defaults.json -Encoding utf8` | [identitySecurityDefaultsEnforcementPolicy](https://learn.microsoft.com/en-us/graph/api/resources/identitysecuritydefaultsenforcementpolicy?view=graph-rest-1.0) |
| `entra_role_assignments` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/roleManagement/directory/roleAssignments?$expand=principal' -OutputType Json \| Out-File role-assignments.json -Encoding utf8` | [unifiedRoleAssignment](https://learn.microsoft.com/en-us/graph/api/resources/unifiedroleassignment?view=graph-rest-1.0) |
| `intune_devices` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/deviceManagement/managedDevices?$select=id,deviceName,azureADDeviceId,operatingSystem,userPrincipalName' -OutputType Json \| Out-File intune-devices.json -Encoding utf8` | [managedDevice](https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice?view=graph-rest-1.0) |

## Defender for Endpoint

The Defender API needs a token from an Entra app registration granted
`Machine.Read.All`. `Invoke-RestMethod` parses the JSON, so write it back with
enough depth:

```powershell
Invoke-RestMethod -Uri 'https://api.security.microsoft.com/api/machines' -Headers @{ Authorization = "Bearer $token" } |
  ConvertTo-Json -Depth 6 | Out-File defender-machines.json -Encoding utf8
```

Reader `defender_machines`. Fields: [Machine](https://learn.microsoft.com/en-us/defender-endpoint/api/machine).

## Veeam Backup for Microsoft 365

On the Veeam server, for the repository that holds the firm's mailboxes:

```powershell
Get-VBOEntityData -Type User -Repository (Get-VBORepository -Name '<repository>') |
  Select-Object Email, DisplayName, IsMailboxBackedUp, MailboxBackedUpTime |
  ConvertTo-Json | Out-File veeam-users.json -Encoding utf8
```

Reader `veeam_users`. One repository per export: a mailbox kept in another
repository shows as missing, which is a gap and never a false backed. The field
names come from Veeam's published examples, not its reference documentation;
check them against the first real export.
````

- [ ] **Step 6: Commit**

```bash
git add attest/readers tests/test_readers_devices_backup.py docs/exports.md
git commit -F - <<'EOF'
Read Intune devices, Defender machines and Veeam mailbox state

docs/exports.md gives the read-only command behind each export and where
its fields are documented.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 5: Reader registry and evidence loaded from the manifest

**Files:**
- Modify: `attest/readers/__init__.py` (replace its contents)
- Create: `attest/evidence.py`
- Test: `tests/test_evidence.py`

**Interfaces:**
- Consumes: every reader module's `read` and types (Tasks 2-4); `Export`, `AttestError`, `parse_time`.
- Produces:
  - `attest.readers.READERS: dict[str, Callable[[Path], tuple]]` with keys `entra_users`, `entra_registration`, `entra_ca_policies`, `entra_security_defaults`, `entra_role_assignments`, `intune_devices`, `defender_machines`, `veeam_users`
  - `attest.evidence.Evidence`: frozen dataclass whose fields have exactly the `READERS` names, each `Optional[Export[...]] = None`
  - `attest.evidence.load_evidence(exports_dir: Path) -> Evidence`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evidence.py`:

```python
import json
from datetime import datetime, timezone

import pytest

from attest.evidence import Evidence, load_evidence
from attest.model import AttestError
from attest.readers import READERS

USERS = {"value": [{"id": "u1", "userPrincipalName": "ann@firm.example",
                    "accountEnabled": True, "userType": "Member"}]}
ONE_USERS_EXPORT = ("exports:\n  - file: users.json\n    reader: entra_users\n"
                    "    exported_at: 2026-10-01T15:00:00Z\n")


def _exports(tmp_path, manifest_text, files):
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    for name, data in files.items():
        (exports / name).write_text(json.dumps(data), encoding="utf-8")
    return exports


def test_every_reader_has_an_evidence_field():
    assert set(READERS) == set(Evidence.__dataclass_fields__)


def test_a_listed_export_is_loaded_with_its_time(tmp_path):
    evidence = load_evidence(_exports(tmp_path, ONE_USERS_EXPORT, {"users.json": USERS}))
    assert evidence.entra_users.file == "users.json"
    assert evidence.entra_users.exported_at == datetime(2026, 10, 1, 15, tzinfo=timezone.utc)
    assert [u.upn for u in evidence.entra_users.items] == ["ann@firm.example"]
    assert evidence.defender_machines is None


@pytest.mark.parametrize("manifest, message", [
    (ONE_USERS_EXPORT.replace("reader: entra_users", "reader: nope"), "unknown reader 'nope'"),
    ("exports:\n  - file: users.json\n    reader: entra_users\n", "entry 1 has no 'exported_at'"),
    (ONE_USERS_EXPORT.replace("file: users.json", "file: missing.json"), "file 'missing.json' does not exist"),
    (ONE_USERS_EXPORT + ONE_USERS_EXPORT.replace("exports:\n", ""), "reader 'entra_users' appears twice"),
    (ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", "someday"), "not a time"),
])
def test_a_bad_manifest_stops_the_run(tmp_path, manifest, message):
    exports = _exports(tmp_path, manifest, {"users.json": USERS})
    with pytest.raises(AttestError, match=message):
        load_evidence(exports)


def test_a_missing_manifest_stops_the_run(tmp_path):
    (tmp_path / "exports").mkdir()
    with pytest.raises(AttestError, match="manifest.yaml not found"):
        load_evidence(tmp_path / "exports")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_evidence.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.evidence'`.

- [ ] **Step 3: Write the registry**

Replace the contents of `attest/readers/__init__.py` with:

```python
"""One reader per export format, by the name a firm's manifest uses."""
from attest.readers import (
    defender_machines,
    entra_ca_policies,
    entra_registration,
    entra_role_assignments,
    entra_security_defaults,
    entra_users,
    intune_devices,
    veeam_users,
)

READERS = {
    "entra_users": entra_users.read,
    "entra_registration": entra_registration.read,
    "entra_ca_policies": entra_ca_policies.read,
    "entra_security_defaults": entra_security_defaults.read,
    "entra_role_assignments": entra_role_assignments.read,
    "intune_devices": intune_devices.read,
    "defender_machines": defender_machines.read,
    "veeam_users": veeam_users.read,
}
```

- [ ] **Step 4: Write the evidence loader**

Create `attest/evidence.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_evidence.py -q`
Expected: `8 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: `71 passed`.

- [ ] **Step 7: Commit**

```bash
git add attest/readers/__init__.py attest/evidence.py tests/test_evidence.py
git commit -F - <<'EOF'
Load a firm's exports through the manifest that names their readers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 6: Control profile and grounded tags

**Files:**
- Create: `profile/controls.yaml`, `attest/profile.py`, `attest/tags.py`
- Test: `tests/test_profile_and_tags.py`

**Interfaces:**
- Consumes: `Tag`, `AttestError` (Task 1).
- Produces:
  - `attest.profile.PROFILE_PATH: Path` (repo `profile/controls.yaml`)
  - `attest.profile.Profile = dict[str, dict[str, str]]`
  - `attest.profile.load_profile(path: Path = PROFILE_PATH, rules: Iterable[str] | None = None) -> Profile`
  - `attest.tags.load_tags(firm: Path, profile: Profile) -> list[Tag]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_profile_and_tags.py`:

```python
import pytest

from attest.model import AttestError, Tag
from attest.profile import load_profile
from attest.tags import load_tags

PROFILE = {"mfa": {"all_users": "mfa_all_users"}, "edr": {"all_endpoints": "edr_all_endpoints"}}
WISP = "All staff use MFA.\nEvery laptop runs EDR.\n"


def _firm(tmp_path, tags_yaml):
    (tmp_path / "attest").mkdir()
    (tmp_path / "attest" / "wisp.txt").write_text(WISP, encoding="utf-8")
    (tmp_path / "tags.yaml").write_text(tags_yaml, encoding="utf-8")
    return tmp_path


def test_the_shipped_profile_has_the_three_controls_and_their_scopes():
    assert load_profile() == {
        "mfa": {"all_users": "mfa_all_users", "email": "mfa_email",
                "admins": "mfa_admins", "remote_access": "mfa_remote_access"},
        "edr": {"all_endpoints": "edr_all_endpoints"},
        "backup": {"m365_mailboxes": "backup_m365_mailboxes", "servers": "backup_servers",
                   "offline_copy": "backup_offline_copy", "restore_tested": "backup_restore_tested"},
    }


def test_a_profile_rule_missing_from_the_registry_stops_the_run(tmp_path):
    path = tmp_path / "controls.yaml"
    path.write_text("mfa:\n  all_users: mfa_all_users\n  email: not_a_rule\n", encoding="utf-8")
    with pytest.raises(AttestError, match="mfa.email names unknown rule 'not_a_rule'"):
        load_profile(path, rules={"mfa_all_users"})


def test_tags_load_when_every_quote_is_in_its_document(tmp_path):
    firm = _firm(tmp_path, "tags:\n  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA., "
                           "control: mfa, scope: all_users}\n")
    assert load_tags(firm, PROFILE) == [Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")]


@pytest.mark.parametrize("tags_yaml, message", [
    ("tags:\n  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA always., control: mfa, scope: all_users}\n",
     "tag 'w1': quote is not an exact substring of attest/wisp.txt"),
    ("tags:\n  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA., control: dlp, scope: all_users}\n",
     "tag 'w1': unknown control 'dlp'"),
    ("tags:\n  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA., control: mfa, scope: guests}\n",
     "tag 'w1': unknown scope 'mfa.guests'"),
    ("tags:\n  - {id: w1, doc: attest/missing.txt, quote: All staff use MFA., control: mfa, scope: all_users}\n",
     "tag 'w1': document attest/missing.txt not found"),
    ("tags:\n  - {id: w1, doc: attest/wisp.txt, control: mfa, scope: all_users}\n",
     "tag 1 has no 'quote'"),
    ("tags:\n  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA., control: mfa, scope: all_users}\n"
     "  - {id: w1, doc: attest/wisp.txt, quote: Every laptop runs EDR., control: edr, scope: all_endpoints}\n",
     "tag id 'w1' appears twice"),
])
def test_a_bad_tag_stops_the_run(tmp_path, tags_yaml, message):
    with pytest.raises(AttestError, match=message):
        load_tags(_firm(tmp_path, tags_yaml), PROFILE)


def test_a_firm_without_tags_yaml_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="tags.yaml not found"):
        load_tags(tmp_path, PROFILE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_profile_and_tags.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.profile'`.

- [ ] **Step 3: Write the profile**

Create `profile/controls.yaml`:

```yaml
# Control -> scope -> proof rule (attest/rules). The profile is the check's
# only list of what an attestation can be tagged as.
mfa:
  all_users: mfa_all_users
  email: mfa_email
  admins: mfa_admins
  remote_access: mfa_remote_access
edr:
  all_endpoints: edr_all_endpoints
backup:
  m365_mailboxes: backup_m365_mailboxes
  servers: backup_servers
  offline_copy: backup_offline_copy
  restore_tested: backup_restore_tested
```

Create `attest/profile.py`:

```python
"""The control profile: which proof rule each control's scope uses (spec: Firm folder and profile)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import yaml

from attest.model import AttestError

PROFILE_PATH = Path(__file__).resolve().parents[1] / "profile" / "controls.yaml"
Profile = dict[str, dict[str, str]]


def load_profile(path: Path = PROFILE_PATH, rules: Optional[Iterable[str]] = None) -> Profile:
    """Controls to scopes to rule names; with `rules`, every named rule must be one of them."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise AttestError(f"{path.name}: expected a mapping of controls to scopes")
    known = None if rules is None else set(rules)
    for control, scopes in data.items():
        if not isinstance(scopes, dict) or not scopes:
            raise AttestError(f"{path.name}: control {control!r} has no scopes")
        for scope, rule in scopes.items():
            if known is not None and rule not in known:
                raise AttestError(f"{path.name}: {control}.{scope} names unknown rule {rule!r}")
    return data
```

- [ ] **Step 4: Write the tag loader**

Create `attest/tags.py`:

```python
"""Confirmed tags, each grounded in its document (spec: Pipeline, step 1)."""
from __future__ import annotations

from pathlib import Path

import yaml

from attest.model import AttestError, Tag
from attest.profile import Profile

FIELDS = ("id", "doc", "quote", "control", "scope")


def load_tags(firm: Path, profile: Profile) -> list[Tag]:
    """Every tag in firm/tags.yaml, refusing one whose quote is not an exact substring of its document."""
    path = Path(firm) / "tags.yaml"
    if not path.is_file():
        raise AttestError(f"{path} not found")
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("tags") or []
    documents: dict[str, str] = {}
    seen: set[str] = set()
    tags: list[Tag] = []
    for i, entry in enumerate(raw, start=1):
        for field in FIELDS:
            if field not in entry:
                raise AttestError(f"tags.yaml: tag {i} has no {field!r}")
        tag = Tag(*(str(entry[field]) for field in FIELDS))
        if tag.id in seen:
            raise AttestError(f"tags.yaml: tag id {tag.id!r} appears twice")
        seen.add(tag.id)
        if tag.control not in profile:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: unknown control {tag.control!r}")
        if tag.scope not in profile[tag.control]:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: unknown scope '{tag.control}.{tag.scope}'")
        if tag.doc not in documents:
            doc_path = Path(firm) / tag.doc
            if not doc_path.is_file():
                raise AttestError(f"tags.yaml: tag {tag.id!r}: document {tag.doc} not found")
            documents[tag.doc] = doc_path.read_text(encoding="utf-8")
        if tag.quote not in documents[tag.doc]:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: quote is not an exact substring of {tag.doc}")
        tags.append(tag)
    return tags
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_profile_and_tags.py -q`
Expected: `10 passed`.

- [ ] **Step 6: Commit**

```bash
git add profile attest/profile.py attest/tags.py tests/test_profile_and_tags.py
git commit -F - <<'EOF'
Load the control profile and refuse tags whose quotes are not in their documents

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 7: MFA proof rules

**Files:**
- Create: `attest/rules/__init__.py`, `attest/rules/common.py`, `attest/rules/mfa.py`
- Create: `tests/builders.py`
- Test: `tests/test_rules_mfa.py`

**Interfaces:**
- Consumes: `Evidence` (Task 5); `Export`, `Verdict` (Task 1); `User`, `Registration`, `SecurityDefaults`, `RoleAssignment` (Task 2); `CaPolicy` (Task 3); `IntuneDevice`, `Machine`, `VeeamUser` (Task 4, used by `tests/builders.py`).
- Produces:
  - `attest.rules.common.Rule = Callable[[Evidence], Verdict]`
  - `attest.rules.common.unchecked(reason: str) -> Verdict`
  - `attest.rules.common.member_accounts(users: Export[User]) -> tuple[tuple[User, ...], str]`
  - `attest.rules.common.never(reason: str) -> Rule`
  - `attest.rules.mfa.mfa_all_users`, `mfa_email`, `mfa_admins`, `mfa_remote_access`: each `Rule`
  - `tests/builders.py`: `NOW`, `GLOBAL_ADMIN`, `EXCHANGE_ADMIN`, `upn`, `user`, `registration`, `policy`, `defaults`, `role`, `device`, `machine`, `mailbox`, `export`, `evidence` (Tasks 8 and 9 use them)

- [ ] **Step 1: Write the shared test builders**

Create `tests/builders.py`:

```python
"""Small constructors for rule tests: evidence built from records, not files."""
from datetime import datetime, timezone

from attest.evidence import Evidence
from attest.model import Export
from attest.readers.defender_machines import Machine
from attest.readers.entra_ca_policies import CaPolicy
from attest.readers.entra_registration import Registration
from attest.readers.entra_role_assignments import RoleAssignment
from attest.readers.entra_security_defaults import SecurityDefaults
from attest.readers.entra_users import User
from attest.readers.intune_devices import IntuneDevice
from attest.readers.veeam_users import VeeamUser

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


def upn(uid):
    return f"{uid}@firm.example"


def user(uid, enabled=True, user_type="Member"):
    return User(uid, upn(uid), uid.title(), enabled, user_type, f"users.json:{uid}")


def registration(uid, registered=True):
    return Registration(uid, upn(uid), registered, f"registration.json:{uid}")


def policy(name="All users MFA", state="enabled", include_users=("All",), exclude_users=(), exclude_groups=(),
           include_roles=(), exclude_roles=(), include_apps=("All",), narrowing=(), requires_mfa=True):
    return CaPolicy(name, name, state, tuple(include_users), tuple(exclude_users), tuple(exclude_groups),
                    tuple(include_roles), tuple(exclude_roles), tuple(include_apps), tuple(narrowing),
                    requires_mfa, f"ca.json:{name}")


def defaults(enabled):
    return SecurityDefaults(enabled, "security-defaults.json:1")


def role(uid, role_id=GLOBAL_ADMIN, kind="user"):
    return RoleAssignment(uid, kind, upn(uid) if kind == "user" else uid, role_id, "/", f"roles.json:{uid}")


def device(n, aad=True):
    return IntuneDevice(f"i{n}", f"LT-{n:02d}", f"d-{n}" if aad else None, "Windows", f"intune.json:{n}")


def machine(n, name=None, aad=True, onboarding="Onboarded", health="Active", last_seen=NOW):
    return Machine(f"m{n}", name or f"lt-{n:02d}.firm.example", f"d-{n}" if aad else None,
                   onboarding, health, last_seen, f"mde.json:{n}")


def mailbox(uid, backed_up=True, when=NOW):
    return VeeamUser(upn(uid), backed_up, when if backed_up else None, f"veeam.json:{uid}")


def export(items, file="export.json", at=NOW):
    return Export(file, at, tuple(items))


def evidence(**exports):
    """Evidence(entra_users=[...], ...) with each list wrapped as an export named <field>.json, taken at NOW."""
    return Evidence(**{name: export(items, file=f"{name}.json") for name, items in exports.items()})
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_rules_mfa.py`:

```python
import pytest

from attest.rules.mfa import mfa_admins, mfa_all_users, mfa_email, mfa_remote_access
from builders import EXCHANGE_ADMIN, GLOBAL_ADMIN, defaults, evidence, policy, registration, role, upn, user

TEAM = ["ann", "bob", "cy"]


def team(**overrides):
    """Three enabled members, all registered, one all-users MFA policy, security defaults off.

    Pass an export as None to leave it out.
    """
    exports = dict(
        entra_users=[user(u) for u in TEAM],
        entra_registration=[registration(u) for u in TEAM],
        entra_ca_policies=[policy()],
        entra_security_defaults=[defaults(False)],
    )
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def admins(**overrides):
    """team() plus Ann as Global Admin, Bob as Exchange Admin, and one policy on those roles."""
    exports = dict(
        entra_role_assignments=[role("ann"), role("bob", role_id=EXCHANGE_ADMIN)],
        entra_ca_policies=[policy("Admins MFA", include_users=(), include_roles=(GLOBAL_ADMIN, EXCHANGE_ADMIN))],
    )
    exports.update(overrides)
    return team(**exports)


def test_backed_when_an_enabled_policy_covers_everyone_and_all_are_registered():
    v = mfa_all_users(team())
    assert v.status == "backed"
    assert v.population == "3 enabled member accounts from entra_users.json"
    assert "'All users MFA'" in v.reason


def test_security_defaults_count_and_the_report_says_what_they_mean():
    v = mfa_all_users(team(entra_ca_policies=None, entra_security_defaults=[defaults(True)]))
    assert v.status == "backed"
    assert "when it judges it necessary" in v.reason


@pytest.mark.parametrize("p, why", [
    (policy(state="enabledForReportingButNotEnforced"), "is enabledForReportingButNotEnforced"),
    (policy(state="disabled"), "is disabled"),
    (policy(narrowing=("locations",)), "applies only under conditions: locations"),
])
def test_a_policy_that_does_not_enforce_is_named_in_a_no_enforcement_gap(p, why):
    v = mfa_all_users(team(entra_ca_policies=[p]))
    assert v.status == "gap"
    assert v.reason.startswith("no enforcement")
    assert why in v.reason


def test_a_policy_that_does_not_require_mfa_is_no_enforcement():
    v = mfa_all_users(team(entra_ca_policies=[policy(requires_mfa=False)]))
    assert (v.status, v.reason.startswith("no enforcement")) == ("gap", True)


def test_an_excluded_account_is_a_cited_gap():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_users=("bob",))]))
    assert v.status == "gap"
    assert v.entities == (upn("bob"),)
    assert "not covered by an enforcing policy: " + upn("bob") in v.reason


def test_an_account_excluded_by_one_policy_but_covered_by_another_is_enforced():
    v = mfa_all_users(team(entra_ca_policies=[policy("A", exclude_users=("bob",)), policy("B")]))
    assert v.status == "backed"


def test_an_excluded_group_makes_every_account_a_gap_naming_the_group():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_groups=("g-travel",))]))
    assert v.status == "gap"
    assert set(v.entities) == {upn(u) for u in TEAM}
    assert "excludes group(s) g-travel, whose members no export lists" in v.reason


def test_an_excluded_role_is_resolved_through_role_assignments():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_roles=(GLOBAL_ADMIN,))],
                           entra_role_assignments=[role("ann")]))
    assert (v.status, v.entities) == ("gap", (upn("ann"),))


def test_an_excluded_role_without_role_assignments_counts_everyone_as_excluded():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_roles=(GLOBAL_ADMIN,))]))
    assert v.status == "gap"
    assert set(v.entities) == {upn(u) for u in TEAM}
    assert "there is no role-assignments export" in v.reason


def test_an_unregistered_account_is_a_cited_gap():
    v = mfa_all_users(team(entra_registration=[registration("ann"), registration("bob", False), registration("cy")]))
    assert (v.status, v.entities) == ("gap", (upn("bob"),))
    assert "not registered for MFA: " + upn("bob") in v.reason


def test_an_account_missing_from_the_registration_export_is_unregistered():
    v = mfa_all_users(team(entra_registration=[registration("ann"), registration("bob")]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))


def test_guests_and_disabled_accounts_are_not_counted_but_are_listed():
    users = [user(u) for u in TEAM] + [user("gus", user_type="Guest"), user("old", enabled=False)]
    v = mfa_all_users(team(entra_users=users))
    assert v.status == "backed"
    assert v.population == ("3 enabled member accounts from entra_users.json; "
                            f"not counted: guests {upn('gus')}; disabled {upn('old')}")


@pytest.mark.parametrize("overrides, why", [
    (dict(entra_users=None), "no users export"),
    (dict(entra_registration=None), "no MFA registration export"),
    (dict(entra_ca_policies=None), "no Conditional Access export"),
    (dict(entra_ca_policies=None, entra_security_defaults=None), "no Conditional Access export"),
    (dict(entra_ca_policies=[policy(state="disabled")], entra_security_defaults=None),
     "no security-defaults export"),
    (dict(entra_users=[user("gus", user_type="Guest")]), "the population is empty"),
])
def test_missing_evidence_is_unchecked_never_backed(overrides, why):
    v = mfa_all_users(team(**overrides))
    assert v.status == "unchecked"
    assert why in v.reason


def test_adversarial_everyone_registered_but_nothing_enforced_is_not_backed():
    v = mfa_all_users(team(entra_ca_policies=[policy(state="enabledForReportingButNotEnforced")]))
    assert v.status == "gap"


def test_adversarial_an_enabled_policy_that_excludes_a_group_is_not_backed():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_groups=("g-1",))]))
    assert v.status == "gap"


def test_email_accepts_a_policy_on_office_365():
    v = mfa_email(team(entra_ca_policies=[policy(include_apps=("Office365",))]))
    assert v.status == "backed"


def test_all_users_does_not_accept_a_policy_on_office_365_alone():
    v = mfa_all_users(team(entra_ca_policies=[policy(include_apps=("Office365",))]))
    assert (v.status, v.reason.startswith("no enforcement")) == ("gap", True)


def test_email_does_not_accept_a_policy_on_one_unrelated_app():
    v = mfa_email(team(entra_ca_policies=[policy(include_apps=("app-123",))]))
    assert v.status == "gap"


def test_admins_are_backed_by_a_policy_on_their_roles():
    v = mfa_admins(admins())
    assert v.status == "backed"
    assert v.population == "2 enabled accounts holding admin roles, from entra_role_assignments.json"


def test_an_admin_excluded_from_the_all_users_policy_but_covered_by_the_admin_policy_is_enforced():
    v = mfa_admins(admins(entra_ca_policies=[
        policy(exclude_users=("ann",)),
        policy("Admins MFA", include_users=(), include_roles=(GLOBAL_ADMIN,)),
    ]))
    assert v.status == "backed"


def test_a_role_policy_does_not_count_for_all_users():
    v = mfa_all_users(admins())
    assert (v.status, v.reason.startswith("no enforcement")) == ("gap", True)


def test_an_admin_role_held_by_a_group_is_unchecked():
    v = mfa_admins(admins(entra_role_assignments=[role("ann"), role("g-admins", kind="group")]))
    assert v.status == "unchecked"
    assert "held by group(s) g-admins" in v.reason


def test_an_admin_missing_from_the_users_export_is_unchecked():
    v = mfa_admins(admins(entra_role_assignments=[role("zed")]))
    assert (v.status, "not in the users export: zed" in v.reason) == ("unchecked", True)


def test_disabled_admins_and_service_principals_are_not_counted():
    users = [user(u) for u in TEAM] + [user("old", enabled=False)]
    v = mfa_admins(admins(entra_users=users, entra_role_assignments=[
        role("ann"), role("old"), role("app-1", kind="servicePrincipal")]))
    assert v.status == "backed"
    assert v.population.startswith("1 enabled accounts holding admin roles")


def test_admins_without_role_assignments_are_unchecked():
    v = mfa_admins(team())
    assert (v.status, "no role-assignments export" in v.reason) == ("unchecked", True)


def test_an_unregistered_admin_is_a_gap():
    v = mfa_admins(admins(entra_registration=[registration("ann"), registration("bob", False), registration("cy")]))
    assert (v.status, v.entities) == ("gap", (upn("bob"),))


def test_remote_access_is_always_unchecked():
    v = mfa_remote_access(team())
    assert v.status == "unchecked"
    assert "VPN or firewall MFA" in v.reason
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_rules_mfa.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.rules'`.

- [ ] **Step 4: Write the shared rule pieces**

Create `attest/rules/__init__.py`:

```python
"""Proof rules, one module per control; the RULES registry arrives with the last rule module (Task 9)."""
```

Create `attest/rules/common.py`:

```python
"""Pieces every proof rule shares: the account population and the never-provable scopes."""
from __future__ import annotations

from collections.abc import Callable

from attest.evidence import Evidence
from attest.model import Export, Verdict
from attest.readers.entra_users import User

Rule = Callable[[Evidence], Verdict]


def unchecked(reason: str) -> Verdict:
    return Verdict("unchecked", reason)


def member_accounts(users: Export[User]) -> tuple[tuple[User, ...], str]:
    """Enabled accounts that are not guests, and a description naming what was left out.

    Only an explicit "Guest" leaves an enabled account out. A null userType is
    counted, because shrinking the population is the one way a rule could back
    too much.
    """
    counted = tuple(u for u in users.items if u.enabled and u.user_type.lower() != "guest")
    guests = [u.upn for u in users.items if u.enabled and u.user_type.lower() == "guest"]
    disabled = [u.upn for u in users.items if not u.enabled]
    description = f"{len(counted)} enabled member accounts from {users.file}"
    left_out = []
    if guests:
        left_out.append("guests " + ", ".join(guests))
    if disabled:
        left_out.append("disabled " + ", ".join(disabled))
    if left_out:
        description += "; not counted: " + "; ".join(left_out)
    return counted, description


def never(reason: str) -> Rule:
    """A scope no export in this stack can prove: unchecked, whatever was exported."""
    def rule(evidence: Evidence) -> Verdict:
        return unchecked(reason)
    return rule
```

- [ ] **Step 5: Write the MFA rules**

Create `attest/rules/mfa.py`:

```python
"""MFA proof rules (spec: Proof rules, MFA, and the planning amendment on what "requires MFA" means).

An account counts as enforced only when an enabled policy that requires MFA,
covers the apps, and has no narrowing condition targets it with no exclusion
that could remove it. Exclusions v1 cannot resolve (any group, or a role with
no role-assignments export) count as removing every account: they can cost a
false gap but can never back a false attestation.
"""
from __future__ import annotations

from typing import Optional

from attest.evidence import Evidence
from attest.model import Export, Verdict
from attest.readers.entra_ca_policies import CaPolicy
from attest.readers.entra_role_assignments import RoleAssignment
from attest.readers.entra_users import User
from attest.rules.common import member_accounts, never, unchecked

ALL_APPS = frozenset({"All"})
EMAIL_APPS = frozenset({"All", "Office365"})
SECURITY_DEFAULTS = ("security defaults are enabled (Microsoft prompts for MFA when it judges it "
                     "necessary, not on every sign-in)")

Roles = Optional[frozenset[str]]


def _roles_by_account(assignments: Optional[Export[RoleAssignment]]) -> Optional[dict[str, frozenset[str]]]:
    """Each user principal's role IDs, or None when there is no role-assignments export."""
    if assignments is None:
        return None
    roles: dict[str, set[str]] = {}
    for a in assignments.items:
        if a.principal_kind == "user":
            roles.setdefault(a.principal_id, set()).add(a.role_id)
    return {account: frozenset(ids) for account, ids in roles.items()}


def _enforces(p: CaPolicy, apps: frozenset[str]) -> bool:
    """Enabled, requires MFA, covers these apps, and nothing narrows when it applies."""
    return p.state == "enabled" and p.requires_mfa and bool(apps & set(p.include_apps)) and not p.narrowing


def _targets(p: CaPolicy, roles: Roles, via_roles: bool) -> bool:
    if "All" in p.include_users:
        return True
    return via_roles and roles is not None and bool(roles & set(p.include_roles))


def _excludes(p: CaPolicy, account: User, roles: Roles) -> bool:
    """Whether p does, or might, exclude this account."""
    if account.id in p.exclude_users or p.exclude_groups:
        return True
    if p.exclude_roles:
        return roles is None or bool(roles & set(p.exclude_roles))
    return False


def _near_miss(p: CaPolicy, apps: frozenset[str]) -> Optional[str]:
    """Why a policy aimed at everyone with MFA still enforces nothing, or None."""
    if not (p.requires_mfa and "All" in p.include_users and apps & set(p.include_apps)):
        return None
    if p.state != "enabled":
        return f"'{p.name}' is {p.state}"
    if p.narrowing:
        return f"'{p.name}' applies only under conditions: {', '.join(p.narrowing)}"
    return None


def _unresolved_exclusions(policies: list[CaPolicy], roles_by: Optional[dict]) -> list[str]:
    notes = []
    for p in policies:
        if p.exclude_groups:
            notes.append(f"'{p.name}' excludes group(s) {', '.join(p.exclude_groups)}, whose members no export lists")
        if p.exclude_roles and roles_by is None:
            notes.append(f"'{p.name}' excludes role(s) {', '.join(p.exclude_roles)}, "
                         "and there is no role-assignments export")
    return notes


def _check(evidence: Evidence, population: tuple[User, ...], population_desc: str,
           apps: frozenset[str], via_roles: bool) -> Verdict:
    """The shared MFA rule: every counted account enforced, and every one registered."""
    if not population:
        return unchecked("the population is empty: " + population_desc)
    registration = evidence.entra_registration
    if registration is None:
        return unchecked("no MFA registration export (entra_registration)")
    defaults, ca = evidence.entra_security_defaults, evidence.entra_ca_policies
    roles_by = _roles_by_account(evidence.entra_role_assignments)
    cited: list[str] = []
    not_enforced: list[User] = []
    notes: list[str] = []
    if defaults is not None and defaults.items[0].enabled:
        how = SECURITY_DEFAULTS
        cited.append(defaults.items[0].cite)
    else:
        if ca is None:
            return unchecked("no Conditional Access export (entra_ca_policies), "
                             "and security defaults are not shown enabled")
        enforcing = [p for p in ca.items
                     if _enforces(p, apps) and ("All" in p.include_users or (via_roles and p.include_roles))]
        if not enforcing:
            if defaults is None:
                return unchecked("no Conditional Access policy enforces MFA here, and there is no "
                                 "security-defaults export (entra_security_defaults) to rule security defaults out")
            misses = [(p, why) for p in ca.items if (why := _near_miss(p, apps))]
            reason = ("no enforcement: no enabled Conditional Access policy requires MFA here "
                      "without narrowing conditions")
            if misses:
                reason += "; " + "; ".join(why for _, why in misses)
            return Verdict("gap", reason, cited=tuple([defaults.items[0].cite] + [p.cite for p, _ in misses]),
                           population=population_desc)
        how = "enforced by " + ", ".join(f"'{p.name}'" for p in enforcing)
        cited += [p.cite for p in enforcing]
        for account in population:
            roles = None if roles_by is None else roles_by.get(account.id, frozenset())
            if not any(_targets(p, roles, via_roles) and not _excludes(p, account, roles) for p in enforcing):
                not_enforced.append(account)
        if not_enforced:
            notes = _unresolved_exclusions(enforcing, roles_by)
    registered = {r.user_id for r in registration.items if r.mfa_registered}
    registration_cites = {r.user_id: r.cite for r in registration.items}
    unregistered = [a for a in population if a.id not in registered]
    if not_enforced or unregistered:
        parts = []
        if not_enforced:
            parts.append("not covered by an enforcing policy: " + ", ".join(a.upn for a in not_enforced))
        parts += notes
        if unregistered:
            parts.append("not registered for MFA: " + ", ".join(a.upn for a in unregistered))
        entities = tuple(dict.fromkeys(a.upn for a in not_enforced + unregistered))
        cited += [a.cite for a in not_enforced]
        cited += [registration_cites.get(a.id, a.cite) for a in unregistered]
        return Verdict("gap", "; ".join(parts), entities, tuple(dict.fromkeys(cited)), population_desc)
    return Verdict("backed", f"all {len(population)} accounts: {how}; every one registered for MFA",
                   cited=tuple(cited) + (registration.file,), population=population_desc)


def mfa_all_users(evidence: Evidence) -> Verdict:
    if evidence.entra_users is None:
        return unchecked("no users export (entra_users)")
    population, description = member_accounts(evidence.entra_users)
    return _check(evidence, population, description, ALL_APPS, via_roles=False)


def mfa_email(evidence: Evidence) -> Verdict:
    if evidence.entra_users is None:
        return unchecked("no users export (entra_users)")
    population, description = member_accounts(evidence.entra_users)
    return _check(evidence, population, description, EMAIL_APPS, via_roles=False)


def mfa_admins(evidence: Evidence) -> Verdict:
    """The population is role holders from the role-assignments export, never the evidence's isAdmin."""
    assignments, users = evidence.entra_role_assignments, evidence.entra_users
    if assignments is None:
        return unchecked("no role-assignments export (entra_role_assignments)")
    if users is None:
        return unchecked("no users export (entra_users)")
    groups = [a for a in assignments.items if a.principal_kind == "group"]
    if groups:
        names = ", ".join(sorted({a.principal_name or a.principal_id for a in groups}))
        return Verdict("unchecked", f"an admin role is held by group(s) {names}, whose members no export lists",
                       cited=tuple(a.cite for a in groups))
    by_id = {u.id: u for u in users.items}
    holder_ids = sorted({a.principal_id for a in assignments.items if a.principal_kind == "user"})
    missing = [i for i in holder_ids if i not in by_id]
    if missing:
        return unchecked("admin role holder(s) not in the users export: " + ", ".join(missing))
    population = tuple(by_id[i] for i in holder_ids if by_id[i].enabled)
    description = f"{len(population)} enabled accounts holding admin roles, from {assignments.file}"
    return _check(evidence, population, description, ALL_APPS, via_roles=True)


mfa_remote_access = never("no export in this stack shows VPN or firewall MFA")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_rules_mfa.py -q`
Expected: `34 passed`.

- [ ] **Step 7: Commit**

```bash
git add attest/rules tests/builders.py tests/test_rules_mfa.py
git commit -F - <<'EOF'
Prove MFA attestations only when every counted account is enforced and registered

Unresolvable exclusions count as excluding everyone, missing exports leave
the attestation unchecked, and the admin population comes from role
assignments rather than the registration report's own isAdmin flag.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 8: EDR proof rule

**Files:**
- Create: `attest/rules/edr.py`
- Test: `tests/test_rules_edr.py`

**Interfaces:**
- Consumes: `Evidence`, `Verdict`, `IntuneDevice`, `Machine`, `unchecked` (Tasks 1-7); `tests/builders.py` `NOW`, `device`, `machine`, `evidence`.
- Produces: `attest.rules.edr.edr_all_endpoints(evidence: Evidence) -> Verdict`; `STALE_AFTER = timedelta(days=7)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rules_edr.py`:

```python
from datetime import timedelta

import pytest

from attest.rules.edr import edr_all_endpoints
from builders import NOW, device, evidence, machine


def fleet(n=3, **overrides):
    """n Intune devices, each matched in Defender by Entra device ID, onboarded, Active, seen at NOW."""
    exports = dict(intune_devices=[device(i) for i in range(1, n + 1)],
                   defender_machines=[machine(i) for i in range(1, n + 1)])
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def test_backed_when_every_intune_device_is_onboarded_active_and_recent():
    v = edr_all_endpoints(fleet())
    assert v.status == "backed"
    assert v.population == "3 devices from intune_devices.json"
    assert "matched by Entra device ID 3" in v.reason


def test_a_device_missing_from_defender_is_a_gap():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2)]))
    assert (v.status, v.entities) == ("gap", ("LT-03",))
    assert "LT-03: not in Defender" in v.reason


@pytest.mark.parametrize("m, why", [
    (machine(3, onboarding="CanBeOnboarded"), "onboarding status CanBeOnboarded"),
    (machine(3, health="Inactive"), "health Inactive"),
    (machine(3, last_seen=NOW - timedelta(days=8)), "last seen 2026-09-23"),
    (machine(3, last_seen=None), "never seen"),
])
def test_an_unonboarded_unhealthy_or_stale_device_is_a_gap(m, why):
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2), m]))
    assert (v.status, v.entities) == ("gap", ("LT-03",))
    assert why in v.reason


def test_seen_exactly_seven_days_before_the_export_is_still_recent():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2),
                                                   machine(3, last_seen=NOW - timedelta(days=7))]))
    assert v.status == "backed"


def test_devices_without_entra_ids_match_by_short_name():
    v = edr_all_endpoints(fleet(intune_devices=[device(1, aad=False)], defender_machines=[machine(1, aad=False)]))
    assert v.status == "backed"
    assert "matched by device name 1" in v.reason


def test_two_defender_machines_with_the_same_short_name_match_neither():
    v = edr_all_endpoints(fleet(intune_devices=[device(1, aad=False)], defender_machines=[
        machine(1, aad=False), machine(9, name="LT-01.other.example", aad=False)]))
    assert (v.status, v.entities) == ("gap", ("LT-01",))


def test_a_defender_only_machine_is_listed_outside_the_population():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2), machine(3),
                                                   machine(9, name="fs-01.firm.example", aad=False)]))
    assert v.status == "backed"
    assert "outside the population): fs-01.firm.example" in v.reason


def test_adversarial_defender_all_healthy_but_intune_has_one_more_device_is_not_backed():
    v = edr_all_endpoints(fleet(n=4, defender_machines=[machine(i) for i in range(1, 4)]))
    assert (v.status, v.entities) == ("gap", ("LT-04",))


@pytest.mark.parametrize("overrides, why", [
    (dict(intune_devices=None), "no Intune managed-devices export"),
    (dict(defender_machines=None), "no Defender device export"),
    (dict(intune_devices=[]), "the population is empty"),
])
def test_missing_evidence_is_unchecked(overrides, why):
    v = edr_all_endpoints(fleet(**overrides))
    assert (v.status, why in v.reason) == ("unchecked", True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_rules_edr.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.rules.edr'`.

- [ ] **Step 3: Write the rule**

Create `attest/rules/edr.py`:

```python
"""EDR proof rule (spec: Proof rules, EDR).

The population is Intune's device list, never Defender's own inventory: a
console only knows the devices already enrolled in it, so "100% healthy" in
Defender alone says nothing about devices it has never seen. A device that
cannot be matched is a gap, so a matching mistake can cost a false gap but
never back a false attestation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from attest.evidence import Evidence
from attest.model import Verdict
from attest.readers.defender_machines import Machine
from attest.readers.intune_devices import IntuneDevice
from attest.rules.common import unchecked

STALE_AFTER = timedelta(days=7)


def _short_name(name: str) -> str:
    """Case-folded, with any domain suffix removed: 'HP-LT-01' and 'hp-lt-01.firm.example' agree."""
    return name.strip().lower().split(".")[0]


def _match(device: IntuneDevice, by_entra_id: dict[str, Machine],
           by_name: dict[str, list[Machine]]) -> tuple[Optional[Machine], str]:
    """The Defender machine for this device by Entra device ID, else by an unambiguous short name."""
    if device.aad_device_id and device.aad_device_id in by_entra_id:
        return by_entra_id[device.aad_device_id], "Entra device ID"
    candidates = by_name.get(_short_name(device.name), [])
    return (candidates[0] if len(candidates) == 1 else None), "device name"


def _problems(machine: Machine, cutoff: datetime) -> list[str]:
    problems = []
    if machine.onboarding.lower() != "onboarded":
        problems.append(f"onboarding status {machine.onboarding}")
    if machine.health.lower() != "active":
        problems.append(f"health {machine.health}")
    if machine.last_seen is None:
        problems.append("never seen")
    elif machine.last_seen < cutoff:
        problems.append(f"last seen {machine.last_seen.date().isoformat()}")
    return problems


def edr_all_endpoints(evidence: Evidence) -> Verdict:
    intune, defender = evidence.intune_devices, evidence.defender_machines
    if intune is None:
        return unchecked("no Intune managed-devices export (intune_devices)")
    if defender is None:
        return unchecked("no Defender device export (defender_machines)")
    if not intune.items:
        return unchecked(f"the population is empty: {intune.file} lists no devices")
    population = f"{len(intune.items)} devices from {intune.file}"
    by_entra_id = {m.aad_device_id: m for m in defender.items if m.aad_device_id}
    by_name: dict[str, list[Machine]] = {}
    for m in defender.items:
        by_name.setdefault(_short_name(m.name), []).append(m)
    cutoff = defender.exported_at - STALE_AFTER
    matched: set[str] = set()
    keys = {"Entra device ID": 0, "device name": 0}
    failing: list[tuple[IntuneDevice, str]] = []
    cited: list[str] = []
    for device in intune.items:
        found, key = _match(device, by_entra_id, by_name)
        if found is None:
            failing.append((device, "not in Defender"))
            cited.append(device.cite)
            continue
        matched.add(found.id)
        keys[key] += 1
        problems = _problems(found, cutoff)
        if problems:
            failing.append((device, ", ".join(problems)))
            cited += [device.cite, found.cite]
    notes = ""
    matched_by = ", ".join(f"{key} {count}" for key, count in keys.items() if count)
    if matched_by:
        notes += f"; matched by {matched_by}"
    outside = [m.name for m in defender.items if m.id not in matched]
    if outside:
        notes += "; in Defender but not Intune (outside the population): " + ", ".join(outside)
    if failing:
        reason = "; ".join(f"{d.name}: {why}" for d, why in failing) + notes
        return Verdict("gap", reason, tuple(d.name for d, _ in failing), tuple(cited), population)
    reason = (f"all {len(intune.items)} devices onboarded to Defender, Active, and seen within 7 days "
              f"of {defender.exported_at.date().isoformat()}" + notes)
    return Verdict("backed", reason, cited=(intune.file, defender.file), population=population)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_rules_edr.py -q`
Expected: `14 passed`.

- [ ] **Step 5: Commit**

```bash
git add attest/rules/edr.py tests/test_rules_edr.py
git commit -F - <<'EOF'
Prove EDR coverage against Intune's device list, not Defender's own

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 9: Backup proof rules and the rule registry

**Files:**
- Create: `attest/rules/backup.py`
- Modify: `attest/rules/__init__.py` (replace its contents)
- Test: `tests/test_rules_backup.py`, `tests/test_rules_registry.py`

**Interfaces:**
- Consumes: `member_accounts`, `never`, `unchecked`, `Rule` (Task 7); `VeeamUser` (Task 4); `load_profile` (Task 6); `tests/builders.py`.
- Produces:
  - `attest.rules.backup.backup_m365_mailboxes`, `backup_servers`, `backup_offline_copy`, `backup_restore_tested`: each `Rule`; `FRESH_WITHIN = timedelta(hours=24)`
  - `attest.rules.RULES: dict[str, Rule]` holding exactly the nine rule names `profile/controls.yaml` uses

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rules_backup.py`:

```python
from datetime import timedelta

import pytest

from attest.readers.veeam_users import VeeamUser
from attest.rules.backup import backup_m365_mailboxes, backup_offline_copy, backup_restore_tested, backup_servers
from builders import NOW, evidence, mailbox, upn, user

TEAM = ["ann", "bob", "cy"]


def office(**overrides):
    """Three enabled members, each with a mailbox backed up at NOW. Pass an export as None to leave it out."""
    exports = dict(entra_users=[user(u) for u in TEAM], veeam_users=[mailbox(u) for u in TEAM])
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def test_backed_when_every_mailbox_was_backed_up_in_the_last_24_hours():
    v = backup_m365_mailboxes(office())
    assert v.status == "backed"
    assert v.population == "3 enabled member accounts from entra_users.json"


@pytest.mark.parametrize("box, why", [
    (mailbox("cy", backed_up=False), "mailbox not backed up"),
    (mailbox("cy", when=NOW - timedelta(hours=25)), "last mailbox backup 2026-09-30T14:00:00+00:00"),
])
def test_an_unprotected_or_stale_mailbox_is_a_gap(box, why):
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"), box]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert why in v.reason


def test_a_backup_exactly_24_hours_old_is_still_fresh():
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"),
                                                  mailbox("cy", when=NOW - timedelta(hours=24))]))
    assert v.status == "backed"


def test_adversarial_an_account_the_veeam_export_omits_is_a_gap():
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob")]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert "no mailbox in the Veeam export" in v.reason


def test_veeam_email_matches_the_upn_case_insensitively():
    boxes = [mailbox("ann"), mailbox("bob"), VeeamUser(upn("cy").upper(), True, NOW, "veeam.json:cy")]
    assert backup_m365_mailboxes(office(veeam_users=boxes)).status == "backed"


def test_guests_are_not_counted():
    v = backup_m365_mailboxes(office(entra_users=[user(u) for u in TEAM] + [user("gus", user_type="Guest")]))
    assert v.status == "backed"


@pytest.mark.parametrize("overrides, why", [
    (dict(entra_users=None), "no users export"),
    (dict(veeam_users=None), "no Veeam user-data export"),
    (dict(entra_users=[user("gus", user_type="Guest")]), "the population is empty"),
])
def test_missing_evidence_is_unchecked(overrides, why):
    v = backup_m365_mailboxes(office(**overrides))
    assert (v.status, why in v.reason) == ("unchecked", True)


@pytest.mark.parametrize("rule, why", [
    (backup_servers, "server backups"),
    (backup_offline_copy, "offline or immutable"),
    (backup_restore_tested, "restore tests"),
])
def test_scopes_no_v1_export_speaks_to_are_always_unchecked(rule, why):
    v = rule(office())
    assert (v.status, why in v.reason) == ("unchecked", True)
```

Create `tests/test_rules_registry.py`:

```python
from attest.profile import load_profile
from attest.rules import RULES


def test_every_rule_the_shipped_profile_names_exists():
    load_profile(rules=RULES)


def test_every_rule_is_named_by_the_profile():
    profile = load_profile()
    assert {rule for scopes in profile.values() for rule in scopes.values()} == set(RULES)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_rules_backup.py tests/test_rules_registry.py -q`
Expected: two collection errors, `ModuleNotFoundError: No module named 'attest.rules.backup'` and `ImportError: cannot import name 'RULES' from 'attest.rules'`.

- [ ] **Step 3: Write the backup rules**

Create `attest/rules/backup.py`:

```python
"""Backup proof rules (spec: Proof rules, Backup).

The population is the same account list the MFA rules use; a mailbox the
Veeam export does not mention is a gap, so an export that lists only the
protected mailboxes cannot back the attestation.
"""
from __future__ import annotations

from datetime import timedelta

from attest.evidence import Evidence
from attest.model import Verdict
from attest.readers.veeam_users import VeeamUser
from attest.rules.common import member_accounts, never, unchecked

FRESH_WITHIN = timedelta(hours=24)
MATCHING = "Veeam Email matched to userPrincipalName"


def backup_m365_mailboxes(evidence: Evidence) -> Verdict:
    users, veeam = evidence.entra_users, evidence.veeam_users
    if users is None:
        return unchecked("no users export (entra_users)")
    if veeam is None:
        return unchecked("no Veeam user-data export (veeam_users)")
    population, description = member_accounts(users)
    if not population:
        return unchecked("the population is empty: " + description)
    by_email: dict[str, VeeamUser] = {}
    for row in veeam.items:
        by_email.setdefault(row.email.strip().lower(), row)
    cutoff = veeam.exported_at - FRESH_WITHIN
    failing: list[tuple[str, str]] = []
    cited: list[str] = []
    for account in population:
        row = by_email.get(account.upn.strip().lower())
        if row is None:
            failing.append((account.upn, "no mailbox in the Veeam export"))
            cited.append(account.cite)
            continue
        if not row.mailbox_backed_up:
            why = "mailbox not backed up"
        elif row.mailbox_backed_up_time is None:
            why = "mailbox never backed up"
        elif row.mailbox_backed_up_time < cutoff:
            why = f"last mailbox backup {row.mailbox_backed_up_time.isoformat()}"
        else:
            continue
        failing.append((account.upn, why))
        cited += [account.cite, row.cite]
    if failing:
        reason = "; ".join(f"{name}: {why}" for name, why in failing) + f"; {MATCHING}"
        return Verdict("gap", reason, tuple(name for name, _ in failing), tuple(cited), description)
    reason = (f"all {len(population)} mailboxes backed up within 24 hours of "
              f"{veeam.exported_at.isoformat()}; {MATCHING}")
    return Verdict("backed", reason, cited=(users.file, veeam.file), population=description)


backup_servers = never("no export in v1 speaks to server backups")
backup_offline_copy = never("no export in v1 speaks to offline or immutable backup copies")
backup_restore_tested = never("no export in v1 speaks to restore tests")
```

- [ ] **Step 4: Write the registry**

Replace the contents of `attest/rules/__init__.py` with:

```python
"""Proof rules by the name the control profile uses (spec: Proof rules)."""
from attest.rules import backup, edr, mfa
from attest.rules.common import Rule

RULES: dict[str, Rule] = {
    "mfa_all_users": mfa.mfa_all_users,
    "mfa_email": mfa.mfa_email,
    "mfa_admins": mfa.mfa_admins,
    "mfa_remote_access": mfa.mfa_remote_access,
    "edr_all_endpoints": edr.edr_all_endpoints,
    "backup_m365_mailboxes": backup.backup_m365_mailboxes,
    "backup_servers": backup.backup_servers,
    "backup_offline_copy": backup.backup_offline_copy,
    "backup_restore_tested": backup.backup_restore_tested,
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_rules_backup.py tests/test_rules_registry.py -q`
Expected: `15 passed`.

- [ ] **Step 6: Run the whole suite**

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: `144 passed`.

- [ ] **Step 7: Commit**

```bash
git add attest/rules tests/test_rules_backup.py tests/test_rules_registry.py
git commit -F - <<'EOF'
Prove mailbox backups against the account list, and register every rule

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 10: Run tags through rules, render the report, and the CLI

**Files:**
- Create: `attest/compare.py`, `attest/report.py`, `attest/__main__.py`
- Test: `tests/test_compare_report_cli.py`

**Interfaces:**
- Consumes: `load_profile`, `PROFILE_PATH` (Task 6); `load_tags` (Task 6); `load_evidence` (Task 5); `RULES` (Task 9); `Tag`, `Verdict`, `AttestError` (Task 1).
- Produces:
  - `attest.compare.check(firm: Path, profile_path: Path = PROFILE_PATH) -> list[tuple[Tag, Verdict]]`
  - `attest.report.render(firm_name: str, results: list[tuple[Tag, Verdict]]) -> str`
  - `attest.__main__.main(argv: list[str] | None = None) -> int`: 0 on success, 2 on `AttestError`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_compare_report_cli.py`:

```python
import json

import pytest

from attest.__main__ import main
from attest.compare import check
from attest.model import Tag, Verdict
from attest.report import render

USERS = {"value": [{"id": "u1", "userPrincipalName": "ann@firm.example", "displayName": "Ann",
                    "accountEnabled": True, "userType": "Member"}]}
REGISTRATION = {"value": [{"id": "u1", "userPrincipalName": "ann@firm.example", "isMfaRegistered": True}]}
CA = {"value": [{"id": "p1", "displayName": "All users MFA", "state": "enabled",
                 "conditions": {"users": {"includeUsers": ["All"]},
                                "applications": {"includeApplications": ["All"]},
                                "clientAppTypes": ["all"]},
                 "grantControls": {"operator": "OR", "builtInControls": ["mfa"]}}]}
SECURITY_DEFAULTS = {"isEnabled": False}

WISP = "All staff use MFA.\nRemote access uses a VPN with MFA.\n"
TAGS = """tags:
  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA., control: mfa, scope: all_users}
  - {id: w2, doc: attest/wisp.txt, quote: Remote access uses a VPN with MFA., control: mfa, scope: remote_access}
"""
MANIFEST = """exports:
  - {file: users.json, reader: entra_users, exported_at: 2026-10-01T15:00:00Z}
  - {file: registration.json, reader: entra_registration, exported_at: 2026-10-01T15:00:00Z}
  - {file: ca.json, reader: entra_ca_policies, exported_at: 2026-10-01T15:00:00Z}
  - {file: sd.json, reader: entra_security_defaults, exported_at: 2026-10-01T15:00:00Z}
"""


@pytest.fixture
def firm(tmp_path):
    root = tmp_path / "tiny"
    (root / "attest").mkdir(parents=True)
    (root / "exports").mkdir()
    (root / "attest" / "wisp.txt").write_text(WISP, encoding="utf-8")
    (root / "tags.yaml").write_text(TAGS, encoding="utf-8")
    (root / "exports" / "manifest.yaml").write_text(MANIFEST, encoding="utf-8")
    exports = {"users.json": USERS, "registration.json": REGISTRATION, "ca.json": CA, "sd.json": SECURITY_DEFAULTS}
    for name, data in exports.items():
        (root / "exports" / name).write_text(json.dumps(data), encoding="utf-8")
    return root


def test_check_runs_each_tag_through_its_scope_rule(firm):
    assert [(t.id, v.status) for t, v in check(firm)] == [("w1", "backed"), ("w2", "unchecked")]


def test_the_report_counts_verdicts_and_shows_each_attestation():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    gap = Verdict("gap", "not registered for MFA: bob@firm.example", ("bob@firm.example",),
                  ("registration.json:2",), "2 enabled member accounts from users.json")
    text = render("tiny", [(tag, gap)])
    assert text.startswith("# Attestation check: tiny\n")
    assert "backed 0, gap 1, unchecked 0" in text
    for line in ["## w1: GAP", "> All staff use MFA.", "- document: `attest/wisp.txt`",
                 "- control: `mfa.all_users`", "- reason: not registered for MFA: bob@firm.example",
                 "- population: 2 enabled member accounts from users.json",
                 "- entities: bob@firm.example", "- cited: `registration.json:2`"]:
        assert line in text


def test_the_cli_prints_and_writes_the_report(firm, capsys):
    assert main(["check", str(firm)]) == 0
    out = capsys.readouterr().out
    assert "backed 1, gap 0, unchecked 1" in out
    assert (firm / "report.md").read_text(encoding="utf-8") == out


def test_the_cli_stops_with_exit_2_on_a_bad_input(firm, capsys):
    bad = TAGS.replace("quote: All staff use MFA.,", "quote: All staff always use MFA.,")
    (firm / "tags.yaml").write_text(bad, encoding="utf-8")
    assert main(["check", str(firm)]) == 2
    assert "attest: tags.yaml: tag 'w1': quote is not an exact substring" in capsys.readouterr().err
    assert not (firm / "report.md").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_compare_report_cli.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'attest.__main__'`.

- [ ] **Step 3: Write compare, report and the CLI**

Create `attest/compare.py`:

```python
"""Run every confirmed tag through its scope's proof rule (spec: Pipeline)."""
from __future__ import annotations

from pathlib import Path

from attest.evidence import load_evidence
from attest.model import Tag, Verdict
from attest.profile import PROFILE_PATH, load_profile
from attest.rules import RULES
from attest.tags import load_tags


def check(firm: Path, profile_path: Path = PROFILE_PATH) -> list[tuple[Tag, Verdict]]:
    """Each tag of firm/tags.yaml, in order, with the verdict its scope's rule gives on firm/exports."""
    profile = load_profile(profile_path, rules=RULES)
    tags = load_tags(firm, profile)
    evidence = load_evidence(Path(firm) / "exports")
    return [(tag, RULES[profile[tag.control][tag.scope]](evidence)) for tag in tags]
```

Create `attest/report.py`:

```python
"""The Markdown report: a count line, then one section per attestation (spec: Pipeline, step 4)."""
from __future__ import annotations

from collections import Counter

from attest.model import Tag, Verdict


def render(firm_name: str, results: list[tuple[Tag, Verdict]]) -> str:
    counts = Counter(v.status for _, v in results)
    lines = [f"# Attestation check: {firm_name}", "",
             f"backed {counts['backed']}, gap {counts['gap']}, unchecked {counts['unchecked']}", ""]
    for tag, verdict in results:
        lines += [f"## {tag.id}: {verdict.status.upper()}", "", f"> {tag.quote}", "",
                  f"- document: `{tag.doc}`",
                  f"- control: `{tag.control}.{tag.scope}`",
                  f"- reason: {verdict.reason}"]
        if verdict.population:
            lines.append(f"- population: {verdict.population}")
        if verdict.entities:
            lines.append("- entities: " + ", ".join(verdict.entities))
        if verdict.cited:
            lines.append("- cited: " + ", ".join(f"`{c}`" for c in verdict.cited))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

Create `attest/__main__.py`:

```python
"""python -m attest check firm/<name>: print the report and write firm/<name>/report.md."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from attest.compare import check
from attest.model import AttestError
from attest.report import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="attest", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check_command = commands.add_parser("check", help="check a firm folder's attestations against its exports")
    check_command.add_argument("firm", type=Path)
    args = parser.parse_args(argv)
    try:
        results = check(args.firm)
    except AttestError as e:
        print(f"attest: {e}", file=sys.stderr)
        return 2
    text = render(args.firm.name, results)
    print(text, end="")
    (args.firm / "report.md").write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_compare_report_cli.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add attest/compare.py attest/report.py attest/__main__.py tests/test_compare_report_cli.py
git commit -F - <<'EOF'
Check a firm folder from the command line and write its Markdown report

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 11: The made-up dev firm, its planted truth, and the Results

**Files:**
- Create: `scripts/build_dev_firm.py`
- Create: `firm/dev/attest/application.txt`, `firm/dev/attest/wisp.txt`, `firm/dev/tags.yaml`, `firm/dev/truth.yaml`
- Generated (commit them): `firm/dev/exports/manifest.yaml` and the eight `firm/dev/exports/*.json`
- Test: `tests/test_dev_firm.py`
- Modify: `docs/superpowers/specs/2026-10-04-attestation-core-design.md` (add a `## Results` section at the end)

**Interfaces:**
- Consumes: `check` (Task 10); every reader's field names (Tasks 2-4).
- Produces: `firm/dev`, which runs clean with `python -m attest check firm/dev`.

- [ ] **Step 1: Write the generator**

Create `scripts/build_dev_firm.py`:

```python
#!/usr/bin/env python3
"""Write firm/dev/exports: the made-up Harbor & Pine CPA tenant, in the API shapes the readers take.

Planted truth (firm/dev/truth.yaml):
- the owner, Dana Whitfield, is excluded from the all-users MFA policy (she travels) and holds no admin role;
- the new hire, Ivan Petrov, has not registered for MFA, and his laptop was never onboarded to Defender;
- Carmen Diaz's mailbox is not backed up by Veeam;
- a pilot policy that would cover everyone is report-only, so it enforces nothing;
- Defender reports Hana Sato's laptop without an Entra device ID, so it must match by name;
- a file server is in Defender but not Intune, so it sits outside the EDR population;
- a disabled former employee and a guest auditor are left out of the population;
- everything else is in order, so the admin-MFA attestations are genuinely backed.

Run from the repo root:  venv/Scripts/python.exe scripts/build_dev_firm.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "firm" / "dev" / "exports"
DOMAIN = "harborpine.example"
EXPORTED_AT = "2026-10-01T15:00:00Z"
LAST_SEEN = "2026-10-01T09:30:00Z"
LAST_BACKUP = "2026-10-01T02:10:00Z"
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


class Person(NamedTuple):
    n: int
    nick: str
    name: str
    enabled: bool
    user_type: str
    mfa_registered: bool
    role: Optional[str]
    laptop: bool
    onboarded: bool
    mailbox_backed_up: bool


PEOPLE = [
    Person(1, "dana.whitfield", "Dana Whitfield", True, "Member", True, None, True, True, True),
    Person(2, "marcus.chen", "Marcus Chen", True, "Member", True, GLOBAL_ADMIN, True, True, True),
    Person(3, "priya.nair", "Priya Nair", True, "Member", True, EXCHANGE_ADMIN, True, True, True),
    Person(4, "tom.reyes", "Tom Reyes", True, "Member", True, None, True, True, True),
    Person(5, "elena.kowalski", "Elena Kowalski", True, "Member", True, None, True, True, True),
    Person(6, "george.okafor", "George Okafor", True, "Member", True, None, True, True, True),
    Person(7, "aisha.rahman", "Aisha Rahman", True, "Member", True, None, True, True, True),
    Person(8, "ben.foster", "Ben Foster", True, "Member", True, None, True, True, True),
    Person(9, "carmen.diaz", "Carmen Diaz", True, "Member", True, None, True, True, False),
    Person(10, "felix.braun", "Felix Braun", True, "Member", True, None, True, True, True),
    Person(11, "hana.sato", "Hana Sato", True, "Member", True, None, True, True, True),
    Person(12, "ivan.petrov", "Ivan Petrov", True, "Member", False, None, True, False, True),
    Person(13, "sam.lowe", "Sam Lowe", False, "Member", False, None, False, False, True),
    Person(14, "audit.partner_auditfirm.example#EXT#", "Audit Partner (guest)", True, "Guest",
           False, None, False, False, False),
]
NO_ENTRA_ID_IN_DEFENDER = {11}


def user_id(n: int) -> str:
    return f"a0000000-0000-4000-8000-{n:012d}"


def device_id(n: int) -> str:
    return f"d0000000-0000-4000-8000-{n:012d}"


def upn(nick: str) -> str:
    return f"{nick}@{DOMAIN}"


def graph_page(context: str, records: list[dict]) -> dict:
    return {"@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#{context}", "value": records}


def users() -> dict:
    return graph_page("users(id,userPrincipalName,displayName,accountEnabled,userType)", [
        {"id": user_id(p.n), "userPrincipalName": upn(p.nick), "displayName": p.name,
         "accountEnabled": p.enabled, "userType": p.user_type}
        for p in PEOPLE
    ])


def registration() -> dict:
    return graph_page("reports/authenticationMethods/userRegistrationDetails", [
        {"id": user_id(p.n), "userPrincipalName": upn(p.nick), "userDisplayName": p.name,
         "userType": p.user_type.lower(), "isAdmin": p.role is not None,
         "isMfaRegistered": p.mfa_registered, "isMfaCapable": p.mfa_registered,
         "methodsRegistered": ["microsoftAuthenticatorPush"] if p.mfa_registered else []}
        for p in PEOPLE
    ])


def _policy(n: int, name: str, state: str, users_condition: dict, grant: list[str],
            client_app_types: tuple[str, ...] = ("all",)) -> dict:
    return {
        "id": f"c0000000-0000-4000-8000-{n:012d}", "displayName": name, "state": state,
        "conditions": {
            "users": {"includeUsers": [], "excludeUsers": [], "includeGroups": [], "excludeGroups": [],
                      "includeRoles": [], "excludeRoles": [], **users_condition},
            "applications": {"includeApplications": ["All"], "excludeApplications": [], "includeUserActions": []},
            "clientAppTypes": list(client_app_types), "locations": None, "platforms": None, "devices": None,
            "signInRiskLevels": [], "userRiskLevels": [], "servicePrincipalRiskLevels": [],
        },
        "grantControls": {"operator": "OR", "builtInControls": grant,
                          "customAuthenticationFactors": [], "termsOfUse": []},
    }


def ca_policies() -> dict:
    return graph_page("identity/conditionalAccess/policies", [
        _policy(1, "Require MFA for all users", "enabled",
                {"includeUsers": ["All"], "excludeUsers": [user_id(1)]}, ["mfa"]),
        _policy(2, "Require MFA for administrators", "enabled",
                {"includeRoles": [GLOBAL_ADMIN, EXCHANGE_ADMIN]}, ["mfa"]),
        _policy(3, "MFA everywhere (pilot)", "enabledForReportingButNotEnforced",
                {"includeUsers": ["All"]}, ["mfa"]),
        _policy(4, "Block legacy authentication", "enabled",
                {"includeUsers": ["All"]}, ["block"], client_app_types=("exchangeActiveSync", "other")),
    ])


def security_defaults() -> dict:
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#policies/"
                          "identitySecurityDefaultsEnforcementPolicy/$entity",
        "id": "00000000-0000-0000-0000-000000000005",
        "displayName": "Security Defaults",
        "description": "Security defaults is a set of basic identity security mechanisms recommended by Microsoft.",
        "isEnabled": False,
    }


def role_assignments() -> dict:
    return graph_page("roleManagement/directory/roleAssignments(principal())", [
        {"id": f"ra-{p.n}", "principalId": user_id(p.n), "roleDefinitionId": p.role, "directoryScopeId": "/",
         "principal": {"@odata.type": "#microsoft.graph.user", "id": user_id(p.n),
                       "userPrincipalName": upn(p.nick), "displayName": p.name}}
        for p in PEOPLE if p.role
    ])


def intune_devices() -> dict:
    return graph_page("deviceManagement/managedDevices", [
        {"id": f"e0000000-0000-4000-8000-{p.n:012d}", "deviceName": f"HP-LT-{p.n:02d}",
         "azureADDeviceId": device_id(p.n), "operatingSystem": "Windows", "userPrincipalName": upn(p.nick)}
        for p in PEOPLE if p.laptop
    ])


def defender_machines() -> dict:
    machines = [
        {"id": f"{p.n:040x}", "computerDnsName": f"hp-lt-{p.n:02d}.{DOMAIN}",
         "aadDeviceId": None if p.n in NO_ENTRA_ID_IN_DEFENDER else device_id(p.n),
         "osPlatform": "Windows11", "onboardingStatus": "Onboarded", "healthStatus": "Active",
         "lastSeen": LAST_SEEN}
        for p in PEOPLE if p.laptop and p.onboarded
    ]
    machines.append({"id": "f" * 40, "computerDnsName": f"hp-fs01.{DOMAIN}", "aadDeviceId": None,
                     "osPlatform": "WindowsServer2022", "onboardingStatus": "Onboarded",
                     "healthStatus": "Active", "lastSeen": LAST_SEEN})
    return {"@odata.context": "https://api.security.microsoft.com/api/$metadata#Machines", "value": machines}


def veeam_users() -> list[dict]:
    return [
        {"Email": upn(p.nick), "DisplayName": p.name, "IsMailboxBackedUp": p.mailbox_backed_up,
         "MailboxBackedUpTime": LAST_BACKUP if p.mailbox_backed_up else None}
        for p in PEOPLE if p.user_type == "Member"
    ]


EXPORTS = {
    "users.json": ("entra_users", users),
    "registration.json": ("entra_registration", registration),
    "ca-policies.json": ("entra_ca_policies", ca_policies),
    "security-defaults.json": ("entra_security_defaults", security_defaults),
    "role-assignments.json": ("entra_role_assignments", role_assignments),
    "intune-devices.json": ("intune_devices", intune_devices),
    "defender-machines.json": ("defender_machines", defender_machines),
    "veeam-users.json": ("veeam_users", veeam_users),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = ["exports:"]
    for file, (reader, build) in EXPORTS.items():
        (OUT / file).write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8", newline="\n")
        manifest.append(f"  - {{file: {file}, reader: {reader}, exported_at: {EXPORTED_AT}}}")
    (OUT / "manifest.yaml").write_text("\n".join(manifest) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(EXPORTS)} exports and manifest.yaml to {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the exports**

Run: `venv/Scripts/python.exe scripts/build_dev_firm.py`
Expected: `wrote 8 exports and manifest.yaml to firm/dev/exports`

- [ ] **Step 3: Write the attestation documents, tags and truth**

Create `firm/dev/attest/application.txt`:

```
Cyber Liability Insurance Application (renewal), Harbor & Pine CPA
Section 4: Security controls

4.1 Do you require multi-factor authentication (MFA) for all employees to access email? Yes
4.2 Do you require MFA for all remote access to your network, including VPN and remote desktop? Yes
4.3 Do you require MFA for all privileged or administrator accounts? Yes
4.4 Do you have endpoint detection and response (EDR) deployed on all endpoints? Yes
4.5 Do you back up Microsoft 365 email at least daily? Yes
4.6 Do you keep backups offline or immutable, separate from your network? Yes
4.7 Have you tested restoring from backup in the last 12 months? No
```

Create `firm/dev/attest/wisp.txt`:

```
Written Information Security Plan, Harbor & Pine CPA

Access control
All staff sign in with multi-factor authentication on every account.
Administrator accounts are protected by multi-factor authentication.
Remote access to the office network requires a VPN connection with multi-factor authentication.

Endpoint protection
Every company laptop runs Microsoft Defender for Business, which is monitored for alerts.

Backup and recovery
Email and files in Microsoft 365 are backed up every night with Veeam.
Backups are kept on immutable storage that cannot be altered or deleted.
```

Create `firm/dev/tags.yaml`:

```yaml
# Confirmed tags for the dev firm. Answer 4.7 ("No") is a disclosure, not an
# attestation, so it is not tagged.
tags:
  - id: app-4.1
    doc: attest/application.txt
    quote: "4.1 Do you require multi-factor authentication (MFA) for all employees to access email? Yes"
    control: mfa
    scope: email
  - id: app-4.2
    doc: attest/application.txt
    quote: "4.2 Do you require MFA for all remote access to your network, including VPN and remote desktop? Yes"
    control: mfa
    scope: remote_access
  - id: app-4.3
    doc: attest/application.txt
    quote: "4.3 Do you require MFA for all privileged or administrator accounts? Yes"
    control: mfa
    scope: admins
  - id: app-4.4
    doc: attest/application.txt
    quote: "4.4 Do you have endpoint detection and response (EDR) deployed on all endpoints? Yes"
    control: edr
    scope: all_endpoints
  - id: app-4.5
    doc: attest/application.txt
    quote: "4.5 Do you back up Microsoft 365 email at least daily? Yes"
    control: backup
    scope: m365_mailboxes
  - id: app-4.6
    doc: attest/application.txt
    quote: "4.6 Do you keep backups offline or immutable, separate from your network? Yes"
    control: backup
    scope: offline_copy
  - id: wisp-mfa-all
    doc: attest/wisp.txt
    quote: "All staff sign in with multi-factor authentication on every account."
    control: mfa
    scope: all_users
  - id: wisp-mfa-admins
    doc: attest/wisp.txt
    quote: "Administrator accounts are protected by multi-factor authentication."
    control: mfa
    scope: admins
  - id: wisp-vpn
    doc: attest/wisp.txt
    quote: "Remote access to the office network requires a VPN connection with multi-factor authentication."
    control: mfa
    scope: remote_access
  - id: wisp-edr
    doc: attest/wisp.txt
    quote: "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts."
    control: edr
    scope: all_endpoints
  - id: wisp-backup
    doc: attest/wisp.txt
    quote: "Email and files in Microsoft 365 are backed up every night with Veeam."
    control: backup
    scope: m365_mailboxes
  - id: wisp-immutable
    doc: attest/wisp.txt
    quote: "Backups are kept on immutable storage that cannot be altered or deleted."
    control: backup
    scope: offline_copy
```

Create `firm/dev/truth.yaml`:

```yaml
# Expected verdicts for firm/dev, in tag order (spec: Testing, Dev firm).
# A gap lists every entity it must cite, and no others.
verdicts:
  app-4.1: {status: gap, entities: [dana.whitfield@harborpine.example, ivan.petrov@harborpine.example]}
  app-4.2: {status: unchecked}
  app-4.3: {status: backed}
  app-4.4: {status: gap, entities: [HP-LT-12]}
  app-4.5: {status: gap, entities: [carmen.diaz@harborpine.example]}
  app-4.6: {status: unchecked}
  wisp-mfa-all: {status: gap, entities: [dana.whitfield@harborpine.example, ivan.petrov@harborpine.example]}
  wisp-mfa-admins: {status: backed}
  wisp-vpn: {status: unchecked}
  wisp-edr: {status: gap, entities: [HP-LT-12]}
  wisp-backup: {status: gap, entities: [carmen.diaz@harborpine.example]}
  wisp-immutable: {status: unchecked}
```

- [ ] **Step 4: Write the regression test**

Create `tests/test_dev_firm.py`:

```python
from pathlib import Path

import yaml

from attest.compare import check

DEV = Path(__file__).resolve().parents[1] / "firm" / "dev"


def _truth():
    return yaml.safe_load((DEV / "truth.yaml").read_text(encoding="utf-8"))["verdicts"]


def test_every_dev_firm_verdict_matches_its_planted_truth():
    results = check(DEV)
    truth = _truth()
    assert [tag.id for tag, _ in results] == list(truth)
    for tag, verdict in results:
        expected = truth[tag.id]
        assert verdict.status == expected["status"], (tag.id, verdict.reason)
        assert sorted(verdict.entities) == sorted(expected.get("entities", [])), (tag.id, verdict.reason)


def test_the_dev_firm_has_zero_false_backed():
    truth = _truth()
    false_backed = [t.id for t, v in check(DEV) if v.status == "backed" and truth[t.id]["status"] != "backed"]
    assert false_backed == []
```

- [ ] **Step 5: Run the dev-firm tests and the whole suite**

Run: `venv/Scripts/python.exe -m pytest tests/test_dev_firm.py -q`
Expected: `2 passed`. If a verdict differs from `truth.yaml`, do not edit the truth to match: the assertion message names the tag and the rule's reason. Find whether the rule or the generated data is wrong, fix that, and say which in the report.

Run: `venv/Scripts/python.exe -m pytest -q`
Expected: `150 passed`.

- [ ] **Step 6: Run the CLI on the dev firm**

Run: `venv/Scripts/python.exe -m attest check firm/dev`
Expected: exit 0; the report starts `# Attestation check: dev` and its count line is `backed 2, gap 6, unchecked 4`; `firm/dev/report.md` is written (it is gitignored).

- [ ] **Step 7: Record the Results in the spec**

Append to the end of `docs/superpowers/specs/2026-10-04-attestation-core-design.md`:

```markdown
## Results

Dev firm (`firm/dev`, Harbor & Pine CPA, generated by
`scripts/build_dev_firm.py`): 12 tagged attestations, `backed 2, gap 6,
unchecked 4`, every verdict matching `truth.yaml` and every gap citing exactly
its planted entities. **Zero false "backed".** Suite: 150 passed.

- Backed: both admin-MFA attestations (4.3 and the WISP line). The owner's
  exclusion from the all-users policy does not touch them because she holds
  no admin role and the admin policy covers both role holders.
- Gap: email and all-staff MFA (owner excluded, new hire unregistered); EDR
  (the new hire's laptop is missing from Defender); mailbox backup (one
  mailbox not backed up).
- Unchecked: VPN MFA (both documents) and immutable backups (both documents),
  as no v1 export speaks to them.

This is a regression check, not a blind test: the builder wrote the firm and
the rules are deterministic. The blind firm of sub-project 2 tests the rules
on data written by someone who has not seen the code.
```

- [ ] **Step 8: Commit**

```bash
git add scripts/build_dev_firm.py firm/dev tests/test_dev_firm.py docs/superpowers/specs/2026-10-04-attestation-core-design.md
git commit -F - <<'EOF'
Add the made-up dev firm with planted gaps, and record its results

The dev firm runs clean against its planted truth: 2 backed, 6 gap,
4 unchecked, with zero false backed.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
