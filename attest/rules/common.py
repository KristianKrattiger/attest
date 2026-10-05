"""Pieces every proof rule shares: the account population and the never-provable scopes."""
from __future__ import annotations

from collections.abc import Callable

from attest.evidence import Evidence
from attest.model import Export, Verdict
from attest.readers.entra_users import User

Rule = Callable[[Evidence], Verdict]


def unchecked(reason: str) -> Verdict:
    return Verdict("unchecked", reason)


def member_accounts(users: Export[User]) -> tuple[tuple[User, ...], str]:
    """Enabled accounts that are not guests, and a description naming what was left out.

    Only an explicit "Guest" leaves an enabled account out. A null userType is
    counted, because shrinking the population is the one way a rule could back
    too much.
    """
    counted = tuple(u for u in users.items if u.enabled and u.user_type.lower() != "guest")
    guests = [u.upn for u in users.items if u.enabled and u.user_type.lower() == "guest"]
    disabled = [u.upn for u in users.items if not u.enabled]
    description = f"{len(counted)} enabled member accounts from {users.file}"
    left_out = []
    if guests:
        left_out.append("guests " + ", ".join(guests))
    if disabled:
        left_out.append("disabled " + ", ".join(disabled))
    if left_out:
        description += "; not counted: " + "; ".join(left_out)
    return counted, description


def never(reason: str) -> Rule:
    """A scope no export in this stack can prove: unchecked, whatever was exported."""
    def rule(evidence: Evidence) -> Verdict:
        return unchecked(reason)
    return rule
