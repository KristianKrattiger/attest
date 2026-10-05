import json
import shutil
from pathlib import Path

import pytest
import yaml

from attest.compare import check
from attest.model import AttestError
from attest.report import attestations, combined_status

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


def test_the_two_compound_attestations_are_each_a_gap():
    # Each WISP line that makes two claims carries a tag per claim; the line's verdict is the worst of them.
    compound = {quote: combined_status(v.status for _, v in tagged)
                for _, quote, tagged in attestations(check(DEV)) if len(tagged) > 1}
    assert compound == {
        "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts.": "gap",
        "Email and files in Microsoft 365 are backed up every night with Veeam.": "gap",
    }


# End to end on files: the dev firm healed of every planted gap, then one mutation at a time (final review, test
# health). Each run copies firm/dev, edits its exports, and checks the copy.

DANA = "a0000000-0000-4000-8000-000000000001"
MARCUS = "a0000000-0000-4000-8000-000000000002"
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
DOMAIN = "harborpine.example"
PROVABLE = {"mfa.email", "mfa.all_users", "mfa.admins", "edr.all_endpoints", "backup.m365_mailboxes"}
MFA_ALL_USERS = ("app-4.1", "wisp-mfa-all")
MFA_ADMINS = ("app-4.3", "wisp-mfa-admins")
EDR = ("app-4.4", "wisp-edr")
BACKUP = ("app-4.5", "wisp-backup")


def _edit(file, change):
    """An edit of one export: change(data) alters the parsed JSON in place."""
    def apply(exports):
        path = exports / file
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return apply


def _policy_1_users(**fields):
    return _edit("ca-policies.json", lambda ca: ca["value"][0]["conditions"]["users"].update(fields))


def _row(rows, key, value):
    (row,) = [r for r in rows if r[key] == value]
    return row


def _machine(name, health="Active", aad=None, last_seen="2026-10-01T09:30:00Z"):
    return {"id": name.split(".")[0].ljust(40, "0")[:40], "computerDnsName": f"{name}.{DOMAIN}", "aadDeviceId": aad,
            "osPlatform": "Windows11", "onboardingStatus": "Onboarded", "healthStatus": health, "lastSeen": last_seen}


def _manifest(old, new):
    def apply(exports):
        manifest = exports / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        assert text.count(old) == 1
        manifest.write_text(text.replace(old, new), encoding="utf-8")
    return apply


HEAL = (
    _policy_1_users(excludeUsers=[]),  # Dana no longer excluded
    _edit("registration.json", lambda reg: _row(reg["value"], "id", "a0000000-0000-4000-8000-000000000012").update(
        isMfaRegistered=True)),  # Ivan registered
    _edit("defender-machines.json", lambda mde: mde["value"].append(
        _machine("hp-lt-12", aad="d0000000-0000-4000-8000-000000000012"))),  # Ivan's laptop onboarded
    _edit("veeam-users.json", lambda rows: _row(rows, "Email", f"carmen.diaz@{DOMAIN}").update(
        IsMailboxBackedUp=True, MailboxBackedUpTime="2026-10-01T02:10:00Z")),  # Carmen's mailbox backed up
)


def _copy(tmp_path, *edits):
    firm = tmp_path / "dev"
    shutil.copytree(DEV, firm, ignore=shutil.ignore_patterns("report.md"))
    for apply in edits:
        apply(firm / "exports")
    return firm


def _by_id(results):
    return {tag.id: verdict for tag, verdict in results}


def test_the_healed_dev_firm_is_backed_wherever_a_scope_can_be_proven(tmp_path):
    results = check(_copy(tmp_path, *HEAL))
    scopes = {f"{tag.control}.{tag.scope}" for tag, _ in results}
    assert PROVABLE <= scopes and scopes - PROVABLE  # both kinds of scope are exercised
    for tag, verdict in results:
        expected = "backed" if f"{tag.control}.{tag.scope}" in PROVABLE else "unchecked"
        assert verdict.status == expected, (tag.id, verdict.reason)
    compound = [combined_status(v.status for _, v in tagged) for _, _, tagged in attestations(results)
                if len(tagged) > 1]
    assert compound == ["unchecked", "unchecked"]


def _mail(nick):
    return f"{nick}@{DOMAIN}"


MUTATIONS = {
    "Dana's GUID upper-cased in excludeUsers": (
        _policy_1_users(excludeUsers=[DANA.upper()]),
        {tag: ("gap", [_mail("dana.whitfield")]) for tag in MFA_ALL_USERS}),
    "Dana's GUID braced in excludeUsers": (
        _policy_1_users(excludeUsers=["{" + DANA + "}"]),
        {tag: ("gap", [_mail("dana.whitfield")]) for tag in MFA_ALL_USERS}),
    "Marcus excluded from policy 1": (  # the admin policy still covers him through his role
        _policy_1_users(excludeUsers=[MARCUS]),
        {tag: ("backed", []) for tag in MFA_ADMINS}),
    "the Global Admin role GUID upper-cased in policy 1's excludeRoles": (
        _policy_1_users(excludeRoles=[GLOBAL_ADMIN.upper()]),
        {tag: ("gap", [_mail("marcus.chen")]) for tag in MFA_ALL_USERS}),
    "a recent Inactive Defender-only machine": (
        _edit("defender-machines.json", lambda mde: mde["value"].append(_machine("hp-ws-20", health="Inactive"))),
        {tag: ("gap", [f"hp-ws-20.{DOMAIN}"]) for tag in EDR}),
    "an unprotected disabled account in the Veeam export": (
        _edit("veeam-users.json", lambda rows: _row(rows, "Email", _mail("sam.lowe")).update(
            IsMailboxBackedUp=False, MailboxBackedUpTime=None)),
        {tag: ("gap", [_mail("sam.lowe")]) for tag in BACKUP}),
    "the users export taken 2 days before the others": (
        _manifest("{file: users.json, reader: entra_users, exported_at: 2026-10-01T15:00:00Z}",
                  "{file: users.json, reader: entra_users, exported_at: 2026-09-29T15:00:00Z}"),
        {tag: ("unchecked", []) for tag in MFA_ALL_USERS + MFA_ADMINS + BACKUP}),
    "a Defender lastSeen without an offset": (
        _edit("defender-machines.json", lambda mde: mde["value"][0].update(lastSeen="2026-10-01T09:30:00")),
        "defender-machines.json: row 1 field 'lastSeen' has no UTC offset"),
    "a single-object users export": (
        _edit("users.json", lambda users: users.update(users.pop("value")[0])),
        "users.json: expected a list of records, got a single object"),
}


@pytest.mark.parametrize("mutation", list(MUTATIONS))
def test_a_mutation_of_the_healed_dev_firm_gets_the_verdict_it_should(tmp_path, mutation):
    edit, expected = MUTATIONS[mutation]
    firm = _copy(tmp_path, *HEAL, edit)
    if isinstance(expected, str):
        with pytest.raises(AttestError, match=expected):
            check(firm)
        return
    verdicts = _by_id(check(firm))
    for tag_id, (status, entities) in expected.items():
        verdict = verdicts[tag_id]
        assert (verdict.status, sorted(verdict.entities)) == (status, sorted(entities)), (tag_id, verdict.reason)
