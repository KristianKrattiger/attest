#!/usr/bin/env python3
"""Copy a raw lab capture into firm/lab with everything that names the tenant or its owner replaced.

The replacement is made on the text, so each file keeps its encoding, byte-order mark and line endings: they are
part of what a PowerShell 5.1 or 7 capture shows. Replaced: every *.onmicrosoft.com domain and each --domain, the
--tenant-id, the --admin-name and --admin-address, every IPv4 address (to 192.0.2.N), and every JSON string that is
an IPv6 address (to 2001:db8::N). Random object GUIDs are kept: they identify nothing outside the lab.

The values replaced are added to firm/lab/raw/deny.txt, which is gitignored with the rest of raw/ and which the
guard test (tests/messy/test_lab_guard.py) reads. The copy is refused, and removed, if anything in it could still
name the tenant or its owner: an onmicrosoft.com domain, a public IP address, or a value deny.txt lists.

Run from the repo root:
  python scripts/scrub_lab_capture.py firm/lab/raw/seed-clean firm/lab/seed-clean \\
      --tenant-id <tenant GUID> --admin-name "<your name>" --admin-address <your sign-up address>
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DENY = ROOT / "firm" / "lab" / "raw" / "deny.txt"
LAB_DOMAIN = "harborlab.example"
LAB_TENANT_ID = "11111111-1111-4111-8111-111111111111"
CAPTURE_FILES = {".json", ".yaml"}
ONMICROSOFT = re.compile(r"[A-Za-z0-9-]+(?:\.mail)?\.onmicrosoft\.com", re.IGNORECASE)
IPV4 = re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])")
IPV6_STRING = re.compile(r'"([0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7})"')
BOMS = ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"), (b"\xef\xbb\xbf", "utf-8"))


def _ip(value: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def decode(raw: bytes) -> tuple[str, str, bytes]:
    """The text, the codec to write it back with, and the byte-order mark that went before it."""
    for bom, codec in BOMS:
        if raw.startswith(bom):
            return raw[len(bom):].decode(codec), codec, bom
    return raw.decode("utf-8"), "utf-8", b""


class Scrubber:
    """Replaces what names the tenant or its owner; one address always becomes the same documentation address."""

    def __init__(self, tenant_id: str, admin_name: str, admin_address: str, domains: tuple[str, ...] = ()):
        self.replacements = [(admin_address, f"lab.admin@{LAB_DOMAIN}"), (admin_name, "Lab Admin"),
                             (tenant_id, LAB_TENANT_ID), *((d, LAB_DOMAIN) for d in domains)]
        self.addresses: dict[str, str] = {}

    @property
    def denied(self) -> list[str]:
        return [old for old, _ in self.replacements if old]

    def scrub(self, text: str) -> str:
        for old, new in self.replacements:
            if old:
                text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
        text = ONMICROSOFT.sub(LAB_DOMAIN, text)
        text = IPV4.sub(lambda m: self._address(m.group(), "192.0.2.{}"), text)
        return IPV6_STRING.sub(lambda m: '"' + self._address(m.group(1), "2001:db8::{:x}") + '"', text)

    def _address(self, value: str, form: str) -> str:
        if _ip(value) is None:
            return value  # a version number or a time, not an address
        return self.addresses.setdefault(value, form.format(len(self.addresses) % 254 + 1))


def leaks(text: str, deny: list[str] | tuple[str, ...] = ()) -> list[str]:
    """What in this text could name the tenant or its owner."""
    found = ["an onmicrosoft.com domain"] if ONMICROSOFT.search(text) else []
    found += [f"public IP address {v}" for v in IPV4.findall(text) + IPV6_STRING.findall(text)
              if (ip := _ip(v)) is not None and ip.is_global]
    lowered = text.lower()
    return found + [f"denied value {v!r}" for v in deny if v and v.lower() in lowered]


def read_deny(path: Path = DENY) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line] if path.exists() else []


def scrub_capture(raw: Path, out: Path, scrubber: Scrubber, deny_file: Path = DENY) -> list[str]:
    """Write the scrubbed copy of raw to out and record the denied values; the problems, when the copy is refused."""
    deny = sorted(set(read_deny(deny_file)) | set(scrubber.denied))
    deny_file.parent.mkdir(parents=True, exist_ok=True)
    deny_file.write_text("".join(f"{v}\n" for v in deny), encoding="utf-8")
    problems = []
    for src in sorted(p for p in raw.rglob("*") if p.is_file()):
        name = src.relative_to(raw).as_posix()
        if src.suffix.lower() not in CAPTURE_FILES:
            problems.append(f"{name}: not an export or a manifest")
            continue
        text, codec, bom = decode(src.read_bytes())
        clean = scrubber.scrub(text)
        problems += [f"{name}: {leak}" for leak in leaks(clean, deny)]
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(bom + clean.encode(codec))
    if problems:
        shutil.rmtree(out, ignore_errors=True)
    return problems


def main(argv: list[str] | None = None, deny_file: Path = DENY) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("raw", type=Path, help="the raw capture folder, under firm/lab/raw/")
    parser.add_argument("out", type=Path, help="the folder to write, under firm/lab/")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--admin-name", required=True)
    parser.add_argument("--admin-address", required=True)
    parser.add_argument("--domain", action="append", default=[], help="a custom domain the tenant uses")
    args = parser.parse_args(argv)
    if args.out.exists():
        print(f"{args.out} already exists; remove it first", file=sys.stderr)
        return 2
    scrubber = Scrubber(args.tenant_id, args.admin_name, args.admin_address, tuple(args.domain))
    problems = scrub_capture(args.raw, args.out, scrubber, deny_file)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"refused: nothing written to {args.out}", file=sys.stderr)
        return 1
    print(f"scrubbed {args.raw} into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
