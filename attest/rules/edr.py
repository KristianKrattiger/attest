"""EDR proof rule (spec: Proof rules, EDR).

The population is Intune's device list, never Defender's own inventory: a
console only knows the devices already enrolled in it, so "100% healthy" in
Defender alone says nothing about devices it has never seen. A device that
cannot be matched is a gap, so a matching mistake can cost a false gap but
never back a false attestation.

Matching is one-to-one: a Defender machine never covers two Intune devices.
The one exception is Intune records that share an Entra device ID, which are
the same Entra device and so the same machine. Two Entra devices are never
paired by name, and when Defender holds several records for one Entra device
(a re-imaged device leaves an old one) the latest lastSeen decides; a tie for
the latest is a gap, because nothing says which record is the device.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from attest.evidence import Evidence
from attest.model import Verdict
from attest.readers.defender_machines import Machine
from attest.readers.intune_devices import IntuneDevice
from attest.rules.common import unchecked

STALE_AFTER = timedelta(days=7)


def _short_name(name: str) -> str:
    """Case-folded, with any domain suffix removed: 'HP-LT-01' and 'hp-lt-01.firm.example' agree."""
    return name.strip().lower().split(".")[0]


class _Match(NamedTuple):
    machine: Optional[Machine]
    key: str  # what the match rests on: "Entra device ID" or "device name"
    failure: str  # why there is no machine, when there is none
    others: tuple[Machine, ...]  # other records for the same Entra device: older ones, or all when tied


def _latest(records: list[Machine]) -> Optional[Machine]:
    """The record with the latest lastSeen (never seen is the oldest), or None when several tie for it."""
    if len(records) == 1:
        return records[0]
    latest = max((m.last_seen for m in records if m.last_seen is not None), default=None)
    newest = [m for m in records if m.last_seen == latest]
    return newest[0] if len(newest) == 1 else None


def _match_all(devices: tuple[IntuneDevice, ...], machines: tuple[Machine, ...]) -> list[_Match]:
    """One Defender machine for each Intune device, in device order, or the reason there is none.

    By Entra device ID first; if Defender has several records for that Entra
    device, the latest decides. Whatever is left is matched by short name, but
    only against machines no Intune device holds by Entra ID, never against a
    machine with a different Entra ID than the device's own (two Entra devices
    are two devices), and only when the name picks out exactly one such machine
    and exactly one device wants it. A name that fits two machines, or one
    machine wanted by two devices, matches none of them: at most one of those
    devices can be that machine, and nothing says which.
    """
    by_entra_id: dict[str, list[Machine]] = {}
    for m in machines:
        if m.aad_device_id:
            by_entra_id.setdefault(m.aad_device_id, []).append(m)
    claimed = {d.aad_device_id for d in devices if d.aad_device_id}
    by_name: dict[str, list[Machine]] = {}
    for m in machines:
        if m.aad_device_id not in claimed:
            by_name.setdefault(_short_name(m.name), []).append(m)
    picks: list[Optional[Machine]] = []
    for d in devices:
        candidates = [] if d.aad_device_id in by_entra_id else [
            m for m in by_name.get(_short_name(d.name), []) if d.aad_device_id is None or m.aad_device_id is None]
        picks.append(candidates[0] if len(candidates) == 1 else None)
    wanted = [p.id for p in picks if p is not None]
    matches = []
    for d, pick in zip(devices, picks):
        if d.aad_device_id in by_entra_id:
            records = by_entra_id[d.aad_device_id]
            decided = _latest(records)
            others = tuple(m for m in records if m is not decided)
            matches.append(_Match(decided, "Entra device ID", "" if decided else "ambiguous Defender records", others))
        elif pick is None:
            matches.append(_Match(None, "device name", "not in Defender", ()))
        elif wanted.count(pick.id) > 1:
            matches.append(_Match(None, "device name", "ambiguous name match", ()))
        else:
            matches.append(_Match(pick, "device name", "", ()))
    return matches


def _outside(devices: tuple[IntuneDevice, ...], machines: tuple[Machine, ...]) -> list[Machine]:
    """Defender machines no Intune device could correspond to: neither their Entra ID nor their short name is any
    device's. A machine the matching set aside (older, tied, contested, or of a different Entra device) is not here."""
    entra_ids = {d.aad_device_id for d in devices if d.aad_device_id}
    names = {_short_name(d.name) for d in devices}
    return [m for m in machines if m.aad_device_id not in entra_ids and _short_name(m.name) not in names]


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
    cutoff = defender.exported_at - STALE_AFTER
    keys = {"Entra device ID": 0, "device name": 0}
    failing: list[tuple[IntuneDevice, str]] = []
    cited: list[str] = []
    set_aside: list[str] = []
    for device, (found, key, failure, others) in zip(intune.items, _match_all(intune.items, defender.items)):
        if others:
            kind = "older" if found else "tied"
            set_aside.append(f"{kind} Defender records for {device.name}: " + ", ".join(m.name for m in others))
        if found is None:
            failing.append((device, failure))
            cited += [device.cite, *(m.cite for m in others)]
            continue
        keys[key] += 1
        problems = _problems(found, cutoff)
        if problems:
            failing.append((device, ", ".join(problems)))
            cited += [device.cite, found.cite]
    notes = ""
    matched_by = ", ".join(f"{key} {count}" for key, count in keys.items() if count)
    if matched_by:
        notes += f"; matched by {matched_by}"
    notes += "".join("; " + note for note in set_aside)
    outside = [m.name for m in _outside(intune.items, defender.items)]
    if outside:
        notes += "; in Defender but not Intune (outside the population): " + ", ".join(outside)
    if failing:
        reason = "; ".join(f"{d.name}: {why}" for d, why in failing) + notes
        return Verdict("gap", reason, tuple(d.name for d, _ in failing), tuple(cited), population)
    reason = (f"all {len(intune.items)} devices onboarded to Defender, Active, and seen within 7 days "
              f"of {defender.exported_at.date().isoformat()}" + notes)
    return Verdict("backed", reason, cited=(intune.file, defender.file), population=population)
