import json
import os
import re
from pathlib import Path

import pytest

from attest.model import AttestError, Span, Tag
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
        "edr": {"all_endpoints": "edr_all_endpoints", "alert_monitoring": "edr_alert_monitoring"},
        "backup": {"m365_mailboxes": "backup_m365_mailboxes", "m365_files": "backup_m365_files",
                   "servers": "backup_servers", "offline_copy": "backup_offline_copy",
                   "restore_tested": "backup_restore_tested"},
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
    ("quote", "null"), ("quote", "[All staff use MFA.]"), ("quote", "true"),
    ("id", "4.1"), ("id", "41"), ("id", "2026-02-01"), ("id", "null"),
    ("doc", "null"), ("doc", "{a: b}"),
    ("control", "null"), ("control", "false"),
    ("scope", "null"), ("scope", "3"),
])
def test_a_tag_field_that_is_not_a_string_stops_the_run(tmp_path, field, value):
    with pytest.raises(AttestError, match=f"tags.yaml: tag 1 field '{field}' must be a string, got "):
        load_tags(_firm(tmp_path, _tags(_entry(**{field: value}))), PROFILE)


@pytest.mark.parametrize("field, value", [
    ("quote", '""'), ("id", '""'), ("doc", '""'), ("control", '""'), ("scope", '""'),
    # blank is not grounding: a space is a substring of nearly every document
    ("quote", '" "'), ("quote", '"\\t"'), ("quote", '" \\t\\n "'), ("id", '" "'), ("doc", '" "'),
    ("control", '" "'), ("scope", '"\\t"'),
    # invisible format characters (Unicode category Cf) are not text either: BOM, soft hyphen, zero-width space
    ("quote", '"\\ufeff"'), ("quote", '"\\u00ad"'), ("quote", '"\\u200b"'), ("quote", '" \\u200b\\ufeff\\u00ad "'),
    ("id", '"\\u200b"'), ("doc", '"\\ufeff"'), ("control", '"\\u00ad"'), ("scope", '"\\u200b"'),
    # every field needs a letter or digit: punctuation and the other invisibles (U+2800 braille blank, U+3164 Hangul
    # filler, variation selector, combining grapheme joiner) are not text either
    ("quote", '"."'), ("quote", '"-"'), ("quote", '" . - "'), ("quote", '"!!"'), ("quote", '"_"'),
    ("quote", '"\\u2800"'), ("quote", '"\\u3164"'), ("quote", '"\\ufe0f"'), ("quote", '"\\u034f"'),
    ("id", '"-"'), ("id", '"\\u2800"'), ("doc", '"."'), ("control", '"_"'), ("scope", '"\\u3164"'),
    # the Hangul fillers are category Lo (letters) that render as blank, so a plain letter test would let them in
    ("quote", '"\\u115f"'), ("quote", '"\\u1160"'), ("quote", '"\\uffa0"'), ("quote", '" \\u3164\\u3164 "'),
    ("id", '"\\uffa0"'), ("doc", '"\\u115f"'), ("control", '"\\u1160"'),
])
def test_a_tag_field_without_a_letter_or_digit_stops_the_run(tmp_path, field, value):
    with pytest.raises(AttestError, match=f"tags.yaml: tag 1 field '{field}' must contain a letter or digit"):
        load_tags(_firm(tmp_path, _tags(_entry(**{field: value}))), PROFILE)


