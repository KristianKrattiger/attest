import json
import re
from datetime import datetime, timezone

import pytest

from attest.evidence import Evidence, load_evidence
from attest.model import AttestError
from attest.readers import READERS

USERS = {"value": [{"id": "a0000000-0000-4000-8000-000000000001", "userPrincipalName": "ann@firm.example",
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
    (ONE_USERS_EXPORT + ONE_USERS_EXPORT.replace("exports:\n", ""), "entry 2 repeats reader 'entra_users'"),
    (ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", "someday"), "entry 1 field 'exported_at' is not a time"),
])
def test_a_bad_manifest_stops_the_run(tmp_path, manifest, message):
    exports = _exports(tmp_path, manifest, {"users.json": USERS})
    with pytest.raises(AttestError, match=message):
        load_evidence(exports)


@pytest.mark.parametrize("written", [
    "2026-10-01T15:00:00",  # unquoted: YAML parses it as a naive datetime
    '"2026-10-01T15:00:00"',  # quoted: a string with no offset
    '"2026-10-01 15:00:00"',
    '"2026-10-01"',
])
def test_an_export_time_with_no_utc_offset_stops_the_run(tmp_path, written):
    # Every staleness window is measured from this time; read as UTC, it would let an operator west of UTC
    # pass backups that are a day or more old.
    manifest = ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", written)
    exports = _exports(tmp_path, manifest, {"users.json": USERS})
    with pytest.raises(AttestError, match="manifest.yaml: entry 1 field 'exported_at' has no UTC offset: "):
        load_evidence(exports)


def test_an_offset_less_export_time_is_named_as_written(tmp_path):
    manifest = ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", '"2026-10-01T15:00:00"')
    exports = _exports(tmp_path, manifest, {"users.json": USERS})
    with pytest.raises(AttestError, match=re.escape("has no UTC offset: '2026-10-01T15:00:00'")):
        load_evidence(exports)


@pytest.mark.parametrize("written, expected", [
    ("2026-10-01T10:00:00-05:00", datetime(2026, 10, 1, 15, tzinfo=timezone.utc)),
    ('"2026-10-01T10:00:00-05:00"', datetime(2026, 10, 1, 15, tzinfo=timezone.utc)),
    ("2026-10-01T15:00:00+00:00", datetime(2026, 10, 1, 15, tzinfo=timezone.utc)),
    ('"2026-10-01T15:00:00Z"', datetime(2026, 10, 1, 15, tzinfo=timezone.utc)),
    ('"2026-10-01T20:30:00+05:30"', datetime(2026, 10, 1, 15, tzinfo=timezone.utc)),
])
def test_an_export_time_with_a_utc_offset_is_converted_to_utc(tmp_path, written, expected):
    manifest = ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", written)
    evidence = load_evidence(_exports(tmp_path, manifest, {"users.json": USERS}))
    assert evidence.entra_users.exported_at == expected


NOT_A_MAPPING = "manifest.yaml: expected a mapping with an 'exports' list"


@pytest.mark.parametrize("manifest, message", [
    ("exports: [\n", "manifest.yaml: not valid YAML"),
    ("- a\n", NOT_A_MAPPING),
    ("export:\n  - {file: users.json}\n", NOT_A_MAPPING),
    (ONE_USERS_EXPORT + "extra: 1\n", "manifest.yaml: unknown key 'extra'"),
    ("exports: users.json\n", NOT_A_MAPPING),
    ("exports:\n  - users.json\n", "manifest.yaml: entry 1 must be a mapping"),
    ("exports:\n  - null\n", "manifest.yaml: entry 1 must be a mapping"),
    (ONE_USERS_EXPORT.replace("file: users.json", "file: 5"),
     "manifest.yaml: entry 1 field 'file' must be a non-empty string"),
    (ONE_USERS_EXPORT.replace("reader: entra_users", "reader: [a]"),
     "manifest.yaml: entry 1 field 'reader' must be a non-empty string"),
    (ONE_USERS_EXPORT.replace("file: users.json", 'file: "a\\x00b"'),
     "manifest.yaml: entry 1 file " + re.escape(repr("a\x00b")) + " is not a usable path"),
    (ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", "null"),
     "manifest.yaml: entry 1 field 'exported_at' is not a time"),
    (ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", "2026-13-45T00:00:00Z"),
     "manifest.yaml: contains an impossible date"),
    (ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", "2026-02-30"),
     "manifest.yaml: contains an impossible date"),
    (ONE_USERS_EXPORT.replace("2026-10-01T15:00:00Z", '"9999-12-31T23:59:59-05:00"'),
     "manifest.yaml: entry 1 field 'exported_at' is not a time"),
])
def test_a_malformed_manifest_stops_the_run(tmp_path, manifest, message):
    exports = _exports(tmp_path, manifest, {"users.json": USERS})
    with pytest.raises(AttestError, match=message):
        load_evidence(exports)


def test_a_manifest_that_is_not_utf8_stops_the_run(tmp_path):
    exports = _exports(tmp_path, "", {"users.json": USERS})
    (exports / "manifest.yaml").write_bytes(ONE_USERS_EXPORT.encode("utf-16"))
    with pytest.raises(AttestError, match="manifest.yaml: not UTF-8 text"):
        load_evidence(exports)


@pytest.mark.parametrize("manifest", ["", "exports: []\n"])
def test_a_manifest_listing_nothing_loads_no_evidence(tmp_path, manifest):
    # Nothing exported is a legitimate result: every verdict that needs evidence is unchecked, never backed.
    assert load_evidence(_exports(tmp_path, manifest, {})) == Evidence()


def test_a_file_outside_the_exports_folder_is_refused(tmp_path):
    (tmp_path / "outside.json").write_text(json.dumps(USERS), encoding="utf-8")
    manifest = ONE_USERS_EXPORT.replace("file: users.json", "file: ../outside.json")
    exports = _exports(tmp_path, manifest, {})
    with pytest.raises(AttestError, match="manifest.yaml: entry 1 file '../outside.json' is outside the exports folder"):
        load_evidence(exports)


def test_an_absolute_path_outside_the_exports_folder_is_refused(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(USERS), encoding="utf-8")
    manifest = ONE_USERS_EXPORT.replace("file: users.json", f"file: {json.dumps(outside.as_posix())}")
    exports = _exports(tmp_path, manifest, {})
    message = f"entry 1 file {re.escape(repr(outside.as_posix()))} is outside the exports folder"
    with pytest.raises(AttestError, match=message):
        load_evidence(exports)


def test_a_file_that_is_a_directory_is_refused(tmp_path):
    exports = _exports(tmp_path, ONE_USERS_EXPORT, {})
    (exports / "users.json").mkdir()
    with pytest.raises(AttestError, match="manifest.yaml: entry 1 file 'users.json' is not a file"):
        load_evidence(exports)


def test_a_missing_manifest_stops_the_run(tmp_path):
    (tmp_path / "exports").mkdir()
    with pytest.raises(AttestError, match="manifest.yaml not found"):
        load_evidence(tmp_path / "exports")


def test_a_manifest_with_two_exports_keys_stops_the_run(tmp_path):
    # plain safe_load keeps only the last 'exports' and silently drops the first block's exports
    exports = _exports(tmp_path, ONE_USERS_EXPORT + ONE_USERS_EXPORT, {"users.json": USERS})
    with pytest.raises(AttestError, match="manifest.yaml: duplicate key 'exports' at line 5"):
        load_evidence(exports)
