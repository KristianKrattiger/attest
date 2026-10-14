from typing import NamedTuple

import pytest

from messy.compose import Outcome, run
from messy.firm import Firm, seed


class Seeded(NamedTuple):
    name: str  # "seed-clean" once the real capture is committed, else "dev"
    firm: Firm
    outcome: Outcome  # the check on the seed with no operator applied


@pytest.fixture(scope="session")
def seeded() -> Seeded:
    name, firm = seed()
    return Seeded(name, firm, run(firm, ()))
