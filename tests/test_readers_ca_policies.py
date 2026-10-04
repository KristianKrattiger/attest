import pytest

from attest.model import AttestError
from attest.readers.entra_ca_policies import CaPolicy, narrowing_conditions, read, requires_mfa

MFA_STRENGTH = {"id": "00000000-0000-0000-0000-000000000002", "displayName": "Multifactor authentication"}
ODATA_STRENGTH_CONTEXT = ("https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/"
                          "policies('p1')/grantControls/authenticationStrength/$entity")
PASSWORDLESS_STRENGTH = {"id": "00000000-0000-0000-0000-000000000003", "displayName": "Passwordless MFA"}
PHISHING_RESISTANT_STRENGTH = {"id": "00000000-0000-0000-0000-000000000004", "displayName": "Phishing-resistant MFA"}

BASE = {
    "clientAppTypes": ["all"],
    "applications": {"includeApplications": ["All"], "excludeApplications": []},
    "users": {"includeUsers": ["All"]},
    "locations": None,
    "platforms": None,
    "devices": None,
    "signInRiskLevels": [],
    "userRiskLevels": [],
    "servicePrincipalRiskLevels": [],
}


@pytest.mark.parametrize("grant, expected", [
    ({"operator": "OR", "builtInControls": ["mfa"]}, True),
    ({"operator": "AND", "builtInControls": ["mfa", "compliantDevice"]}, True),
    ({"operator": "OR", "builtInControls": ["mfa", "compliantDevice"]}, False),
    ({"operator": "OR", "builtInControls": [], "authenticationStrength": MFA_STRENGTH}, True),
    ({"operator": "OR", "builtInControls": [], "authenticationStrength": {"id": "custom-1"}}, False),
    ({"operator": "OR", "builtInControls": ["mfa"], "authenticationStrength": {"id": "custom-1"}}, False),
    ({"operator": "OR", "builtInControls": ["mfa"], "termsOfUse": ["tou-1"]}, False),
    ({"operator": "AND", "builtInControls": ["mfa"], "termsOfUse": ["tou-1"]}, True),
    ({"operator": "OR", "builtInControls": ["block"]}, False),
    ({"operator": "AND", "builtInControls": ["block", "mfa"]}, False),
    ({"operator": "OR", "builtInControls": ["compliantDevice"]}, False),
    ({"builtInControls": ["mfa", "domainJoinedDevice"]}, False),
    (None, False),
    ({"operator": "AND", "builtInControls": ["Block"], "authenticationStrength": MFA_STRENGTH}, False),
    ({"operator": "OR", "builtInControls": ["MFA"]}, True),
    ({"operator": "OR", "builtInControls": ["MFA", "CompliantDevice"]}, False),
    ({"operator": "AND", "builtInControls": ["MFA", "CompliantDevice"]}, True),
    ({"operator": "OR", "builtInControls": [], "authenticationStrength": PASSWORDLESS_STRENGTH}, True),
    ({"operator": "OR", "builtInControls": [], "authenticationStrength": PHISHING_RESISTANT_STRENGTH}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "newAlternative": ["x"]}, False),
    ({"operator": "AND", "builtInControls": ["mfa"], "newAlternative": ["x"]}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "newAlternative": {"x": 1}}, False),
    ({"operator": "OR", "builtInControls": ["mfa"], "newAlternative": None}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "newAlternative": []}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "newAlternative": {}}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "@odata.type": "#microsoft.graph.g"}, True),
    ({"operator": "OR", "builtInControls": [], "customAuthenticationFactors": [], "termsOfUse": [],
      "authenticationStrength@odata.context": ODATA_STRENGTH_CONTEXT,
      "authenticationStrength": MFA_STRENGTH}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "authenticationStrength@odata.context": "x",
      "authenticationStrength": None}, True),
    ({"operator": "OR", "builtInControls": ["mfa"], "@microsoft.graph.tip": "x"}, True),
])
def test_requires_mfa_only_when_every_way_through_takes_mfa(grant, expected):
    assert requires_mfa(grant) is expected


def test_a_plain_all_users_all_apps_policy_has_no_narrowing():
    assert narrowing_conditions(BASE) == ()


def test_locations_that_include_all_without_exclusions_do_not_narrow():
    assert narrowing_conditions({**BASE, "locations": {"includeLocations": ["All"], "excludeLocations": []}}) == ()


def test_an_empty_devices_object_does_not_narrow():
    devices = {"@odata.type": "#microsoft.graph.conditionalAccessDevices",
               "deviceFilter": None, "includeDevices": [], "excludeDevices": []}
    assert narrowing_conditions({**BASE, "devices": devices}) == ()


