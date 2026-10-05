"""python -m attest check firm/<name>: write firm/<name>/report.md and print it."""
from __future__ import annotations

import argparse
import contextlib
import os
import sys
import uuid
from pathlib import Path

from attest.compare import check
from attest.model import AttestError
from attest.report import one_line, render

REPORT = "report.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="attest", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check_command = commands.add_parser("check", help="check a firm folder's attestations against its exports")
    check_command.add_argument("firm", type=Path)
    args = parser.parse_args(argv)
    name = args.firm.resolve().name
    try:
        text = render(name, check(args.firm))
    except AttestError as e:
        # A run that could not check must not leave an earlier run's verdicts looking current.
        if args.firm.is_dir():
            _write_report(args.firm, f"# Attestation check: {one_line(name)}\n\nCHECK FAILED: {one_line(str(e))}\n")
        _emit(f"attest: {e}\n", sys.stderr)
        return 2
    if not _write_report(args.firm, text):
        return 2
    _emit(text, sys.stdout)
    return 0


def _write_report(folder: Path, text: str) -> bool:
    """Replace folder/report.md with text, whole or not at all. On failure say why on stderr and return False."""
    temporary = folder / f".{REPORT}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temporary, "x", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, folder / REPORT)
    except OSError as e:
        _emit(f"attest: cannot write {REPORT}: {e.strerror or e}\n", sys.stderr)
        return False
    finally:
        with contextlib.suppress(OSError):
            temporary.unlink()  # still there only if the replace did not happen
    return True


def _emit(text: str, stream) -> None:
    """Write text to stream; characters its encoding cannot hold come out as replacement characters, not a crash."""
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        stream.write(text.encode(encoding, errors="replace").decode(encoding))


if __name__ == "__main__":
    raise SystemExit(main())
