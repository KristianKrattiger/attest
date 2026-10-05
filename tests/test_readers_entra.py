import re

import pytest

from attest.model import AttestError
from attest.readers import entra_registration, entra_role_assignments, entra_security_defaults, entra_users

GLOBAL_ADMIN = "62e90394-69f5-4237-9190-012177145e10"
EXCHANGE_ADMIN = "29232cdf-9323-42fd-ade2-1d097af3e4de"
ANN = "a0000000-0000-4000-8000-000000000001"
BOB = "a0000000-0000-4000-8000-000000000002"
GROUP = "b0000000-0000-4000-8000-000000000001"


def test_users_are_read_from_a_graph_page(write_json):
    path = write_json("users.json", {"value": [
        {"id": ANN, "userPrincipalName": "ann@firm.example", "displayName": "Ann",
         "accountEnabled": True, "userType": "Member"},
        {"id": BOB, "userPrincipalName": "guest#EXT#@firm.example", "displayName": None,
         "accountEnabled": True, "userType": "Guest"},
    ]})
    users = entra_users.read(path)
    assert users[0] == entra_users.User(ANN, "ann@firm.example", "Ann", True, "Member", "users.json:1")
    assert (users[1].display_name, users[1].user_type, users[1].cite) == ("", "Guest", "users.json:2")


def test_a_null_user_type_reads_as_empty_not_guest(write_json):
    path = write_json("users.json", [
        {"id": ANN, "userPrincipalName": "a@f.example", "accountEnabled": True, "userType": None},
    ])
    assert entra_users.read(path)[0].user_type == ""


def test_a_user_without_account_enabled_stops_the_run(write_json):
    path = write_json("users.json", [{"id": ANN, "userPrincipalName": "a@f.example", "userType": "Member"}])
    with pytest.raises(AttestError, match="users.json: row 1 has no field 'accountEnabled'"):
        entra_users.read(path)


def test_registration_reads_is_mfa_registered(write_json):
    path = write_json("reg.json", {"value": [
        {"id": ANN, "userPrincipalName": "ann@firm.example", "isMfaRegistered": True, "isAdmin": False},
        {"id": BOB, "userPrincipalName": "bob@firm.example", "isMfaRegistered": False},
    ]})
    assert [(r.user_id, r.mfa_registered, r.cite) for r in entra_registration.read(path)] == [
        (ANN, True, "reg.json:1"),
        (BOB, False, "reg.json:2"),
    ]


def test_registration_without_is_mfa_registered_stops_the_run(write_json):
    path = write_json("reg.json", [{"id": ANN, "userPrincipalName": "a@f.example", "isMfaCapable": True}])
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
        {"id": "ra1", "principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": "/",
         "principal": {"@odata.type": "#microsoft.graph.user", "id": ANN,
                       "userPrincipalName": "ann@firm.example", "displayName": "Ann"}},
        {"id": "ra2", "principalId": GROUP, "roleDefinitionId": EXCHANGE_ADMIN,
         "directoryScopeId": "/administrativeUnits/x",
         "principal": {"@odata.type": "#microsoft.graph.group", "id": GROUP, "displayName": "IT admins"}},
    ]})
    first, second = entra_role_assignments.read(path)
    assert (first.principal_kind, first.principal_name, first.role_id, first.scope, first.cite) == (
        "user", "ann@firm.example", GLOBAL_ADMIN, "/", "roles.json:1")
    assert (second.principal_kind, second.principal_name, second.scope) == (
        "group", "IT admins", "/administrativeUnits/x")


