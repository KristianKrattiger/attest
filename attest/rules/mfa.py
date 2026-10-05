"""MFA proof rules (spec: Proof rules, MFA, and the planning amendment on what "requires MFA" means).

An account counts as enforced only when an enabled policy that requires MFA,
covers the apps, and has no narrowing condition targets it with no exclusion
that could remove it. Exclusions v1 cannot resolve (any group, or a role with
no role-assignments export) count as removing every account: they can cost a
false gap but can never back a false attestation.
"""
from __future__ import annotations

from typing import Optional

from attest.evidence import Evidence
from attest.model import Export, Verdict
from attest.readers.entra_ca_policies import CaPolicy
from attest.readers.entra_role_assignments import RoleAssignment
from attest.readers.entra_users import User
from attest.rules.common import member_accounts, never, unchecked

ALL_APPS = frozenset({"All"})
EMAIL_APPS = frozenset({"All", "Office365"})
SECURITY_DEFAULTS = ("security defaults are enabled (Microsoft prompts for MFA when it judges it "
                     "necessary, not on every sign-in)")

Roles = Optional[frozenset[str]]


def _roles_by_account(assignments: Optional[Export[RoleAssignment]]) -> Optional[dict[str, frozenset[str]]]:
    """Each user principal's role IDs, or None when there is no role-assignments export."""
    if assignments is None:
        return None
    roles: dict[str, set[str]] = {}
    for a in assignments.items:
        if a.principal_kind == "user":
            roles.setdefault(a.principal_id, set()).add(a.role_id)
    return {account: frozenset(ids) for account, ids in roles.items()}


def _enforces(p: CaPolicy, apps: frozenset[str]) -> bool:
    """Enabled, requires MFA, covers these apps, and nothing narrows when it applies."""
    return p.state == "enabled" and p.requires_mfa and bool(apps & set(p.include_apps)) and not p.narrowing


def _targets(p: CaPolicy, roles: Roles, via_roles: bool) -> bool:
    if "All" in p.include_users:
        return True
    return via_roles and roles is not None and bool(roles & set(p.include_roles))


def _excludes(p: CaPolicy, account: User, roles: Roles) -> bool:
    """Whether p does, or might, exclude this account."""
    if account.id in p.exclude_users or p.exclude_groups:
        return True
    if p.exclude_roles:
        return roles is None or bool(roles & set(p.exclude_roles))
    return False


def _near_miss(p: CaPolicy, apps: frozenset[str]) -> Optional[str]:
    """Why a policy aimed at everyone with MFA still enforces nothing, or None."""
    if not (p.requires_mfa and "All" in p.include_users and apps & set(p.include_apps)):
        return None
    if p.state != "enabled":
        return f"'{p.name}' is {p.state}"
    if p.narrowing:
        return f"'{p.name}' applies only under conditions: {', '.join(p.narrowing)}"
    return None


def _unresolved_exclusions(policies: list[CaPolicy], roles_by: Optional[dict]) -> list[str]:
    notes = []
    for p in policies:
        if p.exclude_groups:
            notes.append(f"'{p.name}' excludes group(s) {', '.join(p.exclude_groups)}, whose members no export lists")
        if p.exclude_roles and roles_by is None:
            notes.append(f"'{p.name}' excludes role(s) {', '.join(p.exclude_roles)}, "
                         "and there is no role-assignments export")
    return notes


