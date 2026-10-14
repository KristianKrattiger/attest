"""What an operator is, and the helpers operators share to find and add records (spec 2026-10-14, Operators).

An operator edits a firm's exports in memory to make one real-world mess, and declares what that mess does to the
truth:

- "breaks": the truth fails for the scopes in `scopes`; no tag of those scopes may come out backed.
- "holds": the truth is unchanged for the scopes in `scopes`, the ones the mess is about; `why` says why. The rules
  may still lose sight of it there, which the long run measures as noise cost.
- "inert": serialization only; every verdict must equal the seed's.
- "stops": a refusal the docs promise; the run must stop with `stop` in its message.

`alone` is the status of each provable scope that changes when the operator is the only one applied to the seed;
every other provable scope stays backed. For a "holds" operator it pins today's behaviour, false gaps included, so a
change is noticed. `may_stop` is set only once a stop on realistic data has been decided and the refusal kept.
`twin` names the real capture under firm/lab that shows the same mess. A "breaks" operator with `known` set is a
false backed found and not yet fixed: its alone test is a strict expected failure and it is left out of
combinations, until the rule is fixed in its own change.

An operator that adds a record clones a seed record of the same kind and changes what the mess changes, so the
fields stay the ones the real export has. It edits only entities no earlier operator touched (`take`), and returns
False when the firm has nothing left for it; it is then skipped.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, Mapping, Optional

from messy.firm import Firm

Effect = Literal["breaks", "holds", "inert", "stops"]
PROVABLE = ("mfa.email", "mfa.all_users", "mfa.admins", "edr.all_endpoints", "backup.m365_mailboxes")
ALL_USERS = frozenset({"mfa.all_users", "mfa.email"})
ADMINS = frozenset({"mfa.admins"})
ALL_MFA = ALL_USERS | ADMINS
EDR = frozenset({"edr.all_endpoints"})
BACKUP = frozenset({"backup.m365_mailboxes"})
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


@dataclass(frozen=True)
class Operator:
    name: str
    effect: Effect
    edit: Callable[[Firm], bool] = field(repr=False, compare=False)
    alone: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    scopes: frozenset[str] = field(default=frozenset(), repr=False, compare=False)
    why: str = field(default="", repr=False, compare=False)
    stop: str = field(default="", repr=False, compare=False)
    may_stop: str = field(default="", repr=False, compare=False)
    twin: str = field(default="", repr=False, compare=False)
    known: str = field(default="", repr=False, compare=False)


def new_id(label: str) -> str:
    """A GUID that is the same on every run and cannot collide with a seed's."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"attest-messy:{label}"))


def machine_id(label: str) -> str:
    """A Defender machine ID: 40 hex digits, the same on every run."""
    return new_id(label).replace("-", "") + "00000000"


def utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def take(firm: Firm, key: str) -> bool:
    """Mark an entity touched; False when an earlier operator already touched it."""
    if key in firm.touched:
        return False
    firm.touched.add(key)
    return True


def members(firm: Firm) -> list[dict]:
    """Enabled accounts that are not guests, in export order."""
    return [u for u in firm.rows("entra_users") if u["accountEnabled"] and (u.get("userType") or "") != "Guest"]


def domain(firm: Firm) -> str:
    return members(firm)[0]["userPrincipalName"].split("@")[1]


def admin_ids(firm: Firm) -> set[str]:
    return {a["principalId"] for a in firm.rows("entra_role_assignments")
            if a["principal"]["@odata.type"] == "#microsoft.graph.user"}


def member(firm: Firm, admin: bool, mailbox: bool = False) -> Optional[dict]:
    """The first untouched enabled member that holds an admin role or not, with a Veeam row when asked; now touched."""
    admins = admin_ids(firm)
    veeam = {r["Email"].lower() for r in firm.rows("veeam_users")}
    for u in members(firm):
        if (u["id"] in admins) == admin and (not mailbox or u["userPrincipalName"].lower() in veeam):
            if take(firm, f"user:{u['id']}"):
                return u
    return None


def paired(firm: Firm) -> Optional[tuple[dict, dict]]:
    """The first untouched Intune device and the one Defender machine that shares its Entra device ID; now touched."""
    machines = firm.rows("defender_machines")
    for device in firm.rows("intune_devices"):
        aad = (device.get("azureADDeviceId") or "").lower()
        matching = [m for m in machines if (m.get("aadDeviceId") or "").lower() == aad]
        if aad and len(matching) == 1 and take(firm, f"device:{device['id']}"):
            return device, matching[0]
    return None


def clone(rows: list[dict], **changes) -> dict:
    """A copy of the first record with these changes, appended to rows."""
    record = copy.deepcopy(rows[0])
    record.update(changes)
    rows.append(record)
    return record


def veeam_fresh(firm: Firm) -> str:
    """A backup time 10 hours before the Veeam export: fresh."""
    return utc_text(firm.exported_at("veeam_users") - timedelta(hours=10))


def add_account(firm: Firm, label: str, name: str, *, enabled: bool = True, registered: Optional[bool] = True,
                mailbox: Optional[tuple[bool, Optional[str]]] = None) -> dict:
    """A new account cloned from the seed's first: its user row; its registration row, unless registered is None (no
    row yet); and its Veeam row, unless mailbox is None, else (backed up, backup time)."""
    upn = f"{label}@{domain(firm)}"
    uid = new_id(label)
    user = clone(firm.rows("entra_users"), id=uid, userPrincipalName=upn, displayName=name, accountEnabled=enabled,
                 userType="Member")
    if registered is not None:
        row = clone(firm.rows("entra_registration"), id=uid, userPrincipalName=upn, userDisplayName=name,
                    isMfaRegistered=registered, isMfaCapable=registered, isAdmin=False)
        if not registered:
            row["methodsRegistered"] = []
    if mailbox is not None:
        backed_up, when = mailbox
        clone(firm.rows("veeam_users"), Email=upn, DisplayName=name, IsMailboxBackedUp=backed_up,
              MailboxBackedUpTime=when)
    return user


def assign_role(firm: Firm, label: str, principal: dict, role: str = GLOBAL_ADMIN) -> None:
    """A tenant-wide role assignment to this principal (the expanded `principal` object Graph returns)."""
    clone(firm.rows("entra_role_assignments"), id=new_id(f"assignment:{label}"), principalId=principal["id"],
          roleDefinitionId=role, directoryScopeId="/", principal=principal)
