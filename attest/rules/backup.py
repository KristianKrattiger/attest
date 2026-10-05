"""Backup proof rules (spec: Proof rules, Backup).

The population is the same account list the MFA rules use, plus every
disabled account the Veeam export lists (decision 3, 2026-10-05): a shared
mailbox is a disabled user object, and Veeam listing it shows it holds mail.
A mailbox the Veeam export does not mention is a gap, so an export that lists
only the protected mailboxes cannot back the attestation. Veeam rows that
match no account at all are listed with their state and change nothing. The
users and Veeam exports must be taken within 24 hours of each other, or the
verdict is unchecked.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from attest.evidence import Evidence
from attest.model import Verdict
from attest.readers.veeam_users import VeeamUser
from attest.rules.common import exports_apart, member_accounts, never, unchecked

FRESH_WITHIN = timedelta(hours=24)
MATCHING = "Veeam Email matched to userPrincipalName"
KEPT = "disabled accounts Veeam lists"


def _state(row: VeeamUser, exported_at: datetime) -> str:
    """A Veeam row's backup state, for a row no account matches."""
    if not row.mailbox_backed_up:
        return "not backed up"
    if row.mailbox_backed_up_time is None:
        return "never backed up"
    if row.mailbox_backed_up_time > exported_at:
        return "backup time after the export time"
    return f"last backup {row.mailbox_backed_up_time.isoformat()}"


def backup_m365_mailboxes(evidence: Evidence) -> Verdict:
    users, veeam = evidence.entra_users, evidence.veeam_users
    if users is None:
        return unchecked("no users export (entra_users)")
    if veeam is None:
        return unchecked("no Veeam user-data export (veeam_users)")
    if (apart := exports_apart(users, veeam)) is not None:
        return apart
    population, description = member_accounts(users, {row.email.lower() for row in veeam.items}, KEPT)
    if not population:
        return unchecked("the population is empty: " + description)
    by_email: dict[str, VeeamUser] = {}
    for row in veeam.items:
        by_email.setdefault(row.email.lower(), row)
    cutoff = veeam.exported_at - FRESH_WITHIN
    failing: list[tuple[str, str]] = []
    cited: list[str] = []
    for account in population:
        row = by_email.get(account.upn.lower())
        if row is None:
            failing.append((account.upn, "no mailbox in the Veeam export"))
            cited.append(account.cite)
            continue
        if not row.mailbox_backed_up:
            why = "mailbox not backed up"
        elif row.mailbox_backed_up_time is None:
            why = "mailbox never backed up"
        elif row.mailbox_backed_up_time > veeam.exported_at:  # a time from after the export cannot be believed fresh
            why = "mailbox backup time is after the export time"
        elif row.mailbox_backed_up_time < cutoff:
            why = f"last mailbox backup {row.mailbox_backed_up_time.isoformat()}"
        else:
            continue
        failing.append((account.upn, why))
        cited += [account.cite, row.cite]
    accounts = {u.upn.lower() for u in users.items}
    unmatched = [row for row in veeam.items if row.email.lower() not in accounts]
    notes = f"; {MATCHING}"
    if unmatched:
        notes += "; Veeam rows matching no account: " + ", ".join(
            f"{row.email} ({_state(row, veeam.exported_at)})" for row in unmatched)
    if failing:
        reason = "; ".join(f"{name}: {why}" for name, why in failing) + notes
        return Verdict("gap", reason, tuple(name for name, _ in failing), tuple(cited), description)
    reason = (f"all {len(population)} mailboxes backed up within {FRESH_WITHIN // timedelta(hours=1)} hours of "
              f"{veeam.exported_at.isoformat()}" + notes)
    return Verdict("backed", reason, cited=(users.file, veeam.file), population=description)


backup_m365_files = never("no export in v1 shows OneDrive or SharePoint backups")
backup_servers = never("no export in v1 speaks to server backups")
backup_offline_copy = never("no export in v1 speaks to offline or immutable backup copies")
backup_restore_tested = never("no export in v1 speaks to restore tests")