def test_a_quote_with_punctuation_around_letters_and_digits_still_loads(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"MFA: yes. Always."'), _entry(id="w2", quote='"See 2FA (4.1)"')))
    (firm / "attest" / "wisp.txt").write_text("Policy. MFA: yes. Always.\nSee 2FA (4.1) for detail.\n", encoding="utf-8")
    assert [t.quote for t in load_tags(firm, PROFILE)] == ["MFA: yes. Always.", "See 2FA (4.1)"]


def test_a_quote_in_another_script_still_loads(tmp_path):
    # Hebrew letters (category Lo), three words: "all the employees use"
    firm = _firm(tmp_path, _tags(_entry(quote='"\\u05db\\u05dc \\u05d4\\u05e2\\u05d5\\u05d1\\u05d3\\u05d9\\u05dd '
                                              '\\u05de\\u05e9\\u05ea\\u05de\\u05e9\\u05d9\\u05dd"')))
    words = "\u05db\u05dc \u05d4\u05e2\u05d5\u05d1\u05d3\u05d9\u05dd \u05de\u05e9\u05ea\u05de\u05e9\u05d9\u05dd"
    (firm / "attest" / "wisp.txt").write_text(words + " \u05d1-MFA.\n", encoding="utf-8")
    assert [t.quote for t in load_tags(firm, PROFILE)] == [words]


@pytest.mark.parametrize("field, value", [
    ("id", '" w1"'), ("id", '"w1 "'), ("id", '"w1\\n"'), ("doc", '"attest/wisp.txt "'), ("doc", '"\\tattest/wisp.txt"'),
    ("control", '"mfa "'), ("control", '" mfa"'), ("scope", '" all_users"'), ("scope", '"all_users\\t"'),
    # an invisible format character (Unicode category Cf) at an edge looks like nothing but makes a different value
    ("id", '"w1\\u200b"'), ("id", '"\\u200bw1"'), ("id", '"\\ufeffw1"'), ("id", '"w1\\u00ad"'),
    ("doc", '"attest/wisp.txt\\u200b"'), ("control", '"mfa\\u200b"'), ("scope", '"\\u200ball_users"'),
    ("id", '"w1\\u3164"'), ("scope", '"\\uffa0all_users"'),  # blank Hangul fillers are invisible edges too
])
def test_an_id_doc_control_or_scope_with_edge_whitespace_or_invisibles_stops_the_run(tmp_path, field, value):
    message = f"tags.yaml: tag 1 field '{field}' has leading or trailing whitespace or invisible characters"
    with pytest.raises(AttestError, match=message):
        load_tags(_firm(tmp_path, _tags(_entry(**{field: value}))), PROFILE)


def test_a_quote_with_spaces_at_its_edges_is_stored_as_written(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='" staff use MFA on "')))
    (firm / "attest" / "wisp.txt").write_text("All staff use MFA on every account.\n", encoding="utf-8")
    assert load_tags(firm, PROFILE)[0].quote == " staff use MFA on "


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


@pytest.mark.parametrize("doc", [
    "tags.yaml", "exports/users.json", "report.md", "truth.yaml", "attest/../tags.yaml", "./report.md",
])
def test_a_tag_may_quote_only_an_attestation_document_not_the_checks_own_files(tmp_path, doc):
    firm = _firm(tmp_path, _tags(_entry(doc=doc)))
    (firm / "exports").mkdir()
    for own_file in ("exports/users.json", "report.md", "truth.yaml"):
        (firm / own_file).write_text(WISP, encoding="utf-8")  # each holds the quote, so only the rule can refuse
    assert "All staff use MFA." in (firm / "tags.yaml").read_text(encoding="utf-8")
    with pytest.raises(AttestError, match=f"tags.yaml: tag 'w1': document {re.escape(doc)} is not under attest/"):
        load_tags(firm, PROFILE)


def test_a_document_in_a_subfolder_of_attest_loads(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(doc="attest/policies/wisp.txt")))
    (firm / "attest" / "policies").mkdir()
    (firm / "attest" / "policies" / "wisp.txt").write_text(WISP, encoding="utf-8")
    assert [t.doc for t in load_tags(firm, PROFILE)] == ["attest/policies/wisp.txt"]


def _symlink_or_skip(link, target):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"symlinks are not available here ({type(e).__name__})")


def test_a_symlink_in_attest_to_a_file_outside_the_firm_folder_is_refused(tmp_path):
    firm = tmp_path / "firm"
    firm.mkdir()
    (tmp_path / "outside.txt").write_text(WISP, encoding="utf-8")
    _firm(firm, _tags(_entry(doc="attest/link.txt")))
    _symlink_or_skip(firm / "attest" / "link.txt", tmp_path / "outside.txt")
    with pytest.raises(AttestError, match="tags.yaml: tag 'w1': document attest/link.txt is outside the firm folder"):
        load_tags(firm, PROFILE)


