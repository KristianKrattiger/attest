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


MALFORMED = {
    "source is a string": lambda d: d.update(source="WISP.pdf"),
    "source has no name": lambda d: d["source"].pop("name"),
    "lines is null": lambda d: d.update(lines=None),
    "a line entry is a string": lambda d: d.update(lines=["line 1"]),
    "a line has no how": lambda d: d["lines"][0].pop("how"),
    "flags is null": lambda d: d["lines"][0].update(flags=None),
    "loc is null": lambda d: d["lines"][0].update(loc=None),
    "a loc page is a list": lambda d: d["lines"][0]["loc"].update(page=[1]),
    "pages is null": lambda d: d.update(pages=None),
    "a page has no page number": lambda d: d["pages"][0].pop("page"),
    "grades is a list": lambda d: d["pages"][0].update(grades=["excellent"]),
    "format is true": lambda d: d.update(format=True),
    "format is 1.0": lambda d: d.update(format=1.0),
}


@pytest.mark.parametrize("damage", list(MALFORMED.values()), ids=list(MALFORMED))
def test_a_malformed_sidecar_stops_the_run_naming_it(tmp_path, damage):
    data = sidecar()
    damage(data)
    with pytest.raises(AttestError, match="wisp.txt.map.json"):
        load_tags(firm(tmp_path, data), PROFILE)


def test_a_quoted_line_with_no_entry_stops_the_run(tmp_path):
    with pytest.raises(AttestError, match="line 1 has no entry"):
        load_tags(firm(tmp_path, sidecar(lines=[])), PROFILE)


def test_a_line_on_a_page_the_reading_does_not_list_is_refused(tmp_path):
    with pytest.raises(AttestError, match="tag 'w1': line 1 is on page 2, which the reading does not list"):
        load_tags(firm(tmp_path, sidecar(lines=[line(1, 0, 35, page=2)])), PROFILE)


def test_a_page_whose_grade_is_unspecified_is_refused(tmp_path):
    with pytest.raises(AttestError, match="tag 'w1': line 1 is on page 1, whose parse grade is unspecified"):
        load_tags(firm(tmp_path, sidecar(grades={"layout": "excellent", "parse": "unspecified"})), PROFILE)


def test_an_absent_grade_is_not_a_refusal(tmp_path):
    [tag] = load_tags(firm(tmp_path, sidecar(grades={"layout": "excellent"})), PROFILE)
    assert tag.source.endswith("p. 1")


def test_a_line_read_some_other_way_is_refused(tmp_path):
    with pytest.raises(AttestError, match="tag 'w1': line 1 was read in a way attest does not know"):
        load_tags(firm(tmp_path, sidecar(lines=[line(1, 0, 35, how="weird")])), PROFILE)


def test_a_quote_spanning_a_blank_line_is_accepted(tmp_path):
    tags = ('tags:\n  - {id: w1, doc: attest/wisp.txt, quote: "All staff use MFA on every account.\\n\\n'
            'Control: EDR; Scope: All laptops", control: mfa, scope: all_users}\n')
    [tag] = load_tags(firm(tmp_path, sidecar(lines=[line(1, 0, 35), line(3, 37, 69)]), tags=tags), PROFILE)
    assert (tag.span.first, tag.span.last) == (1, 3)
    assert tag.source == f"WISP.pdf (sha256 {SHA[:12]}), p. 1"


def test_a_table_row_is_accepted_and_cited_while_table_rows_are_not_refused(tmp_path):
    tags = "tags:\n  - {id: e1, doc: attest/wisp.txt, quote: 'EDR; Scope: All laptops', control: edr, scope: all_endpoints}\n"
    [tag] = load_tags(firm(tmp_path, sidecar(), tags=tags), PROFILE)
    assert tag.source == f"WISP.pdf (sha256 {SHA[:12]}), p. 1"


@pytest.mark.parametrize("loc, cited", [
    ([{"page": 1, "bbox": [72.0, 700.0, 540.0, 712.0], "origin": "bottomleft"},
      {"page": 2, "bbox": [72.0, 700.0, 540.0, 712.0], "origin": "bottomleft"}], "p. 1, p. 2"),
    ({"slide": 2}, "slide 2"),
    ({"sheet": "Budget", "cells": "A3:D3"}, "Budget!A3:D3"),
])
def test_a_line_is_cited_by_its_location_in_the_original(tmp_path, loc, cited):
    entry = line(1, 0, 35)
    entry["loc"] = loc
    data = sidecar(lines=[entry])
    data["pages"].append({"page": 2, "read": "text_layer", "status": "read", "grades": {"parse": "excellent"},
                          "scores": {}})
    [tag] = load_tags(firm(tmp_path, data), PROFILE)
    assert tag.source == f"WISP.pdf (sha256 {SHA[:12]}), {cited}"
