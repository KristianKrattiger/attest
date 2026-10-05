"""The Markdown report: a count line, then one section per attestation (spec: Pipeline, step 4)."""
from __future__ import annotations

import re
from collections import Counter

from attest.model import Tag, Verdict

TITLE = "# Attestation check:"  # how every report this tool writes begins
_ONE_LINE = str.maketrans("\r\n", "  ")


def one_line(text: str) -> str:
    """The text on one line: a firm's words cannot start a heading, a list or any other block of the report."""
    return text.translate(_ONE_LINE)


def _quote(text: str) -> list[str]:
    """The text as a blockquote, every line of it quoted (a blank one as a bare '>')."""
    return [f"> {line}" if line else ">" for line in re.split(r"\r\n|\r|\n", text)]


def _require_statable(verdict: Verdict) -> None:
    """A verdict the report can state: a known status, and for a backed one the population that was checked."""
    if verdict.status not in ("backed", "gap", "unchecked"):
        raise ValueError(f"cannot report a verdict with status {verdict.status!r}")
    if verdict.status == "backed" and not verdict.population:
        raise ValueError("cannot report a backed verdict without its population")


def render(firm_name: str, results: list[tuple[Tag, Verdict]]) -> str:
    counts = Counter(v.status for _, v in results)
    lines = [f"{TITLE} {one_line(firm_name)}", "",
             f"backed {counts['backed']}, gap {counts['gap']}, unchecked {counts['unchecked']}", ""]
    for tag, verdict in results:
        _require_statable(verdict)
        lines += [f"## {one_line(tag.id)}: {verdict.status.upper()}", "", *_quote(tag.quote), "",
                  f"- document: `{one_line(tag.doc)}`",
                  f"- control: `{one_line(tag.control)}.{one_line(tag.scope)}`",
                  f"- reason: {one_line(verdict.reason)}"]
        if verdict.population:
            lines.append(f"- population: {one_line(verdict.population)}")
        if verdict.entities:
            lines.append("- entities: " + ", ".join(one_line(e) for e in verdict.entities))
        if verdict.cited:
            lines.append("- cited: " + ", ".join(f"`{one_line(c)}`" for c in verdict.cited))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
