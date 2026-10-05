import pytest

from attest.rules.mfa import mfa_admins, mfa_all_users, mfa_email, mfa_remote_access
from builders import EXCHANGE_ADMIN, GLOBAL_ADMIN, defaults, evidence, policy, registration, role, upn, user

TEAM = ["ann", "bob", "cy"]


def team(**overrides):
    """Three enabled members, all registered, one all-users MFA policy, security defaults off.

    Pass an export as None to leave it out.
    """
    exports = dict(
        entra_users=[user(u) for u in TEAM],
        entra_registration=[registration(u) for u in TEAM],
        entra_ca_policies=[policy()],
        entra_security_defaults=[defaults(False)],
    )
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def admins(**overrides):
    """team() plus Ann as Global Admin, Bob as Exchange Admin, and one policy on those roles."""
    exports = dict(
        entra_role_assignments=[role("ann"), role("bob", role_id=EXCHANGE_ADMIN)],
        entra_ca_policies=[policy("Admins MFA", include_users=(), include_roles=(GLOBAL_ADMIN, EXCHANGE_ADMIN))],
    )
    exports.update(overrides)
    return team(**exports)


def test_backed_when_an_enabled_policy_covers_everyone_and_all_are_registered():
    v = mfa_all_users(team())
    assert v.status == "backed"
    assert v.population == "3 enabled member accounts from entra_users.json"
    assert "'All users MFA'" in v.reason


def test_security_defaults_count_and_the_report_says_what_they_mean():
    v = mfa_all_users(team(entra_ca_policies=None, entra_security_defaults=[defaults(True)]))
    assert v.status == "backed"
    assert "when it judges it necessary" in v.reason


@pytest.mark.parametrize("p, why", [
    (policy(state="enabledForReportingButNotEnforced"), "is enabledForReportingButNotEnforced"),
    (policy(state="disabled"), "is disabled"),
    (policy(narrowing=("locations",)), "applies only under conditions: locations"),
])
def test_a_policy_that_does_not_enforce_is_named_in_a_no_enforcement_gap(p, why):
    v = mfa_all_users(team(entra_ca_policies=[p]))
    assert v.status == "gap"
    assert v.reason.startswith("no enforcement")
    assert why in v.reason


def test_a_policy_that_does_not_require_mfa_is_no_enforcement():
    v = mfa_all_users(team(entra_ca_policies=[policy(requires_mfa=False)]))
    assert (v.status, v.reason.startswith("no enforcement")) == ("gap", True)


def test_an_excluded_account_is_a_cited_gap():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_users=("bob",))]))
    assert v.status == "gap"
    assert v.entities == (upn("bob"),)
    assert "not covered by an enforcing policy: " + upn("bob") in v.reason


def test_an_account_excluded_by_one_policy_but_covered_by_another_is_enforced():
    v = mfa_all_users(team(entra_ca_policies=[policy("A", exclude_users=("bob",)), policy("B")]))
    assert v.status == "backed"


def test_an_excluded_group_makes_every_account_a_gap_naming_the_group():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_groups=("g-travel",))]))
    assert v.status == "gap"
    assert set(v.entities) == {upn(u) for u in TEAM}
    assert "excludes group(s) g-travel, whose members no export lists" in v.reason


def test_an_excluded_role_is_resolved_through_role_assignments():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_roles=(GLOBAL_ADMIN,))],
                           entra_role_assignments=[role("ann")]))
    assert (v.status, v.entities) == ("gap", (upn("ann"),))


def test_an_excluded_role_without_role_assignments_counts_everyone_as_excluded():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_roles=(GLOBAL_ADMIN,))]))
    assert v.status == "gap"
    assert set(v.entities) == {upn(u) for u in TEAM}
    assert "there is no role-assignments export" in v.reason


def test_an_unregistered_account_is_a_cited_gap():
    v = mfa_all_users(team(entra_registration=[registration("ann"), registration("bob", False), registration("cy")]))
    assert (v.status, v.entities) == ("gap", (upn("bob"),))
    assert "not registered for MFA: " + upn("bob") in v.reason


def test_an_account_missing_from_the_registration_export_is_unregistered():
    v = mfa_all_users(team(entra_registration=[registration("ann"), registration("bob")]))
    assert (v.status, v.entities) == ("gap", (upn("cy"),))


def test_guests_and_disabled_accounts_are_not_counted_but_are_listed():
    users = [user(u) for u in TEAM] + [user("gus", user_type="Guest"), user("old", enabled=False)]
    v = mfa_all_users(team(entra_users=users))
    assert v.status == "backed"
    assert v.population == ("3 enabled member accounts from entra_users.json; "
                            f"not counted: guests {upn('gus')}; disabled {upn('old')}")


