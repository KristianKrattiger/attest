from datetime import timedelta

import pytest

from attest.rules import edr
from attest.rules.edr import edr_alert_monitoring, edr_all_endpoints
from builders import NOW, device, evidence, machine, taken


def fleet(n=3, **overrides):
    """n Intune devices, each matched in Defender by Entra device ID, onboarded, Active, seen at NOW."""
    exports = dict(intune_devices=[device(i) for i in range(1, n + 1)],
                   defender_machines=[machine(i) for i in range(1, n + 1)])
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def test_backed_when_every_intune_device_is_onboarded_active_and_recent():
    v = edr_all_endpoints(fleet())
    assert v.status == "backed"
    assert v.population == "3 devices from intune_devices.json"
    assert "matched by Entra device ID 3" in v.reason


def test_a_device_missing_from_defender_is_a_gap():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2)]))
    assert (v.status, v.entities) == ("gap", ("LT-03",))
    assert "LT-03: not in Defender" in v.reason


@pytest.mark.parametrize("m, why", [
    (machine(3, onboarding="CanBeOnboarded"), "onboarding status CanBeOnboarded"),
    (machine(3, health="Inactive"), "health Inactive"),
    (machine(3, last_seen=NOW - timedelta(days=8)), "last seen 2026-09-23"),
    (machine(3, last_seen=None), "never seen"),
])
def test_an_unonboarded_unhealthy_or_stale_device_is_a_gap(m, why):
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2), m]))
    assert (v.status, v.entities) == ("gap", ("LT-03",))
    assert why in v.reason


def test_seen_exactly_seven_days_before_the_export_is_still_recent():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2),
                                                   machine(3, last_seen=NOW - timedelta(days=7))]))
    assert v.status == "backed"


def test_seen_exactly_at_the_export_time_is_still_recent():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2), machine(3, last_seen=NOW)]))
    assert v.status == "backed"


def test_seen_after_the_export_time_is_a_gap_not_recent():
    # A lastSeen later than the export it came from cannot be true, so it cannot show a recent check-in.
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2),
                                                   machine(3, last_seen=NOW + timedelta(hours=1))]))
    assert (v.status, v.entities) == ("gap", ("LT-03",))
    assert "last seen after the export time" in v.reason


def test_the_window_in_the_reason_follows_the_constant(monkeypatch):
    monkeypatch.setattr(edr, "STALE_AFTER", timedelta(days=3))
    assert "seen within 3 days of" in edr_all_endpoints(fleet()).reason


def test_devices_without_entra_ids_match_by_short_name():
    v = edr_all_endpoints(fleet(intune_devices=[device(1, aad=False)], defender_machines=[machine(1, aad=False)]))
    assert v.status == "backed"
    assert "matched by device name 1" in v.reason


def test_two_defender_machines_with_the_same_short_name_match_neither():
    v = edr_all_endpoints(fleet(intune_devices=[device(1, aad=False)], defender_machines=[
        machine(1, aad=False), machine(9, name="LT-01.other.example", aad=False)]))
    assert (v.status, v.entities) == ("gap", ("LT-01",))


def test_a_defender_only_machine_is_listed_outside_the_population():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2), machine(3),
                                                   machine(9, name="fs-01.firm.example", aad=False)]))
    assert v.status == "backed"
    assert "outside the population): fs-01.firm.example" in v.reason


def test_adversarial_defender_all_healthy_but_intune_has_one_more_device_is_not_backed():
    v = edr_all_endpoints(fleet(n=4, defender_machines=[machine(i) for i in range(1, 4)]))
    assert (v.status, v.entities) == ("gap", ("LT-04",))


@pytest.mark.parametrize("overrides, why", [
    (dict(intune_devices=None), "no Intune managed-devices export"),
    (dict(defender_machines=None), "no Defender device export"),
    (dict(intune_devices=[]), "the population is empty"),
])
def test_missing_evidence_is_unchecked(overrides, why):
    v = edr_all_endpoints(fleet(**overrides))
    assert (v.status, why in v.reason) == ("unchecked", True)


def test_two_intune_devices_with_one_name_cannot_both_be_the_one_defender_machine():
    v = edr_all_endpoints(fleet(
        intune_devices=[device(1, aad=False), device(2, aad=False, name="LT-01")],
        defender_machines=[machine(1, aad=False)]))
    assert (v.status, v.entities) == ("gap", ("LT-01", "LT-01"))
    assert v.reason.count("LT-01: ambiguous name match") == 2
    assert v.cited == ("intune.json:1", "intune.json:2")
    assert "outside the population" not in v.reason


