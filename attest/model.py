"""Shared types: a confirmed tag, one loaded export, and a verdict."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

Status = Literal["backed", "gap", "unchecked"]
T = TypeVar("T")


class AttestError(Exception):
    """An input problem that stops the run: a bad tag, a missing field, an unknown reader."""


@dataclass(frozen=True)
class Tag:
    """One attestation, confirmed by a reviewer: its words, where they are, and what they claim."""

    id: str
    doc: str
    quote: str
    control: str
    scope: str


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
