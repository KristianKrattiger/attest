"""Four named combinations whose every verdict a person checked by hand, one truth file per seed."""
from pathlib import Path

import pytest
import yaml

from messy.catalog import BY_NAME
from messy.compose import run

ARCHETYPES = Path(__file__).parent / "archetypes"
NAMES = ("msp-run-firm", "reimaged-fleet", "backup-over-its-limit", "powershell-5-1-admin")


@pytest.mark.parametrize("name", NAMES)
def test_an_archetype_gets_its_hand_checked_verdicts(seeded, name):
    path = ARCHETYPES / seeded.name / f"{name}.yaml"
    if not path.exists():
        pytest.fail(f"hand-check the {name} archetype on the {seeded.name} seed and write {path}")
    truth = yaml.safe_load(path.read_text(encoding="utf-8"))
    outcome = run(seeded.firm, [BY_NAME[op] for op in truth["operators"]])
    assert (outcome.skipped, outcome.stopped) == ((), "")
    assert list(outcome.verdicts) == list(truth["verdicts"])
    for tag, expected in truth["verdicts"].items():
        _, status, entities = outcome.verdicts[tag]
        assert (status, list(entities)) == (expected["status"], sorted(expected.get("entities", []))), tag