def test_a_defender_machine_matched_by_entra_id_is_not_matched_again_by_name():
    v = edr_all_endpoints(fleet(
        intune_devices=[device(1), device(2, aad=False, name="LT-01")],
        defender_machines=[machine(1)]))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert v.reason.startswith("LT-01: not in Defender")
    assert v.cited == ("intune.json:2",)
    assert "matched by Entra device ID 1" in v.reason
    assert "outside the population" not in v.reason


OLD = "lt-01-old.firm.example"


@pytest.mark.parametrize("reverse", [False, True])
def test_the_latest_defender_record_for_an_entra_device_decides_when_it_is_inactive(reverse):
    records = [machine(1, health="Inactive"), machine(2, entra="d-1", name=OLD, last_seen=NOW - timedelta(days=2))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records[::-1] if reverse else records))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: health Inactive" in v.reason
    assert f"older Defender records for LT-01: {OLD}" in v.reason
    assert "outside the population" not in v.reason


@pytest.mark.parametrize("reverse", [False, True])
def test_the_latest_defender_record_for_an_entra_device_decides_when_it_is_healthy(reverse):
    records = [machine(1), machine(2, entra="d-1", name=OLD, health="Inactive", last_seen=NOW - timedelta(days=30))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records[::-1] if reverse else records))
    assert v.status == "backed"
    assert f"older Defender records for LT-01: {OLD}" in v.reason
    assert "outside the population" not in v.reason


@pytest.mark.parametrize("reverse", [False, True])
def test_a_defender_record_never_seen_is_older_than_any_that_was(reverse):
    records = [machine(1, last_seen=None),
               machine(2, entra="d-1", name=OLD, health="Inactive", last_seen=NOW - timedelta(days=1))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records[::-1] if reverse else records))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: health Inactive" in v.reason
    assert "never seen" not in v.reason


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("seen", [NOW, None])
def test_defender_records_for_an_entra_device_tied_on_last_seen_are_ambiguous(reverse, seen):
    records = [machine(1, last_seen=seen), machine(2, entra="d-1", name=OLD, health="Inactive", last_seen=seen)]
    exported = records[::-1] if reverse else records
    v = edr_all_endpoints(fleet(n=1, defender_machines=exported))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: ambiguous Defender records" in v.reason
    assert "tied Defender records for LT-01: " in v.reason
    assert v.cited == ("intune.json:1",) + tuple(m.cite for m in exported)
    assert "outside the population" not in v.reason


