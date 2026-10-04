import json
import re

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


# Malformed tags.yaml and controls.yaml stop the run as AttestError, never a raw Python exception.

GOOD_FIELDS = {"id": "w1", "doc": "attest/wisp.txt", "quote": "All staff use MFA.",
               "control": "mfa", "scope": "all_users"}


def _entry(**changes):
    return "{" + ", ".join(f"{name}: {value}" for name, value in {**GOOD_FIELDS, **changes}.items()) + "}"


def _tags(*entries):
    return "tags:\n" + "".join(f"  - {entry}\n" for entry in entries)


@pytest.mark.parametrize("tags_yaml, message", [
    ("tags: [\n", "tags.yaml: not valid YAML"),
    ("tags:\n  - {id: w1\n", "tags.yaml: not valid YAML"),
    ("tags:\n\t- x\n", "tags.yaml: not valid YAML"),
    (_tags(_entry(id="2026-02-30")), "tags.yaml: contains an impossible date or value"),
    (_tags(_entry(id="2026-13-45T00:00:00Z")), "tags.yaml: contains an impossible date or value"),
])
def test_a_tags_file_that_is_not_readable_yaml_stops_the_run(tmp_path, tags_yaml, message):
    with pytest.raises(AttestError, match=message):
        load_tags(_firm(tmp_path, tags_yaml), PROFILE)


def test_a_tags_file_that_is_not_utf8_stops_the_run(tmp_path):
    firm = _firm(tmp_path, "")
    (firm / "tags.yaml").write_bytes(b"tags:\n  - {id: caf\xe9}\n")
    with pytest.raises(AttestError, match="tags.yaml: not UTF-8 text"):
        load_tags(firm, PROFILE)


@pytest.mark.parametrize("tags_yaml", [
    "- not: a mapping\n",
    "just a string\n",
    "other: 1\n",
    "tags:\n",
    "tags: oops\n",
    "tags: {w1: x}\n",
])
def test_a_tags_file_of_the_wrong_shape_stops_the_run(tmp_path, tags_yaml):
    with pytest.raises(AttestError, match=r"tags\.yaml: expected a mapping with a 'tags' list"):
        load_tags(_firm(tmp_path, tags_yaml), PROFILE)


def test_an_unknown_top_level_key_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="tags.yaml: unknown key 'tag'"):
        load_tags(_firm(tmp_path, "tags: []\ntag: []\n"), PROFILE)


@pytest.mark.parametrize("tags_yaml", ["", "# nothing attested yet\n", "tags: []\n", "{tags: []}\n"])
def test_a_firm_with_no_attestations_loads_no_tags(tmp_path, tags_yaml):
    assert load_tags(_firm(tmp_path, tags_yaml), PROFILE) == []


@pytest.mark.parametrize("entry", ["just a string", "[w1, attest/wisp.txt]", "null", "42"])
def test_a_tag_that_is_not_a_mapping_stops_the_run(tmp_path, entry):
    with pytest.raises(AttestError, match="tags.yaml: tag 2 must be a mapping"):
        load_tags(_firm(tmp_path, _tags(_entry(), entry)), PROFILE)


@pytest.mark.parametrize("field, value", [
    ("quote", "null"), ("quote", '""'), ("quote", "[All staff use MFA.]"), ("quote", "true"),
    ("id", "4.1"), ("id", "41"), ("id", "2026-02-01"), ("id", '""'), ("id", "null"),
    ("doc", "null"), ("doc", '""'), ("doc", "{a: b}"),
    ("control", "null"), ("control", "false"), ("control", '""'),
    ("scope", "null"), ("scope", "3"), ("scope", '""'),
    # blank is not grounding: a space is a substring of nearly every document
    ("quote", '" "'), ("quote", '"\\t"'), ("quote", '" \\t\\n "'), ("id", '" "'), ("doc", '" "'),
    ("control", '" "'), ("scope", '"\\t"'),
])
def test_a_tag_field_that_is_not_a_non_empty_string_stops_the_run(tmp_path, field, value):
    with pytest.raises(AttestError, match=f"tags.yaml: tag 1 field '{field}' must be a non-empty string"):
        load_tags(_firm(tmp_path, _tags(_entry(**{field: value}))), PROFILE)


def test_a_quote_with_spaces_at_its_edges_is_stored_as_written(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='" staff use "')))
    assert load_tags(firm, PROFILE)[0].quote == " staff use "