def _check(evidence: Evidence, population: tuple[User, ...], population_desc: str,
           apps: frozenset[str], via_roles: bool) -> Verdict:
    """The shared MFA rule: every counted account enforced, and every one registered."""
    if not population:
        return unchecked("the population is empty: " + population_desc)
    registration = evidence.entra_registration
    if registration is None:
        return unchecked("no MFA registration export (entra_registration)")
    defaults, ca = evidence.entra_security_defaults, evidence.entra_ca_policies
    roles_by = _roles_by_account(evidence.entra_role_assignments)
    cited: list[str] = []
    not_enforced: list[User] = []
    notes: list[str] = []
    if defaults is not None and defaults.items[0].enabled:
        how = SECURITY_DEFAULTS
        cited.append(defaults.items[0].cite)
    else:
        if ca is None:
            return unchecked("no Conditional Access export (entra_ca_policies), "
                             "and security defaults are not shown enabled")
        enforcing = [p for p in ca.items
                     if _enforces(p, apps) and ("All" in p.include_users or (via_roles and p.include_roles))]
        if not enforcing:
            if defaults is None:
                return unchecked("no Conditional Access policy enforces MFA here, and there is no "
                                 "security-defaults export (entra_security_defaults) to rule security defaults out")
            misses = [(p, why) for p in ca.items if (why := _near_miss(p, apps))]
            reason = ("no enforcement: no enabled Conditional Access policy requires MFA here "
                      "without narrowing conditions")
            if misses:
                reason += "; " + "; ".join(why for _, why in misses)
            return Verdict("gap", reason, cited=tuple([defaults.items[0].cite] + [p.cite for p, _ in misses]),
                           population=population_desc)
        how = "enforced by " + ", ".join(f"'{p.name}'" for p in enforcing)
        cited += [p.cite for p in enforcing]
        for account in population:
            roles = None if roles_by is None else roles_by.get(account.id, frozenset())
            if not any(_targets(p, roles, via_roles) and not _excludes(p, account, roles) for p in enforcing):
                not_enforced.append(account)
        if not_enforced:
            notes = _unresolved_exclusions(enforcing, roles_by)
    registered = {r.user_id for r in registration.items if r.mfa_registered}
    registration_cites = {r.user_id: r.cite for r in registration.items}
    unregistered = [a for a in population if a.id not in registered]
    if not_enforced or unregistered:
        parts = []
        if not_enforced:
            parts.append("not covered by an enforcing policy: " + ", ".join(a.upn for a in not_enforced))
        parts += notes
        if unregistered:
            parts.append("not registered for MFA: " + ", ".join(a.upn for a in unregistered))
        entities = tuple(dict.fromkeys(a.upn for a in not_enforced + unregistered))
        cited += [a.cite for a in not_enforced]
        cited += [registration_cites.get(a.id, a.cite) for a in unregistered]
        return Verdict("gap", "; ".join(parts), entities, tuple(dict.fromkeys(cited)), population_desc)
    return Verdict("backed", f"all {len(population)} accounts: {how}; every one registered for MFA",
                   cited=tuple(cited) + (registration.file,), population=population_desc)


def mfa_all_users(evidence: Evidence) -> Verdict:
    if evidence.entra_users is None:
        return unchecked("no users export (entra_users)")
    population, description = member_accounts(evidence.entra_users)
    return _check(evidence, population, description, ALL_APPS, via_roles=False)


def mfa_email(evidence: Evidence) -> Verdict:
    if evidence.entra_users is None:
        return unchecked("no users export (entra_users)")
    population, description = member_accounts(evidence.entra_users)
    return _check(evidence, population, description, EMAIL_APPS, via_roles=False)


def mfa_admins(evidence: Evidence) -> Verdict:
    """The population is role holders from the role-assignments export, never the evidence's isAdmin."""
    assignments, users = evidence.entra_role_assignments, evidence.entra_users
    if assignments is None:
        return unchecked("no role-assignments export (entra_role_assignments)")
    if users is None:
        return unchecked("no users export (entra_users)")
    groups = [a for a in assignments.items if a.principal_kind == "group"]
    if groups:
        names = ", ".join(sorted({a.principal_name or a.principal_id for a in groups}))
        return Verdict("unchecked", f"an admin role is held by group(s) {names}, whose members no export lists",
                       cited=tuple(a.cite for a in groups))
    by_id = {u.id: u for u in users.items}
    holder_ids = sorted({a.principal_id for a in assignments.items if a.principal_kind == "user"})
    missing = [i for i in holder_ids if i not in by_id]
    if missing:
        return unchecked("admin role holder(s) not in the users export: " + ", ".join(missing))
    population = tuple(by_id[i] for i in holder_ids if by_id[i].enabled)
    description = f"{len(population)} enabled accounts holding admin roles, from {assignments.file}"
    return _check(evidence, population, description, ALL_APPS, via_roles=True)


mfa_remote_access = never("no export in this stack shows VPN or firewall MFA")
