from datetime import datetime, timezone

import pytest

from attest.model import AttestError
from attest.readers import defender_machines, intune_devices, veeam_users


def test_intune_devices_read_name_and_entra_device_id(write_json):
    path = write_json("intune.json", {"value": [
        {"id": "i1", "deviceName": "HP-LT-01", "azureADDeviceId": "D0000000-0000-4000-8000-000000000001",
         "operatingSystem": "Windows"},
        {"id": "i2", "deviceName": "PHONE-1", "azureADDeviceId": "00000000-0000-0000-0000-000000000000",
         "operatingSystem": "iOS"},
    ]})
    first, second = intune_devices.read(path)
    assert first == intune_devices.IntuneDevice(
        "i1", "HP-LT-01", "d0000000-0000-4000-8000-000000000001", "Windows", "intune.json:1")
    assert second.aad_device_id is None  # the all-zero GUID means "not joined"


def test_an_intune_device_without_the_azure_ad_device_id_field_stops_the_run(write_json):
    path = write_json("intune.json", [{"id": "i1", "deviceName": "HP-LT-01"}])
    with pytest.raises(AttestError, match="no field 'azureADDeviceId'"):
        intune_devices.read(path)


def test_defender_machines_read_health_onboarding_and_last_seen(write_json):
    path = write_json("mde.json", {"value": [
        {"id": "m1", "computerDnsName": "hp-lt-01.firm.example", "aadDeviceId": "d0000000-0000-4000-8000-000000000001",
         "onboardingStatus": "Onboarded", "healthStatus": "Active", "lastSeen": "2026-10-01T09:30:00.1234567Z"},
        {"id": "m2", "computerDnsName": "hp-fs01.firm.example", "aadDeviceId": None,
         "onboardingstatus": "CanBeOnboarded", "healthStatus": "Inactive", "lastSeen": None},
    ]})
    first, second = defender_machines.read(path)
    assert (first.name, first.aad_device_id, first.onboarding, first.health) == (
        "hp-lt-01.firm.example", "d0000000-0000-4000-8000-000000000001", "Onboarded", "Active")
    assert first.last_seen == datetime(2026, 10, 1, 9, 30, 0, 123456, tzinfo=timezone.utc)
    assert (second.aad_device_id, second.onboarding, second.last_seen) == (None, "CanBeOnboarded", None)


def test_a_defender_machine_without_health_status_stops_the_run(write_json):
    path = write_json("mde.json", [
        {"id": "m1", "computerDnsName": "x", "onboardingStatus": "Onboarded", "lastSeen": None},
    ])
    with pytest.raises(AttestError, match="no field 'healthStatus'"):
        defender_machines.read(path)


def test_veeam_users_read_mailbox_state_in_powershell_5_and_7_forms(write_json):
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "DisplayName": "Ann", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": "/Date(1790820613000)/"},
        {"Email": "bob@firm.example", "DisplayName": "Bob", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": "2026-10-01T02:10:13Z"},
        {"Email": "cy@firm.example", "DisplayName": "Cy", "IsMailboxBackedUp": False,
         "MailboxBackedUpTime": None},
    ])
    ann, bob, cy = veeam_users.read(path)
    when = datetime(2026, 10, 1, 2, 10, 13, tzinfo=timezone.utc)
    assert (ann.mailbox_backed_up_time, bob.mailbox_backed_up_time) == (when, when)
    assert (cy.email, cy.mailbox_backed_up, cy.mailbox_backed_up_time, cy.cite) == (
        "cy@firm.example", False, None, "veeam.json:3")


def test_a_veeam_export_without_mailbox_backup_time_stops_the_run(write_json):
    path = write_json("veeam.json", [{"Email": "ann@firm.example", "IsMailboxBackedUp": True}])
    with pytest.raises(AttestError, match="no field 'MailboxBackedUpTime'"):
        veeam_users.read(path)