def test_a_quote_whose_edge_spaces_are_not_in_the_document_is_refused(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"All staff use MFA. "')))  # the document has a newline after it
    with pytest.raises(AttestError, match="tag 'w1': quote is not an exact substring of attest/wisp.txt"):
        load_tags(firm, PROFILE)


def test_quoted_and_dashed_ids_are_strings_and_load(tmp_path):
    second = _entry(id="app-4.1", quote="Every laptop runs EDR.", control="edr", scope="all_endpoints")
    firm = _firm(tmp_path, _tags(_entry(id='"4.1"'), second))
    assert [t.id for t in load_tags(firm, PROFILE)] == ["4.1", "app-4.1"]


def test_an_unknown_key_in_a_tag_stops_the_run(tmp_path):
    entry = _entry(confirmed_by="ann")
    with pytest.raises(AttestError, match="tags.yaml: tag 1 has unknown key 'confirmed_by'"):
        load_tags(_firm(tmp_path, _tags(entry)), PROFILE)


def test_a_document_outside_the_firm_folder_is_refused(tmp_path):
    firm = tmp_path / "firm"
    firm.mkdir()
    (tmp_path / "outside.txt").write_text(WISP, encoding="utf-8")
    _firm(firm, _tags(_entry(doc="../outside.txt")))
    with pytest.raises(AttestError, match=r"tags.yaml: tag 'w1': document \.\./outside\.txt is outside the firm folder"):
        load_tags(firm, PROFILE)


def test_an_absolute_document_path_outside_the_firm_folder_is_refused(tmp_path):
    firm = tmp_path / "firm"
    firm.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text(WISP, encoding="utf-8")
    _firm(firm, _tags(_entry(doc=json.dumps(outside.as_posix()))))
    message = f"tags.yaml: tag 'w1': document {re.escape(outside.as_posix())} is outside the firm folder"
    with pytest.raises(AttestError, match=message):
        load_tags(firm, PROFILE)


def test_a_roundabout_path_that_stays_inside_the_firm_folder_still_loads(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(doc="attest/../attest/wisp.txt")))
    assert [t.id for t in load_tags(firm, PROFILE)] == ["w1"]


def test_a_document_that_is_a_directory_is_refused(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(doc="attest")))
    with pytest.raises(AttestError, match="tags.yaml: tag 'w1': document attest is not a file"):
        load_tags(firm, PROFILE)


def test_a_document_path_with_a_nul_is_refused(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(doc='"attest/wisp\\x00.txt"')))
    message = "tags.yaml: tag 'w1': document " + re.escape("attest/wisp\x00.txt") + " is not a usable path"
    with pytest.raises(AttestError, match=message):
        load_tags(firm, PROFILE)


def test_a_document_that_is_not_utf8_is_refused(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(doc="attest/scan.txt")))
    (firm / "attest" / "scan.txt").write_bytes(b"All staff use MFA.\xff\xfe\n")
    with pytest.raises(AttestError, match="tags.yaml: tag 'w1': document attest/scan.txt is not UTF-8 text"):
        load_tags(firm, PROFILE)


@pytest.mark.parametrize("text, message", [
    ("mfa: [\n", "controls.yaml: not valid YAML"),
    ("mfa:\n  all_users: a\n bad: b\n", "controls.yaml: not valid YAML"),
    ("2026-02-30:\n  all_users: a\n", "controls.yaml: contains an impossible date or value"),
])
def test_a_profile_that_is_not_readable_yaml_stops_the_run(tmp_path, text, message):
    path = tmp_path / "controls.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AttestError, match=message):
        load_profile(path)


def test_a_profile_that_is_not_utf8_stops_the_run(tmp_path):
    path = tmp_path / "controls.yaml"
    path.write_bytes(b"mfa:\n  caf\xe9: mfa_all_users\n")
    with pytest.raises(AttestError, match="controls.yaml: not UTF-8 text"):
        load_profile(path)


def test_a_missing_profile_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="controls.yaml not found"):
        load_profile(tmp_path / "controls.yaml")


@pytest.mark.parametrize("text, message", [
    ("3:\n  all_users: mfa_all_users\n", "controls.yaml: control name 3 must be a non-empty string"),
    ("~:\n  all_users: mfa_all_users\n", "controls.yaml: control name None must be a non-empty string"),
    ('"":\n  all_users: mfa_all_users\n', "controls.yaml: control name '' must be a non-empty string"),
    ("mfa:\n  3: mfa_all_users\n", "controls.yaml: mfa.3 scope name must be a non-empty string"),
    ("mfa:\n  ~: mfa_all_users\n", "controls.yaml: mfa.None scope name must be a non-empty string"),
    ('mfa:\n  "": mfa_all_users\n', "controls.yaml: mfa.'' scope name must be a non-empty string"),
    ("mfa:\n  email:\n", "controls.yaml: mfa.email rule name must be a non-empty string"),
    ("mfa:\n  email: 5\n", "controls.yaml: mfa.email rule name must be a non-empty string"),
    ('mfa:\n  email: ""\n', "controls.yaml: mfa.email rule name must be a non-empty string"),
    ("mfa:\n  email: [mfa_email]\n", "controls.yaml: mfa.email rule name must be a non-empty string"),
])
@pytest.mark.parametrize("rules", [None, {"mfa_all_users", "mfa_email"}])
def test_a_profile_name_that_is_not_a_non_empty_string_stops_the_run(tmp_path, text, message, rules):
    path = tmp_path / "controls.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AttestError, match=re.escape(message)):
        load_profile(path, rules=rules)
