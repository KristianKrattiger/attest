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
