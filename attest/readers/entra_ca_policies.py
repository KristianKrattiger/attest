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


def requires_mfa(grant: dict | None) -> bool:
    """Whether every way of satisfying this grant takes MFA.

    With operator OR, any other control is an alternative that passes without
    MFA, so "MFA or a compliant device" does not require MFA. A grant that
    blocks does not prove MFA. A missing operator is read as OR.
    """
    if not grant:
        return False
    controls = list(grant.get("builtInControls") or [])
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


def narrowing_conditions(conditions: dict) -> tuple[str, ...]:
    """Every condition that limits when the policy applies beyond its users and applications."""
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
    applications = conditions.get("applications") or {}
    for key in ("excludeApplications", "applicationFilter", "includeUserActions",
                "includeAuthenticationContextClassReferences"):
        if _is_set(applications.get(key)):
            found.append(f"applications.{key}")
    return tuple(found)


def read(path: Path) -> tuple[CaPolicy, ...]:
    file = Path(path).name
    policies = []
    for row, r in enumerate(load_records(path), start=1):
        conditions = require(r, "conditions", file, row)
        if not isinstance(conditions, dict):
            raise AttestError(f"{file}: row {row} field 'conditions' must be an object")
        users = conditions.get("users") or {}
        applications = conditions.get("applications") or {}
        policy_id = require_str(r, "id", file, row)
        policies.append(CaPolicy(
            id=policy_id,
            name=r.get("displayName") or policy_id,
            state=require_str(r, "state", file, row),
            include_users=tuple(users.get("includeUsers") or ()),
            exclude_users=tuple(users.get("excludeUsers") or ()),
            exclude_groups=tuple(users.get("excludeGroups") or ()),
            include_roles=tuple(users.get("includeRoles") or ()),
            exclude_roles=tuple(users.get("excludeRoles") or ()),
            include_apps=tuple(applications.get("includeApplications") or ()),
            narrowing=narrowing_conditions(conditions),
            requires_mfa=requires_mfa(require(r, "grantControls", file, row)),
            cite=f"{file}:{row}",
        ))
    return tuple(policies)