def test_a_tie_for_the_latest_last_seen_is_ambiguous_even_with_an_older_record_present():
    records = [machine(1), machine(2, entra="d-1", name=OLD, health="Inactive"),
               machine(3, entra="d-1", name="lt-01-older.firm.example", last_seen=NOW - timedelta(days=5))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert v.reason.endswith("LT-01: ambiguous Defender records; "
                             f"tied Defender records for LT-01: lt-01.firm.example, {OLD}; "
                             "older Defender records for LT-01: lt-01-older.firm.example")
    assert v.cited == ("intune.json:1", "mde.json:1", "mde.json:2")


def test_a_device_never_pairs_by_name_with_a_machine_of_a_different_entra_device():
    v = edr_all_endpoints(fleet(n=1, defender_machines=[machine(9, name="lt-01.firm.example")]))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: not in Defender" in v.reason
    assert "in Defender but not Intune (outside the population): lt-01.firm.example" in v.reason


def test_a_machine_of_a_different_entra_device_with_the_same_name_is_outside_the_population():
    v = edr_all_endpoints(fleet(n=1, defender_machines=[machine(1), machine(9, name="lt-01.firm.example")]))
    assert v.status == "backed"
    assert v.reason.endswith("; matched by Entra device ID 1; "
                             "in Defender but not Intune (outside the population): lt-01.firm.example")


def test_a_machine_of_a_different_entra_device_adds_no_ambiguity_to_a_name_match():
    v = edr_all_endpoints(fleet(n=1, defender_machines=[
        machine(9, name="lt-01.firm.example"), machine(8, name="LT-01.other", aad=False)]))
    assert v.status == "backed"
    assert "matched by device name 1" in v.reason
    assert "(outside the population): lt-01.firm.example" in v.reason


@pytest.mark.parametrize("intune_has_id, defender_has_id", [(True, False), (False, True)])
def test_a_device_pairs_by_name_when_either_side_has_no_entra_id(intune_has_id, defender_has_id):
    v = edr_all_endpoints(fleet(n=1, intune_devices=[device(1, aad=intune_has_id)],
                                defender_machines=[machine(1, aad=defender_has_id)]))
    assert v.status == "backed"
    assert "matched by device name 1" in v.reason


def test_machines_a_device_could_not_choose_between_are_not_called_outside_the_population():
    v = edr_all_endpoints(fleet(intune_devices=[device(1, aad=False)], defender_machines=[
        machine(1, aad=False), machine(9, name="LT-01.other.example", aad=False)]))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "outside the population" not in v.reason


def test_an_empty_defender_export_leaves_every_device_a_gap_not_unchecked():
    v = edr_all_endpoints(fleet(defender_machines=[]))
    assert (v.status, v.entities) == ("gap", ("LT-01", "LT-02", "LT-03"))
    assert v.reason.count(": not in Defender") == 3


def test_onboarding_and_health_are_compared_without_regard_to_case():
    v = edr_all_endpoints(fleet(defender_machines=[
        machine(i, onboarding="ONBOARDED", health="active") for i in range(1, 4)]))
    assert v.status == "backed"


def test_alert_monitoring_is_always_unchecked():
    v = edr_alert_monitoring(fleet())
    assert (v.status, v.reason) == ("unchecked", "no export in v1 shows that alerts are monitored")


# Defender machines no Intune device could be (decision 3, 2026-10-05): one that is onboardable, seen recently and not
# healthy is a gap; one seen long ago or never is listed with when it was last seen and changes nothing.

SERVER = "srv-01.firm.example"


def with_server(**state):
    return fleet(defender_machines=[machine(1), machine(2), machine(3), machine(9, name=SERVER, aad=False, **state)])


@pytest.mark.parametrize("state, problems", [
    (dict(health="Inactive"), "health Inactive"),
    (dict(onboarding="CanBeOnboarded"), "onboarding status CanBeOnboarded"),
    (dict(onboarding="CanBeOnboarded", health="Inactive", last_seen=NOW - timedelta(days=7)),
     "onboarding status CanBeOnboarded, health Inactive"),
    # a lastSeen after the export is recent too: only onboarding and health decide the gap (final re-review N2)
    (dict(health="Inactive", last_seen=NOW + timedelta(hours=1)), "health Inactive, last seen after the export time"),
])
def test_a_recent_unhealthy_defender_only_machine_is_a_gap(state, problems):
    v = edr_all_endpoints(with_server(**state))
    assert (v.status, v.entities) == ("gap", (SERVER,))
    assert v.reason.startswith(f"in Defender but not Intune and not healthy: {SERVER}: {problems}; ")
    assert v.cited == ("mde.json:9",)
    assert v.population == "3 devices from intune_devices.json"
    assert "outside the population" not in v.reason


def test_an_unhealthy_defender_only_machine_is_listed_after_the_population_s_own_gaps():
    v = edr_all_endpoints(fleet(defender_machines=[machine(1), machine(2),
                                                   machine(9, name=SERVER, aad=False, health="Inactive")]))
    assert (v.status, v.entities) == ("gap", ("LT-03", SERVER))
    assert v.reason.startswith(f"LT-03: not in Defender; in Defender but not Intune and not healthy: {SERVER}: ")


@pytest.mark.parametrize("onboarding", ["Unsupported", "UNSUPPORTED"])
def test_an_unsupported_defender_only_machine_is_no_gap(onboarding):
    v = edr_all_endpoints(with_server(onboarding=onboarding, health="Inactive"))
    assert v.status == "backed"
    assert v.reason.endswith(f"; in Defender but not Intune (outside the population): "
                             f"{SERVER} (onboarding status {onboarding}, health Inactive)")


@pytest.mark.parametrize("state, listed", [
    (dict(health="Inactive", last_seen=NOW - timedelta(days=30)), "health Inactive, last seen 2026-09-01"),
    (dict(onboarding="CanBeOnboarded", last_seen=None), "onboarding status CanBeOnboarded, never seen"),
    (dict(last_seen=NOW - timedelta(days=30)), "last seen 2026-09-01"),
    # a healthy machine seen after the export is listed, not a gap: only onboarding and health decide the gap
    (dict(last_seen=NOW + timedelta(hours=1)), "last seen after the export time"),
])
def test_a_defender_only_machine_not_seen_recently_is_listed_with_when_and_changes_nothing(state, listed):
    v = edr_all_endpoints(with_server(**state))
    assert v.status == "backed"
    assert v.reason.endswith(f"; in Defender but not Intune (outside the population): {SERVER} ({listed})")


# Every export a rule reads must be taken within 24 hours of the others (decision 4, 2026-10-05).

@pytest.mark.parametrize("field", ["intune_devices", "defender_machines"])
def test_edr_exports_taken_more_than_24_hours_apart_are_unchecked(field):
    v = edr_all_endpoints(taken(fleet(), field, 25))
    other = "defender_machines" if field == "intune_devices" else "intune_devices"
    assert v.status == "unchecked"
    assert v.reason == (f"exports taken more than 24 hours apart: {field}.json at 2026-09-30T14:00:00+00:00, "
                        f"{other}.json at 2026-10-01T15:00:00+00:00")


def test_edr_exports_taken_exactly_24_hours_apart_are_still_checked():
    assert edr_all_endpoints(taken(fleet(), "intune_devices", 24)).status == "backed"
