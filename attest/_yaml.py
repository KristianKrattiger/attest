"""Reading a firm's YAML files so that a malformed one stops the run as an AttestError."""
from __future__ import annotations

from pathlib import Path

import yaml

from attest.model import AttestError


def read_yaml(path: Path, label: str) -> object:
    """The parsed YAML in `path`; text that is not UTF-8 or not YAML is an AttestError naming `label`."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as e:
        raise AttestError(f"{label}: not UTF-8 text ({e.reason})") from e
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark else ""
        raise AttestError(f"{label}: not valid YAML{where}") from e
    except ValueError as e:  # PyYAML's timestamp constructor: 2026-02-30 is a ValueError, not a YAMLError
        raise AttestError(f"{label}: contains an impossible date or value ({e})") from e
