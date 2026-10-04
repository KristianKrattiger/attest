"""Conditional Access policies: Microsoft Graph `GET /identity/conditionalAccess/policies`.

Fields: conditionalAccessPolicy and its conditionalAccessConditionSet,
conditionalAccessUsers, conditionalAccessApplications and
conditionalAccessGrantControls, from
https://learn.microsoft.com/en-us/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0

Two judgments live here because both are about what the policy JSON says,
not about any firm: whether the grant requires MFA, and which conditions
narrow when the policy applies. Both err toward "does not count": a policy
wrongly counted could back an attestation that is false, while a policy
wrongly discounted can only cost a false gap.

Narrowing is an allow-list that fails closed: only the condition keys named
here are understood, and any other key that carries a value narrows, as
"unknown condition <key>". The users the policy leaves out are recorded for
the rules, including the guest and external user exclusion
(`exclude_guest_types`). Input of the wrong shape stops the run with the file
and row named; it is never guessed around.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from attest.model import AttestError
from attest.readers._json import load_records, require, require_str

# Microsoft's built-in authentication strengths that require MFA:
# Multifactor authentication, Passwordless MFA, Phishing-resistant MFA.
MFA_STRENGTH_IDS = frozenset({
    "00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000003",
    "00000000-0000-0000-0000-000000000004",
})


@dataclass(frozen=True)
class CaPolicy:
    id: str
    name: str
    state: str
    include_users: tuple[str, ...]
    exclude_users: tuple[str, ...]
    exclude_groups: tuple[str, ...]
    include_roles: tuple[str, ...]
    exclude_roles: tuple[str, ...]
    include_apps: tuple[str, ...]
    narrowing: tuple[str, ...]
    requires_mfa: bool
    cite: str
    exclude_guest_types: tuple[str, ...] = ()


def requires_mfa(grant: dict | None) -> bool:
    """Whether every way of satisfying this grant takes MFA.

    With operator OR, any other control is an alternative that passes without
    MFA, so "MFA or a compliant device" does not require MFA. A grant that
    blocks does not prove MFA. A missing operator is read as OR. Control names
    are compared without regard to case.
    """
    if not grant:
        return False
    controls = [c.lower() for c in grant.get("builtInControls") or []]
    if "block" in controls:
        return False
    strength = grant.get("authenticationStrength")
    strength_is_mfa = isinstance(strength, dict) and strength.get("id") in MFA_STRENGTH_IDS
    if "mfa" not in controls and not strength_is_mfa:
        return False
    alternatives = [c for c in controls if c != "mfa"]
    alternatives += list(grant.get("customAuthenticationFactors") or [])
    alternatives += list(grant.get("termsOfUse") or [])
    if strength and not strength_is_mfa:
        alternatives.append("authenticationStrength")
    return (grant.get("operator") or "OR").upper() == "AND" or not alternatives


def _is_set(value: Any) -> bool:
    """True when a condition carries anything, ignoring @odata annotations."""
    if isinstance(value, dict):
        return any(_is_set(v) for k, v in value.items() if not k.startswith("@odata"))
    return bool(value)


def _locations_narrow(locations: dict | None) -> bool:
    if not locations:
        return False
    include = [loc.lower() for loc in locations.get("includeLocations") or ["all"]]
    return include != ["all"] or bool(locations.get("excludeLocations"))


def _platforms_narrow(platforms: dict | None) -> bool:
    if not platforms:
        return False
    include = [p.lower() for p in platforms.get("includePlatforms") or ["all"]]
    return include != ["all"] or bool(platforms.get("excludePlatforms"))


# The condition keys this reader understands. Anything else that carries a value
# is a condition it cannot judge, so it narrows (fails closed).
_CONDITION_KEYS = frozenset({
    "users", "applications", "clientAppTypes", "locations", "platforms", "devices",
    "signInRiskLevels", "userRiskLevels", "servicePrincipalRiskLevels", "insiderRiskLevels",
    "authenticationFlows", "clientApplications",
})
_APPLICATION_KEYS = frozenset({
    "includeApplications", "excludeApplications", "applicationFilter",
    "includeUserActions", "includeAuthenticationContextClassReferences",
})
_USER_KEYS = frozenset({
    "includeUsers", "excludeUsers", "includeGroups", "excludeGroups", "includeRoles", "excludeRoles",
    "includeGuestsOrExternalUsers", "excludeGuestsOrExternalUsers",
})


def _unknown_keys(obj: dict, known: frozenset[str], prefix: str) -> list[str]:
    """Names of keys outside the allow-list that carry a value, as "unknown condition <prefix><key>"."""
    return [f"unknown condition {prefix}{key}" for key, value in obj.items()
            if key not in known and not key.startswith("@odata") and _is_set(value)]


def narrowing_conditions(conditions: dict) -> tuple[str, ...]:
    """Every condition that limits when the policy applies beyond its users and applications.

    The keys it understands are checked one by one; any other key that carries
    a value is named "unknown condition ..." so a condition Graph adds later
    narrows instead of passing unseen.
    """
    found: list[str] = []
    if [t.lower() for t in conditions.get("clientAppTypes") or ["all"]] != ["all"]:
        found.append("clientAppTypes")
    if _locations_narrow(conditions.get("locations")):
        found.append("locations")
    if _platforms_narrow(conditions.get("platforms")):
        found.append("platforms")
    for key in ("devices", "authenticationFlows", "clientApplications", "insiderRiskLevels",
                "signInRiskLevels", "userRiskLevels", "servicePrincipalRiskLevels"):
        if _is_set(conditions.get(key)):
            found.append(key)
    found += _unknown_keys(conditions, _CONDITION_KEYS, "")
    applications = conditions.get("applications") or {}
    for key in ("excludeApplications", "applicationFilter", "includeUserActions",
                "includeAuthenticationContextClassReferences"):
        if _is_set(applications.get(key)):
            found.append(f"applications.{key}")
    found += _unknown_keys(applications, _APPLICATION_KEYS, "applications.")
    found += _unknown_keys(conditions.get("users") or {}, _USER_KEYS, "users.")
    return tuple(found)


def _object(value: Any, file: str, row: int, field: str) -> dict:
    """A JSON object, or {} for null; anything else stops the run."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AttestError(f"{file}: row {row} field {field!r} must be an object, got {value!r}")
    return value