def test_a_symlink_in_attest_to_the_tags_file_is_refused(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(doc="attest/link.txt")))
    _symlink_or_skip(firm / "attest" / "link.txt", firm / "tags.yaml")
    with pytest.raises(AttestError, match="tags.yaml: tag 'w1': document attest/link.txt is not under attest/"):
        load_tags(firm, PROFILE)


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
    ("3:\n  all_users: mfa_all_users\n", "controls.yaml: control name 3 must be a string"),
    ("~:\n  all_users: mfa_all_users\n", "controls.yaml: control name None must be a string"),
    ('"":\n  all_users: mfa_all_users\n', "controls.yaml: control name '' must contain a letter or digit"),
    ("mfa:\n  3: mfa_all_users\n", "controls.yaml: mfa.3 scope name must be a string"),
    ("mfa:\n  ~: mfa_all_users\n", "controls.yaml: mfa.None scope name must be a string"),
    ('mfa:\n  "": mfa_all_users\n', "controls.yaml: mfa.'' scope name must contain a letter or digit"),
    ("mfa:\n  email:\n", "controls.yaml: mfa.email rule name must be a string"),
    ("mfa:\n  email: 5\n", "controls.yaml: mfa.email rule name must be a string"),
    ('mfa:\n  email: ""\n', "controls.yaml: mfa.email rule name must contain a letter or digit"),
    ("mfa:\n  email: [mfa_email]\n", "controls.yaml: mfa.email rule name must be a string"),
    # the same rule as a tag field: some text that is neither whitespace nor an invisible format character
    ('" ":\n  all_users: mfa_all_users\n', "controls.yaml: control name ' ' must contain a letter or digit"),
    ('"\\u200b":\n  all_users: mfa_all_users\n',
     f"controls.yaml: control name {chr(0x200b)!r} must contain a letter or digit"),
    ('mfa:\n  " ": mfa_all_users\n', "controls.yaml: mfa.' ' scope name must contain a letter or digit"),
    ('mfa:\n  "\\t": mfa_all_users\n', f"controls.yaml: mfa.{chr(9)!r} scope name must contain a letter or digit"),
    ('mfa:\n  "\\ufeff": mfa_all_users\n',
     f"controls.yaml: mfa.{chr(0xfeff)!r} scope name must contain a letter or digit"),
    ('mfa:\n  email: " "\n', "controls.yaml: mfa.email rule name must contain a letter or digit"),
    ('mfa:\n  email: "\\u00ad"\n', "controls.yaml: mfa.email rule name must contain a letter or digit"),
    # and it needs a letter or digit: punctuation and the other invisibles are not names either
    ('".":\n  all_users: mfa_all_users\n', "controls.yaml: control name '.' must contain a letter or digit"),
    ('"\\u3164":\n  all_users: mfa_all_users\n',
     f"controls.yaml: control name {chr(0x3164)!r} must contain a letter or digit"),
    ('mfa:\n  "-": mfa_all_users\n', "controls.yaml: mfa.'-' scope name must contain a letter or digit"),
    ('mfa:\n  "\\u2800": mfa_all_users\n',
     f"controls.yaml: mfa.{chr(0x2800)!r} scope name must contain a letter or digit"),
    ('mfa:\n  email: "_"\n', "controls.yaml: mfa.email rule name must contain a letter or digit"),
    ('mfa:\n  email: "\\u3164"\n', "controls.yaml: mfa.email rule name must contain a letter or digit"),
    ('mfa:\n  email: "\\uffa0"\n', "controls.yaml: mfa.email rule name must contain a letter or digit"),
    ('mfa:\n  "\\u115f\\u1160": mfa_all_users\n',
     f"controls.yaml: mfa.{chr(0x115f) + chr(0x1160)!r} scope name must contain a letter or digit"),
])
@pytest.mark.parametrize("rules", [None, {"mfa_all_users", "mfa_email"}])
def test_a_profile_name_that_is_not_a_non_empty_string_stops_the_run(tmp_path, text, message, rules):
    path = tmp_path / "controls.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AttestError, match=re.escape(message)):
        load_profile(path, rules=rules)


def test_a_document_that_starts_with_a_byte_order_mark_still_grounds_a_real_quote(tmp_path):
    firm = _firm(tmp_path, _tags(_entry()))
    (firm / "attest" / "wisp.txt").write_bytes(b"\xef\xbb\xbf" + WISP.encode("utf-8"))
    assert [t.quote for t in load_tags(firm, PROFILE)] == ["All staff use MFA."]


def test_a_byte_order_mark_is_not_document_text(tmp_path):
    # the quote starts with U+FEFF followed by real text: it matches only if the BOM were read as text
    firm = _firm(tmp_path, _tags(_entry(quote='"\\ufeffAll staff use MFA."')))
    (firm / "attest" / "wisp.txt").write_bytes(b"\xef\xbb\xbf" + WISP.encode("utf-8"))
    with pytest.raises(AttestError, match="tag 'w1': quote is not an exact substring of attest/wisp.txt"):
        load_tags(firm, PROFILE)


# Documents are read with universal newlines: CRLF and CR become LF before a quote is matched.

