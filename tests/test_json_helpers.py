import json
import re
from datetime import datetime, timezone

import pytest

from attest.model import AttestError
from attest.readers._json import (
    device_id, load_records, object_id, optional_object, optional_strings, optional_text, parse_time, require,
    require_bool, require_str)


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


@pytest.mark.parametrize("value, shown", [
    ("2026-10-01T02:10:13", "'2026-10-01T02:10:13'"),
    ({"value": "2026-10-01T02:10:13", "DisplayHint": 2}, "'2026-10-01T02:10:13'"),
    (datetime(2026, 10, 1, 2, 10, 13), "datetime.datetime(2026, 10, 1, 2, 10, 13)"),
])
def test_a_time_without_a_utc_offset_is_refused(value, shown):
    # Read as UTC, a local time east of UTC would look fresher than it is.
    with pytest.raises(AttestError, match=re.escape(f"f.json: row 1 field 't' has no UTC offset: {shown}")):
        parse_time(value, "f.json", 1, "t")


def test_an_unreadable_time_stops_the_run():
    with pytest.raises(AttestError, match="field 't' is not a time"):
        parse_time("yesterday", "f.json", 1, "t")


def test_a_file_in_another_encoding_stops_the_run_naming_the_file(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_bytes('[{"displayName": "Zoë"}]'.encode("cp1252"))
    with pytest.raises(AttestError, match="legacy.json: not UTF-8 or UTF-16 text"):
        load_records(path)


def test_an_offset_time_is_converted_to_utc():
    moment = parse_time("2026-10-01T04:10:13+02:00", "f.json", 1, "t")
    assert moment == datetime(2026, 10, 1, 2, 10, 13, tzinfo=timezone.utc)
    assert moment.tzinfo == timezone.utc


def test_an_out_of_range_powershell_date_stops_the_run():
    with pytest.raises(AttestError, match="field 't' is not a time"):
        parse_time("/Date(99999999999999999)/", "f.json", 1, "t")


@pytest.mark.parametrize("value, expected", [
    (None, None),
    ("", None),
    ("00000000-0000-0000-0000-000000000000", None),
    ("D0000000-0000-4000-8000-000000000001", "d0000000-0000-4000-8000-000000000001"),
])
def test_device_id_reads_a_guid_or_not_joined(value, expected):
    assert device_id(value, "f.json", 1, "aadDeviceId") == expected


@pytest.mark.parametrize("value", ["n/a", 12, 0, False, []])
def test_device_id_refuses_anything_that_is_not_a_guid_or_null(value):
    with pytest.raises(AttestError, match="f.json: row 2 field 'aadDeviceId' must be a device GUID or null"):
        device_id(value, "f.json", 2, "aadDeviceId")


@pytest.mark.parametrize("value", ["9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:00"])
def test_a_time_whose_utc_moment_is_out_of_range_stops_the_run(value):
    with pytest.raises(AttestError, match=re.escape(f"f.json: row 1 field 't' is not a time: {value!r}")):
        parse_time(value, "f.json", 1, "t")


def test_parse_time_can_name_the_entry_instead_of_the_row():
    with pytest.raises(AttestError, match=re.escape("manifest.yaml: entry 3 field 'exported_at' has no UTC offset")):
        parse_time("2026-10-01T02:10:13", "manifest.yaml", 3, "exported_at", unit="entry")


def test_a_single_object_is_refused_where_a_list_of_records_is_required(tmp_path):
    with pytest.raises(AttestError, match="export.json: expected a list of records, got a single object"):
        load_records(_write(tmp_path, {"id": "1"}), allow_single=False)
    assert load_records(_write(tmp_path, [{"id": "1"}]), allow_single=False) == [{"id": "1"}]
    assert load_records(_write(tmp_path, {"value": [{"id": "1"}]}), allow_single=False) == [{"id": "1"}]


GUID = "a0000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize("value", [GUID, GUID.upper(), "{" + GUID + "}", "{" + GUID.upper() + "}"])
def test_object_id_reads_any_spelling_of_a_guid_as_its_canonical_lower_case(value):
    assert object_id(value, "f.json", 1, "id") == GUID


@pytest.mark.parametrize("value", ["u1", "", " " + GUID, GUID + " ", 12, None, [GUID]])
def test_object_id_refuses_anything_that_is_not_a_guid(value):
    message = f"f.json: row 2 field 'id' must be an object GUID, got {value!r}"
    with pytest.raises(AttestError, match=re.escape(message)):
        object_id(value, "f.json", 2, "id")


def test_the_optional_helpers_read_null_as_empty():
    assert (optional_text(None, "f.json", 1, "x"), optional_strings(None, "f.json", 1, "x"),
            optional_object(None, "f.json", 1, "x")) == ("", (), {})
    assert (optional_text("a", "f.json", 1, "x"), optional_strings(["a"], "f.json", 1, "x"),
            optional_object({"a": 1}, "f.json", 1, "x")) == ("a", ("a",), {"a": 1})


@pytest.mark.parametrize("helper, value, kind", [
    (optional_text, 5, "a string"), (optional_text, ["a"], "a string"),
    (optional_strings, "a", "a list of strings"), (optional_strings, [1], "a list of strings"),
    (optional_object, [], "an object"), (optional_object, "a", "an object"),
])
def test_the_optional_helpers_refuse_the_wrong_type(helper, value, kind):
    with pytest.raises(AttestError, match=re.escape(f"f.json: row 4 field 'x' must be {kind}, got {value!r}")):
        helper(value, "f.json", 4, "x")
