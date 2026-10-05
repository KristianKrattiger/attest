"""Shared types: a confirmed tag, one loaded export, and a verdict."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

Status = Literal["backed", "gap", "unchecked"]
T = TypeVar("T")


class AttestError(Exception):
    """An input problem that stops the run: a bad tag, a missing field, an unknown reader."""


@dataclass(frozen=True)
class Span:
    """The lines of its document a quote touches: the first and last line numbers (from 1), and those whole lines."""

    first: int
    last: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Tag:
    """One claim, confirmed by a reviewer: its words, where they are, and what they claim.

    `span` is set when the quote is grounded in its document; it is where the tag is, not what it is, so it takes
    no part in comparing tags.
    """

    id: str
    doc: str
    quote: str
    control: str
    scope: str
    span: Optional[Span] = field(default=None, compare=False)


@dataclass(frozen=True)
class Export(Generic[T]):
    """One export file's records, and when the firm took it."""

    file: str
    exported_at: datetime
    items: tuple[T, ...]


@dataclass(frozen=True)
class Verdict:
    """A rule's answer. `entities` names what failed; `cited` names the rows the verdict rests on."""

    status: Status
    reason: str
    entities: tuple[str, ...] = ()
    cited: tuple[str, ...] = ()
    population: Optional[str] = None