def test_a_quote_with_lf_line_breaks_grounds_in_a_crlf_document(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"use MFA.\\nEvery laptop"')))
    (firm / "attest" / "wisp.txt").write_bytes(WISP.replace("\n", "\r\n").encode("utf-8"))
    assert [t.quote for t in load_tags(firm, PROFILE)] == ["use MFA.\nEvery laptop"]


@pytest.mark.parametrize("quote", ['"use MFA.\\r\\nEvery laptop"', '"use MFA.\\rEvery laptop"'])
def test_a_quote_containing_a_carriage_return_is_refused(tmp_path, quote):
    firm = _firm(tmp_path, _tags(_entry(quote=quote)))
    (firm / "attest" / "wisp.txt").write_bytes(WISP.replace("\n", "\r\n").encode("utf-8"))
    with pytest.raises(AttestError, match="tag 'w1': quote is not an exact substring of attest/wisp.txt"):
        load_tags(firm, PROFILE)


@pytest.mark.parametrize("text, message", [
    (_tags(_entry()) + _tags(_entry(id="w2")), "tags.yaml: duplicate key 'tags' at line 3"),
    ("tags:\n  - " + _entry()[:-1] + ", quote: Every laptop runs EDR.}\n",
     "tags.yaml: duplicate key 'quote' at line 2"),
    ("tags:\n  - id: w1\n    doc: attest/wisp.txt\n    id: w2\n    quote: x\n    control: mfa\n    scope: all_users\n",
     "tags.yaml: duplicate key 'id' at line 4"),
    ("? [a]\n: b\n", "tags.yaml: not valid YAML"),  # an unhashable key is still the base loader's error
])
def test_a_tags_file_with_a_repeated_key_stops_the_run(tmp_path, text, message):
    with pytest.raises(AttestError, match=message):
        load_tags(_firm(tmp_path, text), PROFILE)


@pytest.mark.parametrize("text, message", [
    ("mfa:\n  all_users: a\nmfa:\n  email: b\n", "controls.yaml: duplicate key 'mfa' at line 3"),
    ("mfa:\n  all_users: a\n  all_users: b\n", "controls.yaml: duplicate key 'all_users' at line 3"),
])
def test_a_profile_with_a_repeated_key_stops_the_run(tmp_path, text, message):
    path = tmp_path / "controls.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AttestError, match=message):
        load_profile(path)


def test_the_same_key_in_different_mappings_is_not_a_repeat(tmp_path):
    second = _entry(id="w2", quote="Every laptop runs EDR.", control="edr", scope="all_endpoints")
    assert [t.id for t in load_tags(_firm(tmp_path, _tags(_entry(), second)), PROFILE)] == ["w1", "w2"]


def _fail_reads(monkeypatch, method, name, error):
    real = getattr(Path, method)

    def failing(self, *args, **kwargs):
        if self.name == name:
            raise error
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, method, failing)


@pytest.mark.parametrize("method", ["read_text", "is_file"])
def test_a_tags_file_that_cannot_be_read_stops_the_run(tmp_path, monkeypatch, method):
    firm = _firm(tmp_path, _tags(_entry()))
    _fail_reads(monkeypatch, method, "tags.yaml", PermissionError(13, "Permission denied"))
    with pytest.raises(AttestError, match=r"tags.yaml: could not be read \(Permission denied\)"):
        load_tags(firm, PROFILE)


def test_a_profile_that_cannot_be_read_stops_the_run(tmp_path, monkeypatch):
    path = tmp_path / "controls.yaml"
    path.write_text("mfa:\n  all_users: mfa_all_users\n", encoding="utf-8")
    _fail_reads(monkeypatch, "read_text", "controls.yaml", PermissionError(13, "Permission denied"))
    with pytest.raises(AttestError, match=r"controls.yaml: could not be read \(Permission denied\)"):
        load_profile(path)


@pytest.mark.parametrize("method", ["read_text", "exists", "is_file"])
def test_a_document_that_cannot_be_read_stops_the_run(tmp_path, monkeypatch, method):
    firm = _firm(tmp_path, _tags(_entry()))
    _fail_reads(monkeypatch, method, "wisp.txt", PermissionError(13, "Permission denied"))
    message = r"tags.yaml: tag 'w1': document attest/wisp.txt could not be read \(Permission denied\)"
    with pytest.raises(AttestError, match=message):
        load_tags(firm, PROFILE)


