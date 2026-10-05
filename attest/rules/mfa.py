"""MFA proof rules (spec: Proof rules, MFA, and the planning amendment on what "requires MFA" means).

An account counts as enforced only when an enabled policy that requires MFA,
covers the apps, and has no narrowing condition targets it with no exclusion
that could remove it. Exclusions v1 cannot resolve (any group, an external
user type no export identifies, a role held by a principal no export resolves
to accounts, or a role with no role-assignments export) count as removing
every account: they can cost a false gap but can never back a false
attestation. A guest-only exclusion removes just the accounts whose userType
is Guest.

An account the registration export has no row for is missing evidence, not a
failure: the verdict is unchecked unless something else already shows a gap.

The exports a verdict reads (the population's, registration, security
defaults when exported, Conditional Access unless security defaults are on,
and role assignments when a rule reads them) must be taken within 24 hours of
one another, or the verdict is unchecked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from attest.evidence import Evidence
from attest.model import Export, Verdict
from attest.readers.entra_ca_policies import CaPolicy
from attest.readers.entra_registration import Registration
from attest.readers.entra_role_assignments import RoleAssignment
from attest.readers.entra_users import User
from attest.rules.common import exports_apart, member_accounts, never, not_counted, unchecked

ALL_APPS = frozenset({"All"})
EMAIL_APPS = frozenset({"All", "Office365"})
GUEST_ONLY_TYPES = frozenset({"internalguest", "b2bcollaborationguest"})
SECURITY_DEFAULTS = ("security defaults are enabled (Microsoft prompts for MFA when it judges it "
                     "necessary, not on every sign-in)")

# Principal kinds an export resolves: a user is an account, a service principal is known not to be one.
# Any other kind (a group, or a type Graph adds later) may hold accounts no export lists.
RESOLVED_KINDS = frozenset({"user", "servicePrincipal"})


@dataclass(frozen=True)
class Roles:
    """What the role-assignments export says about who holds which role."""

    # Each user's role IDs. A Conditional Access role condition does not apply to an assignment scoped to an
    # administrative unit, so only tenant-wide assignments (scope "/") count for targeting; an assignment
    # at any scope still counts for exclusion, because over-excluding can only cost a false gap.
    tenant_wide: dict[str, frozenset[str]]
    any_scope: dict[str, frozenset[str]]
    unresolved: frozenset[str]  # role IDs held by principals no export resolves to accounts


@dataclass(frozen=True)
class Enforcement:
    """What the verdict says enforces MFA, the rows that show it, and the exports read to say so."""

    how: str
    cited: tuple[str, ...]
    policies: Optional[tuple[CaPolicy, ...]]  # None: security defaults, which cover every account; (): nothing does
    read: tuple[Export, ...]


def _index_roles(assignments: Optional[Export[RoleAssignment]]) -> Optional[Roles]:
    """The roles by account, or None when there is no role-assignments export."""
    if assignments is None:
        return None
    tenant_wide: dict[str, set[str]] = {}
    any_scope: dict[str, set[str]] = {}
    for a in assignments.items:
        if a.principal_kind == "user":
            any_scope.setdefault(a.principal_id, set()).add(a.role_id)
            if a.scope == "/":
                tenant_wide.setdefault(a.principal_id, set()).add(a.role_id)
    unresolved = frozenset(a.role_id for a in assignments.items if a.principal_kind not in RESOLVED_KINDS)
    return Roles({account: frozenset(ids) for account, ids in tenant_wide.items()},
                 {account: frozenset(ids) for account, ids in any_scope.items()}, unresolved)


def _includes(p: CaPolicy, held: frozenset[str], via_roles: bool) -> bool:
    """Whether p includes an account holding these roles: everyone, or (for admins) a role it names."""
    return "All" in p.include_users or (via_roles and bool(held & set(p.include_roles)))


def _is_candidate(p: CaPolicy, apps: frozenset[str], via_roles: bool) -> bool:
    """Whether p is aimed at the accounts a rule counts, with MFA, on these apps; state and narrowing aside."""
    return p.requires_mfa and bool(apps & set(p.include_apps)) and _includes(p, frozenset(p.include_roles), via_roles)


def _enforces(p: CaPolicy, apps: frozenset[str], via_roles: bool) -> bool:
    """A candidate that is enabled and has no condition narrowing when it applies."""
    return _is_candidate(p, apps, via_roles) and p.state == "enabled" and not p.narrowing


def _near_miss(p: CaPolicy, apps: frozenset[str], via_roles: bool) -> Optional[str]:
    """Why a candidate policy still enforces nothing, or None."""
    if not _is_candidate(p, apps, via_roles):
        return None
    if p.state != "enabled":
        return f"'{p.name}' is {p.state}"
    if p.narrowing:
        return f"'{p.name}' applies only under conditions: {', '.join(p.narrowing)}"
    return None


def _excludes_unidentified_types(p: CaPolicy) -> bool:
    """Whether p excludes an external user type that only a guest userType could identify.

    "internalGuest" and "b2bCollaborationGuest" are the guests the users export
    marks. Anything else (an external member type, "unknown", or the legacy
    "GuestsOrExternalUsers") names accounts no v1 export identifies.
    """
    return any(t.lower() not in GUEST_ONLY_TYPES for t in p.exclude_guest_types)


def _excludes(p: CaPolicy, account: User, roles: Optional[Roles]) -> bool:
    """Whether p does, or might, exclude this account."""
    if account.id in p.exclude_users or p.exclude_groups:
        return True
    if p.exclude_guest_types and (_excludes_unidentified_types(p) or account.user_type.lower() == "guest"):
        return True
    if p.exclude_roles:
        if roles is None:
            return True
        excluded = set(p.exclude_roles)
        return bool(roles.unresolved & excluded) or bool(roles.any_scope.get(account.id, frozenset()) & excluded)
    return False


def _unresolved_exclusions(policies: tuple[CaPolicy, ...], roles: Optional[Roles]) -> list[str]:
    notes = []
    for p in policies:
        if p.exclude_groups:
            notes.append(f"'{p.name}' excludes group(s) {', '.join(p.exclude_groups)}, whose members no export lists")
        if _excludes_unidentified_types(p):
            notes.append(f"'{p.name}' excludes external user types {', '.join(p.exclude_guest_types)}, "
                         "which no export identifies")
        if p.exclude_roles and roles is None:
            notes.append(f"'{p.name}' excludes role(s) {', '.join(p.exclude_roles)}, "
                         "and there is no role-assignments export")
        elif roles is not None and roles.unresolved & set(p.exclude_roles):
            held = sorted(roles.unresolved & set(p.exclude_roles))
            notes.append(f"'{p.name}' excludes role(s) {', '.join(held)}, "
                         "held by principals no export resolves to accounts")
    return notes


def _enforcement(evidence: Evidence, apps: frozenset[str], via_roles: bool) -> Enforcement | Verdict:
    """What enforces MFA here (no policies when nothing does), or unchecked when the evidence to say is missing."""
    defaults, ca = evidence.entra_security_defaults, evidence.entra_ca_policies
    if defaults is not None and defaults.items[0].enabled:
        return Enforcement(SECURITY_DEFAULTS, (defaults.items[0].cite,), None, (defaults,))
    if ca is None:
        return unchecked("no Conditional Access export (entra_ca_policies), "
                         "and security defaults are not shown enabled")
    enforcing = tuple(p for p in ca.items if _enforces(p, apps, via_roles))
    if not enforcing and defaults is None:
        return unchecked("no Conditional Access policy enforces MFA here, and there is no "
                         "security-defaults export (entra_security_defaults) to rule security defaults out")
    return Enforcement("enforced by " + ", ".join(f"'{p.name}'" for p in enforcing),
                       tuple(p.cite for p in enforcing), enforcing, (ca,) if defaults is None else (defaults, ca))


def _no_enforcement(evidence: Evidence, apps: frozenset[str], via_roles: bool, population_desc: str) -> Verdict:
    """The gap when no Conditional Access policy enforces MFA here and security defaults are shown off."""
    defaults, ca = evidence.entra_security_defaults, evidence.entra_ca_policies
    misses = [(p, why) for p in ca.items if (why := _near_miss(p, apps, via_roles))]
    reason = "no enforcement: no enabled Conditional Access policy requires MFA here without narrowing conditions"
    if misses:
        reason += "; " + "; ".join(why for _, why in misses)
    return Verdict("gap", reason, cited=tuple([defaults.items[0].cite] + [p.cite for p, _ in misses]),
                   population=population_desc)


def _uncovered(population: tuple[User, ...], policies: tuple[CaPolicy, ...], roles: Optional[Roles],
               via_roles: bool) -> list[User]:
    """The accounts no enforcing policy both includes and leaves alone."""
    def covered(account: User) -> bool:
        held = frozenset() if roles is None else roles.tenant_wide.get(account.id, frozenset())
        return any(_includes(p, held, via_roles) and not _excludes(p, account, roles) for p in policies)
    return [account for account in population if not covered(account)]


def _registration_status(population: tuple[User, ...],
                         registration: Export[Registration]) -> tuple[list[tuple[User, Registration]], list[User]]:
    """The accounts the export shows as not registered (with their rows), and those it has no row for."""
    rows = {r.user_id: r for r in registration.items}
    not_registered = [(a, rows[a.id]) for a in population if a.id in rows and not rows[a.id].mfa_registered]
    no_record = [a for a in population if a.id not in rows]
    return not_registered, no_record


def _check(evidence: Evidence, population: tuple[User, ...], population_desc: str,
           apps: frozenset[str], via_roles: bool, population_exports: tuple[Export, ...]) -> Verdict:
    """The shared MFA rule: every counted account enforced, and every one registered."""
    registration = evidence.entra_registration
    if registration is None:
        return unchecked("no MFA registration export (entra_registration)")
    source = _enforcement(evidence, apps, via_roles)
    if isinstance(source, Verdict):
        return source
    roles = _index_roles(evidence.entra_role_assignments)
    read = [*population_exports, registration, *source.read]
    if roles is not None and any(p.exclude_roles for p in source.policies or ()):  # exclusions read role holders
        read.append(evidence.entra_role_assignments)
    if (apart := exports_apart(*read)) is not None:
        return apart
    if not population:
        return unchecked("the population is empty: " + population_desc)
    if source.policies == ():
        return _no_enforcement(evidence, apps, via_roles, population_desc)
    not_enforced = [] if source.policies is None else _uncovered(population, source.policies, roles, via_roles)
    not_registered, no_record = _registration_status(population, registration)
    if not_enforced or not_registered:
        parts = []
        if not_enforced:
            parts.append("not covered by an enforcing policy: " + ", ".join(a.upn for a in not_enforced))
            parts += _unresolved_exclusions(source.policies, roles)
        if not_registered:
            parts.append("not registered for MFA: " + ", ".join(a.upn for a, _ in not_registered))
        cited = list(source.cited) + [a.cite for a in not_enforced] + [row.cite for _, row in not_registered]
        if no_record:
            parts.append("no registration record for: " + ", ".join(a.upn for a in no_record))
            cited.append(registration.file)
        entities = tuple(dict.fromkeys([a.upn for a in not_enforced] + [a.upn for a, _ in not_registered]))
        return Verdict("gap", "; ".join(parts), entities, tuple(dict.fromkeys(cited)), population_desc)
    if no_record:
        return unchecked("the registration export has no record of: " + ", ".join(a.upn for a in no_record))
    return Verdict("backed", f"all {len(population)} accounts: {source.how}; every one registered for MFA",
                   cited=source.cited + (registration.file,), population=population_desc)


def _member_accounts_rule(evidence: Evidence, apps: frozenset[str]) -> Verdict:
    if evidence.entra_users is None:
        return unchecked("no users export (entra_users)")
    population, description = member_accounts(evidence.entra_users)
    return _check(evidence, population, description, apps, via_roles=False,
                  population_exports=(evidence.entra_users,))


def mfa_all_users(evidence: Evidence) -> Verdict:
    return _member_accounts_rule(evidence, ALL_APPS)


def mfa_email(evidence: Evidence) -> Verdict:
    return _member_accounts_rule(evidence, EMAIL_APPS)


def mfa_admins(evidence: Evidence) -> Verdict:
    """The population is role holders from the role-assignments export, never the evidence's isAdmin."""
    assignments, users = evidence.entra_role_assignments, evidence.entra_users
    if assignments is None:
        return unchecked("no role-assignments export (entra_role_assignments)")
    if users is None:
        return unchecked("no users export (entra_users)")
    unresolved = [a for a in assignments.items if a.principal_kind not in RESOLVED_KINDS]
    if unresolved:
        names = ", ".join(sorted({a.principal_name or a.principal_id for a in unresolved}))
        return Verdict("unchecked", f"an admin role is held by principal(s) {names} that no export resolves to accounts",
                       cited=tuple(a.cite for a in unresolved))
    by_id = {u.id: u for u in users.items}
    holder_ids = sorted({a.principal_id for a in assignments.items if a.principal_kind == "user"})
    missing = [i for i in holder_ids if i not in by_id]
    if missing:
        return unchecked("admin role holder(s) not in the users export: " + ", ".join(missing))
    population = tuple(by_id[i] for i in holder_ids if by_id[i].enabled)
    left_out = []
    disabled = [by_id[i].upn for i in holder_ids if not by_id[i].enabled]
    if disabled:
        left_out.append("disabled " + ", ".join(disabled))
    service_principals = sorted({a.principal_name or a.principal_id
                                 for a in assignments.items if a.principal_kind == "servicePrincipal"})
    if service_principals:
        left_out.append("service principals " + ", ".join(service_principals))
    description = not_counted(f"{len(population)} enabled accounts holding admin roles, from {assignments.file}",
                              left_out)
    return _check(evidence, population, description, ALL_APPS, via_roles=True,
                  population_exports=(assignments, users))


mfa_remote_access = never("no export in this stack shows VPN or firewall MFA")
