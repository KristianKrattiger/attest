from dataclasses import replace
from datetime import timedelta

import pytest

from attest.readers.veeam_users import VeeamUser
from attest.rules import backup
from attest.rules.backup import (
    backup_m365_files, backup_m365_mailboxes, backup_offline_copy, backup_restore_tested, backup_servers)
from builders import NOW, evidence, mailbox, upn, user

TEAM = ["ann", "bob", "cy"]


def office(**overrides):
    """Three enabled members, each with a mailbox backed up at NOW. Pass an export as None to leave it out."""
    exports = dict(entra_users=[user(u) for u in TEAM], veeam_users=[mailbox(u) for u in TEAM])
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def test_backed_when_every_mailbox_was_backed_up_in_the_last_24_hours():
    v = backup_m365_mailboxes(office())
    assert v.status == "backed"
    assert v.population == "3 enabled member accounts from entra_users.json"


@pytest.mark.parametrize("box, why", [
    (mailbox("cy", backed_up=False), "mailbox not backed up"),
    (mailbox("cy", when=NOW - timedelta(hours=25)), "last mailbox backup 2026-09-30T14:00:00+00:00"),
])
def test_an_unprotected_or_stale_mailbox_is_a_gap(box, why):
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"), box]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert why in v.reason


def test_a_backup_exactly_24_hours_old_is_still_fresh():
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"),
                                                  mailbox("cy", when=NOW - timedelta(hours=24))]))
    assert v.status == "backed"


def test_a_backup_time_exactly_at_the_export_time_is_still_fresh():
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"), mailbox("cy", when=NOW)]))
    assert v.status == "backed"


def test_a_backup_time_after_the_export_time_is_a_gap_not_fresh():
    # A time later than the export it came from cannot be true, so it cannot show a backup within 24 hours.
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"),
                                                  mailbox("cy", when=NOW + timedelta(hours=1))]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert "mailbox backup time is after the export time" in v.reason


def test_a_mailbox_flagged_backed_up_with_no_time_is_a_gap():
    box = VeeamUser(email=upn("cy"), mailbox_backed_up=True, mailbox_backed_up_time=None, cite="veeam.json:cy")
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"), box]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert "mailbox never backed up" in v.reason


def test_a_mailbox_not_backed_up_is_a_gap_whatever_its_time_says():
    box = VeeamUser(email=upn("cy"), mailbox_backed_up=False, mailbox_backed_up_time=NOW, cite="veeam.json:cy")
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"), box]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert "mailbox not backed up" in v.reason


def test_a_disabled_account_is_not_counted():
    users = [user(u) for u in TEAM] + [user("dan", enabled=False)]
    v = backup_m365_mailboxes(office(entra_users=users))  # no mailbox for dan in the Veeam export
    assert v.status == "backed"
    assert v.population == "3 enabled member accounts from entra_users.json; not counted: disabled dan@firm.example"


def test_the_window_in_the_reasons_follows_the_constant(monkeypatch):
    monkeypatch.setattr(backup, "FRESH_WITHIN", timedelta(hours=36))
    assert "within 36 hours of" in backup_m365_mailboxes(office()).reason


def test_adversarial_an_account_the_veeam_export_omits_is_a_gap():
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob")]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert "no mailbox in the Veeam export" in v.reason


def test_veeam_email_matches_the_upn_case_insensitively():
    boxes = [mailbox("ann"), mailbox("bob"), VeeamUser(upn("cy").upper(), True, NOW, "veeam.json:cy")]
    assert backup_m365_mailboxes(office(veeam_users=boxes)).status == "backed"


def test_a_padded_veeam_email_is_not_the_account_it_resembles():
    # The reader refuses a padded address, so one can only arrive here built by hand; matching on the address as
    # written (case folded) means it never stands in for the account, and the first row cannot decide.
    padded = VeeamUser(upn("cy") + " ", True, NOW, "veeam.json:cy")
    v = backup_m365_mailboxes(office(veeam_users=[mailbox("ann"), mailbox("bob"), padded]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))
    assert "no mailbox in the Veeam export" in v.reason


def test_a_padded_account_upn_is_not_matched_to_the_mailbox_it_resembles():
    padded = replace(user("cy"), upn=upn("cy") + " ")
    v = backup_m365_mailboxes(office(entra_users=[user("ann"), user("bob"), padded]))
    assert (v.status, v.entities) == ("gap", (upn("cy") + " ",))
    assert "no mailbox in the Veeam export" in v.reason


def test_guests_are_not_counted():
    v = backup_m365_mailboxes(office(entra_users=[user(u) for u in TEAM] + [user("gus", user_type="Guest")]))
    assert v.status == "backed"


@pytest.mark.parametrize("overrides, why", [
    (dict(entra_users=None), "no users export"),
    (dict(veeam_users=None), "no Veeam user-data export"),
    (dict(entra_users=[user("gus", user_type="Guest")]), "the population is empty"),
])
def test_missing_evidence_is_unchecked(overrides, why):
    v = backup_m365_mailboxes(office(**overrides))
    assert (v.status, why in v.reason) == ("unchecked", True)


@pytest.mark.parametrize("rule, why", [
    (backup_servers, "server backups"),
    (backup_offline_copy, "offline or immutable"),
    (backup_restore_tested, "restore tests"),
])
def test_scopes_no_v1_export_speaks_to_are_always_unchecked(rule, why):
    v = rule(office())
    assert (v.status, why in v.reason) == ("unchecked", True)


def test_onedrive_and_sharepoint_backups_are_always_unchecked():
    v = backup_m365_files(office())
    assert (v.status, v.reason) == ("unchecked", "no export in v1 shows OneDrive or SharePoint backups")
