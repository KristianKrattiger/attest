"""Operators against the real captures of the same mess, and the real captures against what the seed promises."""
import copy

import pytest

from messy.catalog import BY_NAME, CATALOG
from messy.compose import Outcome, apply, run, run_capture, violations
from messy.fidelity import mismatches
from messy.firm import DEV, LAB, SEED_CLEAN, Firm
from messy.mfa import _all_users_policy

TWINS = [op for op in CATALOG if op.twin]


def _made(firm, name):
    return apply(firm, (BY_NAME[name],))[0]


def _edited(before, after, reader):
    """The position of the one record `after` edited in place, among the `reader` records of both."""
    (index,) = [i for i, (old, new) in enumerate(zip(before.rows(reader), after.rows(reader))) if old != new]
    return index


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
        "defender_machines: the operator changes healthStatus (string), which the capture does not"]


def test_a_capture_that_changed_another_nested_key_than_the_operator_is_a_mismatch(seeded):
    before = seeded.firm
    real = before.copy()
    _all_users_policy(real)["conditions"]["applications"]["includeApplications"] = ["Office365"]
    assert mismatches(before, _made(before, "MFA exclusions group"), real) == [
        "entra_ca_policies: the operator changes conditions.users.excludeGroups (array), which the capture does not"]


def test_a_capture_that_changed_the_field_to_another_json_type_is_a_mismatch(seeded):
    before = seeded.firm
    synthetic = _made(before, "sensor cut off")
    real = before.copy()
    real.rows("defender_machines")[_edited(before, synthetic, "defender_machines")]["healthStatus"] = None
    assert mismatches(before, synthetic, real) == [
        "defender_machines: the operator changes healthStatus (string), which the capture does not"]


def test_an_operator_removing_a_key_the_capture_kept_is_a_mismatch(seeded):
    before = seeded.firm
    synthetic = before.copy()
    del synthetic.rows("defender_machines")[0]["osPlatform"]
    assert mismatches(before, synthetic, before.copy()) == [
        "defender_machines: the operator changes osPlatform (absent), which the capture does not"]


def test_a_capture_that_changed_all_the_operator_did_and_drifted_elsewhere_agrees(seeded):
    before = seeded.firm
    synthetic = _made(before, "sensor cut off")
    real = synthetic.copy()
    machines = real.rows("defender_machines")
    drifted = (_edited(before, synthetic, "defender_machines") + 1) % len(machines)
    machines[drifted]["lastSeen"] = "2000-01-01T00:00:00Z"
    assert machines[drifted] != before.rows("defender_machines")[drifted]
    assert mismatches(before, synthetic, real) == []


def test_added_records_with_other_fields_are_a_mismatch(seeded):
    before = seeded.firm
    synthetic = _made(before, "discovered unmanaged PC")
    real = synthetic.copy()
    del real.rows("defender_machines")[-1]["osPlatform"]
    assert mismatches(before, synthetic, real) == [
        "defender_machines: added records differ; only the operator's have ['osPlatform (string)'], "
        "only the capture's have []"]


def _twin_problems(op, folder):
    """Why this operator does not agree with its twin capture in `folder`, in words; [] when it does."""
    real = run_capture(folder / "after" / "exports")
    if op.effect == "stops":
        return [] if op.stop in real.stopped else [f"the capture does not stop with '{op.stop}': {real.stopped!r}"]
    before, after = Firm.load(folder / "before" / "exports"), Firm.load(folder / "after" / "exports")
    synthetic, applied, _ = apply(before, (op,))
    if applied != (op,):
        return [f"the operator finds nothing to edit in {folder.name}/before"]
    if problems := mismatches(before, synthetic, after):
        return problems
    # A before that is already a gap would let a rule that misses the real mess pass, so it must be backed first.
    start = run_capture(folder / "before" / "exports")
    if start.stopped:
        return [f"the before capture stops: {start.stopped}"]
    scoped = {tag: (scope, status) for tag, (scope, status, _) in start.verdicts.items() if scope in op.scopes}
    if untagged := sorted(op.scopes - {scope for scope, _ in scoped.values()}):
        return [f"the before capture has no tag on {', '.join(untagged)}, so it shows nothing about the mess"]
    if unbacked := [f"{tag} ({scope}) is {status}" for tag, (scope, status) in scoped.items() if status != "backed"]:
        return [f"the before capture is already not backed: {', '.join(unbacked)}"]
    problems = violations(Outcome((op,), (), real.verdicts, real.stopped), start)
    if op.known:  # only a false backed confirms it: any other problem, an undecided stop included, is not that
        if any(problem.startswith("false backed") for problem in problems):
            return []
        if problems:
            return [f"'{op.name}' is `known` for a false backed, but its real capture gives: {'; '.join(problems)}"]
        return [f"'{op.name}' no longer gives a false backed on its real capture: clear `known`"]
    return problems


