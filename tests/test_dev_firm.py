from pathlib import Path

import yaml

from attest.compare import check
from attest.report import attestations, combined_status

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


def test_the_two_compound_attestations_are_each_a_gap():
    # Each WISP line that makes two claims carries a tag per claim; the line's verdict is the worst of them.
    compound = {quote: combined_status(v.status for _, v in tagged)
                for _, quote, tagged in attestations(check(DEV)) if len(tagged) > 1}
    assert compound == {
        "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts.": "gap",
        "Email and files in Microsoft 365 are backed up every night with Veeam.": "gap",
    }
