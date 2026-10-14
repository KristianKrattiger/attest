"""Seeded combinations of mess under the four properties (compose.py), and the long run that writes the summary."""
from datetime import date

import pytest

from messy.compose import Tally, combinations, run, shrink, violations
from messy.firm import LAB

SEED_NUMBER = 20261014
COMBINATIONS = combinations(SEED_NUMBER, 200)


@pytest.mark.parametrize("number", range(len(COMBINATIONS)))
def test_a_combination_of_mess_keeps_every_property(seeded, number):
    combo = COMBINATIONS[number]
    problems = violations(run(seeded.firm, combo), seeded.outcome)
    if problems:
        smallest = shrink(combo, lambda ops: bool(violations(run(seeded.firm, ops), seeded.outcome)))
        pytest.fail(f"{problems}; smallest failing set: {[op.name for op in smallest]}")


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
