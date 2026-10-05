"""Run every confirmed tag through its scope's proof rule (spec: Pipeline)."""
from __future__ import annotations

from pathlib import Path

from attest.evidence import load_evidence
from attest.model import Tag, Verdict
from attest.profile import PROFILE_PATH, load_profile
from attest.rules import RULES
from attest.tags import load_tags


def check(firm: Path, profile_path: Path = PROFILE_PATH) -> list[tuple[Tag, Verdict]]:
    """Each tag of firm/tags.yaml, in order, with the verdict its scope's rule gives on firm/exports."""
    profile = load_profile(profile_path, rules=RULES)
    tags = load_tags(firm, profile)
    evidence = load_evidence(Path(firm) / "exports")
    return [(tag, RULES[profile[tag.control][tag.scope]](evidence)) for tag in tags]
