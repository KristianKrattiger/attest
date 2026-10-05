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
from attest.report import TITLE, one_line, render

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
        _write_stub(args.firm, name, str(e))
        _emit(f"attest: {e}\n", sys.stderr)
        return 2
    except Exception as e:  # a bug: still no earlier verdicts left looking current, and the traceback still shows
        with contextlib.suppress(Exception):  # whatever fails here, the operator needs the original error
            _write_stub(args.firm, name, f"internal error: {type(e).__name__}: {e}")
        raise
    if not _write_report(args.firm, text):
        return 2
    _emit(text, sys.stdout)
    return 0


def _write_stub(folder: Path, name: str, why: str) -> None:
    """A run that could not check must not leave an earlier run's verdicts looking current: replace the report.

    Only the tool's own report is replaced (an existing report.md that begins with TITLE), and only a firm folder
    (one with a tags.yaml) gets a new one. Any other report.md, or a folder that is not a firm, is left alone: a typo
    in the path must not cost anyone an unrelated file."""
    report = folder / REPORT
    if os.path.lexists(report):
        replaceable = _begins_with_title(report)
    else:
        replaceable = (folder / "tags.yaml").is_file()
    if replaceable:
        _write_report(folder, f"{TITLE} {one_line(name)}\n\nCHECK FAILED: {one_line(why)}\n")


def _begins_with_title(path: Path) -> bool:
    """Whether the file starts with TITLE; one that cannot be read, or is not text, is not the tool's."""
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            return f.read(len(TITLE)) == TITLE
    except OSError:
        return False


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