def _strings(value: Any, file: str, row: int, field: str) -> tuple[str, ...]:
    """A list of strings, or () for null. A bare string is refused, not read as a list of characters."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise AttestError(f"{file}: row {row} field {field!r} must be a list of strings, got {value!r}")
    return tuple(value)


def _text(value: Any, file: str, row: int, field: str) -> str:
    """A string, or "" for null; anything else stops the run."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AttestError(f"{file}: row {row} field {field!r} must be a string, got {value!r}")
    return value


def _excluded_guest_types(guests: dict, exclude_users: tuple[str, ...], file: str, row: int) -> tuple[str, ...]:
    """The guest and external user types the policy leaves out, in Graph's spelling.

    Graph writes them as one comma-separated string. An exclusion that is set
    but names no type is recorded as "unknown" rather than as no exclusion. The
    legacy form, "GuestsOrExternalUsers" among excludeUsers, means all of them.
    """
    types: list[str] = []
    if _is_set(guests):
        named = _text(guests.get("guestOrExternalUserTypes"), file, row,
                      "conditions.users.excludeGuestsOrExternalUsers.guestOrExternalUserTypes")
        types = [t.strip() for t in named.split(",") if t.strip()] or ["unknown"]
    if "GuestsOrExternalUsers" in exclude_users:
        types.append("GuestsOrExternalUsers")
    return tuple(types)


def _grant(value: Any, file: str, row: int) -> dict:
    """The grant controls, checked for the shapes requires_mfa reads."""
    grant = _object(value, file, row, "grantControls")
    _text(grant.get("operator"), file, row, "grantControls.operator")
    _strings(grant.get("builtInControls"), file, row, "grantControls.builtInControls")
    return grant


def read(path: Path) -> tuple[CaPolicy, ...]:
    file = Path(path).name
    policies = []
    for row, r in enumerate(load_records(path), start=1):
        conditions = require(r, "conditions", file, row)
        if not isinstance(conditions, dict):
            raise AttestError(f"{file}: row {row} field 'conditions' must be an object")
        users = _object(conditions.get("users"), file, row, "conditions.users")
        applications = _object(conditions.get("applications"), file, row, "conditions.applications")
        _object(conditions.get("locations"), file, row, "conditions.locations")
        _object(conditions.get("platforms"), file, row, "conditions.platforms")
        _strings(require(conditions, "clientAppTypes", file, row), file, row, "conditions.clientAppTypes")
        include_users = _strings(users.get("includeUsers"), file, row, "conditions.users.includeUsers")
        exclude_users = _strings(users.get("excludeUsers"), file, row, "conditions.users.excludeUsers")
        exclude_groups = _strings(users.get("excludeGroups"), file, row, "conditions.users.excludeGroups")
        include_roles = _strings(users.get("includeRoles"), file, row, "conditions.users.includeRoles")
        exclude_roles = _strings(users.get("excludeRoles"), file, row, "conditions.users.excludeRoles")
        guests = _object(users.get("excludeGuestsOrExternalUsers"), file, row,
                         "conditions.users.excludeGuestsOrExternalUsers")
        include_apps = _strings(applications.get("includeApplications"), file, row,
                                "conditions.applications.includeApplications")
        grant = _grant(require(r, "grantControls", file, row), file, row)
        policy_id = require_str(r, "id", file, row)
        policies.append(CaPolicy(
            id=policy_id,
            name=r.get("displayName") or policy_id,
            state=require_str(r, "state", file, row),
            include_users=include_users,
            exclude_users=exclude_users,
            exclude_groups=exclude_groups,
            include_roles=include_roles,
            exclude_roles=exclude_roles,
            include_apps=include_apps,
            narrowing=narrowing_conditions(conditions),
            requires_mfa=requires_mfa(grant),
            cite=f"{file}:{row}",
            exclude_guest_types=_excluded_guest_types(guests, exclude_users, file, row),
        ))
    return tuple(policies)
