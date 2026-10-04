"""The control profile: which proof rule each control's scope uses (spec: Firm folder and profile)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import yaml

from attest.model import AttestError

PROFILE_PATH = Path(__file__).resolve().parents[1] / "profile" / "controls.yaml"
Profile = dict[str, dict[str, str]]


def load_profile(path: Path = PROFILE_PATH, rules: Optional[Iterable[str]] = None) -> Profile:
    """Controls to scopes to rule names; with `rules`, every named rule must be one of them."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise AttestError(f"{path.name}: expected a mapping of controls to scopes")
    known = None if rules is None else set(rules)
    for control, scopes in data.items():
        if not isinstance(scopes, dict) or not scopes:
            raise AttestError(f"{path.name}: control {control!r} has no scopes")
        for scope, rule in scopes.items():
            if known is not None and rule not in known:
                raise AttestError(f"{path.name}: {control}.{scope} names unknown rule {rule!r}")
    return data
