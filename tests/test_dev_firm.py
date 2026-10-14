import shutil
from pathlib import Path

import pytest
import yaml

from attest.__main__ import main
from attest.compare import check, run
from attest.model import AttestError
from attest.report import attestations, combined_status, render
from messy.heal import DOMAIN, HEAL
from messy.heal import edit as _edit
from messy.heal import machine as _machine
from messy.heal import row as _row

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
PROVABLE = {"mfa.email", "mfa.all_users", "mfa.admins", "edr.all_endpoints", "backup.m365_mailboxes"}
MFA_ALL_USERS = ("app-4.1", "wisp-mfa-all")
MFA_ADMINS = ("app-4.3", "wisp-mfa-admins")
EDR = ("app-4.4", "wisp-edr")
BACKUP = ("app-4.5", "wisp-backup")


def _policy_1_users(**fields):
    return _edit("ca-policies.json", lambda ca: ca["value"][0]["conditions"]["users"].update(fields))


def _manifest(old, new):
    def apply(exports):
        manifest = exports / "manifest.yaml"
        text = manifest.read_text(encoding="utf-8")
        assert text.count(old) == 1
        manifest.write_text(text.replace(old, new), encoding="utf-8")
    return apply


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


# A compound sentence tagged by clause is still one attestation (final re-review probes N1 and N1b): its section quotes
# the whole line under the worst verdict of its tags, and no section shows a fragment.

def _requote(quotes):
    """An edit of the copy's tags.yaml: each tag named in quotes gets that quote."""
    def apply(exports):
        path = exports.parent / "tags.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for tag in data["tags"]:
            tag["quote"] = quotes.get(tag["id"], tag["quote"])
        assert set(quotes) <= {tag["id"] for tag in data["tags"]}
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return apply


BACKUP_LINE = "Email and files in Microsoft 365 are backed up every night with Veeam."
EDR_LINE = "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts."
CLAUSES = {
    "N1": ({"wisp-backup-files": "and files in Microsoft 365", "wisp-edr-alerts": "which is monitored for alerts."},
           {"wisp-backup, wisp-backup-files": BACKUP_LINE, "wisp-edr, wisp-edr-alerts": EDR_LINE}),
    "N1b": ({"wisp-backup": "are backed up every night with Veeam.",
             "wisp-backup-files": "Email and files in Microsoft 365"},
            {"wisp-backup, wisp-backup-files": BACKUP_LINE, "wisp-edr, wisp-edr-alerts": EDR_LINE}),
}


@pytest.mark.parametrize("probe", list(CLAUSES))
def test_a_compound_sentence_tagged_by_clause_is_one_unchecked_attestation_quoting_its_whole_line(tmp_path, probe):
    quotes, compound = CLAUSES[probe]
    firm = _copy(tmp_path, *HEAL, _requote(quotes))
    text = render("dev", *run(firm))
    lines = {line for doc in ("application.txt", "wisp.txt")
             for line in (firm / "attest" / doc).read_text(encoding="utf-8").splitlines()}
    sections = {section.splitlines()[0]: section.splitlines() for section in text.split("\n## ")[1:]}
    for heading, section in sections.items():
        quoted = [line[2:] for line in section if line.startswith("> ")]
        assert quoted and all(q in lines for q in quoted), heading  # whole lines only, never a fragment
    for ids, line in compound.items():
        assert f"> {line}" in sections[f"{ids}: UNCHECKED"]
    assert "\nbacked 6, gap 0, unchecked 6\n" in text


def _redoc(docs):
    """An edit of the copy's tags.yaml: each tag named in docs gets that document path."""
    def apply(exports):
        path = exports.parent / "tags.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for tag in data["tags"]:
            tag["doc"] = docs.get(tag["id"], tag["doc"])
        assert set(docs) <= {tag["id"] for tag in data["tags"]}
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return apply


def test_a_compound_line_s_second_tag_naming_its_document_another_way_stops_the_run(tmp_path, capsys):
    # Third review G1: under its own spelling of wisp.txt, the files tag was a separate attestation, and the backup
    # line came out BACKED on its own.
    firm = _copy(tmp_path, *HEAL, _redoc({"wisp-backup-files": "attest/./wisp.txt"}))
    assert main(["check", str(firm)]) == 2
    error = "tags.yaml: tag 'wisp-backup-files': document attest/./wisp.txt must be written as 'attest/wisp.txt'"
    assert f"attest: {error}" in capsys.readouterr().err
    report = (firm / "report.md").read_text(encoding="utf-8")
    assert report == f"# Attestation check: dev\n\nCHECK FAILED: {error}\n"
    assert "BACKED" not in report
