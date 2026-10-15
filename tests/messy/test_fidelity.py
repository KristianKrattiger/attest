"""Operators against the real captures of the same mess, and the real captures against what the seed promises."""
import copy

import pytest

from messy.compose import Outcome, apply, run_capture, violations
from messy.fidelity import mismatches
from messy.firm import LAB, SEED_CLEAN, Firm
from messy.catalog import BY_NAME, CATALOG

TWINS = [op for op in CATALOG if op.twin]


def _made(firm, name):
    return apply(firm, (BY_NAME[name],))[0]


def test_an_operator_agrees_with_a_capture_that_made_the_same_mess(seeded):
    before = seeded.firm
    assert mismatches(before, _made(before, "VM off for 8 days"), _made(before, "VM off for 8 days")) == []


def test_a_capture_that_added_a_record_the_operator_did_not_is_a_mismatch(seeded):
    before = seeded.firm
    synthetic = _made(before, "sensor cut off")
    real = synthetic.copy()
    extra = copy.deepcopy(real.rows("defender_machines")[0])
    extra["id"] = "e" * 40
    real.rows("defender_machines").append(extra)
    assert mismatches(before, synthetic, real) == [
        "defender_machines: the operator adds 0 and removes 0 records; the capture adds 1 and removes 0"]


def test_an_operator_changing_a_field_the_capture_left_alone_is_a_mismatch(seeded):
    before = seeded.firm
    assert mismatches(before, _made(before, "sensor cut off"), before.copy()) == [
        "defender_machines: the operator changes healthStatus, which the capture does not"]


def test_added_records_with_other_fields_are_a_mismatch(seeded):
    before = seeded.firm
    synthetic = _made(before, "discovered unmanaged PC")
    real = synthetic.copy()
    del real.rows("defender_machines")[-1]["osPlatform"]
    assert mismatches(before, synthetic, real) == [
        "defender_machines: added records differ; only the operator's have ['osPlatform (string)'], "
        "only the capture's have []"]


@pytest.mark.parametrize("op", TWINS, ids=lambda op: op.name)
def test_an_operator_makes_its_mess_the_way_the_tenant_did(op):
    folder = LAB / op.twin
    if not folder.exists():
        pytest.skip(f"no twin capture yet: firm/lab/{op.twin} (docs/engineering/lab.md)")
    real = run_capture(folder / "after" / "exports")
    if op.effect == "stops":
        assert op.stop in real.stopped
        return
    before, after = Firm.load(folder / "before" / "exports"), Firm.load(folder / "after" / "exports")
    synthetic, applied, _ = apply(before, (op,))
    assert applied == (op,), f"the operator finds nothing to edit in firm/lab/{op.twin}/before"
    assert mismatches(before, synthetic, after) == []
    problems = violations(Outcome((op,), (), real.verdicts, real.stopped), run_capture(folder / "before" / "exports"))
    if op.known:
        assert problems, f"'{op.name}' no longer gives a false backed on its real capture: clear `known`"
        return
    assert problems == []


def test_the_seed_capture_as_written_gives_the_verdicts_the_harness_sees(seeded):
    if seeded.name != "seed-clean":
        pytest.skip("no seed-clean capture yet (docs/engineering/lab.md)")
    assert run_capture(SEED_CLEAN / "exports") == seeded.outcome


def test_the_powershell_5_1_capture_reads_as_the_powershell_7_one():
    ps51 = LAB / "seed-clean-ps51" / "exports"
    if not ps51.exists():
        pytest.skip("no PowerShell 5.1 capture yet (docs/engineering/lab.md)")
    ps7 = run_capture(SEED_CLEAN / "exports")
    assert ps7.stopped == ""
    assert run_capture(ps51) == ps7
