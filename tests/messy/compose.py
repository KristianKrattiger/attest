"""Apply operators to the seed, run the check, and judge the result against what the operators declare.

Properties, for every run (spec 2026-10-14, The harness):
1. No false backed: no scope an applied operator breaks comes out backed.
2. Inert is identical: when every applied operator is inert, each tag's status and entities equal the seed's.
3. Promised stops happen: when an applied operator is "stops", the run stops with that operator's text.
4. No undecided stops: a run stops only when an applied operator declares `stop` or `may_stop`.
"""
from __future__ import annotations

import random
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from attest.compare import check
from attest.model import AttestError
from messy.catalog import COMBINABLE
from messy.firm import Firm, assemble
from messy.operators import Operator

Verdicts = dict[str, tuple[str, str, tuple[str, ...]]]  # tag id -> (control.scope, status, sorted entities)


@dataclass(frozen=True)
class Outcome:
    applied: tuple[Operator, ...]
    skipped: tuple[Operator, ...]
    verdicts: Verdicts  # empty when the run stopped
    stopped: str  # the AttestError message, or "" when the run finished


def apply(seed: Firm, ops: Sequence[Operator]) -> tuple[Firm, tuple[Operator, ...], tuple[Operator, ...]]:
    """A copy of the seed with each operator applied; inert operators go last, so they reshape whatever the others
    wrote. Returns the firm, the operators that applied, and those skipped for want of anything to edit."""
    firm = seed.copy()
    applied, skipped = [], []
    for op in sorted(ops, key=lambda op: op.effect == "inert"):
        (applied if op.edit(firm) else skipped).append(op)
    return firm, tuple(applied), tuple(skipped)


def _outcome(folder: Path, applied: tuple[Operator, ...], skipped: tuple[Operator, ...]) -> Outcome:
    try:
        results = check(folder)
    except AttestError as e:
        return Outcome(applied, skipped, {}, str(e))
    verdicts = {tag.id: (f"{tag.control}.{tag.scope}", v.status, tuple(sorted(v.entities))) for tag, v in results}
    return Outcome(applied, skipped, verdicts, "")


def run(seed: Firm, ops: Sequence[Operator]) -> Outcome:
    """The check on a copy of the seed with these operators applied."""
    firm, applied, skipped = apply(seed, ops)
    with tempfile.TemporaryDirectory() as tmp:
        return _outcome(firm.write(Path(tmp) / "firm"), applied, skipped)


def run_capture(exports: Path) -> Outcome:
    """The check on a capture exactly as its files were written: encoding, byte-order mark and line endings kept."""
    with tempfile.TemporaryDirectory() as tmp:
        return _outcome(assemble(Path(tmp) / "firm", exports), (), ())


def violations(outcome: Outcome, seed: Outcome) -> list[str]:
    """Each property this run breaks, in words; [] when it holds them all."""
    ops = outcome.applied
    allowed = [op.stop or op.may_stop for op in ops if op.stop or op.may_stop]
    if outcome.stopped:
        if not allowed:
            return [f"undecided stop: {outcome.stopped}"]
        if not any(text in outcome.stopped for text in allowed):
            return [f"stopped for a reason no applied operator gives: {outcome.stopped}"]
        return []
    promised = [op.name for op in ops if op.effect == "stops"]
    if promised:
        return [f"did not stop, though {', '.join(promised)} must stop it"]
    problems = [f"false backed: {tag} ({scope}) after '{op.name}'"
                for op in ops if op.effect == "breaks"
                for tag, (scope, status, _) in outcome.verdicts.items() if scope in op.scopes and status == "backed"]
    if ops and all(op.effect == "inert" for op in ops):
        problems += [f"inert changed {tag}: {seed.verdicts[tag][1:]} -> {verdict[1:]}"
                     for tag, verdict in outcome.verdicts.items() if verdict != seed.verdicts[tag]]
    return problems


