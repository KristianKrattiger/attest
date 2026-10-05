#!/usr/bin/env python3
"""Write firm/dev/exports: the made-up Harbor & Pine CPA tenant, in the API shapes the readers take.

Planted truth (firm/dev/truth.yaml):
- the owner, Dana Whitfield, is excluded from the all-users MFA policy (she travels) and holds no admin role;
- the new hire, Ivan Petrov, has not registered for MFA, and his laptop was never onboarded to Defender;
- Carmen Diaz's mailbox is not backed up by Veeam;
- a pilot policy that would cover everyone is report-only, so it enforces nothing;
- Defender reports Hana Sato's laptop without an Entra device ID, so it must match by name;
- a file server is in Defender but not Intune, so it sits outside the EDR population;
- a disabled former employee and a guest auditor are left out of the population;
- everything else is in order, so the admin-MFA attestations are genuinely backed.

Run from the repo root:  venv/Scripts/python.exe scripts/build_dev_firm.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "firm" / "dev" / "exports"
DOMAIN = "harborpine.example"
EXPORTED_AT = "2026-10-01T15:00:00Z"
LAST_SEEN = "2026-10-01T09:30:00Z"
LAST_BACKUP = "2026-10-01T02:10:00Z"
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


class Person(NamedTuple):
    n: int
    nick: str
    name: str
    enabled: bool
    user_type: str
    mfa_registered: bool
    role: Optional[str]
    laptop: bool
    onboarded: bool
    mailbox_backed_up: bool


PEOPLE = [
    Person(1, "dana.whitfield", "Dana Whitfield", True, "Member", True, None, True, True, True),
    Person(2, "marcus.chen", "Marcus Chen", True, "Member", True, GLOBAL_ADMIN, True, True, True),
    Person(3, "priya.nair", "Priya Nair", True, "Member", True, EXCHANGE_ADMIN, True, True, True),
    Person(4, "tom.reyes", "Tom Reyes", True, "Member", True, None, True, True, True),
    Person(5, "elena.kowalski", "Elena Kowalski", True, "Member", True, None, True, True, True),
    Person(6, "george.okafor", "George Okafor", True, "Member", True, None, True, True, True),
    Person(7, "aisha.rahman", "Aisha Rahman", True, "Member", True, None, True, True, True),
    Person(8, "ben.foster", "Ben Foster", True, "Member", True, None, True, True, True),
    Person(9, "carmen.diaz", "Carmen Diaz", True, "Member", True, None, True, True, False),
    Person(10, "felix.braun", "Felix Braun", True, "Member", True, None, True, True, True),
    Person(11, "hana.sato", "Hana Sato", True, "Member", True, None, True, True, True),
    Person(12, "ivan.petrov", "Ivan Petrov", True, "Member", False, None, True, False, True),
    Person(13, "sam.lowe", "Sam Lowe", False, "Member", False, None, False, False, True),
    Person(14, "audit.partner_auditfirm.example#EXT#", "Audit Partner (guest)", True, "Guest",
           False, None, False, False, False),
]
NO_ENTRA_ID_IN_DEFENDER = {11}


def user_id(n: int) -> str:
    return f"a0000000-0000-4000-8000-{n:012d}"


def device_id(n: int) -> str:
    return f"d0000000-0000-4000-8000-{n:012d}"


def upn(nick: str) -> str:
    return f"{nick}@{DOMAIN}"


def graph_page(context: str, records: list[dict]) -> dict:
    return {"@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#{context}", "value": records}


def users() -> dict:
    return graph_page("users(id,userPrincipalName,displayName,accountEnabled,userType)", [
        {"id": user_id(p.n), "userPrincipalName": upn(p.nick), "displayName": p.name,
         "accountEnabled": p.enabled, "userType": p.user_type}
        for p in PEOPLE
    ])


def registration() -> dict:
    return graph_page("reports/authenticationMethods/userRegistrationDetails", [
        {"id": user_id(p.n), "userPrincipalName": upn(p.nick), "userDisplayName": p.name,
         "userType": p.user_type.lower(), "isAdmin": p.role is not None,
         "isMfaRegistered": p.mfa_registered, "isMfaCapable": p.mfa_registered,
         "methodsRegistered": ["microsoftAuthenticatorPush"] if p.mfa_registered else []}
        for p in PEOPLE
    ])


def _policy(n: int, name: str, state: str, users_condition: dict, grant: list[str],
            client_app_types: tuple[str, ...] = ("all",)) -> dict:
    return {
        "id": f"c0000000-0000-4000-8000-{n:012d}", "displayName": name, "state": state,
        "conditions": {
            "users": {"includeUsers": [], "excludeUsers": [], "includeGroups": [], "excludeGroups": [],
                      "includeRoles": [], "excludeRoles": [], **users_condition},
            "applications": {"includeApplications": ["All"], "excludeApplications": [], "includeUserActions": []},
            "clientAppTypes": list(client_app_types), "locations": None, "platforms": None, "devices": None,
            "signInRiskLevels": [], "userRiskLevels": [], "servicePrincipalRiskLevels": [],
        },
        "grantControls": {"operator": "OR", "builtInControls": grant,
                          "customAuthenticationFactors": [], "termsOfUse": []},
    }


def ca_policies() -> dict:
    return graph_page("identity/conditionalAccess/policies", [
        _policy(1, "Require MFA for all users", "enabled",
                {"includeUsers": ["All"], "excludeUsers": [user_id(1)]}, ["mfa"]),
        _policy(2, "Require MFA for administrators", "enabled",
                {"includeRoles": [GLOBAL_ADMIN, EXCHANGE_ADMIN]}, ["mfa"]),
        _policy(3, "MFA everywhere (pilot)", "enabledForReportingButNotEnforced",
                {"includeUsers": ["All"]}, ["mfa"]),
        _policy(4, "Block legacy authentication", "enabled",
                {"includeUsers": ["All"]}, ["block"], client_app_types=("exchangeActiveSync", "other")),
    ])


def security_defaults() -> dict:
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#policies/"
                          "identitySecurityDefaultsEnforcementPolicy/$entity",
        "id": "00000000-0000-0000-0000-000000000005",
        "displayName": "Security Defaults",
        "description": "Security defaults is a set of basic identity security mechanisms recommended by Microsoft.",
        "isEnabled": False,
    }


def role_assignments() -> dict:
    return graph_page("roleManagement/directory/roleAssignments(principal())", [
        {"id": f"ra-{p.n}", "principalId": user_id(p.n), "roleDefinitionId": p.role, "directoryScopeId": "/",
         "principal": {"@odata.type": "#microsoft.graph.user", "id": user_id(p.n),
                       "userPrincipalName": upn(p.nick), "displayName": p.name}}
        for p in PEOPLE if p.role
    ])


def intune_devices() -> dict:
    return graph_page("deviceManagement/managedDevices", [
        {"id": f"e0000000-0000-4000-8000-{p.n:012d}", "deviceName": f"HP-LT-{p.n:02d}",
         "azureADDeviceId": device_id(p.n), "operatingSystem": "Windows", "userPrincipalName": upn(p.nick)}
        for p in PEOPLE if p.laptop
    ])


def defender_machines() -> dict:
    machines = [
        {"id": f"{p.n:040x}", "computerDnsName": f"hp-lt-{p.n:02d}.{DOMAIN}",
         "aadDeviceId": None if p.n in NO_ENTRA_ID_IN_DEFENDER else device_id(p.n),
         "osPlatform": "Windows11", "onboardingStatus": "Onboarded", "healthStatus": "Active",
         "lastSeen": LAST_SEEN}
        for p in PEOPLE if p.laptop and p.onboarded
    ]
    machines.append({"id": "f" * 40, "computerDnsName": f"hp-fs01.{DOMAIN}", "aadDeviceId": None,
                     "osPlatform": "WindowsServer2022", "onboardingStatus": "Onboarded",
                     "healthStatus": "Active", "lastSeen": LAST_SEEN})
    return {"@odata.context": "https://api.security.microsoft.com/api/$metadata#Machines", "value": machines}


def veeam_users() -> list[dict]:
    return [
        {"Email": upn(p.nick), "DisplayName": p.name, "IsMailboxBackedUp": p.mailbox_backed_up,
         "MailboxBackedUpTime": LAST_BACKUP if p.mailbox_backed_up else None}
        for p in PEOPLE if p.user_type == "Member"
    ]


EXPORTS = {
    "users.json": ("entra_users", users),
    "registration.json": ("entra_registration", registration),
    "ca-policies.json": ("entra_ca_policies", ca_policies),
    "security-defaults.json": ("entra_security_defaults", security_defaults),
    "role-assignments.json": ("entra_role_assignments", role_assignments),
    "intune-devices.json": ("intune_devices", intune_devices),
    "defender-machines.json": ("defender_machines", defender_machines),
    "veeam-users.json": ("veeam_users", veeam_users),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = ["exports:"]
    for file, (reader, build) in EXPORTS.items():
        (OUT / file).write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8", newline="\n")
        manifest.append(f"  - {{file: {file}, reader: {reader}, exported_at: {EXPORTED_AT}}}")
    (OUT / "manifest.yaml").write_text("\n".join(manifest) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(EXPORTS)} exports and manifest.yaml to {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
