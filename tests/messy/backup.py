"""Backup mess: Veeam's user limit, a paused job, shared mailboxes, SMTP addresses (spec 2026-10-14, catalog)."""
from __future__ import annotations

from datetime import timedelta

from messy.firm import Firm
from messy.operators import BACKUP, Operator, add_account, domain, member, take, utc_text


def _over_limit(firm: Firm) -> bool:
    add_account(firm, "eleventh.user", "Eleventh User", registered=True, mailbox=None)
    return True


def _paused(firm: Firm) -> bool:
    if not take(firm, "veeam-times"):
        return False
    stale = utc_text(firm.exported_at("veeam_users") - timedelta(days=2))
    for r in firm.rows("veeam_users"):
        if r["IsMailboxBackedUp"]:
            r["MailboxBackedUpTime"] = stale
    return True


def _shared_mailbox(firm: Firm) -> bool:
    add_account(firm, "front.desk", "Front Desk (shared)", enabled=False, registered=False, mailbox=(False, None))
    return True


def _shared_mailbox_never_seen(firm: Firm) -> bool:
    add_account(firm, "front.desk", "Front Desk (shared)", enabled=False, registered=False, mailbox=None)
    return True


def _primary_smtp(firm: Firm) -> bool:
    account = member(firm, admin=False, mailbox=True)
    if account is None:
        return False
    upn = account["userPrincipalName"]
    (row,) = [r for r in firm.rows("veeam_users") if r["Email"].lower() == upn.lower()]
    row["Email"] = f"{upn.split('@')[0].split('.')[0]}@mail.{domain(firm)}"
    return True


OPERATORS = (
    Operator("11th user over the Veeam limit", "breaks", _over_limit,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP, twin="real-messy-over-limit"),
    Operator("backup job paused for 2 days", "breaks", _paused,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP, twin="real-messy-paused"),
    Operator("shared mailbox listed but not backed up", "breaks", _shared_mailbox,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP),
    Operator("shared mailbox Veeam never saw", "breaks", _shared_mailbox_never_seen,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP, twin="real-messy-shared-mailbox",
             known="a disabled account Veeam does not list is left out of the backup population "
                   "(attest/rules/backup.py), so a shared mailbox the job never covered is not counted"),
    Operator("Veeam Email is the primary SMTP address", "holds", _primary_smtp,
             alone={"backup.m365_mailboxes": "gap"}, scopes=BACKUP,
             why="the mailbox is backed up; Veeam names it by its SMTP address, not its UPN"),
)
