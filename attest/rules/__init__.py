"""Proof rules by the name the control profile uses (spec: Proof rules)."""
from attest.rules import backup, edr, mfa
from attest.rules.common import Rule

RULES: dict[str, Rule] = {
    "mfa_all_users": mfa.mfa_all_users,
    "mfa_email": mfa.mfa_email,
    "mfa_admins": mfa.mfa_admins,
    "mfa_remote_access": mfa.mfa_remote_access,
    "edr_all_endpoints": edr.edr_all_endpoints,
    "backup_m365_mailboxes": backup.backup_m365_mailboxes,
    "backup_servers": backup.backup_servers,
    "backup_offline_copy": backup.backup_offline_copy,
    "backup_restore_tested": backup.backup_restore_tested,
}
