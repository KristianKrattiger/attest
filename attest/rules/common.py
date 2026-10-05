"""Pieces every proof rule shares: the account population, the export-age check and the never-provable scopes."""
from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import timedelta
from typing import Optional

from attest.evidence import Evidence
from attest.model import Export, Verdict
from attest.readers.entra_users import User

Rule = Callable[[Evidence], Verdict]

# The most the exports one verdict reads may be apart (decision 4, 2026-10-05).
EXPORTS_APART = timedelta(hours=24)


def unchecked(reason: str) -> Verdict:
    return Verdict("unchecked", reason)


def not_counted(description: str, left_out: list[str]) -> str:
    """A population description followed by what it left out, if anything."""
    if not left_out:
        return description
    return description + "; not counted: " + "; ".join(left_out)


def member_accounts(users: Export[User], keep_disabled: Collection[str] = (),
                    kept_as: str = "") -> tuple[tuple[User, ...], str]:
    """Enabled accounts that are not guests, and a description naming what was left out.

    Only an explicit "Guest" leaves an enabled account out. A null userType is
    counted, because shrinking the population is the one way a rule could back
    too much. A disabled account whose UPN (case folded) is in keep_disabled is
    counted too, and the description names it after "plus <kept_as>:".
    """
    def member(u: User) -> bool:
        return u.enabled and u.user_type.lower() != "guest"

    def kept(u: User) -> bool:
        return not u.enabled and u.upn.lower() in keep_disabled

    counted = tuple(u for u in users.items if member(u) or kept(u))
    guests = [u.upn for u in users.items if u.enabled and not member(u)]
    disabled = [u.upn for u in users.items if not u.enabled and not kept(u)]
    plus = [u.upn for u in users.items if kept(u)]
    description = f"{len(counted) - len(plus)} enabled member accounts from {users.file}"
    if plus:
        description += f"; plus {kept_as}: " + ", ".join(plus)
    left_out = []
    if guests:
        left_out.append("guests " + ", ".join(guests))
    if disabled:
        left_out.append("disabled " + ", ".join(disabled))
    return counted, not_counted(description, left_out)


def exports_apart(*exports: Export) -> Optional[Verdict]:
    """Unchecked when the exports a verdict reads were taken more than EXPORTS_APART apart; None when they were not.

    Exports taken far apart can describe different firms: an account list from
    January checked against an October backup report would miss every account
    added since. Each rule passes the exports it actually read, after its
    missing-export checks and before any other verdict.
    """
    earliest = min(exports, key=lambda e: e.exported_at)
    latest = max(exports, key=lambda e: e.exported_at)
    if latest.exported_at - earliest.exported_at <= EXPORTS_APART:
        return None
    return unchecked(f"exports taken more than {EXPORTS_APART // timedelta(hours=1)} hours apart: "
                     f"{earliest.file} at {earliest.exported_at.isoformat()}, "
                     f"{latest.file} at {latest.exported_at.isoformat()}")


def never(reason: str) -> Rule:
    """A scope no export in this stack can prove: unchecked, whatever was exported."""
    def rule(evidence: Evidence) -> Verdict:
        return unchecked(reason)
    return rule