@pytest.mark.parametrize("op", TWINS, ids=lambda op: op.name)
def test_an_operator_makes_its_mess_the_way_the_tenant_did(op):
    folder = LAB / op.twin
    if not folder.exists():
        pytest.skip(f"no twin capture yet: firm/lab/{op.twin} (docs/engineering/lab.md)")
    assert _twin_problems(op, folder) == []


def _twin(tmp_path, before, after):
    """A twin folder holding these two firms as its before and after captures."""
    before.write(tmp_path / "before")
    after.write(tmp_path / "after")
    return tmp_path


def test_a_twin_made_from_a_backed_before_agrees(seeded, tmp_path):
    op = BY_NAME["VM off for 8 days"]
    assert _twin_problems(op, _twin(tmp_path, seeded.firm, apply(seeded.firm, (op,))[0])) == []


def test_a_twin_whose_before_is_already_a_gap_does_not_pass(seeded, tmp_path):
    op = BY_NAME["VM off for 8 days"]
    already_gap = apply(seeded.firm, (BY_NAME["sensor cut off"],))[0]  # one laptop is unhealthy before the mess
    problems = _twin_problems(op, _twin(tmp_path, already_gap, apply(already_gap, (op,))[0]))
    assert len(problems) == 1 and problems[0].startswith("the before capture is already not backed")
    assert "edr.all_endpoints" in problems[0]


def test_a_twin_whose_before_stops_does_not_pass(seeded, tmp_path):
    op = BY_NAME["VM off for 8 days"]
    padded = seeded.firm.copy()
    padded.rows("entra_users")[0]["userPrincipalName"] += " "
    problems = _twin_problems(op, _twin(tmp_path, padded, apply(padded, (op,))[0]))
    assert len(problems) == 1 and problems[0].startswith("the before capture stops")


def test_a_known_false_backed_is_confirmed_by_a_false_backed_and_by_nothing_else(seeded, tmp_path):
    op = BY_NAME["shared mailbox Veeam never saw"]
    assert op.known
    after = apply(seeded.firm, (op,))[0]
    assert _twin_problems(op, _twin(tmp_path / "honest", seeded.firm, after)) == []
    after.rows("entra_users")[0]["userPrincipalName"] += " "  # the capture stops, for a reason nothing declares
    problems = _twin_problems(op, _twin(tmp_path / "stops", seeded.firm, after))
    assert len(problems) == 1 and "is `known` for a false backed" in problems[0]
    assert "undecided stop" in problems[0]


def test_the_dev_capture_as_written_gives_the_verdicts_the_harness_sees():
    assert run_capture(DEV / "exports") == run(Firm.load(DEV / "exports"), ())


def test_the_seed_capture_as_written_gives_the_verdicts_the_harness_sees(seeded):
    if seeded.name != "seed-clean":
        pytest.skip("no seed-clean capture yet (docs/engineering/lab.md)")
    assert run_capture(SEED_CLEAN / "exports") == seeded.outcome


def test_the_powershell_5_1_capture_reads_as_the_powershell_7_one():
    ps51, ps7_exports = LAB / "seed-clean-ps51" / "exports", SEED_CLEAN / "exports"
    if not (ps51.exists() and ps7_exports.exists()):
        pytest.skip("no PowerShell 5.1 and seed-clean captures yet (docs/engineering/lab.md)")
    ps7 = run_capture(ps7_exports)
    assert ps7.stopped == ""
    assert run_capture(ps51) == ps7
