from dataclasses import replace
from datetime import timedelta

import pytest

from attest.rules.edr import edr_all_endpoints
from builders import NOW, device, evidence, machine


def fleet(n=3, **overrides):
    """n Intune devices, each matched in Defender by Entra device ID, onboarded, Active, seen at NOW."""
    exports = dict(intune_devices=[device(i) for i in range(1, n + 1)],
                   defender_machines=[machine(i) for i in range(1, n + 1)])
    exports.update(overrides)
    return evidence(**{k: v for k, v in exports.items() if v is not None})


def sibling(n, **overrides):
    """Another Defender record for device 1: a different machine ID and name, the same Entra device ID."""
    return replace(machine(n, **overrides), aad_device_id="d-1")


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
    records = [machine(1, health="Inactive"), sibling(2, name=OLD, last_seen=NOW - timedelta(days=2))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records[::-1] if reverse else records))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: health Inactive" in v.reason
    assert f"older Defender records for LT-01: {OLD}" in v.reason
    assert "outside the population" not in v.reason


@pytest.mark.parametrize("reverse", [False, True])
def test_the_latest_defender_record_for_an_entra_device_decides_when_it_is_healthy(reverse):
    records = [machine(1), sibling(2, name=OLD, health="Inactive", last_seen=NOW - timedelta(days=30))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records[::-1] if reverse else records))
    assert v.status == "backed"
    assert f"older Defender records for LT-01: {OLD}" in v.reason
    assert "outside the population" not in v.reason


@pytest.mark.parametrize("reverse", [False, True])
def test_a_defender_record_never_seen_is_older_than_any_that_was(reverse):
    records = [machine(1, last_seen=None), sibling(2, name=OLD, health="Inactive", last_seen=NOW - timedelta(days=1))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records[::-1] if reverse else records))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: health Inactive" in v.reason
    assert "never seen" not in v.reason


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("seen", [NOW, None])
def test_defender_records_for_an_entra_device_tied_on_last_seen_are_ambiguous(reverse, seen):
    records = [machine(1, last_seen=seen), sibling(2, name=OLD, health="Inactive", last_seen=seen)]
    exported = records[::-1] if reverse else records
    v = edr_all_endpoints(fleet(n=1, defender_machines=exported))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: ambiguous Defender records" in v.reason
    assert "tied Defender records for LT-01: " in v.reason
    assert v.cited == ("intune.json:1",) + tuple(m.cite for m in exported)
    assert "outside the population" not in v.reason


def test_a_tie_for_the_latest_last_seen_is_ambiguous_even_with_an_older_record_present():
    records = [machine(1), sibling(2, name=OLD, health="Inactive"),
               sibling(3, name="lt-01-older.firm.example", last_seen=NOW - timedelta(days=5))]
    v = edr_all_endpoints(fleet(n=1, defender_machines=records))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "ambiguous Defender records" in v.reason


def test_a_device_never_pairs_by_name_with_a_machine_of_a_different_entra_device():
    v = edr_all_endpoints(fleet(n=1, defender_machines=[machine(9, name="lt-01.firm.example")]))
    assert (v.status, v.entities) == ("gap", ("LT-01",))
    assert "LT-01: not in Defender" in v.reason
    assert "outside the population" not in v.reason


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
