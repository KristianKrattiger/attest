"""Confirmed tags, each grounded in its document (spec: Pipeline, step 1)."""
from __future__ import annotations

from pathlib import Path

from attest._yaml import has_visible_text, read_yaml
from attest.model import AttestError, Tag
from attest.profile import Profile

FIELDS = ("id", "doc", "quote", "control", "scope")
ATTEST_DIR = "attest"  # the firm folder's attestation documents (spec: Firm folder and profile)


def load_tags(firm: Path, profile: Profile) -> list[Tag]:
    """Every tag in firm/tags.yaml, refusing one whose quote is not an exact substring of its document."""
    firm = Path(firm)
    documents: dict[str, str] = {}
    seen: set[str] = set()
    tags: list[Tag] = []
    for i, entry in enumerate(_tag_entries(firm / "tags.yaml"), start=1):
        tag = _checked_tag(entry, i)
        if tag.id in seen:
            raise AttestError(f"tags.yaml: tag id {tag.id!r} appears twice")
        seen.add(tag.id)
        _check_in_profile(tag, profile)
        if tag.doc not in documents:
            documents[tag.doc] = _document_text(firm, tag)
        if tag.quote not in documents[tag.doc]:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: quote is not an exact substring of {tag.doc}")
        tags.append(tag)
    return tags


def _tag_entries(path: Path) -> list:
    """The raw entries of tags.yaml's 'tags' list; an empty file lists none."""
    data = read_yaml(path, "tags.yaml")
    if data is None:
        return []
    if not isinstance(data, dict) or "tags" not in data:
        raise AttestError("tags.yaml: expected a mapping with a 'tags' list")
    for key in data:
        if key != "tags":
            raise AttestError(f"tags.yaml: unknown key {key!r}")
    if not isinstance(data["tags"], list):
        raise AttestError("tags.yaml: expected a mapping with a 'tags' list")
    return data["tags"]


def _checked_tag(entry: object, i: int) -> Tag:
    """One entry as a Tag: a mapping of exactly the five fields, each a string with some visible text.

    The quote is stored as written, edge spaces included, because grounding is exact. A value with no visible
    text is refused (see `has_visible_text`), and so is an id, doc, control or scope with edge whitespace."""
    if not isinstance(entry, dict):
        raise AttestError(f"tags.yaml: tag {i} must be a mapping")
    for field in FIELDS:
        if field not in entry:
            raise AttestError(f"tags.yaml: tag {i} has no {field!r}")
    for key in entry:
        if key not in FIELDS:
            raise AttestError(f"tags.yaml: tag {i} has unknown key {key!r}")
    for field in FIELDS:
        value = entry[field]
        if not has_visible_text(value):
            raise AttestError(f"tags.yaml: tag {i} field {field!r} must be a non-empty string")
        if field != "quote" and value != value.strip():
            raise AttestError(f"tags.yaml: tag {i} field {field!r} has leading or trailing whitespace")
    return Tag(*(entry[field] for field in FIELDS))


def _check_in_profile(tag: Tag, profile: Profile) -> None:
    if tag.control not in profile:
        raise AttestError(f"tags.yaml: tag {tag.id!r}: unknown control {tag.control!r}")
    if tag.scope not in profile[tag.control]:
        raise AttestError(f"tags.yaml: tag {tag.id!r}: unknown scope '{tag.control}.{tag.scope}'")


def _document_text(firm: Path, tag: Tag) -> str:
    """The text of the tag's document: an existing UTF-8 regular file under firm/attest/.

    Any other file in the firm folder (tags.yaml, truth.yaml, exports/*, a previous run's report.md) holds the
    very quotes it would be asked to ground, so only attestation documents may be quoted."""
    path = firm / tag.doc
    where = f"tags.yaml: tag {tag.id!r}: document {tag.doc}"
    try:
        resolved = path.resolve()
        inside = resolved.is_relative_to(firm.resolve())
        under_attest = resolved.is_relative_to((firm / ATTEST_DIR).resolve())
    except (OSError, ValueError) as e:  # e.g. a NUL in the name
        raise AttestError(f"{where} is not a usable path") from e
    if not inside:
        raise AttestError(f"{where} is outside the firm folder")
    if not under_attest:
        raise AttestError(f"{where} is not under {ATTEST_DIR}/")
    try:
        if not path.exists():
            raise AttestError(f"{where} not found")
        if not path.is_file():
            raise AttestError(f"{where} is not a file")
        # Universal newlines: CRLF and CR are read as LF, so a quote matches whatever line endings the document has
        # (and a quote written with a CR never does). utf-8-sig drops a leading BOM: a file marker, not quotable text.
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise AttestError(f"{where} is not UTF-8 text ({e.reason})") from e
    except OSError as e:
        raise AttestError(f"{where} could not be read ({e.strerror or e})") from e
