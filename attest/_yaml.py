"""Reading the YAML files a run depends on, and the one rule for what counts as text in them.

Every problem with a file (missing, unreadable, not UTF-8, not YAML, a repeated key) stops the run as an
AttestError that names the file; none escapes as a raw Python exception.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Hashable
from pathlib import Path

import yaml

from attest.model import AttestError

_MERGE_TAG = "tag:yaml.org,2002:merge"


# The Hangul fillers are classed as letters (category Lo) yet render as blank, so a plain "is a letter" test
# would accept them; every other invisible character is whitespace or in a category other than L and N.
_BLANK_LETTERS = frozenset("ᅟᅠㅤﾠ")


def has_letter_or_digit(value: object) -> bool:
    """A string with at least one letter or digit (Unicode category L or N, not a blank Hangul filler).

    Whitespace, punctuation and every invisible character (byte-order mark, soft hyphen, zero-width space, variation
    selectors, braille blank, Hangul filler, ...) occur in nearly every document, so a value made only of them would
    "ground" while naming nothing."""
    return isinstance(value, str) and any(
        unicodedata.category(ch)[0] in "LN" and ch not in _BLANK_LETTERS for ch in value)


def has_invisible_edge(value: str) -> bool:
    """Whether the first or last character is whitespace or invisible (category Cf, or a blank Hangul filler)."""
    return any(ch.isspace() or unicodedata.category(ch) == "Cf" or ch in _BLANK_LETTERS
               for ch in value[:1] + value[-1:])


class _DuplicateKey(Exception):
    def __init__(self, key: object, line: int) -> None:
        super().__init__(key, line)
        self.key = key
        self.line = line


class _UniqueKeyLoader(yaml.SafeLoader):
    """A SafeLoader that refuses a mapping with a repeated key; plain safe_load silently keeps the last one."""

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for key_node, _ in node.value:
                if key_node.tag == _MERGE_TAG:  # '<<' is flattened by the base class, where explicit keys override
                    continue
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, Hashable):  # the base class reports an unhashable key
                    continue
                if key in seen:
                    raise _DuplicateKey(key, key_node.start_mark.line + 1)
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


def read_yaml(path: Path, label: str) -> object:
    """The parsed YAML in `path`, a file of the firm's or the product's own profile, named `label` in errors.

    A missing file is `<path> not found`; one that cannot be read, is not UTF-8 text, is not valid YAML, is nested
    too deeply, has an impossible date or repeats a mapping key is an AttestError beginning with `label`."""
    try:
        if not path.is_file():
            raise AttestError(f"{path} not found")
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except UnicodeDecodeError as e:
        raise AttestError(f"{label}: not UTF-8 text ({e.reason})") from e
    except _DuplicateKey as e:
        raise AttestError(f"{label}: duplicate key {e.key!r} at line {e.line}") from e
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark else ""
        raise AttestError(f"{label}: not valid YAML{where}") from e
    except ValueError as e:  # PyYAML's timestamp constructor: 2026-02-30 is a ValueError, not a YAMLError
        raise AttestError(f"{label}: contains an impossible date or value ({e})") from e
    except OSError as e:
        raise AttestError(f"{label}: could not be read ({e.strerror or e})") from e
    except RecursionError as e:
        raise AttestError(f"{label}: nested too deeply") from e
