"""A document's reading sidecar, written by intake when it read the original file (intake docs/format.md, format 1).

When attest/<name>.txt has attest/<name>.txt.map.json beside it, the text was read from an original (a PDF, a
Word file, a scan) and the sidecar says where each line came from and how it was read. attest uses it twice:
to refuse a quote it cannot vouch for, and to cite the original and the page in the report. A document with no
sidecar is plain text, as before. Standard library only: attest does not depend on intake, only on its format."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from attest.model import AttestError, Span

FORMAT = 1
NEEDED = ("reader", "source", "text_sha256", "complete", "pages", "lines")
PLAIN = "plain text, no source location"

# What a quote may rest on. A line is vouched for only if it was read from a text layer or a native document, on a
# page the reading lists, and each graded page's parse and OCR grades (where Docling computed them) are good or
# excellent. Layout grades are not checked: a born-digital form's layout graded FAIR while its text layer read
# exactly (intake RESULTS.md).
VOUCHED_HOWS = {"text_layer", "native"}
GRADED = ("parse", "ocr")
VOUCHED_GRADES = {"good", "excellent"}
# Docling's OCR grade stayed EXCELLENT on pages missing up to 27% of their words (RapidOCR medium, intake RESULTS.md),
# so no line read by OCR is vouched for, whatever its grade.
REFUSED_HOWS = {"ocr": "was read by OCR, whose grade does not show its errors",
                "rescanned": "was read by OCR, whose grade does not show its errors"}
REFUSED_FLAGS = {"quoted": "is quoted from an earlier message, not the sender's own words",
                 "no_header": "is a table row read without its column headers"}
# Set True if intake's table-fidelity bar is missed (intake RESULTS.md): then no table row is vouched for.
REFUSE_TABLE_ROWS = False


@dataclass(frozen=True)
class Reading:
    name: str  # the original file's name
    sha256: str  # the original file's hash
    lines: dict[int, dict]  # line number -> the sidecar's entry for it (blank lines have none)
    pages: dict[int, dict]  # page number -> the sidecar's entry for it


def sidecar(firm: Path, doc: str) -> Path:
    return firm / f"{doc}.map.json"


def load_reading(firm: Path, doc: str, text: str) -> Reading | None:
    """The document's reading, or None when it has no sidecar. `text` is the document as attest read it
    (universal newlines, BOM dropped); intake hashed the same LF text, so a CRLF checkout still matches.

    A sidecar that is not format 1 or lacks a field attest reads stops the run, naming the field."""
    path = sidecar(firm, doc)
    if not path.exists():
        return None
    where = f"{doc}.map.json"
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise AttestError(f"{where} is not a readable sidecar ({e})") from e
    found = data.get("format") if isinstance(data, dict) else None
    if type(found) is not int or found != FORMAT:
        raise AttestError(f"{where}: format {found!r}; attest reads format {FORMAT}")
    missing = [k for k in NEEDED if k not in data]
    if missing:
        raise AttestError(f"{where}: missing {', '.join(missing)}")
    _validate(data, where)
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != data["text_sha256"]:
        raise AttestError(f"{doc} was edited after it was read: its text no longer matches {where}; "
                          "read the original again, or remove the sidecar to check it as plain text")
    if data["complete"] is not True:
        raise AttestError(f"{doc}: its reading is incomplete (a page timed out); read the original again")
    source = data["source"]
    return Reading(source["name"], source["sha256"], {e["line"]: e for e in data["lines"]},
                   {p["page"]: p for p in data["pages"]})


def refusal(reading: Reading, span: Span) -> str | None:
    """Why a quote on these lines cannot be vouched for, or None when every line it touches can be.

    A line the quote spans that is not blank but has no entry means the reading is damaged, not that the quote is
    doubtful, so it stops the run with AttestError rather than returning a refusal."""
    for number in range(span.first, span.last + 1):
        entry = reading.lines.get(number)
        if entry is None:
            if span.lines[number - span.first].strip():
                raise AttestError(f"line {number} has no entry in the reading of {reading.name}; the reading is "
                                  "damaged, so read the original again")
            continue
        how = entry["how"]
        if how in REFUSED_HOWS:
            return f"line {number} {REFUSED_HOWS[how]}"
        if how not in VOUCHED_HOWS:
            return f"line {number} was read in a way attest does not know ({how!r})"
        for flag, why in REFUSED_FLAGS.items():
            if flag in entry["flags"]:
                return f"line {number} {why}"
        if REFUSE_TABLE_ROWS and entry["kind"] in ("table_row", "chart_row"):
            return f"line {number} is a table row, and table rows are not vouched for"
        for page in _pages(entry):
            if page not in reading.pages:
                return f"line {number} is on page {page}, which the reading does not list"
            grades = reading.pages[page]["grades"]
            for name in GRADED:
                if name in grades and grades[name] not in VOUCHED_GRADES:
                    return f"line {number} is on page {page}, whose {name} grade is {grades[name]}"
    return None


def location(reading: Reading, span: Span) -> str:
    """The original and where the quoted lines sit in it: 'WISP.pdf (sha256 1a2b3c4d5e6f), p. 3'."""
    places: list[str] = []
    for number in range(span.first, span.last + 1):
        entry = reading.lines.get(number)
        for loc in ([] if entry is None else _locs(entry)):
            place = _place(loc)
            if place and place not in places:
                places.append(place)
    head = f"{reading.name} (sha256 {reading.sha256[:12]})"
    return f"{head}, {', '.join(places)}" if places else head


def _validate(data: dict, where: str) -> None:
    """Refuse a sidecar whose fields attest reads are missing or of the wrong type, naming the first one."""
    if not isinstance(data["source"], dict):
        raise _bad(where, "source", "must be a mapping")
    _require(data["source"], "source", where, "name", _is_text, "a non-empty string")
    _require(data["source"], "source", where, "sha256", _is_text, "a non-empty string")
    _require(data, "", where, "text_sha256", _is_str, "a string")
    _require(data, "", where, "complete", _is_bool, "true or false")
    if not isinstance(data["pages"], list):
        raise _bad(where, "pages", "must be a list")
    numbers: set[int] = set()
    for i, page in enumerate(data["pages"]):
        at = f"pages[{i}]"
        if not isinstance(page, dict):
            raise _bad(where, at, "must be a mapping")
        _require(page, at, where, "page", _is_int, "an integer")
        if page["page"] in numbers:
            raise _bad(where, f"{at}.page", f"repeats page {page['page']}")
        numbers.add(page["page"])
        _require(page, at, where, "grades", _is_mapping, "a mapping")
        for name, grade in page["grades"].items():
            if not isinstance(grade, str):
                raise _bad(where, f"{at}.grades.{name}", "must be a string")
    if not isinstance(data["lines"], list):
        raise _bad(where, "lines", "must be a list")
    numbers = set()
    for i, entry in enumerate(data["lines"]):
        at = f"lines[{i}]"
        if not isinstance(entry, dict):
            raise _bad(where, at, "must be a mapping")
        _require(entry, at, where, "line", _is_int, "an integer")
        if entry["line"] in numbers:
            raise _bad(where, f"{at}.line", f"repeats line {entry['line']}")
        numbers.add(entry["line"])
        for key in ("start", "end"):
            _require(entry, at, where, key, _is_int, "an integer")
        for key in ("kind", "how"):
            _require(entry, at, where, key, _is_str, "a string")
        _require(entry, at, where, "flags", _is_flags, "a list of strings")
        _require(entry, at, where, "loc", _is_loc, "a mapping or a non-empty list of mappings")
        for j, loc in enumerate(_locs(entry)):
            spot = f"{at}.loc" if isinstance(entry["loc"], dict) else f"{at}.loc[{j}]"
            if "page" in loc and type(loc["page"]) is not int:
                raise _bad(where, f"{spot}.page", "must be an integer")


def _bad(where: str, path: str, what: str) -> AttestError:
    return AttestError(f"{where}: {path} {what}")


def _require(obj: dict, at: str, where: str, key: str, ok, what: str) -> None:
    """obj[key] must be present and pass ok; the message names it by its path in the sidecar."""
    path = f"{at}.{key}" if at else key
    if key not in obj:
        raise _bad(where, path, "is missing")
    if not ok(obj[key]):
        raise _bad(where, path, f"must be {what}")


def _is_int(value: object) -> bool:
    return type(value) is int  # not bool, which is an int in Python


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_str(value: object) -> bool:
    return isinstance(value, str)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _is_mapping(value: object) -> bool:
    return isinstance(value, dict)


def _is_flags(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(flag, str) for flag in value)


def _is_loc(value: object) -> bool:
    if isinstance(value, dict):
        return True
    return isinstance(value, list) and len(value) > 0 and all(isinstance(loc, dict) for loc in value)


def _locs(entry: dict) -> list[dict]:
    """A line's locations: its one loc, or each mapping of a list of them (a line can run across pages)."""
    loc = entry["loc"]
    return loc if isinstance(loc, list) else [loc]


def _pages(entry: dict) -> list[int]:
    return [loc["page"] for loc in _locs(entry) if "page" in loc]


def _place(loc: dict) -> str:
    if "page" in loc:
        return f"p. {loc['page']}"
    if "slide" in loc:
        return f"slide {loc['slide']}"
    if "sheet" in loc:
        return f"{loc['sheet']}!{loc['cells']}" if "cells" in loc else loc["sheet"]
    if "part" in loc:
        return f"email {loc['part']}"
    return ""  # a Word, HTML or text file has no pages to cite
