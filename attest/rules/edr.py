"""EDR proof rule (spec: Proof rules, EDR).

The population is Intune's device list, never Defender's own inventory: a
console only knows the devices already enrolled in it, so "100% healthy" in
Defender alone says nothing about devices it has never seen. A device that
cannot be matched is a gap, so a matching mistake can cost a false gap but
never back a false attestation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from attest.evidence import Evidence
from attest.model import Verdict
from attest.readers.defender_machines import Machine
from attest.readers.intune_devices import IntuneDevice
from attest.rules.common import unchecked

STALE_AFTER = timedelta(days=7)


def _short_name(name: str) -> str:
    """Case-folded, with any domain suffix removed: 'HP-LT-01' and 'hp-lt-01.firm.example' agree."""
    return name.strip().lower().split(".")[0]


def _match(device: IntuneDevice, by_entra_id: dict[str, Machine],
           by_name: dict[str, list[Machine]]) -> tuple[Optional[Machine], str]:
    """The Defender machine for this device by Entra device ID, else by an unambiguous short name."""
    if device.aad_device_id and device.aad_device_id in by_entra_id:
        return by_entra_id[device.aad_device_id], "Entra device ID"
    candidates = by_name.get(_short_name(device.name), [])
    return (candidates[0] if len(candidates) == 1 else None), "device name"


def _problems(machine: Machine, cutoff: datetime) -> list[str]:
    problems = []
    if machine.onboarding.lower() != "onboarded":
        problems.append(f"onboarding status {machine.onboarding}")
    if machine.health.lower() != "active":
        problems.append(f"health {machine.health}")
    if machine.last_seen is None:
        problems.append("never seen")
    elif machine.last_seen < cutoff:
        problems.append(f"last seen {machine.last_seen.date().isoformat()}")
    return problems


def edr_all_endpoints(evidence: Evidence) -> Verdict:
    intune, defender = evidence.intune_devices, evidence.defender_machines
    if intune is None:
        return unchecked("no Intune managed-devices export (intune_devices)")
    if defender is None:
        return unchecked("no Defender device export (defender_machines)")
    if not intune.items:
        return unchecked(f"the population is empty: {intune.file} lists no devices")
    population = f"{len(intune.items)} devices from {intune.file}"
    by_entra_id = {m.aad_device_id: m for m in defender.items if m.aad_device_id}
    by_name: dict[str, list[Machine]] = {}
    for m in defender.items:
        by_name.setdefault(_short_name(m.name), []).append(m)
    cutoff = defender.exported_at - STALE_AFTER
    matched: set[str] = set()
    keys = {"Entra device ID": 0, "device name": 0}
    failing: list[tuple[IntuneDevice, str]] = []
    cited: list[str] = []
    for device in intune.items:
        found, key = _match(device, by_entra_id, by_name)
        if found is None:
            failing.append((device, "not in Defender"))
            cited.append(device.cite)
            continue
        matched.add(found.id)
        keys[key] += 1
        problems = _problems(found, cutoff)
        if problems:
            failing.append((device, ", ".join(problems)))
            cited += [device.cite, found.cite]
    notes = ""
    matched_by = ", ".join(f"{key} {count}" for key, count in keys.items() if count)
    if matched_by:
        notes += f"; matched by {matched_by}"
    outside = [m.name for m in defender.items if m.id not in matched]
    if outside:
        notes += "; in Defender but not Intune (outside the population): " + ", ".join(outside)
    if failing:
        reason = "; ".join(f"{d.name}: {why}" for d, why in failing) + notes
        return Verdict("gap", reason, tuple(d.name for d, _ in failing), tuple(cited), population)
    reason = (f"all {len(intune.items)} devices onboarded to Defender, Active, and seen within 7 days "
              f"of {defender.exported_at.date().isoformat()}" + notes)
    return Verdict("backed", reason, cited=(intune.file, defender.file), population=population)
