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
