"""The Markdown report: a count line, then one section per attestation (spec: Pipeline, step 4).

An attestation is one quote in one document. Several tags may share it, one per claim it makes; its section is
headed by the worst of their verdicts (any gap makes it a gap, else any unchecked makes it unchecked, else it is
backed) and lists each tag with its own verdict. The count line counts attestations, not tags.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from attest.model import Status, Tag, Verdict

TITLE = "# Attestation check:"  # how every report this tool writes begins
_ONE_LINE = str.maketrans("\r\n", "  ")

Attestation = tuple[str, str, list[tuple[Tag, Verdict]]]  # doc, quote, and each tag on it with its verdict


def one_line(text: str) -> str:
    """The text on one line: a firm's words cannot start a heading, a list or any other block of the report."""
    return text.translate(_ONE_LINE)


def attestations(results: list[tuple[Tag, Verdict]]) -> list[Attestation]:
    """The results grouped by attestation (a distinct doc and quote), in the order each first appears."""
    grouped: dict[tuple[str, str], list[tuple[Tag, Verdict]]] = {}
    for tag, verdict in results:
        grouped.setdefault((tag.doc, tag.quote), []).append((tag, verdict))
    return [(doc, quote, tagged) for (doc, quote), tagged in grouped.items()]


def combined_status(statuses: Iterable[Status]) -> Status:
    """An attestation's verdict: gap if any of its tags is a gap, else unchecked if any is, else backed."""
    statuses = set(statuses)
    for status in ("gap", "unchecked"):
        if status in statuses:
            return status
    if statuses != {"backed"}:
        raise ValueError(f"cannot combine the statuses {sorted(statuses)!r}")
    return "backed"


def _quote(text: str) -> list[str]:
    """The text as a blockquote, every line of it quoted (a blank one as a bare '>')."""
    return [f"> {line}" if line else ">" for line in re.split(r"\r\n|\r|\n", text)]


def _require_statable(verdict: Verdict) -> None:
    """A verdict the report can state: a known status, and for a backed one the population that was checked."""
    if verdict.status not in ("backed", "gap", "unchecked"):
        raise ValueError(f"cannot report a verdict with status {verdict.status!r}")
    if verdict.status == "backed" and not verdict.population:
        raise ValueError("cannot report a backed verdict without its population")


def _tag_lines(tag: Tag, verdict: Verdict) -> list[str]:
    """One tag under its attestation: its verdict, then its control and scope and what the verdict rests on."""
    lines = [f"- tag {one_line(tag.id)}: {verdict.status.upper()}",
             f"  - control: `{one_line(tag.control)}.{one_line(tag.scope)}`",
             f"  - reason: {one_line(verdict.reason)}"]
    if verdict.population:
        lines.append(f"  - population: {one_line(verdict.population)}")
    if verdict.entities:
        lines.append("  - entities: " + ", ".join(one_line(e) for e in verdict.entities))
    if verdict.cited:
        lines.append("  - cited: " + ", ".join(f"`{one_line(c)}`" for c in verdict.cited))
    return lines


def render(firm_name: str, results: list[tuple[Tag, Verdict]]) -> str:
    for _, verdict in results:
        _require_statable(verdict)
    sections = [(doc, quote, tagged, combined_status(v.status for _, v in tagged))
                for doc, quote, tagged in attestations(results)]
    counts = Counter(status for *_, status in sections)
    lines = [f"{TITLE} {one_line(firm_name)}", "",
             f"backed {counts['backed']}, gap {counts['gap']}, unchecked {counts['unchecked']}", ""]
    for doc, quote, tagged, status in sections:
        ids = ", ".join(one_line(tag.id) for tag, _ in tagged)
        lines += [f"## {ids}: {status.upper()}", "", *_quote(quote), "", f"- document: `{one_line(doc)}`"]
        for tag, verdict in tagged:
            lines += _tag_lines(tag, verdict)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
