import pytest

from attest.model import AttestError
from attest.readers import entra_registration, entra_role_assignments, entra_security_defaults, entra_users

GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"


def test_users_are_read_from_a_graph_page(write_json):
    path = write_json("users.json", {"value": [
        {"id": "u1", "userPrincipalName": "ann@firm.example", "displayName": "Ann",
         "accountEnabled": True, "userType": "Member"},
        {"id": "u2", "userPrincipalName": "guest#EXT#@firm.example", "displayName": None,
         "accountEnabled": True, "userType": "Guest"},
    ]})
    users = entra_users.read(path)
    assert users[0] == entra_users.User("u1", "ann@firm.example", "Ann", True, "Member", "users.json:1")
    assert (users[1].display_name, users[1].user_type, users[1].cite) == ("", "Guest", "users.json:2")


def test_a_null_user_type_reads_as_empty_not_guest(write_json):
    path = write_json("users.json", [
        {"id": "u1", "userPrincipalName": "a@f.example", "accountEnabled": True, "userType": None},
    ])
    assert entra_users.read(path)[0].user_type == ""


def test_a_user_without_account_enabled_stops_the_run(write_json):
    path = write_json("users.json", [{"id": "u1", "userPrincipalName": "a@f.example", "userType": "Member"}])
    with pytest.raises(AttestError, match="users.json: row 1 has no field 'accountEnabled'"):
        entra_users.read(path)


def test_registration_reads_is_mfa_registered(write_json):
    path = write_json("reg.json", {"value": [
        {"id": "u1", "userPrincipalName": "ann@firm.example", "isMfaRegistered": True, "isAdmin": False},
        {"id": "u2", "userPrincipalName": "bob@firm.example", "isMfaRegistered": False},
    ]})
    assert [(r.user_id, r.mfa_registered, r.cite) for r in entra_registration.read(path)] == [
        ("u1", True, "reg.json:1"),
        ("u2", False, "reg.json:2"),
    ]


def test_registration_without_is_mfa_registered_stops_the_run(write_json):
    path = write_json("reg.json", [{"id": "u1", "userPrincipalName": "a@f.example", "isMfaCapable": True}])
    with pytest.raises(AttestError, match="no field 'isMfaRegistered'"):
        entra_registration.read(path)


def test_security_defaults_is_one_object(write_json):
    path = write_json("sd.json", {"@odata.context": "x", "id": "00000000-0000-0000-0000-000000000005",
                                  "isEnabled": True})
    assert entra_security_defaults.read(path) == (entra_security_defaults.SecurityDefaults(True, "sd.json:1"),)


def test_security_defaults_must_be_exactly_one_policy(write_json):
    path = write_json("sd.json", [{"isEnabled": True}, {"isEnabled": False}])
    with pytest.raises(AttestError, match="expected one security-defaults policy, found 2"):
        entra_security_defaults.read(path)


def test_role_assignments_read_the_expanded_principal(write_json):
    path = write_json("roles.json", {"value": [
        {"id": "ra1", "principalId": "u1", "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": "/",
         "principal": {"@odata.type": "#microsoft.graph.user", "id": "u1",
                       "userPrincipalName": "ann@firm.example", "displayName": "Ann"}},
        {"id": "ra2", "principalId": "g1", "roleDefinitionId": EXCHANGE_ADMIN,
         "directoryScopeId": "/administrativeUnits/x",
         "principal": {"@odata.type": "#microsoft.graph.group", "id": "g1", "displayName": "IT admins"}},
    ]})
    first, second = entra_role_assignments.read(path)
    assert (first.principal_kind, first.principal_name, first.role_id, first.scope, first.cite) == (
        "user", "ann@firm.example", GLOBAL_ADMIN, "/", "roles.json:1")
    assert (second.principal_kind, second.principal_name, second.scope) == (
        "group", "IT admins", "/administrativeUnits/x")


def test_role_assignments_without_expanded_principal_say_how_to_export(write_json):
    path = write_json("roles.json", [{"id": "ra1", "principalId": "u1", "roleDefinitionId": "r"}])
    with pytest.raises(AttestError, match=r"\$expand=principal"):
        entra_role_assignments.read(path)


def test_a_role_scope_is_recorded_as_exported_never_guessed(write_json):
    principal = {"@odata.type": "#microsoft.graph.user", "id": "u1", "userPrincipalName": "ann@firm.example"}
    path = write_json("roles.json", [
        {"principalId": "u1", "roleDefinitionId": "r", "appScopeId": "/AccessPackageCatalog/c1", "principal": principal},
        {"principalId": "u1", "roleDefinitionId": "r", "directoryScopeId": None, "principal": principal},
    ])
    app_scoped, unscoped = entra_role_assignments.read(path)
    assert (app_scoped.scope, unscoped.scope) == ("/AccessPackageCatalog/c1", "")


def test_a_null_principal_stops_the_run_naming_both_causes(write_json):
    path = write_json("roles.json", [{"principalId": "u1", "roleDefinitionId": "r", "principal": None}])
    with pytest.raises(AttestError, match="a null principal means its account was deleted"):
        entra_role_assignments.read(path)
