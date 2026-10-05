"""The control profile: which proof rule each control's scope uses (spec: Firm folder and profile)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Optional

from attest._yaml import has_letter_or_digit, read_yaml
from attest.model import AttestError

PROFILE_PATH = Path(__file__).resolve().parents[1] / "profile" / "controls.yaml"
Profile = dict[str, dict[str, str]]


def load_profile(path: Path = PROFILE_PATH, rules: Optional[Iterable[str]] = None) -> Profile:
    """Controls to scopes to rule names; with `rules`, every named rule must be one of them."""
    path = Path(path)
    data = _profile_mapping(path)
    known = None if rules is None else set(rules)
    for control, scopes in data.items():
        _check_names(path.name, control, scopes)
        for scope, rule in scopes.items():
            if known is not None and rule not in known:
                raise AttestError(f"{path.name}: {control}.{scope} names unknown rule {rule!r}")
    return data


def _profile_mapping(path: Path) -> dict:
    """The parsed profile, which must be a non-empty mapping."""
    data = read_yaml(path, path.name)
    if not isinstance(data, dict) or not data:
        raise AttestError(f"{path.name}: expected a mapping of controls to scopes")
    return data


def _check_names(file: str, control: object, scopes: object) -> None:
    """One control's name, scopes and rule names must each be a string holding a letter or digit, with a scope."""
    if (problem := _name_problem(control)) is not None:
        raise AttestError(f"{file}: control name {control!r} {problem}")
    if not isinstance(scopes, dict) or not scopes:
        raise AttestError(f"{file}: control {control!r} has no scopes")
    for scope, rule in scopes.items():
        if (problem := _name_problem(scope)) is not None:
            raise AttestError(f"{file}: {control}.{scope!r} scope name {problem}")
        if (problem := _name_problem(rule)) is not None:
            raise AttestError(f"{file}: {control}.{scope} rule name {problem}")


def _name_problem(name: object) -> Optional[str]:
    """Which rule a name breaks, or None: it must be a string, and the string must hold a letter or digit."""
    if not isinstance(name, str):
        return "must be a string"
    if not has_letter_or_digit(name):
        return "must contain a letter or digit"
    return None
