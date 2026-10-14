"""Every operator, by area. A new real-world mess gets a new operator, not an edit to an old one."""
from messy import backup, edr, mfa

CATALOG = mfa.OPERATORS + edr.OPERATORS + backup.OPERATORS
BY_NAME = {op.name: op for op in CATALOG}
COMBINABLE = tuple(op for op in CATALOG if not op.known)  # a known false backed would fail every combination
