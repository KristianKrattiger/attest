# attest: documents read by intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a tag quote an attestation document that intake read from a PDF, Word file or scan, refuse a quote the reading cannot vouch for, and cite the original and its page in the report.

**Architecture:** A new standard-library module, `attest/reading.py`, loads `attest/<name>.txt.map.json` (intake's format 1) when it sits beside a document, checks it against the text attest read, and answers two questions per tag: may this quote be vouched for, and where in the original is it. `load_tags` asks both after grounding each quote; `Tag` gains a `source`; the report prints it under each attestation. attest imports no intake code; its dependencies stay at PyYAML.

**Tech Stack:** Python 3.12, PyYAML, pytest (attest's own venv). intake (its own repo and venv) only to make real readings for the end-to-end check.

**Spec:** intake's `docs/superpowers/specs/2026-10-08-intake-reader-design.md`, section "attest". **Comes after:** intake's plan through Task 14 (`RESULTS.md` holds the grade-calibration and table-fidelity decisions this plan reads).

## Global Constraints

- Standard library only in `attest/reading.py`; `requirements.txt` does not change.
- Every refusal stops the run with the tag and the reason named, like attest's other grounding refusals (`AttestError`).
- A document without a sidecar behaves exactly as today, except for its new `- source: plain text, no source location` line.
- Commands run from `C:\Users\krist\Projects\attest` in Git Bash; commit messages say what changed and why, and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Two decisions this plan makes, for Kristian to confirm

Both follow from intake's measurements (scratch run 2026-10-08, confirmed in intake's `RESULTS.md`) and depart from the intake spec's wording "a line from a page with any grade below GOOD":

1. **No line read by OCR is vouched for, whatever its grade.** Docling's OCR grade stayed EXCELLENT on scan pages that lost up to 27% of their words. (`REFUSED_HOWS` in `attest/reading.py`.)
2. **The layout grade is not a reason to refuse.** A born-digital insurance form's layout was graded FAIR (0.68) while its text layer read exactly; refusing it would refuse the very document attest exists for. Parse and OCR grades below GOOD still refuse. (`GRADED` in `attest/reading.py`.)

If intake's `RESULTS.md` says table fidelity missed its bar, set `REFUSE_TABLE_ROWS = True` in Task 1 Step 3.

---

### Task 1: Read intake's sidecar, refuse what it cannot vouch for, cite the original

**Files:**
- Create: `attest/reading.py`
- Modify: `attest/model.py` (Tag gains `source`), `attest/tags.py` (`load_tags`, `_document_text`), `attest/report.py` (`render`)
- Test: `tests/test_readings.py`

**Interfaces:**
- Consumes: `AttestError`, `Span`, `Tag` (`attest/model.py`); `load_tags` (`attest/tags.py`); `render` (`attest/report.py`).
- Produces: `attest.reading.Reading(name, sha256, lines, pages)`; `load_reading(firm, doc, text) -> Reading | None`; `refusal(reading, span) -> str | None`; `location(reading, span) -> str`; `PLAIN`; the policy constants `REFUSED_GRADES`, `GRADED`, `REFUSED_HOWS`, `REFUSED_FLAGS`, `REFUSE_TABLE_ROWS`; `Tag.source: Optional[str]` (compare=False).

- [ ] **Step 1: Write the failing test**

`tests/test_readings.py`:

```python
"""Documents read by intake: the sidecar's checks, the refusals it adds, and the source line in the report."""
import hashlib
import json

import pytest

from attest import reading as reading_module
from attest.model import AttestError, Verdict
from attest.reading import PLAIN
from attest.report import render
from attest.tags import load_tags

PROFILE = {"mfa": {"all_users": "mfa_all_users"}, "edr": {"all_endpoints": "edr_all_endpoints"}}
WISP = "All staff use MFA on every account.\n\nControl: EDR; Scope: All laptops\n"
SHA = "a" * 64
TAGS = ("tags:\n  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA, control: mfa, scope: all_users}\n")


def line(n, start, end, kind="paragraph", how="text_layer", flags=(), page=1):
    return {"line": n, "start": start, "end": end, "kind": kind, "how": how, "flags": list(flags),
            "loc": {"page": page, "bbox": [72.0, 700.0, 540.0, 712.0], "origin": "bottomleft"}}


def sidecar(text=WISP, lines=None, grades=None, complete=True, fmt=1):
    return {"format": fmt, "reader": {"intake": "0.1.0"},
            "source": {"name": "WISP.pdf", "sha256": SHA, "bytes": 1, "type": "pdf", "extension_type": "pdf"},
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "complete": complete,
            "pages": [{"page": 1, "read": "text_layer", "status": "read",
                       "grades": grades or {"layout": "excellent", "parse": "excellent"}, "scores": {}}],
            "lines": lines if lines is not None else [line(1, 0, 35), line(3, 37, 69, kind="table_row")],
            "not_read": [], "attachments": []}


def firm(tmp_path, data=None, tags=TAGS, text_bytes=None):
    (tmp_path / "attest").mkdir()
    (tmp_path / "attest" / "wisp.txt").write_bytes(text_bytes or WISP.encode("utf-8"))
    if data is not None:
        (tmp_path / "attest" / "wisp.txt.map.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "tags.yaml").write_text(tags, encoding="utf-8")
    return tmp_path


def test_a_plain_text_document_says_it_has_no_source(tmp_path):
    [tag] = load_tags(firm(tmp_path), PROFILE)
    assert tag.source == PLAIN
    report = render("tiny", [(tag, Verdict("unchecked", "no export"))])
    assert "- document: `attest/wisp.txt`\n- source: plain text, no source location\n" in report


def test_a_read_document_cites_its_original_and_page(tmp_path):
    [tag] = load_tags(firm(tmp_path, sidecar()), PROFILE)
    assert tag.source == f"WISP.pdf (sha256 {SHA[:12]}), p. 1"


def test_a_crlf_checkout_still_matches_its_sidecar(tmp_path):
    [tag] = load_tags(firm(tmp_path, sidecar(), text_bytes=WISP.replace("\n", "\r\n").encode("utf-8")), PROFILE)
    assert tag.source.startswith("WISP.pdf")


def test_an_edited_text_stops_the_run(tmp_path):
    folder = firm(tmp_path, sidecar(), text_bytes=WISP.replace("every", "each").encode("utf-8"))
    with pytest.raises(AttestError, match="attest/wisp.txt was edited after it was read"):
        load_tags(folder, PROFILE)


def test_an_incomplete_reading_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="its reading is incomplete"):
        load_tags(firm(tmp_path, sidecar(complete=False)), PROFILE)


def test_another_format_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="format 2; attest reads format 1"):
        load_tags(firm(tmp_path, sidecar(fmt=2)), PROFILE)


@pytest.mark.parametrize("entry, grades, message", [
    (line(1, 0, 35, how="ocr"), None, "line 1 was read by OCR"),
    (line(1, 0, 35, how="rescanned"), None, "line 1 was read by OCR"),
    (line(1, 0, 35, flags=["quoted"]), None, "line 1 is quoted from an earlier message"),
    (line(1, 0, 35), {"layout": "excellent", "parse": "fair"}, "line 1 is on page 1, whose parse grade is fair"),
])
def test_a_quote_the_reading_cannot_vouch_for_is_refused(tmp_path, entry, grades, message):
    with pytest.raises(AttestError, match=f"tag 'w1': {message}"):
        load_tags(firm(tmp_path, sidecar(lines=[entry], grades=grades)), PROFILE)


def test_a_fair_layout_grade_alone_does_not_refuse(tmp_path):
    [tag] = load_tags(firm(tmp_path, sidecar(grades={"layout": "fair", "parse": "excellent"})), PROFILE)
    assert tag.source.endswith("p. 1")


def test_a_table_row_without_headers_is_refused(tmp_path):
    tags = "tags:\n  - {id: e1, doc: attest/wisp.txt, quote: 'EDR; Scope: All laptops', control: edr, scope: all_endpoints}\n"
    data = sidecar(lines=[line(1, 0, 35), line(3, 37, 69, kind="table_row", flags=["no_header"])])
    with pytest.raises(AttestError, match="line 3 is a table row read without its column headers"):
        load_tags(firm(tmp_path, data, tags=tags), PROFILE)


def test_table_rows_are_refused_when_their_fidelity_bar_was_missed(tmp_path, monkeypatch):
    monkeypatch.setattr(reading_module, "REFUSE_TABLE_ROWS", True)
    tags = "tags:\n  - {id: e1, doc: attest/wisp.txt, quote: 'EDR; Scope: All laptops', control: edr, scope: all_endpoints}\n"
    with pytest.raises(AttestError, match="line 3 is a table row, and table rows are not vouched for"):
        load_tags(firm(tmp_path, sidecar(), tags=tags), PROFILE)


def test_a_sidecar_is_never_a_document(tmp_path):
    tags = "tags:\n  - {id: w1, doc: attest/wisp.txt.map.json, quote: All staff use MFA, control: mfa, scope: all_users}\n"
    with pytest.raises(AttestError, match="is a reading's sidecar, not a document"):
        load_tags(firm(tmp_path, sidecar(), tags=tags), PROFILE)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
venv/Scripts/python.exe -m pytest tests/test_readings.py -q
```

Expected: `ImportError: cannot import name 'reading' from 'attest'`.

- [ ] **Step 3: Write `attest/reading.py`**

`attest/reading.py`:

```python
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
# intake RESULTS.md: Docling's OCR grade stayed EXCELLENT on pages missing up to half their words, so no line
# read by OCR is vouched for, whatever its grade.
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
```

- [ ] **Step 4: Give a tag its source**

In `attest/model.py`, replace

```python
    `span` is set when the quote is grounded in its document; it is where the tag is, not what it is, so it takes
    no part in comparing tags.
    """

    id: str
    doc: str
    quote: str
    control: str
    scope: str
    span: Optional[Span] = field(default=None, compare=False)
```

with

```python
    `span` is set when the quote is grounded in its document, and `source` with it: the original file and the
    place the quoted lines came from, or that the document is plain text. Both are where the tag is, not what it
    is, so they take no part in comparing tags.
    """

    id: str
    doc: str
    quote: str
    control: str
    scope: str
    span: Optional[Span] = field(default=None, compare=False)
    source: Optional[str] = field(default=None, compare=False)
```

- [ ] **Step 5: Check each grounded quote against its reading**

In `attest/tags.py`, replace

```python
from dataclasses import replace
from pathlib import Path

from attest._yaml import has_invisible_edge, has_letter_or_digit, read_yaml
from attest.model import AttestError, Span, Tag
from attest.profile import Profile
```

with

```python
from dataclasses import replace
from pathlib import Path
from typing import Optional

from attest._yaml import has_invisible_edge, has_letter_or_digit, read_yaml
from attest.model import AttestError, Span, Tag
from attest.profile import Profile
from attest.reading import PLAIN, Reading, load_reading, location, refusal
```

In `attest/tags.py`, replace

```python
    documents: dict[str, str] = {}
    files: dict[tuple[int, int], str] = {}
```

with

```python
    documents: dict[str, str] = {}
    readings: dict[str, Optional[Reading]] = {}
    files: dict[tuple[int, int], str] = {}
```

In `attest/tags.py`, replace

```python
            documents[tag.doc] = _document_text(firm, tag)
            _refuse_a_second_name(firm, tag, files)
```

with

```python
            documents[tag.doc] = _document_text(firm, tag)
            readings[tag.doc] = load_reading(firm, tag.doc, documents[tag.doc])
            _refuse_a_second_name(firm, tag, files)
```

In `attest/tags.py`, replace

```python
        tags.append(replace(tag, span=_span(documents[tag.doc], tag.quote)))
    return tags
```

with

```python
        span = _span(documents[tag.doc], tag.quote)
        reading = readings[tag.doc]
        if reading is not None:
            why = refusal(reading, span)
            if why:
                raise AttestError(f"tags.yaml: tag {tag.id!r}: {why}; check the passage against {reading.name} "
                                  "and tag a document a person has confirmed")
        tags.append(replace(tag, span=span, source=location(reading, span) if reading else PLAIN))
    return tags
```

In `attest/tags.py`, replace

```python
    path = firm / tag.doc
    where = f"tags.yaml: tag {tag.id!r}: document {tag.doc}"
    try:
```

with

```python
    path = firm / tag.doc
    where = f"tags.yaml: tag {tag.id!r}: document {tag.doc}"
    if tag.doc.lower().endswith(".map.json"):
        raise AttestError(f"{where} is a reading's sidecar, not a document; name the text beside it")
    try:
```

- [ ] **Step 6: Print the source under each attestation**

In `attest/report.py`, replace

```python
        lines += [f"## {ids}: {status.upper()}", "", *_quote(passage), "", f"- document: `{one_line(doc)}`"]
```

with

```python
        lines += [f"## {ids}: {status.upper()}", "", *_quote(passage), "", f"- document: `{one_line(doc)}`"]
        sources = list(dict.fromkeys(tag.source for tag, _ in tagged if tag.source))
        if sources:
            lines.append(f"- source: {one_line('; '.join(sources))}")
```

Tags built by hand in the existing report tests carry no source, so their exact report text does not change.

- [ ] **Step 7: Run the whole suite**

```bash
venv/Scripts/python.exe -m pytest -q
```

Expected: `763 passed, 2 skipped` (749 before, 14 new).

- [ ] **Commit**

```bash
git add attest/reading.py attest/model.py attest/tags.py attest/report.py tests/test_readings.py
git commit -F - <<'EOF'
Read intake's sidecar beside a document: refuse quotes it cannot vouch for, and cite the original

A text edited after reading, an incomplete reading or another format stops the run. A quote on a line read by OCR, a quoted email, a table row without headers, or a page whose parse or OCR grade is below good is refused. The report names the original and its page.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 2: Prove it on real readings, then document it

**Files:**
- Modify: `README.md`, `docs/superpowers/specs/2026-10-04-attestation-core-design.md`

- [ ] **Step 1: Make a firm folder from intake's fixtures**

From the attest repository, with intake's venv and models from intake's plan:

```bash
INTAKE=../intake
FIRM=$(mktemp -d)/firmx
mkdir -p "$FIRM/sources" "$FIRM/attest"
cp -r firm/dev/exports "$FIRM/exports"
cp $INTAKE/fixtures/files/wisp.pdf "$FIRM/sources/WISP.pdf"
cp $INTAKE/fixtures/files/insurance-form.pdf "$FIRM/sources/application.pdf"
cp $INTAKE/fixtures/files/scan-clean.pdf "$FIRM/sources/scan.pdf"
$INTAKE/.venv/Scripts/python -m intake.cli read "$FIRM/sources/WISP.pdf" --out "$FIRM/attest/wisp.txt"
$INTAKE/.venv/Scripts/python -m intake.cli read "$FIRM/sources/application.pdf" --out "$FIRM/attest/application.txt"
$INTAKE/.venv/Scripts/python -m intake.cli read "$FIRM/sources/scan.pdf" --out "$FIRM/attest/scan.txt"
cat > "$FIRM/tags.yaml" <<'YAML'
tags:
  - {id: w1, doc: attest/wisp.txt, quote: "All staff sign in to email", control: mfa, scope: email}
  - {id: w2, doc: attest/wisp.txt, quote: "Control: MFA; Scope: All users", control: mfa, scope: all_users}
  - {id: a1, doc: attest/application.txt, quote: "MFA required for remote access: checked", control: mfa, scope: remote_access}
YAML
venv/Scripts/python.exe -m attest check "$FIRM"
```

Expected: a report whose three attestations each carry a `- source:` line, `WISP.pdf (sha256 ...), p. 1` and `application.pdf (sha256 ...), p. 1`; `a1` is unchecked (remote access has no export). The application's layout grade is FAIR and its tag is still accepted.

- [ ] **Step 2: Watch the refusals fire on real readings**

```bash
cat >> "$FIRM/tags.yaml" <<'YAML'
  - {id: s1, doc: attest/scan.txt, quote: "All staff sign in to email", control: mfa, scope: email}
YAML
venv/Scripts/python.exe -m attest check "$FIRM"; echo "exit $?"
sed -i 's/practice management/practise management/' "$FIRM/attest/wisp.txt"
sed -i '$d' "$FIRM/tags.yaml"
venv/Scripts/python.exe -m attest check "$FIRM"; echo "exit $?"
```

Expected: first `attest: tags.yaml: tag 's1': line ... was read by OCR, whose grade does not show its errors; ...` and `exit 2`; then `attest/wisp.txt was edited after it was read` and `exit 2`, with `report.md` replaced by the CHECK FAILED stub both times. Delete the temporary folder after.

- [ ] **Step 3: Document the firm folder and the rules**

Apply this change to `README.md` (the firm folder tree, then a new section before `## Running`):

```diff
@@ -18,7 +18,10 @@
 
     firm/<name>/
       attest/            the attestation documents, plain UTF-8 text
-                         (application.txt, wisp.txt, ...); tags may quote only these
+                         (application.txt, wisp.txt, ...); tags may quote only these.
+                         A document intake read from a PDF, Word file or scan has
+                         its sidecar beside it (wisp.txt.map.json)
+      sources/           the originals intake read (WISP.pdf, ...); never quoted
       exports/
         manifest.yaml    each export file with its reader and exported_at
         *.json           the export files (see docs/exports.md)
@@ -76,6 +79,26 @@
 - An application answer of "No" is a disclosure, not an attestation, and is
   not tagged.
 
+## Documents read by intake
+
+A firm's WISP and insurance application usually arrive as PDF or Word. intake, a separate private package,
+reads them into the text attest quotes and a sidecar that says where each line came from and how it was read:
+
+    intake read firm/<name>/sources/WISP.pdf --out firm/<name>/attest/wisp.txt
+
+Tags name `attest/wisp.txt` as before. With the sidecar beside it, attest also:
+
+- **stops the run** if the text was edited after it was read (its hash no longer matches the sidecar; a CRLF
+  checkout still matches), if the reading is incomplete, or if the sidecar is not intake's format 1;
+- **refuses a tag** whose quote touches a line read by OCR, a quoted earlier email, a table row read without its
+  headers, or a line on a page whose parse or OCR grade is below good. Docling's OCR grade stayed "excellent" on
+  scans that lost a quarter of their words (intake's RESULTS.md), so attest never vouches for OCR text: tag a
+  born-digital copy, or a plain-text document a person has checked against the original;
+- **cites the original** in the report: `- source: WISP.pdf (sha256 cc5d02b898ad), p. 1`.
+
+A document with no sidecar is checked as plain text, and the report says `- source: plain text, no source
+location`. A tag may never name a `.map.json` file.
+
 ## Running
 
 `venv/Scripts/python.exe -m attest check firm/<name>` writes
```

Append to `docs/superpowers/specs/2026-10-04-attestation-core-design.md`:

```markdown
## Amended 2026-10-08 (documents read by intake)

- Attestation documents may come from intake (intake `docs/format.md`, format 1): `attest/<name>.txt` with
  `attest/<name>.txt.map.json` beside it, the original under `sources/`. attest reads the sidecar with the
  standard library and imports no intake code (intake spec, decision 3).
- The run stops on a sidecar of another format, a text edited after it was read (the hash is taken on the LF
  text, so a CRLF checkout still matches) or an incomplete reading.
- A tag is refused (the run stops with the tag and the reason named, like the other grounding refusals) when its
  quote touches a line read by OCR (`how` is `ocr` or `rescanned`), a `quoted` line, a `no_header` table row, or a
  line on a page whose parse or OCR grade is below GOOD; and every table row when intake's table-fidelity bar is
  missed (`REFUSE_TABLE_ROWS` in `attest/reading.py`).
- Two departures from the intake spec's wording, with their evidence (intake RESULTS.md; scratch run of
  2026-10-08): the OCR rule replaces "any grade below GOOD" for OCR text, because Docling's OCR grade stayed
  EXCELLENT on pages that lost up to 27% of their words; and the layout grade is not a reason to refuse, because
  a born-digital form's layout was graded FAIR (0.68) while its text layer read exactly.
- Each attestation in the report gets a `- source:` line: the original's name, the first 12 hex digits of its
  hash and the pages, slides or cells its lines came from, or `plain text, no source location`.
```

- [ ] **Commit**

```bash
git add README.md docs/superpowers/specs/2026-10-04-attestation-core-design.md
git commit -F - <<'EOF'
Document documents read by intake: the sources folder, the sidecar's checks and refusals, the source line

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