@pytest.mark.parametrize("overrides, why", [
    (dict(entra_users=None), "no users export"),
    (dict(entra_registration=None), "no MFA registration export"),
    (dict(entra_ca_policies=None), "no Conditional Access export"),
    (dict(entra_ca_policies=None, entra_security_defaults=None), "no Conditional Access export"),
    (dict(entra_ca_policies=[policy(state="disabled")], entra_security_defaults=None),
     "no security-defaults export"),
    (dict(entra_users=[user("gus", user_type="Guest")]), "the population is empty"),
])
def test_missing_evidence_is_unchecked_never_backed(overrides, why):
    v = mfa_all_users(team(**overrides))
    assert v.status == "unchecked"
    assert why in v.reason


def test_adversarial_everyone_registered_but_nothing_enforced_is_not_backed():
    v = mfa_all_users(team(entra_ca_policies=[policy(state="enabledForReportingButNotEnforced")]))
    assert v.status == "gap"


def test_adversarial_an_enabled_policy_that_excludes_a_group_is_not_backed():
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_groups=("g-1",))]))
    assert v.status == "gap"


def test_email_accepts_a_policy_on_office_365():
    v = mfa_email(team(entra_ca_policies=[policy(include_apps=("Office365",))]))
    assert v.status == "backed"


def test_all_users_does_not_accept_a_policy_on_office_365_alone():
    v = mfa_all_users(team(entra_ca_policies=[policy(include_apps=("Office365",))]))
    assert (v.status, v.reason.startswith("no enforcement")) == ("gap", True)


def test_email_does_not_accept_a_policy_on_one_unrelated_app():
    v = mfa_email(team(entra_ca_policies=[policy(include_apps=("app-123",))]))
    assert v.status == "gap"


def test_admins_are_backed_by_a_policy_on_their_roles():
    v = mfa_admins(admins())
    assert v.status == "backed"
    assert v.population == "2 enabled accounts holding admin roles, from entra_role_assignments.json"


def test_an_admin_excluded_from_the_all_users_policy_but_covered_by_the_admin_policy_is_enforced():
    v = mfa_admins(admins(entra_ca_policies=[
        policy(exclude_users=("ann",)),
        policy("Admins MFA", include_users=(), include_roles=(GLOBAL_ADMIN,)),
    ]))
    assert v.status == "backed"


def test_a_role_policy_does_not_count_for_all_users():
    v = mfa_all_users(admins())
    assert (v.status, v.reason.startswith("no enforcement")) == ("gap", True)


def test_an_admin_role_held_by_a_group_is_unchecked():
    v = mfa_admins(admins(entra_role_assignments=[role("ann"), role("g-admins", kind="group")]))
    assert v.status == "unchecked"
    assert "held by group(s) g-admins" in v.reason


def test_an_admin_missing_from_the_users_export_is_unchecked():
    v = mfa_admins(admins(entra_role_assignments=[role("zed")]))
    assert (v.status, "not in the users export: zed" in v.reason) == ("unchecked", True)


def test_disabled_admins_and_service_principals_are_not_counted():
    users = [user(u) for u in TEAM] + [user("old", enabled=False)]
    v = mfa_admins(admins(entra_users=users, entra_role_assignments=[
        role("ann"), role("old"), role("app-1", kind="servicePrincipal")]))
    assert v.status == "backed"
    assert v.population.startswith("1 enabled accounts holding admin roles")


def test_admins_without_role_assignments_are_unchecked():
    v = mfa_admins(team())
    assert (v.status, "no role-assignments export" in v.reason) == ("unchecked", True)


def test_an_unregistered_admin_is_a_gap():
    v = mfa_admins(admins(entra_registration=[registration("ann"), registration("bob", False), registration("cy")]))
    assert (v.status, v.entities) == ("gap", (upn("bob"),))


def test_remote_access_is_always_unchecked():
    v = mfa_remote_access(team())
    assert v.status == "unchecked"
    assert "VPN or firewall MFA" in v.reason


def test_a_guest_only_exclusion_leaves_the_member_accounts_covered():
    v = mfa_all_users(team(entra_ca_policies=[
        policy(exclude_guest_types=("internalGuest", "b2bCollaborationGuest"))]))
    assert v.status == "backed"


def test_a_guest_admin_is_not_covered_by_a_policy_that_excludes_guests():
    users = [user(u) for u in TEAM] + [user("gus", user_type="Guest")]
    v = mfa_admins(admins(
        entra_users=users,
        entra_role_assignments=[role("gus")],
        entra_registration=[registration(u) for u in TEAM] + [registration("gus")],
        entra_ca_policies=[policy(exclude_guest_types=("internalGuest",))],
    ))
    assert (v.status, v.entities) == ("gap", (upn("gus"),))


@pytest.mark.parametrize("types", [("b2bCollaborationMember",), ("GuestsOrExternalUsers",), ("unknown",)])
def test_an_external_type_exclusion_no_export_identifies_counts_as_excluding_everyone(types):
    v = mfa_all_users(team(entra_ca_policies=[policy(exclude_guest_types=types)]))
    assert v.status == "gap"
    assert set(v.entities) == {upn(u) for u in TEAM}
    assert f"excludes external user types {', '.join(types)}, which no export identifies" in v.reason
