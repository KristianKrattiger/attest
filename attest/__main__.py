"""python -m attest check firm/<name>: print the report and write firm/<name>/report.md."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from attest.compare import check
from attest.model import AttestError
from attest.report import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="attest", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check_command = commands.add_parser("check", help="check a firm folder's attestations against its exports")
    check_command.add_argument("firm", type=Path)
    args = parser.parse_args(argv)
    try:
        results = check(args.firm)
    except AttestError as e:
        print(f"attest: {e}", file=sys.stderr)
        return 2
    text = render(args.firm.name, results)
    print(text, end="")
    (args.firm / "report.md").write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
