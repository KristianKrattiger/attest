"""The Markdown report: a count line, the exports, then one section per attestation (spec: Pipeline, step 4).

An attestation is the set of document lines its tags touch: tags in one document whose line ranges meet, directly
or through other tags, are one attestation, however their quotes divide the passage. Its section quotes those whole
lines, is headed by the worst of its tags' verdicts (any gap makes it a gap, else any unchecked makes it unchecked,
else it is backed), and lists each tag with its own verdict. So no section shows a backed fragment of lines that
another tag finds unchecked or failing. The count line counts attestations, not tags. Under it, when the run's
evidence is given, a table lists every export: its reader, file, exported_at in UTC and row count.
"""
from __future__ import annotations

import dataclasses
import re
from collections import Counter
from collections.abc import Iterable
from datetime import timezone
from typing import TYPE_CHECKING, Optional

from attest.model import Span, Status, Tag, Verdict

if TYPE_CHECKING:
    from attest.evidence import Evidence

TITLE = "# Attestation check:"  # how every report this tool writes begins
_ONE_LINE = str.maketrans("\r\n", "  ")

Attestation = tuple[str, str, list[tuple[Tag, Verdict]]]  # doc, its whole lines, and each tag on them with its verdict


def one_line(text: str) -> str:
    """The text on one line: a firm's words cannot start a heading, a list or any other block of the report."""
    return text.translate(_ONE_LINE)


def _span(tag: Tag) -> Span:
    """The tag's line range, which grouping needs: a tag without one (built by hand, never grounded) is refused.

    Grouping such tags by their exact quote instead would split a passage tagged by clause (final re-review N1).
    """
    if tag.span is None:
        raise ValueError(f"cannot report tag {tag.id!r} without its line range (load_tags records it when it "
                         "grounds the quote)")
    return tag.span


def _same_passage(a: Tag, b: Tag) -> bool:
    """Whether two tags touch a common line of one document."""
    return a.doc == b.doc and _span(a).first <= _span(b).last and _span(b).first <= _span(a).last


def _passage(tags: list[Tag]) -> str:
    """The whole lines the tags touch, first to last."""
    lines: dict[int, str] = {}
    for span in map(_span, tags):
        lines.update(enumerate(span.lines, start=span.first))
    return "\n".join(lines[n] for n in range(min(lines), max(lines) + 1))  # spans that meet leave no line out


def attestations(results: list[tuple[Tag, Verdict]]) -> list[Attestation]:
    """The results grouped by attestation, in the order each first appears, with their tags in result order.

    Tags whose lines meet are joined transitively: a tag spanning two lines joins the tags on either line. Every
    tag must carry its line range.
    """
    for tag, _ in results:
        _span(tag)
    group = list(range(len(results)))

    def root(i: int) -> int:
        while group[i] != i:
            i = group[i]
        return i

    for i, (tag, _) in enumerate(results):
        for j in range(i):
            if _same_passage(tag, results[j][0]):
                group[root(i)] = root(j)
    grouped: dict[int, list[tuple[Tag, Verdict]]] = {}
    for i, result in enumerate(results):
        grouped.setdefault(root(i), []).append(result)
    return [(tagged[0][0].doc, _passage([tag for tag, _ in tagged]), tagged) for tagged in grouped.values()]


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


def _cell(text: str) -> str:
    """Firm text as one table cell: on one line, with no bare pipe to split the cell."""
    return one_line(text).replace("|", "\\|")


def _exports_table(evidence: Evidence) -> list[str]:
    """Each export the run read: reader, file, exported_at in UTC, and row count."""
    exports = [(field.name, export) for field in dataclasses.fields(evidence)
               if (export := getattr(evidence, field.name)) is not None]
    if not exports:
        return ["Exports: none"]
    lines = ["Exports:", "", "| reader | file | exported_at (UTC) | rows |", "|---|---|---|---|"]
    for reader, export in exports:
        when = export.exported_at.astimezone(timezone.utc).isoformat()
        lines.append(f"| `{reader}` | `{_cell(export.file)}` | {when} | {len(export.items)} |")
    return lines


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


def render(firm_name: str, results: list[tuple[Tag, Verdict]], evidence: Optional[Evidence] = None) -> str:
    for _, verdict in results:
        _require_statable(verdict)
    sections = [(doc, passage, tagged, combined_status(v.status for _, v in tagged))
                for doc, passage, tagged in attestations(results)]
    counts = Counter(status for *_, status in sections)
    lines = [f"{TITLE} {one_line(firm_name)}", "",
             f"backed {counts['backed']}, gap {counts['gap']}, unchecked {counts['unchecked']}", ""]
    if evidence is not None:
        lines += [*_exports_table(evidence), ""]
    for doc, passage, tagged, status in sections:
        ids = ", ".join(one_line(tag.id) for tag, _ in tagged)
        lines += [f"## {ids}: {status.upper()}", "", *_quote(passage), "", f"- document: `{one_line(doc)}`"]
        for tag, verdict in tagged:
            lines += _tag_lines(tag, verdict)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
