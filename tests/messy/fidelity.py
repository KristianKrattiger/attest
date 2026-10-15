"""Whether an operator makes a mess the way the tenant really made it (spec 2026-10-14, Fidelity check).

Each twin capture holds the firm just before the mess (`before/exports`) and just after it (`after/exports`), so
drift between captures taken days apart (a Defender lastSeen, an OS build) is not mistaken for the mess. The operator
is applied to `before` and the change it makes is compared with the change the capture shows: the same number of
records added and removed per export, every field the operator changes (at its nested path, to the same JSON type)
also changed that way in the capture, and added records with the same fields and JSON types. Values are not
compared: IDs, times and addresses differ by nature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from messy.firm import Firm

# The field that identifies a record in each export; a record whose key changes counts as removed and added.
KEYS = {
    "entra_users": "id", "entra_registration": "id", "entra_ca_policies": "id", "entra_security_defaults": "id",
    "entra_role_assignments": "id", "intune_devices": "id", "defender_machines": "id", "veeam_users": "Email",
}


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "array" if isinstance(value, list) else "object"


_ABSENT = object()  # a key one record has and the other lacks


def _kind(value: Any) -> str:
    return "absent" if value is _ABSENT else json_type(value)


def _changed_shape(old: Any, new: Any, path: str) -> set[tuple[str, str]]:
    """(dotted path, JSON type of the new value) of every value that differs, descending where both are objects."""
    if isinstance(old, dict) and isinstance(new, dict):
        return {pair for k in old.keys() | new.keys()
                for pair in _changed_shape(old.get(k, _ABSENT), new.get(k, _ABSENT), f"{path}.{k}" if path else k)}
    return set() if _kind(old) == _kind(new) and old == new else {(path, _kind(new))}


@dataclass(frozen=True)
class Change:
    added: int
    removed: int
    changed_shape: frozenset[tuple[str, str]]  # (path, JSON type) of every value changed in a record both firms have
    added_shape: frozenset[tuple[str, str]]  # (field, JSON type) over every added record


def change(before: Firm, after: Firm, reader: str) -> Change:
    key = KEYS[reader]
    old = {str(r.get(key)).lower(): r for r in before.rows(reader)}
    new = {str(r.get(key)).lower(): r for r in after.rows(reader)}
    added = [new[k] for k in new.keys() - old.keys()]
    changed = {pair for k in new.keys() & old.keys() for pair in _changed_shape(old[k], new[k], "")}
    shape = {(f, json_type(v)) for r in added for f, v in r.items()}
    return Change(len(added), len(old.keys() - new.keys()), frozenset(changed), frozenset(shape))


def mismatches(before: Firm, synthetic: Firm, real: Firm) -> list[str]:
    """How the operator's mess (synthetic) differs from the capture's (real), both from `before`; [] when it agrees."""
    problems = []
    for reader in sorted(KEYS):
        if not any(e["reader"] == reader for e in before.manifest):
            continue
        made, seen = change(before, synthetic, reader), change(before, real, reader)
        if (made.added, made.removed) != (seen.added, seen.removed):
            problems.append(f"{reader}: the operator adds {made.added} and removes {made.removed} records; "
                            f"the capture adds {seen.added} and removes {seen.removed}")
        if missing := sorted(f"{path} ({kind})" for path, kind in made.changed_shape - seen.changed_shape):
            problems.append(f"{reader}: the operator changes {', '.join(missing)}, which the capture does not")
        if made.added and seen.added and made.added_shape != seen.added_shape:
            only_made = sorted(f"{f} ({t})" for f, t in made.added_shape - seen.added_shape)
            only_seen = sorted(f"{f} ({t})" for f, t in seen.added_shape - made.added_shape)
            problems.append(f"{reader}: added records differ; only the operator's have {only_made}, "
                            f"only the capture's have {only_seen}")
    return problems
