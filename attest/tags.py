"""Confirmed tags, each grounded in its document (spec: Pipeline, step 1).

A quote must appear exactly once in its document and hold at least three words, so that it names one passage and
says something; several tags may share one quote, one for each claim the passage makes.
"""
from __future__ import annotations

from pathlib import Path

from attest._yaml import has_invisible_edge, has_letter_or_digit, read_yaml
from attest.model import AttestError, Tag
from attest.profile import Profile

FIELDS = ("id", "doc", "quote", "control", "scope")
ATTEST_DIR = "attest"  # the firm folder's attestation documents (spec: Firm folder and profile)


def load_tags(firm: Path, profile: Profile) -> list[Tag]:
    """Every tag in firm/tags.yaml, refusing one whose quote is under three words or not once in its document."""
    firm = Path(firm)
    documents: dict[str, str] = {}
    seen: set[str] = set()
    tags: list[Tag] = []
    for i, entry in enumerate(_tag_entries(firm / "tags.yaml"), start=1):
        tag = _checked_tag(entry, i)
        if tag.id in seen:
            raise AttestError(f"tags.yaml: tag id {tag.id!r} appears twice")
        seen.add(tag.id)
        if _words(tag.quote) < 3:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: quote must contain at least three words")
        _check_in_profile(tag, profile)
        if tag.doc not in documents:
            documents[tag.doc] = _document_text(firm, tag)
        found = _occurrences(documents[tag.doc], tag.quote)
        if found == 0:
            raise AttestError(f"tags.yaml: tag {tag.id!r}: quote is not an exact substring of {tag.doc}")
        if found > 1:
            raise AttestError(
                f"tags.yaml: tag {tag.id!r}: quote appears {found} times in {tag.doc}; quote enough to be unique")
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
    """One entry as a Tag: a mapping of exactly the five fields, each a string with a letter or digit in it.

    The quote is stored as written, edge spaces included, because grounding is exact. An id, doc, control or scope
    must also not begin or end with whitespace or an invisible character, which would make a lookalike value."""
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
        if not isinstance(value, str):
            raise AttestError(f"tags.yaml: tag {i} field {field!r} must be a string, got {value!r}")
        if not has_letter_or_digit(value):
            raise AttestError(f"tags.yaml: tag {i} field {field!r} must contain a letter or digit")
        if field != "quote" and has_invisible_edge(value):
            raise AttestError(
                f"tags.yaml: tag {i} field {field!r} has leading or trailing whitespace or invisible characters")
    return Tag(*(entry[field] for field in FIELDS))


def _words(quote: str) -> int:
    """The quote's words: whitespace-separated tokens that hold a letter or digit."""
    return sum(1 for token in quote.split() if has_letter_or_digit(token))


def _occurrences(text: str, quote: str) -> int:
    """How many times quote occurs in text, overlapping occurrences included."""
    count, at = 0, text.find(quote)
    while at != -1:
        count += 1
        at = text.find(quote, at + 1)
    return count


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
