"""MFA mess: Conditional Access policies, exclusions, role holders and registration (spec 2026-10-14, catalog)."""
from __future__ import annotations

from typing import Optional

from messy.firm import Firm
from messy.operators import (
    ADMINS, ALL_MFA, ALL_USERS, BACKUP, EXCHANGE_ADMIN, GLOBAL_ADMIN, Operator, add_account, assign_role, clone, new_id,
    take, veeam_fresh)

MFA_STRENGTH = "00000000-0000-0000-0000-000000000002"  # the built-in "Multifactor authentication" strength


def _requires_mfa(policy: dict) -> bool:
    grant = policy["grantControls"] or {}
    return ("mfa" in [c.lower() for c in grant.get("builtInControls") or []]
            or (grant.get("authenticationStrength") or {}).get("id") == MFA_STRENGTH)


def _all_users_policy(firm: Firm) -> Optional[dict]:
    """The enabled policy that requires MFA, through builtInControls, of every user on every app."""
    for p in firm.rows("entra_ca_policies"):
        users, apps = p["conditions"]["users"], p["conditions"]["applications"]
        if (p["state"] == "enabled" and "All" in (users.get("includeUsers") or [])
                and "All" in (apps.get("includeApplications") or [])
                and "mfa" in [c.lower() for c in (p["grantControls"] or {}).get("builtInControls") or []]):
            return p
    return None


def _admin_portals(firm: Firm) -> bool:
    policies = firm.rows("entra_ca_policies")
    if any((p.get("displayName") or "").startswith("Multifactor authentication for admins accessing")
           for p in policies):
        return False  # a real capture has it already
    policy = clone(policies, id=new_id("policy:admin-portals"), state="enabledForReportingButNotEnforced",
                   displayName="Multifactor authentication for admins accessing Microsoft Admin Portals")
    policy["conditions"]["users"] = {**policy["conditions"]["users"], "includeUsers": [], "excludeUsers": [],
                                     "includeGroups": [], "excludeGroups": [], "includeRoles": [GLOBAL_ADMIN],
                                     "excludeRoles": []}
    policy["conditions"]["applications"] = {**policy["conditions"]["applications"],
                                            "includeApplications": ["MicrosoftAdminPortals"]}
    policy["grantControls"] = {**policy["grantControls"], "operator": "OR", "builtInControls": ["mfa"]}
    return True


def _break_glass(firm: Firm) -> bool:
    for n in (1, 2):
        account = add_account(firm, f"break.glass{n}", f"Break Glass {n}")
        assign_role(firm, f"break.glass{n}", {"@odata.type": "#microsoft.graph.user", "id": account["id"],
                                              "userPrincipalName": account["userPrincipalName"],
                                              "displayName": account["displayName"]})
        for p in firm.rows("entra_ca_policies"):
            users = p["conditions"]["users"]
            users["excludeUsers"] = [*(users.get("excludeUsers") or []), account["id"]]
    return True


def _exclusion_group(firm: Firm) -> bool:
    policy = _all_users_policy(firm)
    if policy is None:
        return False
    users = policy["conditions"]["users"]
    users["excludeGroups"] = [*(users.get("excludeGroups") or []), new_id("group:mfa-exclusions")]
    return True


def _office365_only(firm: Firm) -> bool:
    policy = _all_users_policy(firm)
    if policy is None or not take(firm, f"policy-apps:{policy['id']}"):
        return False
    policy["conditions"]["applications"]["includeApplications"] = ["Office365"]
    return True


def _authentication_strength(firm: Firm) -> bool:
    policy = _all_users_policy(firm)
    if policy is None or not take(firm, f"policy-grant:{policy['id']}"):
        return False
    grant = policy["grantControls"]
    grant["builtInControls"] = []
    grant["authenticationStrength@odata.context"] = (
        "https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies('x')/grantControls/"
        "authenticationStrength/$entity")
    grant["authenticationStrength"] = {
        "id": MFA_STRENGTH, "displayName": "Multifactor authentication", "policyType": "builtIn",
        "requirementsSatisfied": "mfa",
        "allowedCombinations": ["windowsHelloForBusiness", "fido2", "password,microsoftAuthenticatorPush",
                                "password,softwareOath", "password,sms"]}
    return True