@pytest.mark.parametrize("change, name", [
    ({"clientAppTypes": ["browser", "mobileAppsAndDesktopClients"]}, "clientAppTypes"),
    ({"locations": {"includeLocations": ["All"], "excludeLocations": ["AllTrusted"]}}, "locations"),
    ({"locations": {"includeLocations": ["loc-1"], "excludeLocations": []}}, "locations"),
    ({"platforms": {"includePlatforms": ["windows"], "excludePlatforms": []}}, "platforms"),
    ({"platforms": {"includePlatforms": ["all"], "excludePlatforms": ["iOS"]}}, "platforms"),
    ({"devices": {"deviceFilter": {"mode": "exclude", "rule": "device.isCompliant -eq True"}}}, "devices"),
    ({"signInRiskLevels": ["high"]}, "signInRiskLevels"),
    ({"userRiskLevels": ["medium"]}, "userRiskLevels"),
    ({"servicePrincipalRiskLevels": ["high"]}, "servicePrincipalRiskLevels"),
    ({"insiderRiskLevels": "elevated"}, "insiderRiskLevels"),
    ({"authenticationFlows": {"transferMethods": "deviceCodeFlow"}}, "authenticationFlows"),
    ({"applications": {"includeApplications": ["All"], "excludeApplications": ["app-1"]}},
     "applications.excludeApplications"),
    ({"applications": {"includeApplications": ["All"], "includeUserActions": ["urn:user:registersecurityinfo"]}},
     "applications.includeUserActions"),
    ({"clientAppTypes": ["all", "browser"]}, "clientAppTypes"),
    ({"clientApplications": {"includeServicePrincipals": ["All"], "excludeServicePrincipals": ["sp-1"]}},
     "clientApplications"),
    ({"applications": {"includeApplications": ["All"], "applicationFilter": {"mode": "include", "rule": "x"}}},
     "applications.applicationFilter"),
    ({"applications": {"includeApplications": ["All"],
                       "includeAuthenticationContextClassReferences": ["c1"]}},
     "applications.includeAuthenticationContextClassReferences"),
    ({"deviceStates": {"includeStates": ["All"], "excludeStates": ["Compliant"]}},
     "unknown condition deviceStates"),
    ({"applications": {"includeApplications": ["All"], "someNewFilter": {"x": 1}}},
     "unknown condition applications.someNewFilter"),
    ({"users": {"includeUsers": ["All"], "someNewExclusion": ["u1"]}},
     "unknown condition users.someNewExclusion"),
    ({"locations": {"includeLocations": ["All"], "newLocationFilter": {"x": 1}}},
     "unknown condition locations.newLocationFilter"),
    ({"platforms": {"includePlatforms": ["all"], "newPlatformFilter": ["x"]}},
     "unknown condition platforms.newPlatformFilter"),
])
def test_each_narrowing_condition_is_named(change, name):
    assert name in narrowing_conditions({**BASE, **change})


@pytest.mark.parametrize("empty", [None, [], {}])
@pytest.mark.parametrize("change", [
    lambda empty: {"deviceStates": empty},
    lambda empty: {"applications": {"includeApplications": ["All"], "someNewFilter": empty}},
    lambda empty: {"users": {"includeUsers": ["All"], "someNewExclusion": empty}},
    lambda empty: {"locations": {"includeLocations": ["All"], "newLocationFilter": empty}},
    lambda empty: {"platforms": {"includePlatforms": ["all"], "newPlatformFilter": empty}},
], ids=["conditions", "applications", "users", "locations", "platforms"])
def test_an_unknown_condition_with_nothing_in_it_does_not_narrow(change, empty):
    assert narrowing_conditions({**BASE, **change(empty)}) == ()


COLLECTION = "#Collection(String)"


@pytest.mark.parametrize("change", [
    {"clientAppTypes@odata.type": COLLECTION},
    {"users": {"includeUsers": ["All"], "includeUsers@odata.type": COLLECTION}},
    {"applications": {"includeApplications": ["All"], "@microsoft.graph.tip": "x"}},
    {"applications": {"includeApplications": ["All"], "includeApplications@odata.type": COLLECTION}},
    {"locations": {"includeLocations": ["All"], "includeLocations@odata.type": COLLECTION}},
    {"platforms": {"includePlatforms": ["all"], "includePlatforms@odata.type": COLLECTION}},
    {"devices": {"deviceFilter": None, "includeDevices": [], "includeDevices@odata.type": COLLECTION}},
], ids=["conditions", "users", "applications-instance", "applications", "locations", "platforms", "devices"])
def test_property_level_annotations_never_narrow(change):
    assert narrowing_conditions({**BASE, **change}) == ()


