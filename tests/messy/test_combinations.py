"""Seeded combinations of mess under the four properties (compose.py), and the long run that writes the summary."""
from datetime import date

import pytest

from messy.compose import Outcome, Tally, combinations, run, shrink, violations
from messy.firm import LAB
from messy.operators import Operator

SEED_NUMBER = 20261014
COMBINATIONS = combinations(SEED_NUMBER, 200)


@pytest.mark.parametrize("number", range(len(COMBINATIONS)))
def test_a_combination_of_mess_keeps_every_property(seeded, number):
    combo = COMBINATIONS[number]
    problems = violations(run(seeded.firm, combo), seeded.outcome)
    if problems:
        smallest = shrink(combo, lambda ops: bool(violations(run(seeded.firm, ops), seeded.outcome)))
        pytest.fail(f"{problems}; smallest failing set: {[op.name for op in smallest]}")


def test_the_tally_counts_a_holds_operator_only_in_runs_that_finished(seeded):
    noisy = Operator("noisy mess", "holds", lambda firm: True, scopes=frozenset({"mfa.admins"}))
    silent = Operator("silent mess", "holds", lambda firm: True, scopes=frozenset({"mfa.admins"}))
    stopped = Outcome((noisy, silent), (), {}, "users.json: the export is one page of several (it has @odata.nextLink)")
    finished = Outcome((noisy,), (), seeded.outcome.verdicts, "")
    tally = Tally()
    for outcome in (stopped, finished):
        tally.add(outcome, seeded.outcome, [])
    assert tally.applied[noisy.name] == 1
    assert sum(tally.stops.values()) == 1
    table = tally.markdown("dev", 1, date(2026, 10, 14)).splitlines()
    assert [line for line in table if line.startswith(f"| {noisy.name} |")] == [f"| {noisy.name} | 1 | 0 | - |"]
    # An operator that only ever applied in runs that stopped keeps its row: its cost is unmeasured, shown as 0 runs.
    assert [line for line in table if line.startswith(f"| {silent.name} |")] == [f"| {silent.name} | 0 | 0 | - |"]


@pytest.mark.messy
def test_five_thousand_combinations_keep_every_property_and_write_the_summary(seeded):
    tally = Tally()
    for combo in combinations(SEED_NUMBER, 5000):
        outcome = run(seeded.firm, combo)
        problems = violations(outcome, seeded.outcome)
        if problems:
            smallest = shrink(combo, lambda ops: bool(violations(run(seeded.firm, ops), seeded.outcome)))
            problems = [f"{p}; smallest failing set: {[op.name for op in smallest]}" for p in problems]
        tally.add(outcome, seeded.outcome, problems)
    LAB.mkdir(parents=True, exist_ok=True)
    (LAB / "messy-summary.md").write_text(tally.markdown(seeded.name, SEED_NUMBER, date.today()), encoding="utf-8",
                                          newline="\n")
    assert tally.problems == []