def _per_user_mfa(firm: Firm) -> bool:
    policies = [p for p in firm.rows("entra_ca_policies") if _requires_mfa(p) and p["state"] == "enabled"]
    if not policies or not all(take(firm, f"policy-state:{p['id']}") for p in policies):
        return False
    for p in policies:
        p["state"] = "disabled"
    return True


def _group_admin(firm: Firm, unregistered_member: bool) -> bool:
    label = "admins-group-unregistered" if unregistered_member else "admins-group"
    assign_role(firm, label, {"@odata.type": "#microsoft.graph.group", "id": new_id(f"group:{label}"),
                              "displayName": "Tenant Admins", "mail": None, "securityEnabled": True,
                              "isAssignableToRole": True})
    if unregistered_member:
        add_account(firm, "new.admin", "New Admin", registered=False, mailbox=(True, veeam_fresh(firm)))
    return True


def _service_principal_admin(firm: Firm) -> bool:
    assign_role(firm, "backup-connector", {"@odata.type": "#microsoft.graph.servicePrincipal",
                                           "id": new_id("sp:backup-connector"), "displayName": "Backup Connector",
                                           "appId": new_id("app:backup-connector")}, role=EXCHANGE_ADMIN)
    return True


def _registration_lag(firm: Firm) -> bool:
    add_account(firm, "new.hire", "New Hire", registered=None, mailbox=None)
    return True


OPERATORS = (
    Operator("microsoft-managed admin-portals policy", "holds", _admin_portals, scopes=ALL_MFA,
             why="a report-only policy enforces nothing and excludes no one"),
    Operator("break-glass accounts excluded", "breaks", _break_glass,
             # Backup is a false gap: break-glass accounts hold no mailbox, but every enabled member is counted.
             alone={"mfa.all_users": "gap", "mfa.email": "gap", "mfa.admins": "gap", "backup.m365_mailboxes": "gap"},
             scopes=ALL_MFA, twin="real-messy-break-glass"),
    Operator("MFA exclusions group", "breaks", _exclusion_group,
             alone={"mfa.all_users": "gap", "mfa.email": "gap"}, scopes=ALL_USERS, twin="real-messy-exclusion-group"),
    Operator("all-users policy limited to Office 365", "breaks", _office365_only,
             alone={"mfa.all_users": "gap"}, scopes=frozenset({"mfa.all_users"})),
    Operator("grant through an authentication strength", "holds", _authentication_strength, scopes=ALL_USERS,
             why="the built-in Multifactor authentication strength requires MFA, as builtInControls mfa does"),
    Operator("per-user MFA instead of Conditional Access", "holds", _per_user_mfa,
             alone={"mfa.all_users": "gap", "mfa.email": "gap", "mfa.admins": "gap"}, scopes=ALL_MFA,
             why="per-user MFA prompts every account on every sign-in; no export in this set shows it"),
    Operator("admin role held by a group", "holds", lambda firm: _group_admin(firm, unregistered_member=False),
             alone={"mfa.admins": "unchecked"}, scopes=ADMINS,
             why="the group's members are existing accounts, registered and covered like everyone else"),
    Operator("admin role held by a group with an unregistered member", "breaks",
             lambda firm: _group_admin(firm, unregistered_member=True),
             alone={"mfa.all_users": "gap", "mfa.email": "gap", "mfa.admins": "unchecked"}, scopes=ALL_MFA),
    Operator("admin role held by a service principal", "holds", _service_principal_admin, scopes=ADMINS,
             why="a service principal signs in with a secret or a certificate; MFA does not apply to it"),
    Operator("user created after the registration report", "breaks", _registration_lag,
             alone={"mfa.all_users": "unchecked", "mfa.email": "unchecked", "backup.m365_mailboxes": "gap"},
             scopes=ALL_USERS | BACKUP, twin="real-messy-new-user"),
)