def test_role_assignments_without_expanded_principal_say_how_to_export(write_json):
    path = write_json("roles.json", [{"id": "ra1", "principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN}])
    with pytest.raises(AttestError, match=r"\$expand=principal"):
        entra_role_assignments.read(path)


def test_a_role_scope_is_recorded_as_exported_never_guessed(write_json):
    principal = {"@odata.type": "#microsoft.graph.user", "id": ANN, "userPrincipalName": "ann@firm.example"}
    path = write_json("roles.json", [
        {"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "appScopeId": "/AccessPackageCatalog/c1",
         "principal": principal},
        {"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": None, "principal": principal},
    ])
    app_scoped, unscoped = entra_role_assignments.read(path)
    assert (app_scoped.scope, app_scoped.app_scope) == ("", "/AccessPackageCatalog/c1")
    assert (unscoped.scope, unscoped.app_scope) == ("", "")


def test_a_null_principal_stops_the_run_naming_both_causes(write_json):
    path = write_json("roles.json", [{"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "principal": None}])
    with pytest.raises(AttestError, match="a null principal means its account was deleted"):
        entra_role_assignments.read(path)


def test_two_users_sharing_an_id_stop_the_run_naming_both_rows(write_json):
    path = write_json("users.json", [
        {"id": ANN, "userPrincipalName": "ann@firm.example", "accountEnabled": True, "userType": "Member"},
        {"id": BOB, "userPrincipalName": "bob@firm.example", "accountEnabled": True, "userType": "Member"},
        {"id": ANN, "userPrincipalName": "ann2@firm.example", "accountEnabled": False, "userType": "Member"},
    ])
    with pytest.raises(AttestError, match=rf"users\.json: rows 1 and 3 share id '{ANN}'"):
        entra_users.read(path)


def test_two_users_sharing_a_user_principal_name_in_another_case_stop_the_run(write_json):
    path = write_json("users.json", [
        {"id": ANN, "userPrincipalName": "Ann@firm.example", "accountEnabled": True, "userType": "Member"},
        {"id": BOB, "userPrincipalName": "ann@FIRM.example", "accountEnabled": False, "userType": "Member"},
    ])
    with pytest.raises(AttestError, match=r"users\.json: rows 1 and 2 share userPrincipalName 'ann@FIRM\.example'"):
        entra_users.read(path)


def test_two_registration_rows_sharing_an_id_stop_the_run(write_json):
    path = write_json("reg.json", [
        {"id": ANN, "userPrincipalName": "ann@firm.example", "isMfaRegistered": False},
        {"id": ANN, "userPrincipalName": "ann@firm.example", "isMfaRegistered": True},
    ])
    with pytest.raises(AttestError, match=rf"reg\.json: rows 1 and 2 share id '{ANN}'"):
        entra_registration.read(path)


@pytest.mark.parametrize("upn", ["cy@firm.example ", " cy@firm.example", "cy@firm.example\n"])
def test_a_user_principal_name_with_leading_or_trailing_whitespace_stops_the_run(write_json, upn):
    path = write_json("users.json", [
        {"id": ANN, "userPrincipalName": "ann@firm.example", "accountEnabled": True, "userType": "Member"},
        {"id": BOB, "userPrincipalName": upn, "accountEnabled": True, "userType": "Member"},
    ])
    message = f"users.json: row 2 field 'userPrincipalName' has leading or trailing whitespace: {re.escape(repr(upn))}"
    with pytest.raises(AttestError, match=message):
        entra_users.read(path)


@pytest.mark.parametrize("padded_second", [True, False])
def test_two_accounts_for_one_address_one_padded_stop_the_run_in_either_order(write_json, padded_second):
    plain = {"id": ANN, "userPrincipalName": "cy@firm.example", "accountEnabled": False, "userType": "Member"}
    padded = {"id": BOB, "userPrincipalName": "cy@firm.example ", "accountEnabled": True, "userType": "Member"}
    path = write_json("users.json", [plain, padded] if padded_second else [padded, plain])
    row = 2 if padded_second else 1
    message = f"users.json: row {row} field 'userPrincipalName' has leading or trailing whitespace"
    with pytest.raises(AttestError, match=message):
        entra_users.read(path)


def _user_row(**changes):
    return {"id": ANN, "userPrincipalName": "ann@firm.example", "displayName": "Ann", "accountEnabled": True,
            "userType": "Member", **changes}


def test_a_user_id_that_is_not_a_guid_stops_the_run(write_json):
    path = write_json("users.json", [_user_row(id="u1")])
    with pytest.raises(AttestError, match=re.escape("users.json: row 1 field 'id' must be an object GUID, got 'u1'")):
        entra_users.read(path)


@pytest.mark.parametrize("spelling", [ANN.upper(), "{" + ANN + "}"])
def test_a_user_id_is_read_as_the_canonical_lower_case_guid(write_json, spelling):
    assert entra_users.read(write_json("users.json", [_user_row(id=spelling)]))[0].id == ANN


def test_two_spellings_of_one_user_id_are_one_id(write_json):
    path = write_json("users.json", [_user_row(), _user_row(id=ANN.upper(), userPrincipalName="ann2@firm.example")])
    with pytest.raises(AttestError, match=rf"users\.json: rows 1 and 2 share id '{ANN}'"):
        entra_users.read(path)


@pytest.mark.parametrize("field, value", [("userType", 5), ("displayName", 7), ("userType", ["Member"])])
def test_a_user_type_or_display_name_that_is_not_a_string_stops_the_run(write_json, field, value):
    path = write_json("users.json", [_user_row(**{field: value})])
    message = f"users.json: row 1 field '{field}' must be a string, got {value!r}"
    with pytest.raises(AttestError, match=re.escape(message)):
        entra_users.read(path)


def test_a_users_export_that_is_a_single_object_stops_the_run(write_json):
    # GET /users/{id} returns one user: read as the whole population, it would shrink it to one account.
    path = write_json("users.json", _user_row())
    with pytest.raises(AttestError, match="users.json: expected a list of records, got a single object"):
        entra_users.read(path)


def test_a_registration_id_is_read_as_the_canonical_guid_and_must_be_one(write_json):
    row = {"id": ANN.upper(), "userPrincipalName": "ann@firm.example", "isMfaRegistered": True}
    assert entra_registration.read(write_json("reg.json", [row]))[0].user_id == ANN
    with pytest.raises(AttestError, match=re.escape("reg.json: row 1 field 'id' must be an object GUID, got 'u1'")):
        entra_registration.read(write_json("reg.json", [{**row, "id": "u1"}]))


USER_PRINCIPAL = {"@odata.type": "#microsoft.graph.user", "id": ANN, "userPrincipalName": "ann@firm.example"}


def test_role_assignment_principal_and_role_ids_are_read_as_canonical_guids(write_json):
    path = write_json("roles.json", [{"principalId": "{" + ANN.upper() + "}", "roleDefinitionId": GLOBAL_ADMIN.upper(),
                                      "directoryScopeId": "/", "principal": USER_PRINCIPAL}])
    (assignment,) = entra_role_assignments.read(path)
    assert (assignment.principal_id, assignment.role_id) == (ANN, GLOBAL_ADMIN)


@pytest.mark.parametrize("field, value", [("principalId", "u1"), ("roleDefinitionId", "Global Administrator")])
def test_a_role_assignment_id_that_is_not_a_guid_stops_the_run(write_json, field, value):
    row = {"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": "/", "principal": USER_PRINCIPAL}
    path = write_json("roles.json", [{**row, field: value}])
    with pytest.raises(AttestError, match=re.escape(f"roles.json: row 1 field '{field}' must be an object GUID")):
        entra_role_assignments.read(path)


@pytest.mark.parametrize("principal, field", [
    ({"@odata.type": "#microsoft.graph.group", "id": GROUP, "displayName": 7}, "principal.displayName"),
    ({**USER_PRINCIPAL, "userPrincipalName": 7}, "principal.userPrincipalName"),
])
def test_a_principal_name_that_is_not_a_string_stops_the_run(write_json, principal, field):
    path = write_json("roles.json", [{"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": "/",
                                      "principal": principal}])
    with pytest.raises(AttestError, match=re.escape(f"roles.json: row 1 field '{field}' must be a string, got 7")):
        entra_role_assignments.read(path)


def test_an_app_scope_of_slash_is_not_a_directory_scope(write_json):
    path = write_json("roles.json", [{"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "appScopeId": "/",
                                      "principal": USER_PRINCIPAL}])
    (assignment,) = entra_role_assignments.read(path)
    assert (assignment.scope, assignment.app_scope) == ("", "/")


def test_a_role_assignments_export_that_is_a_single_object_stops_the_run(write_json):
    # The role assignments are the admin population; one assignment read as all of them would shrink it.
    path = write_json("roles.json", {"principalId": ANN, "roleDefinitionId": GLOBAL_ADMIN, "directoryScopeId": "/",
                                     "principal": USER_PRINCIPAL})
    with pytest.raises(AttestError, match="roles.json: expected a list of records, got a single object"):
        entra_role_assignments.read(path)
