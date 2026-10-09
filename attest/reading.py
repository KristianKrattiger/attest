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

# What a quote may not rest on. Grades: Docling's parse and OCR grades below GOOD. Layout grades are left out:
# a born-digital form's layout graded FAIR while its text layer read exactly (intake RESULTS.md).
REFUSED_GRADES = {"poor", "fair"}
GRADED = ("parse", "ocr")
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
    (universal newlines, BOM dropped); intake hashed the same LF text, so a CRLF checkout still matches."""
    path = sidecar(firm, doc)
    if not path.exists():
        return None
    where = f"{doc}.map.json"
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise AttestError(f"{where} is not a readable sidecar ({e})") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        found = data.get("format") if isinstance(data, dict) else None
        raise AttestError(f"{where}: format {found!r}; attest reads format {FORMAT}")
    missing = [k for k in NEEDED if k not in data]
    if missing:
        raise AttestError(f"{where}: missing {', '.join(missing)}")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != data["text_sha256"]:
        raise AttestError(f"{doc} was edited after it was read: its text no longer matches {where}; "
                          "read the original again, or remove the sidecar to check it as plain text")
    if data["complete"] is not True:
        raise AttestError(f"{doc}: its reading is incomplete (a page timed out); read the original again")
    source = data["source"]
    return Reading(source["name"], source["sha256"], {e["line"]: e for e in data["lines"]},
                   {p["page"]: p for p in data["pages"]})


def refusal(reading: Reading, span: Span) -> str | None:
    """Why a quote on these lines cannot be vouched for, or None when every line it touches can be."""
    for number in range(span.first, span.last + 1):
        entry = reading.lines.get(number)
        if entry is None:
            continue
        if entry["how"] in REFUSED_HOWS:
            return f"line {number} {REFUSED_HOWS[entry['how']]}"
        for flag, why in REFUSED_FLAGS.items():
            if flag in entry["flags"]:
                return f"line {number} {why}"
        if REFUSE_TABLE_ROWS and entry["kind"] in ("table_row", "chart_row"):
            return f"line {number} is a table row, and table rows are not vouched for"
        for page in _pages(entry):
            grades = reading.pages.get(page, {}).get("grades", {})
            for name in GRADED:
                if grades.get(name) in REFUSED_GRADES:
                    return f"line {number} is on page {page}, whose {name} grade is {grades[name]}"
    return None


def location(reading: Reading, span: Span) -> str:
    """The original and where the quoted lines sit in it: 'WISP.pdf (sha256 1a2b3c4d5e6f), p. 3'."""
    places: list[str] = []
    for number in range(span.first, span.last + 1):
        entry = reading.lines.get(number)
        for loc in ([] if entry is None else entry["loc"] if isinstance(entry["loc"], list) else [entry["loc"]]):
            place = _place(loc)
            if place and place not in places:
                places.append(place)
    head = f"{reading.name} (sha256 {reading.sha256[:12]})"
    return f"{head}, {', '.join(places)}" if places else head


def _pages(entry: dict) -> list[int]:
    locs = entry["loc"] if isinstance(entry["loc"], list) else [entry["loc"]]
    return [loc["page"] for loc in locs if "page" in loc]


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
