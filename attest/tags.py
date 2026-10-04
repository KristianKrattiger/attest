"""Confirmed tags, each grounded in its document (spec: Pipeline, step 1)."""
from __future__ import annotations

from pathlib import Path

import yaml

from attest.model import AttestError, Tag
from attest.profile import Profile

FIELDS = ("id", "doc", "quote", "control", "scope")


def load_tags(firm: Path, profile: Profile) -> list[Tag]:
    """Every tag in firm/tags.yaml, refusing one whose quote is not an exact substring of its document."""
    path = Path(firm) / "tags.yaml"
    if not path.is_file():
        raise AttestError(f"{path} not found")
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("tags") or []
    documents: dict[str, str] = {}
    seen: set[str] = set()
    tags: list[Tag] = []
    for i, entry in enumerate(raw, start=1):
        for field in FIELDS:
            if field not in entry:
                raise AttestError(f"tags.yaml: tag {i} has no {field!r}")
        tag = Tag(*(str(entry[field]) for field in FIELDS))
        if tag.id in seen:
            raise AttestError(f"tags.yaml: tag id {tag.id!r} appears twice")
        seen.add(tag.id)
        if tag.control not in profile:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: unknown control {tag.control!r}")
        if tag.scope not in profile[tag.control]:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: unknown scope '{tag.control}.{tag.scope}'")
        if tag.doc not in documents:
            doc_path = Path(firm) / tag.doc
            if not doc_path.is_file():
                raise AttestError(f"tags.yaml: tag {tag.id!r}: document {tag.doc} not found")
            documents[tag.doc] = doc_path.read_text(encoding="utf-8")
        if tag.quote not in documents[tag.doc]:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: quote is not an exact substring of {tag.doc}")
        tags.append(tag)
    return tags