def test_a_missing_or_empty_client_app_types_narrows_in_the_pure_function():
    without = {k: v for k, v in BASE.items() if k != "clientAppTypes"}
    assert "clientAppTypes" in narrowing_conditions(without)
    assert "clientAppTypes" in narrowing_conditions({**BASE, "clientAppTypes": []})
    assert "clientAppTypes" in narrowing_conditions({**BASE, "clientAppTypes": None})


def test_odata_annotations_never_narrow():
    conditions = {**BASE, "@odata.context": "ctx",
                  "applications": {"includeApplications": ["All"], "@odata.type": "#microsoft.graph.x"},
                  "users": {"includeUsers": ["All"], "@odata.type": "#microsoft.graph.y"},
                  "locations": {"includeLocations": ["All"], "@odata.type": "#microsoft.graph.z"},
                  "platforms": {"includePlatforms": ["all"], "@odata.type": "#microsoft.graph.w"}}
    assert narrowing_conditions(conditions) == ()


def test_read_builds_a_policy_from_graph_json(write_json):
    path = write_json("ca.json", {"value": [{
        "id": "p1", "displayName": "Require MFA for all users", "state": "enabled",
        "conditions": {**BASE, "users": {"includeUsers": ["All"], "excludeUsers": ["u9"], "excludeGroups": ["g1"],
                                         "includeRoles": [], "excludeRoles": ["r1"]}},
        "grantControls": {"operator": "OR", "builtInControls": ["mfa"]},
    }]})
    assert read(path) == (CaPolicy(
        id="p1", name="Require MFA for all users", state="enabled",
        include_users=("All",), exclude_users=("u9",), exclude_groups=("g1",),
        include_roles=(), exclude_roles=("r1",), include_apps=("All",),
        narrowing=(), requires_mfa=True, cite="ca.json:1"),)


def test_a_session_only_policy_with_null_grant_does_not_require_mfa(write_json):
    path = write_json("ca.json", [{"id": "p2", "displayName": "Sign-in frequency", "state": "enabled",
                                   "conditions": BASE, "grantControls": None}])
    assert read(path)[0].requires_mfa is False


def test_a_policy_without_conditions_stops_the_run(write_json):
    path = write_json("ca.json", [{"id": "p3", "state": "enabled", "grantControls": None}])
    with pytest.raises(AttestError, match="no field 'conditions'"):
        read(path)


GOOD_GRANT = {"operator": "OR", "builtInControls": ["mfa"]}


def _one_policy(write_json, conditions=BASE, grant=GOOD_GRANT):
    return write_json("ca.json", [{"id": "p1", "displayName": "P", "state": "enabled",
                                   "conditions": conditions, "grantControls": grant}])


def test_a_new_policy_field_leaves_the_twelve_argument_constructor_working():
    policy = CaPolicy("p1", "P", "enabled", (), (), (), (), (), (), (), True, "ca.json:1")
    assert policy.exclude_guest_types == ()


def test_the_excluded_guest_and_external_user_types_are_recorded(write_json):
    users = {"includeUsers": ["All"], "excludeGuestsOrExternalUsers": {
        "guestOrExternalUserTypes": "internalGuest,b2bCollaborationGuest",
        "externalTenants": {"membershipKind": "all"}}}
    path = _one_policy(write_json, {**BASE, "users": users})
    assert read(path)[0].exclude_guest_types == ("internalGuest", "b2bCollaborationGuest")


def test_an_exclusion_object_that_names_no_guest_type_is_recorded_as_unknown(write_json):
    users = {"includeUsers": ["All"], "excludeGuestsOrExternalUsers": {
        "guestOrExternalUserTypes": "", "externalTenants": {"membershipKind": "all"}}}
    path = _one_policy(write_json, {**BASE, "users": users})
    assert read(path)[0].exclude_guest_types == ("unknown",)


def test_an_empty_exclusion_object_records_no_guest_type(write_json):
    users = {"includeUsers": ["All"], "excludeGuestsOrExternalUsers": {
        "@odata.type": "#microsoft.graph.conditionalAccessGuestsOrExternalUsers",
        "guestOrExternalUserTypes": "", "externalTenants": None}}
    path = _one_policy(write_json, {**BASE, "users": users})
    assert read(path)[0].exclude_guest_types == ()


