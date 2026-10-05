"""The Markdown report: a count line, then one section per attestation (spec: Pipeline, step 4)."""
from __future__ import annotations

from collections import Counter

from attest.model import Tag, Verdict


def render(firm_name: str, results: list[tuple[Tag, Verdict]]) -> str:
    counts = Counter(v.status for _, v in results)
    lines = [f"# Attestation check: {firm_name}", "",
             f"backed {counts['backed']}, gap {counts['gap']}, unchecked {counts['unchecked']}", ""]
    for tag, verdict in results:
        lines += [f"## {tag.id}: {verdict.status.upper()}", "", f"> {tag.quote}", "",
                  f"- document: `{tag.doc}`",
                  f"- control: `{tag.control}.{tag.scope}`",
                  f"- reason: {verdict.reason}"]
        if verdict.population:
            lines.append(f"- population: {verdict.population}")
        if verdict.entities:
            lines.append("- entities: " + ", ".join(verdict.entities))
        if verdict.cited:
            lines.append("- cited: " + ", ".join(f"`{c}`" for c in verdict.cited))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
