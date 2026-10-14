"""EDR mess: re-imaged, stale, cut-off, renamed and discovered devices (spec 2026-10-14, catalog)."""
from __future__ import annotations

import copy
from datetime import timedelta

from messy.firm import Firm
from messy.operators import EDR, Operator, clone, domain, machine_id, new_id, paired, take, utc_text


def _reimaged(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    device, machine = pair
    new_aad = new_id(f"aad:reimaged:{device['id']}")
    old = copy.deepcopy(machine)
    old.update(healthStatus="Inactive", lastSeen=utc_text(firm.exported_at("defender_machines") - timedelta(days=10)))
    firm.rows("defender_machines").append(old)
    machine.update(id=machine_id(f"machine:reimaged:{device['id']}"), aadDeviceId=new_aad)
    device.update(id=new_id(f"intune:reimaged:{device['id']}"), azureADDeviceId=new_aad)
    firm.touched.add(f"device:{device['id']}")  # the new Intune record is the same laptop
    return True


def _vm_off(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    pair[1].update(healthStatus="Inactive",
                   lastSeen=utc_text(firm.exported_at("defender_machines") - timedelta(days=8)))
    return True


def _sensor_cut_off(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    pair[1]["healthStatus"] = "ImpairedCommunication"
    return True


def _discovered(firm: Firm, label: str, **changes) -> bool:
    if not take(firm, f"discovered:{label}"):
        return False
    clone(firm.rows("defender_machines"), id=machine_id(f"machine:{label}"), aadDeviceId=None,
          lastSeen=utc_text(firm.exported_at("defender_machines") - timedelta(hours=6)), **changes)
    return True


def _renamed(firm: Firm) -> bool:
    pair = paired(firm)
    if pair is None:
        return False
    device, machine = pair
    machine["computerDnsName"] = f"renamed-{device['deviceName'].lower()}.{domain(firm)}"
    return True


def _no_primary_user(firm: Firm) -> bool:
    for device in firm.rows("intune_devices"):
        if take(firm, f"device-user:{device['id']}"):
            device["userPrincipalName"] = ""
            return True
    return False


OPERATORS = (
    Operator("laptop re-imaged", "holds", _reimaged, scopes=EDR, twin="real-messy-reimaged",
             why="the laptop is onboarded again under a new Entra device; the old Defender record is a ghost"),
    Operator("VM off for 8 days", "breaks", _vm_off,
             alone={"edr.all_endpoints": "gap"}, scopes=EDR, twin="real-messy-vm-off"),
    Operator("sensor cut off", "breaks", _sensor_cut_off,
             alone={"edr.all_endpoints": "gap"}, scopes=EDR, twin="real-messy-sensor-cut"),
    Operator("discovered printer", "holds",
             lambda firm: _discovered(firm, "printer", computerDnsName="hp-laserjet-01", osPlatform="Linux",
                                      onboardingStatus="Unsupported", healthStatus="Inactive"),
             scopes=EDR, why="a printer cannot run Defender; it is not an endpoint the claim is about"),
    Operator("discovered unmanaged PC", "breaks",
             lambda firm: _discovered(firm, "unmanaged-pc", computerDnsName="desktop-7q2k9", osPlatform="Windows11",
                                      onboardingStatus="CanBeOnboarded", healthStatus="Inactive"),
             alone={"edr.all_endpoints": "gap"}, scopes=EDR, twin="real-messy-discovered"),
    Operator("discovered device with no DNS name", "holds",
             lambda firm: _discovered(firm, "nameless", computerDnsName=None, osPlatform="Unknown",
                                      onboardingStatus="InsufficientInfo", healthStatus="Inactive"),
             scopes=EDR, why="a device known only by its network address is not shown to be a company endpoint",
             # Provisional: kept until a real capture shows whether Defender writes a null name.
             may_stop="field 'computerDnsName' must be a non-empty string, got None"),
    Operator("device renamed after onboarding", "holds", _renamed, scopes=EDR, twin="real-messy-renamed",
             why="the same device, paired by its Entra device ID"),
    Operator("Intune device with no primary user", "inert", _no_primary_user),
)
