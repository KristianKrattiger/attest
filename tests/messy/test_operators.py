import pytest

from messy.compose import run, violations
from messy.catalog import CATALOG
from messy.operators import PROVABLE


def test_every_operator_declares_what_its_effect_needs():
    assert len({op.name for op in CATALOG}) == len(CATALOG)
    for op in CATALOG:
        assert op.effect in ("breaks", "holds", "inert", "stops"), op.name
        assert bool(op.scopes) == (op.effect in ("breaks", "holds")), op.name
        assert op.scopes <= set(PROVABLE) and set(op.alone) <= set(PROVABLE), op.name
        assert bool(op.why) == (op.effect == "holds"), op.name  # review reads every "holds" justification
        assert bool(op.stop) == (op.effect == "stops"), op.name
        assert all(status in ("gap", "unchecked") for status in op.alone.values()), op.name
        assert not op.known or op.effect == "breaks", op.name


def _expected_to_fail_while_known(op):
    if not op.known:
        return op
    return pytest.param(op, marks=pytest.mark.xfail(strict=True, reason=f"known false backed: {op.known}"))


@pytest.mark.parametrize("op", [_expected_to_fail_while_known(op) for op in CATALOG], ids=lambda op: op.name)
def test_an_operator_alone_gives_the_verdicts_it_declares(seeded, op):
    outcome = run(seeded.firm, (op,))
    if outcome.skipped:
        pytest.skip(f"the {seeded.name} seed has nothing for this operator to edit")
    assert violations(outcome, seeded.outcome) == []
    if outcome.stopped:
        return  # violations() checked the stop is one this operator declares
    statuses: dict[str, set[str]] = {}
    for scope, status, _ in outcome.verdicts.values():
        statuses.setdefault(scope, set()).add(status)
    assert all(len(found) == 1 for found in statuses.values()), statuses
    changed = {scope: found.pop() for scope, found in statuses.items() if scope in PROVABLE and found != {"backed"}}
    assert changed == dict(op.alone)
