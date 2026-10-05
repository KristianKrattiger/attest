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
