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
    return User(id=uid, upn=upn(uid), display_name=uid.title(), enabled=enabled, user_type=user_type,
                cite=f"users.json:{uid}")


def registration(uid, registered=True):
    return Registration(user_id=uid, upn=upn(uid), mfa_registered=registered, cite=f"registration.json:{uid}")


def policy(name="All users MFA", state="enabled", include_users=("All",), exclude_users=(), exclude_groups=(),
           include_roles=(), exclude_roles=(), include_apps=("All",), narrowing=(), requires_mfa=True,
           exclude_guest_types=()):
    return CaPolicy(id=name, name=name, state=state, include_users=tuple(include_users),
                    exclude_users=tuple(exclude_users), exclude_groups=tuple(exclude_groups),
                    include_roles=tuple(include_roles), exclude_roles=tuple(exclude_roles),
                    include_apps=tuple(include_apps), narrowing=tuple(narrowing), requires_mfa=requires_mfa,
                    cite=f"ca.json:{name}", exclude_guest_types=tuple(exclude_guest_types))


def defaults(enabled):
    return SecurityDefaults(enabled=enabled, cite="security-defaults.json:1")


def role(uid, role_id=GLOBAL_ADMIN, kind="user", scope="/"):
    return RoleAssignment(principal_id=uid, principal_kind=kind, principal_name=upn(uid) if kind == "user" else uid,
                          role_id=role_id, scope=scope, cite=f"roles.json:{uid}")


def device(n, aad=True, name=None):
    return IntuneDevice(id=f"i{n}", name=name or f"LT-{n:02d}", aad_device_id=f"d-{n}" if aad else None,
                        os="Windows", cite=f"intune.json:{n}")


def machine(n, name=None, aad=True, onboarding="Onboarded", health="Active", last_seen=NOW):
    return Machine(id=f"m{n}", name=name or f"lt-{n:02d}.firm.example", aad_device_id=f"d-{n}" if aad else None,
                   onboarding=onboarding, health=health, last_seen=last_seen, cite=f"mde.json:{n}")


def mailbox(uid, backed_up=True, when=NOW):
    return VeeamUser(email=upn(uid), mailbox_backed_up=backed_up,
                     mailbox_backed_up_time=when if backed_up else None, cite=f"veeam.json:{uid}")


def export(items, file="export.json", at=NOW):
    return Export(file, at, tuple(items))


def evidence(**exports):
    """Evidence(entra_users=[...], ...) with each list wrapped as an export named <field>.json, taken at NOW."""
    return Evidence(**{name: export(items, file=f"{name}.json") for name, items in exports.items()})
