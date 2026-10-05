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


def test_a_defender_machine_without_the_aad_device_id_field_stops_the_run(write_json):
    # The Machine resource always emits aadDeviceId (a nullable Guid): a dropped key must not
    # silently switch device matching from Entra ID to hostname.
    path = write_json("mde.json", [
        {"id": "m1", "computerDnsName": "x", "onboardingStatus": "Onboarded", "healthStatus": "Active",
         "lastSeen": None},
    ])
    with pytest.raises(AttestError, match="no field 'aadDeviceId'"):
        defender_machines.read(path)


def test_an_intune_device_without_the_operating_system_field_stops_the_run(write_json):
    path = write_json("intune.json", [
        {"id": "i1", "deviceName": "HP-LT-01", "azureADDeviceId": "d0000000-0000-4000-8000-000000000001"},
    ])
    with pytest.raises(AttestError, match="no field 'operatingSystem'"):
        intune_devices.read(path)


def test_an_intune_device_with_a_null_operating_system_reads_as_empty(write_json):
    path = write_json("intune.json", [
        {"id": "i1", "deviceName": "HP-LT-01", "azureADDeviceId": None, "operatingSystem": None},
    ])
    (device,) = intune_devices.read(path)
    assert (device.os, device.aad_device_id) == ("", None)


def test_a_defender_machine_without_last_seen_stops_the_run_but_a_null_last_seen_reads_as_none(write_json):
    row = {"id": "m1", "computerDnsName": "x", "aadDeviceId": None, "onboardingStatus": "Onboarded",
           "healthStatus": "Active"}
    with pytest.raises(AttestError, match="no field 'lastSeen'"):
        defender_machines.read(write_json("mde.json", [row]))
    (machine,) = defender_machines.read(write_json("mde-null.json", [{**row, "lastSeen": None}]))
    assert machine.last_seen is None


def test_a_device_id_that_is_not_a_guid_stops_the_run_naming_file_row_and_field(write_json):
    intune = write_json("intune.json", [
        {"id": "i1", "deviceName": "HP-LT-01", "azureADDeviceId": "n/a", "operatingSystem": "Windows"},
    ])
    with pytest.raises(AttestError, match="intune.json: row 1 field 'azureADDeviceId' must be a device GUID or null"):
        intune_devices.read(intune)
    mde = write_json("mde.json", [
        {"id": "m1", "computerDnsName": "x", "aadDeviceId": 12, "onboardingStatus": "Onboarded",
         "healthStatus": "Active", "lastSeen": None},
    ])
    with pytest.raises(AttestError, match="mde.json: row 1 field 'aadDeviceId' must be a device GUID or null"):
        defender_machines.read(mde)


def test_a_veeam_time_with_no_utc_offset_stops_the_run(write_json):
    # A server east of UTC that wrote local time without an offset would look fresher than it is.
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "IsMailboxBackedUp": True, "MailboxBackedUpTime": "2026-10-01T02:10:13"},
    ])
    with pytest.raises(AttestError, match="veeam.json: row 1 field 'MailboxBackedUpTime' has no UTC offset"):
        veeam_users.read(path)


def test_a_veeam_time_with_no_utc_offset_inside_the_value_wrapper_stops_the_run(write_json):
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": {"value": "2026-10-01T02:10:13", "DisplayHint": 2}},
    ])
    with pytest.raises(AttestError, match="has no UTC offset"):
        veeam_users.read(path)


def test_a_veeam_time_with_an_offset_is_read_as_utc(write_json):
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "IsMailboxBackedUp": True, "MailboxBackedUpTime": "2026-10-01T04:10:13+02:00"},
        {"Email": "bob@firm.example", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": {"value": "/Date(1790820613000)/", "DisplayHint": 2}},
        {"Email": "cy@firm.example", "IsMailboxBackedUp": True,
         "MailboxBackedUpTime": {"value": "2026-10-01T02:10:13Z", "DisplayHint": 2}},
    ])
    when = datetime(2026, 10, 1, 2, 10, 13, tzinfo=timezone.utc)
    assert [u.mailbox_backed_up_time for u in veeam_users.read(path)] == [when, when, when]


def test_an_empty_veeam_time_reads_as_never_backed_up(write_json):
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "IsMailboxBackedUp": False, "MailboxBackedUpTime": ""},
    ])
    (ann,) = veeam_users.read(path)
    assert ann.mailbox_backed_up_time is None


def test_a_veeam_row_flagged_backed_up_with_no_time_is_read_as_it_stands(write_json):
    # The reader only reports; the rule treats a mailbox with no time as never backed up.
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "IsMailboxBackedUp": True, "MailboxBackedUpTime": None},
    ])
    (ann,) = veeam_users.read(path)
    assert (ann.mailbox_backed_up, ann.mailbox_backed_up_time) == (True, None)


def test_a_veeam_backed_up_flag_that_is_not_a_json_boolean_stops_the_run(write_json):
    path = write_json("veeam.json", [
        {"Email": "ann@firm.example", "IsMailboxBackedUp": "True", "MailboxBackedUpTime": None},
    ])
    with pytest.raises(AttestError, match="true or false"):
        veeam_users.read(path)


def test_a_veeam_row_without_an_email_stops_the_run(write_json):
    path = write_json("veeam.json", [{"IsMailboxBackedUp": False, "MailboxBackedUpTime": None}])
    with pytest.raises(AttestError, match="no field 'Email'"):
        veeam_users.read(path)


def test_two_intune_devices_sharing_an_id_stop_the_run(write_json):
    row = {"id": "i1", "deviceName": "HP-LT-01", "azureADDeviceId": None, "operatingSystem": "Windows"}
    path = write_json("intune.json", [row, {**row, "deviceName": "HP-LT-02"}])
    with pytest.raises(AttestError, match=r"intune\.json: rows 1 and 2 share id 'i1'"):
        intune_devices.read(path)


def test_two_defender_machines_sharing_an_id_stop_the_run(write_json):
    row = {"id": "m1", "computerDnsName": "hp-lt-01.firm.example", "aadDeviceId": None,
           "onboardingStatus": "Onboarded", "healthStatus": "Active", "lastSeen": None}
    path = write_json("mde.json", [row, {**row, "healthStatus": "Inactive"}])
    with pytest.raises(AttestError, match=r"mde\.json: rows 1 and 2 share id 'm1'"):
        defender_machines.read(path)


def test_two_veeam_rows_sharing_an_email_in_another_case_stop_the_run(write_json):
    path = write_json("veeam.json", [
        {"Email": "Ann@firm.example", "IsMailboxBackedUp": False, "MailboxBackedUpTime": None},
        {"Email": "ann@firm.example", "IsMailboxBackedUp": True, "MailboxBackedUpTime": "2026-10-01T02:10:13Z"},
    ])
    with pytest.raises(AttestError, match=r"veeam\.json: rows 1 and 2 share Email 'ann@firm\.example'"):
        veeam_users.read(path)
