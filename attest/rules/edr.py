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

from collections import Counter
from datetime import datetime, timedelta
from functools import cache
from typing import NamedTuple, Optional

from attest.evidence import Evidence
from attest.model import Verdict
from attest.readers.defender_machines import Machine
from attest.readers.intune_devices import IntuneDevice
from attest.rules.common import unchecked

STALE_AFTER = timedelta(days=7)


@cache
def _short_name(name: str) -> str:
    """Case-folded, with any domain suffix removed: 'HP-LT-01' and 'hp-lt-01.firm.example' agree."""
    return name.strip().lower().split(".")[0]


def _can_pair(device: IntuneDevice, machine: Machine) -> bool:
    """Whether this Defender machine could be this Intune device.

    The same Entra device, or the same short name when at least one of them has
    no Entra ID. Two different Entra devices never pair, whatever they are
    called. Matching and the "outside the population" list both ask this, so
    they cannot disagree about what a machine could be.
    """
    if device.aad_device_id and machine.aad_device_id:
        return device.aad_device_id == machine.aad_device_id
    return _short_name(device.name) == _short_name(machine.name)


class _Match(NamedTuple):
    machine: Optional[Machine]
    key: str  # what the match rests on: "Entra device ID" or "device name"
    failure: str  # why there is no machine, when there is none
    tied: tuple[Machine, ...]  # Entra-device records sharing the latest lastSeen, when none can decide
    older: tuple[Machine, ...]  # Entra-device records a later one outranks


def _newest(records: list[Machine]) -> tuple[list[Machine], list[Machine]]:
    """Records for one Entra device: those with the latest lastSeen (never seen is the oldest), and the rest."""
    latest = max((m.last_seen for m in records if m.last_seen is not None), default=None)
    return ([m for m in records if m.last_seen == latest],
            [m for m in records if m.last_seen != latest])


def _match_all(devices: tuple[IntuneDevice, ...], machines: tuple[Machine, ...]) -> list[_Match]:
    """One Defender machine for each Intune device, in device order, or the reason there is none.

    By Entra device ID first; if Defender has several records for that Entra
    device, the latest decides, and a tie for the latest decides nothing.
    Whatever is left is matched by short name (`_can_pair`), but only against
    machines no Intune device holds by Entra ID, and only when exactly one such
    machine fits and exactly one device wants it. A name that fits two
    machines, or one machine wanted by two devices, matches none of them: at
    most one of those devices can be that machine, and nothing says which. A
    machine that cannot pair with a device (a different Entra device) adds no
    ambiguity to it.
    """
    by_entra_id: dict[str, list[Machine]] = {}
    for m in machines:
        if m.aad_device_id:
            by_entra_id.setdefault(m.aad_device_id, []).append(m)
    held = {d.aad_device_id for d in devices if d.aad_device_id}
    unclaimed = [m for m in machines if m.aad_device_id not in held]
    picks: list[Optional[Machine]] = []
    for d in devices:
        fits = [] if d.aad_device_id in by_entra_id else [m for m in unclaimed if _can_pair(d, m)]
        picks.append(fits[0] if len(fits) == 1 else None)
    wanted = Counter(p.id for p in picks if p is not None)
    matches = []
    for d, pick in zip(devices, picks):
        if d.aad_device_id in by_entra_id:
            newest, older = _newest(by_entra_id[d.aad_device_id])
            if len(newest) == 1:
                matches.append(_Match(newest[0], "Entra device ID", "", (), tuple(older)))
            else:
                matches.append(_Match(None, "Entra device ID", "ambiguous Defender records",
                                      tuple(newest), tuple(older)))
        elif pick is None:
            matches.append(_Match(None, "device name", "not in Defender", (), ()))
        elif wanted[pick.id] > 1:
            matches.append(_Match(None, "device name", "ambiguous name match", (), ()))
        else:
            matches.append(_Match(pick, "device name", "", (), ()))
    return matches


def _outside(devices: tuple[IntuneDevice, ...], machines: tuple[Machine, ...]) -> list[Machine]:
    """Defender machines no Intune device could be: every machine `_can_pair` rules out for all of them."""
    return [m for m in machines if not any(_can_pair(d, m) for d in devices)]


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
    for device, (found, key, failure, tied, older) in zip(intune.items, _match_all(intune.items, defender.items)):
        for kind, records in (("tied", tied), ("older", older)):
            if records:
                set_aside.append(f"{kind} Defender records for {device.name}: " + ", ".join(m.name for m in records))
        if found is None:
            failing.append((device, failure))
            cited += [device.cite, *(m.cite for m in tied)]
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
