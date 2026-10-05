from attest.profile import load_profile
from attest.rules import RULES


def test_every_rule_the_shipped_profile_names_exists():
    load_profile(rules=RULES)


def test_every_rule_is_named_by_the_profile():
    profile = load_profile()
    assert {rule for scopes in profile.values() for rule in scopes.values()} == set(RULES)
