"""The judge itself: a harness that never fails proves nothing, so each property is shown to catch a planted lie."""
from messy.compose import combinations, degraded, run, shrink, violations
from messy.operators import PROVABLE, Operator


def _all_users_scopes(outcome):
    return {status for scope, status, _ in outcome.verdicts.values() if scope == "mfa.all_users"}


def test_the_seed_is_backed_wherever_a_scope_can_be_proven(seeded):
    assert seeded.outcome.stopped == ""
    for tag, (scope, status, _) in seeded.outcome.verdicts.items():
        assert status == ("backed" if scope in PROVABLE else "unchecked"), tag


def test_a_breaks_operator_that_breaks_nothing_is_a_false_backed(seeded):
    lie = Operator("claims to break MFA but edits nothing", "breaks", lambda firm: True,
                   scopes=frozenset({"mfa.all_users"}))
    outcome = run(seeded.firm, (lie,))
    assert _all_users_scopes(outcome) == {"backed"}
    assert violations(outcome, seeded.outcome) == [
        f"false backed: {tag} (mfa.all_users) after 'claims to break MFA but edits nothing'"
        for tag, (scope, _, _) in outcome.verdicts.items() if scope == "mfa.all_users"]


def test_an_inert_operator_that_changes_a_verdict_is_caught(seeded):
    def drop_registration(firm):
        firm.rows("entra_registration").pop(0)  # the first member's row
        return True
    outcome = run(seeded.firm, (Operator("claims to be inert", "inert", drop_registration),))
    assert any(problem.startswith("inert changed ") for problem in violations(outcome, seeded.outcome))


def test_a_promised_stop_that_does_not_happen_is_caught(seeded):
    outcome = run(seeded.firm, (Operator("claims to stop", "stops", lambda firm: True, stop="never said"),))
    assert violations(outcome, seeded.outcome) == ["did not stop, though claims to stop must stop it"]


def test_a_stop_no_operator_allows_is_caught(seeded):
    def pad(firm):
        firm.rows("entra_users")[0]["userPrincipalName"] += " "
        return True
    outcome = run(seeded.firm, (Operator("pads an address", "holds", pad, scopes=frozenset(PROVABLE), why="x"),))
    assert violations(outcome, seeded.outcome) == [f"undecided stop: {outcome.stopped}"]
    assert "leading or trailing whitespace" in outcome.stopped


def test_a_holds_operator_is_charged_only_for_its_own_scopes(seeded):
    def drop_registration(firm):
        firm.rows("entra_registration").pop(0)  # the first member's row
        return True
    edr_only = Operator("touches EDR only", "holds", drop_registration, scopes=frozenset({"edr.all_endpoints"}),
                        why="x")
    mfa = Operator("touches MFA", "holds", drop_registration, scopes=frozenset({"mfa.all_users"}), why="x")
    assert degraded(run(seeded.firm, (edr_only,)), seeded.outcome) == {}
    assert degraded(run(seeded.firm, (mfa,)), seeded.outcome) == {"touches MFA": {"unchecked"}}


FAKES = tuple(Operator(name, "inert", lambda firm: True) for name in "abcdefgh")


def test_combinations_are_the_same_for_the_same_seed_number():
    assert combinations(7, 20, catalog=FAKES) == combinations(7, 20, catalog=FAKES)
    assert combinations(7, 20, catalog=FAKES) != combinations(8, 20, catalog=FAKES)
    assert all(1 <= len(combo) <= 4 and len(set(combo)) == len(combo)
               for combo in combinations(7, 200, catalog=FAKES))


def test_shrinking_keeps_only_the_operators_the_failure_needs():
    a, b, c, d = FAKES[:4]
    assert shrink((a, b, c, d), lambda ops: b in ops and d in ops) == (b, d)
    assert shrink((a,), lambda ops: True) == (a,)