def test_the_legacy_guest_exclusion_in_exclude_users_is_recorded(write_json):
    path = _one_policy(write_json, {**BASE, "users": {"includeUsers": ["All"],
                                                      "excludeUsers": ["GuestsOrExternalUsers"]}})
    policy = read(path)[0]
    assert policy.exclude_guest_types == ("GuestsOrExternalUsers",)
    assert policy.exclude_users == ("GuestsOrExternalUsers",)


def _users(**fields):
    return {**BASE, "users": {"includeUsers": ["All"], **fields}}


@pytest.mark.parametrize("conditions, grant", [
    (_users(excludeUsers="u9"), GOOD_GRANT),
    (BASE, {"operator": "OR", "builtInControls": "mfa"}),
    ({**BASE, "locations": ["x"]}, GOOD_GRANT),
    (BASE, ["mfa"]),
    (BASE, {"operator": 1, "builtInControls": ["mfa"]}),
    ({**BASE, "clientAppTypes": [None]}, GOOD_GRANT),
    ({k: v for k, v in BASE.items() if k != "clientAppTypes"}, GOOD_GRANT),
    ({**BASE, "users": "All"}, GOOD_GRANT),
    ({**BASE, "applications": ["All"]}, GOOD_GRANT),
    ({**BASE, "platforms": "windows"}, GOOD_GRANT),
    (BASE, {"operator": "OR", "builtInControls": ["mfa", 2]}),
    (_users(includeUsers="All"), GOOD_GRANT),
    (_users(excludeGroups="g1"), GOOD_GRANT),
    (_users(includeRoles="r1"), GOOD_GRANT),
    (_users(excludeRoles=[1]), GOOD_GRANT),
    (_users(excludeGuestsOrExternalUsers="internalGuest"), GOOD_GRANT),
    (_users(excludeGuestsOrExternalUsers={"guestOrExternalUserTypes": ["internalGuest"]}), GOOD_GRANT),
    ({**BASE, "applications": {"includeApplications": "All"}}, GOOD_GRANT),
    ({**BASE, "clientAppTypes": "all"}, GOOD_GRANT),
    ({**BASE, "locations": {"includeLocations": [None]}}, GOOD_GRANT),
    ({**BASE, "locations": {"includeLocations": "All"}}, GOOD_GRANT),
    ({**BASE, "locations": {"includeLocations": ["All"], "excludeLocations": "loc-1"}}, GOOD_GRANT),
    ({**BASE, "platforms": {"includePlatforms": "all"}}, GOOD_GRANT),
    ({**BASE, "platforms": {"includePlatforms": ["all"], "excludePlatforms": 5}}, GOOD_GRANT),
    (BASE, {"operator": "OR", "builtInControls": ["mfa"], "termsOfUse": 5}),
    (BASE, {"operator": "OR", "builtInControls": ["mfa"], "customAuthenticationFactors": "x"}),
], ids=["excludeUsers-string", "builtInControls-string", "locations-list", "grantControls-list",
        "operator-number", "clientAppTypes-None-item", "clientAppTypes-missing", "users-string",
        "applications-list", "platforms-string", "builtInControls-number-item", "includeUsers-string",
        "excludeGroups-string", "includeRoles-string", "excludeRoles-number-item",
        "excludeGuests-string", "guestTypes-list", "includeApplications-string", "clientAppTypes-string",
        "includeLocations-None-item", "includeLocations-string", "excludeLocations-string",
        "includePlatforms-string", "excludePlatforms-number", "termsOfUse-number",
        "customAuthenticationFactors-string"])
def test_malformed_policy_json_stops_the_run_with_file_and_row(write_json, conditions, grant):
    path = _one_policy(write_json, conditions, grant)
    with pytest.raises(AttestError, match=r"ca\.json: row 1"):
        read(path)


@pytest.mark.parametrize("empty", [None, []], ids=["null", "empty-list"])
def test_a_client_app_types_with_nothing_in_it_stops_the_run(write_json, empty):
    path = _one_policy(write_json, {**BASE, "clientAppTypes": empty})
    with pytest.raises(AttestError,
                       match=r"ca\.json: row 1 field 'clientAppTypes' must name at least one client app type"):
        read(path)


def test_null_objects_and_lists_read_as_empty(write_json):
    conditions = {**BASE, "users": None, "applications": None, "locations": None, "platforms": None}
    policy = read(_one_policy(write_json, conditions, None))[0]
    assert (policy.include_users, policy.include_apps, policy.requires_mfa) == ((), (), False)
