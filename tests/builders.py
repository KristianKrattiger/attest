"""Small constructors for rule tests: evidence built from records, not files."""
from datetime import datetime, timezone

from attest.evidence import Evidence
from attest.model import Export
from attest.readers.defender_machines import Machine
from attest.readers.entra_ca_policies import CaPolicy
from attest.readers.entra_registration import Registration
from attest.readers.entra_role_assignments import RoleAssignment
from attest.readers.entra_security_defaults import SecurityDefaults
from attest.readers.entra_users import User
from attest.readers.intune_devices import IntuneDevice
from attest.readers.veeam_users import VeeamUser

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)
GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


def upn(uid):
    return f"{uid}@firm.example"


def user(uid, enabled=True, user_type="Member"):
    return User(uid, upn(uid), uid.title(), enabled, user_type, f"users.json:{uid}")


def registration(uid, registered=True):
    return Registration(uid, upn(uid), registered, f"registration.json:{uid}")


def policy(name="All users MFA", state="enabled", include_users=("All",), exclude_users=(), exclude_groups=(),
           include_roles=(), exclude_roles=(), include_apps=("All",), narrowing=(), requires_mfa=True):
    return CaPolicy(name, name, state, tuple(include_users), tuple(exclude_users), tuple(exclude_groups),
                    tuple(include_roles), tuple(exclude_roles), tuple(include_apps), tuple(narrowing),
                    requires_mfa, f"ca.json:{name}")


def defaults(enabled):
    return SecurityDefaults(enabled, "security-defaults.json:1")


def role(uid, role_id=GLOBAL_ADMIN, kind="user"):
    return RoleAssignment(uid, kind, upn(uid) if kind == "user" else uid, role_id, "/", f"roles.json:{uid}")


def device(n, aad=True):
    return IntuneDevice(f"i{n}", f"LT-{n:02d}", f"d-{n}" if aad else None, "Windows", f"intune.json:{n}")


def machine(n, name=None, aad=True, onboarding="Onboarded", health="Active", last_seen=NOW):
    return Machine(f"m{n}", name or f"lt-{n:02d}.firm.example", f"d-{n}" if aad else None,
                   onboarding, health, last_seen, f"mde.json:{n}")


def mailbox(uid, backed_up=True, when=NOW):
    return VeeamUser(upn(uid), backed_up, when if backed_up else None, f"veeam.json:{uid}")


def export(items, file="export.json", at=NOW):
    return Export(file, at, tuple(items))


def evidence(**exports):
    """Evidence(entra_users=[...], ...) with each list wrapped as an export named <field>.json, taken at NOW."""
    return Evidence(**{name: export(items, file=f"{name}.json") for name, items in exports.items()})