def test_a_tags_file_nested_too_deeply_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="tags.yaml: nested too deeply"):
        load_tags(_firm(tmp_path, "tags: " + "[" * 1000 + "\n"), PROFILE)


def test_a_profile_nested_too_deeply_stops_the_run(tmp_path):
    path = tmp_path / "controls.yaml"
    path.write_text("mfa: " + "[" * 1000 + "\n", encoding="utf-8")
    with pytest.raises(AttestError, match="controls.yaml: nested too deeply"):
        load_profile(path)


# Several tags may share one quote: each claim in it gets its own tag (decision 1, 2026-10-05).

def test_several_tags_may_share_one_quote(tmp_path):
    second = _entry(id="w2", control="edr", scope="all_endpoints")
    tags = load_tags(_firm(tmp_path, _tags(_entry(), second)), PROFILE)
    assert [(t.id, t.doc, t.quote) for t in tags] == [("w1", "attest/wisp.txt", "All staff use MFA."),
                                                     ("w2", "attest/wisp.txt", "All staff use MFA.")]


# A quote must appear exactly once in its document and hold at least three words (decision 2, 2026-10-05).

def test_a_quote_that_appears_twice_in_its_document_is_refused(tmp_path):
    firm = _firm(tmp_path, _tags(_entry()))
    (firm / "attest" / "wisp.txt").write_text("All staff use MFA.\nAs section 2 says, All staff use MFA.\n",
                                              encoding="utf-8")
    message = "tags.yaml: tag 'w1': quote appears 2 times in attest/wisp.txt; quote enough to be unique"
    with pytest.raises(AttestError, match=re.escape(message)):
        load_tags(firm, PROFILE)


def test_overlapping_occurrences_of_a_quote_are_counted(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"MFA on MFA on"')))
    (firm / "attest" / "wisp.txt").write_text("We use MFA on MFA on MFA on everything.\n", encoding="utf-8")
    with pytest.raises(AttestError, match="quote appears 2 times in attest/wisp.txt"):
        load_tags(firm, PROFILE)


def test_occurrences_are_counted_in_the_newline_normalised_text(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"use MFA.\\nEvery laptop"')))
    (firm / "attest" / "wisp.txt").write_bytes((WISP + WISP).replace("\n", "\r\n").encode("utf-8"))
    with pytest.raises(AttestError, match="quote appears 2 times in attest/wisp.txt"):
        load_tags(firm, PROFILE)


@pytest.mark.parametrize("quote", ['"a"', '"MFA: yes."', '"use MFA."', '"MFA - yes ."', '"All  staff"'])
def test_a_quote_of_fewer_than_three_words_is_refused(tmp_path, quote):
    firm = _firm(tmp_path, _tags(_entry(quote=quote)))
    (firm / "attest" / "wisp.txt").write_text("a\nMFA: yes.\nuse MFA.\nMFA - yes .\nAll  staff\n", encoding="utf-8")
    with pytest.raises(AttestError, match=re.escape("tags.yaml: tag 'w1': quote must contain at least three words")):
        load_tags(firm, PROFILE)


def test_a_unique_quote_of_three_words_loads(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"staff use MFA."')))
    assert [t.quote for t in load_tags(firm, PROFILE)] == ["staff use MFA."]


# Grounding records the lines of its document each quote touches (final re-review): attestations group on them.

@pytest.mark.parametrize("line_end", ["\n", "\r\n"])
def test_grounding_records_the_whole_lines_each_quote_touches(tmp_path, line_end):
    second = _entry(id="w2", quote='"use MFA.\\nEvery laptop"', control="edr", scope="all_endpoints")
    firm = _firm(tmp_path, _tags(_entry(quote='"staff use MFA."'), second))
    (firm / "attest" / "wisp.txt").write_bytes(WISP.replace("\n", line_end).encode("utf-8"))
    w1, w2 = load_tags(firm, PROFILE)
    assert w1.span == Span(1, 1, ("All staff use MFA.",))
    assert w2.span == Span(1, 2, ("All staff use MFA.", "Every laptop runs EDR."))


def test_a_quote_ending_in_its_line_s_newline_touches_only_that_line(tmp_path):
    firm = _firm(tmp_path, _tags(_entry(quote='"All staff use MFA.\\n"')))
    assert load_tags(firm, PROFILE)[0].span == Span(1, 1, ("All staff use MFA.",))


def test_a_span_does_not_change_which_tag_a_tag_is():
    assert Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", Span(1, 1, ("x",))) == Tag(
        "w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
