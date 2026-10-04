import pytest

from attest.model import AttestError
from attest.readers.entra_ca_policies import CaPolicy, narrowing_conditions, read, requires_mfa

MFA_STRENGTH = {"id": "00000000-0000-0000-0000-000000000002", "displayName": "Multifactor authentication"}

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
])
def test_each_narrowing_condition_is_named(change, name):
    assert name in narrowing_conditions({**BASE, **change})


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
