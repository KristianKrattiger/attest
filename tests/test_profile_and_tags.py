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
