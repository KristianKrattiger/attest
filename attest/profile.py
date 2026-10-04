"""The control profile: which proof rule each control's scope uses (spec: Firm folder and profile)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Optional

from attest._yaml import read_yaml
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
    if not path.is_file():
        raise AttestError(f"{path} not found")
    data = read_yaml(path, path.name)
    if not isinstance(data, dict) or not data:
        raise AttestError(f"{path.name}: expected a mapping of controls to scopes")
    return data


def _check_names(file: str, control: object, scopes: object) -> None:
    """One control's name, scopes and rule names must each be a non-empty string, with at least one scope."""
    if not _is_name(control):
        raise AttestError(f"{file}: control name {control!r} must be a non-empty string")
    if not isinstance(scopes, dict) or not scopes:
        raise AttestError(f"{file}: control {control!r} has no scopes")
    for scope, rule in scopes.items():
        if not _is_name(scope):
            raise AttestError(f"{file}: {control}.{scope!r} scope name must be a non-empty string")
        if not _is_name(rule):
            raise AttestError(f"{file}: {control}.{scope} rule name must be a non-empty string")


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value)
