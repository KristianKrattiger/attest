from pathlib import Path

import yaml

from attest.compare import check

DEV = Path(__file__).resolve().parents[1] / "firm" / "dev"


def _truth():
    return yaml.safe_load((DEV / "truth.yaml").read_text(encoding="utf-8"))["verdicts"]


def test_every_dev_firm_verdict_matches_its_planted_truth():
    results = check(DEV)
    truth = _truth()
    assert [tag.id for tag, _ in results] == list(truth)
    for tag, verdict in results:
        expected = truth[tag.id]
        assert verdict.status == expected["status"], (tag.id, verdict.reason)
        assert sorted(verdict.entities) == sorted(expected.get("entities", [])), (tag.id, verdict.reason)


def test_the_dev_firm_has_zero_false_backed():
    truth = _truth()
    false_backed = [t.id for t, v in check(DEV) if v.status == "backed" and truth[t.id]["status"] != "backed"]
    assert false_backed == []