def degraded(outcome: Outcome, seed: Outcome) -> dict[str, set[str]]:
    """For each applied "holds" operator, the statuses its scopes dropped to, leaving out scopes an applied "breaks"
    operator breaks; an operator whose scopes all kept the seed's status is left out."""
    if outcome.stopped:
        return {}
    broken = {scope for op in outcome.applied if op.effect == "breaks" for scope in op.scopes}
    found = {}
    for op in outcome.applied:
        if op.effect == "holds":
            drops = {status for tag, (scope, status, _) in outcome.verdicts.items()
                     if scope in op.scopes - broken and status != seed.verdicts[tag][1]}
            if drops:
                found[op.name] = drops
    return found


def combinations(seed_number: int, count: int, most: int = 4,
                 catalog: Sequence[Operator] = COMBINABLE) -> list[tuple[Operator, ...]]:
    """`count` combinations of one to `most` distinct operators; the same seed number always gives the same ones.
    Known false backeds are left out, so each combination tests what is not yet known."""
    rng = random.Random(seed_number)
    return [tuple(rng.sample(list(catalog), rng.randint(1, most))) for _ in range(count)]


def shrink(ops: Sequence[Operator], fails: Callable[[tuple[Operator, ...]], bool]) -> tuple[Operator, ...]:
    """The smallest subset found, one removal at a time, that still fails."""
    ops = tuple(ops)
    shrunk = True
    while shrunk and len(ops) > 1:
        shrunk = False
        for i in range(len(ops)):
            candidate = ops[:i] + ops[i + 1:]
            if fails(candidate):
                ops, shrunk = candidate, True
                break
    return ops


@dataclass
class Tally:
    """What a long run found: every property violation, every stop, and the noise cost of each "holds" operator."""

    runs: int = 0
    problems: list[str] = field(default_factory=list)
    stops: Counter = field(default_factory=Counter)
    applied: Counter = field(default_factory=Counter)
    degraded: Counter = field(default_factory=Counter)
    drops: defaultdict = field(default_factory=lambda: defaultdict(Counter))

    def add(self, outcome: Outcome, seed: Outcome, problems: list[str]) -> None:
        self.runs += 1
        self.problems += problems
        if outcome.stopped:
            self.stops[re.sub(r"rows? \d+( and \d+)?", "row N", outcome.stopped)] += 1
        for op in outcome.applied:
            if op.effect == "holds":
                # Only a run that finished is counted; adding 0 for one that stopped still gives the operator its row.
                self.applied[op.name] += 0 if outcome.stopped else 1
        for name, statuses in degraded(outcome, seed).items():
            self.degraded[name] += 1
            self.drops[name].update(statuses)

    def markdown(self, seed_name: str, seed_number: int, today: date) -> str:
        lines = [
            "# Messy-firm run", "",
            f"Run {today.isoformat()} on the {seed_name} seed: {self.runs} combinations of one to four operators "
            f"from tests/messy/catalog.py, random seed {seed_number}.", "",
            f"- Property violations: {len(self.problems)}",
            f"- Runs that stopped: {sum(self.stops.values())}", "",
        ]
        if self.problems:
            lines += ["## Violations", ""] + [f"- {p}" for p in self.problems] + [""]
        lines += ["## Stops", "", "| Reason | Runs |", "|---|---|"]
        lines += [f"| {reason} | {n} |" for reason, n in sorted(self.stops.items())]
        lines += ["", '## Noise cost of "holds" operators', "",
                  "A run counts against an operator when a scope it declares left the seed's status while it was "
                  'applied and no applied "breaks" operator breaks that scope. Every "holds" operator applied in '
                  "that run with the same scope is charged. Runs that stopped are not counted, because they give no "
                  'verdict to degrade. "Degraded to" counts, for each status, the runs in which one of the '
                  "operator's scopes reached it; a run can reach two statuses.", "",
                  "| Operator | Runs applied and finished | Runs degraded | Degraded to |", "|---|---|---|---|"]
        for name in sorted(self.applied):
            to = ", ".join(f"{status} {n}" for status, n in sorted(self.drops.get(name, Counter()).items())) or "-"
            lines.append(f"| {name} | {self.applied[name]} | {self.degraded[name]} | {to} |")
        return "\n".join(lines) + "\n"
