#!/usr/bin/env python3
"""Copy a raw lab capture into firm/lab with everything that names the tenant or its owner replaced.

The replacement is made on the text, so each file keeps its encoding, byte-order mark and line endings: they are
part of what a PowerShell 5.1 or 7 capture shows. A file that is not UTF-8 or UTF-16 text is refused, by name.

Every file is scrubbed in one pass, so a replacement is never rewritten by a later rule. Replaced: every
<label>.onmicrosoft.com, <label>.mail.onmicrosoft.com and .onmicrosoft.us domain, and each --domain, with
harborlab.example; the tenant label itself, learned from those domains in every file of the capture before anything
is replaced, wherever it stands as a DNS label (contosolab.sharepoint.com, contosolab-admin.sharepoint.com), with
harborlab; and the --tenant-id. The owner, from --admin-name and --admin-address, is replaced in every form Graph
writes: the full name (to "Lab Admin"), "Surname, Given" (to "Admin, Lab"), each name part of three or more characters
(the given names to "Lab", the surname to "Admin"), the dotted lower-case form such as pat.example, the address and
its local part (to lab.admin). Each --also VALUE, a repeatable option for anything else the owner spots, such as a
phone number or a device name, is replaced with "redacted" and denied. Names, name parts, the local part and the
tenant label are replaced as whole words only, in any case, so replacing "Pat" leaves "Patch" alone; the tenant ID,
each --domain and each --also value are replaced wherever they stand.

Every IPv4 and IPv6 address is replaced wherever it stands in the text, including before a sentence's full stop and
inside a CIDR range, a URL or key=value text. Each candidate is checked with the ipaddress module, so a time, a MAC
address, a GUID or a version string is left alone. The Nth distinct address becomes a documentation address: for IPv4
192.0.2.1 to 254, then 198.51.100.1 to 254, then 203.0.113.1 to 254 (a capture with more is refused), and for IPv6
2001:db8::N. Two spellings of one IPv6 address become one. Random object GUIDs are kept: they identify nothing
outside the lab.

The values replaced are added to firm/lab/raw/deny.txt, which is gitignored with the rest of raw/ and which the
guard test (tests/messy/test_lab_guard.py) reads. The scrubbed copy is written to a staging folder beside the output
and moved into place only when every file was scrubbed and none still holds anything that could name the tenant or its
owner: an onmicrosoft.com domain, a public IP address, or a value deny.txt lists. Otherwise the staging folder is
removed, so the output never holds a partial copy. Exit status: 0 written, 1 refused, 2 the output already exists.

Run from the repo root:
  python scripts/scrub_lab_capture.py firm/lab/raw/seed-clean firm/lab/seed-clean \\
      --tenant-id <tenant GUID> --admin-name "<your name>" --admin-address <your sign-up address> \\
      [--domain <custom domain>] [--also <anything else to replace>]
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import re
import shutil
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENY = ROOT / "firm" / "lab" / "raw" / "deny.txt"
LAB_DOMAIN = "harborlab.example"
LAB_LABEL = "harborlab"
LAB_TENANT_ID = "11111111-1111-4111-8111-111111111111"
CAPTURE_FILES = {".json", ".yaml"}
BOMS = ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"), (b"\xef\xbb\xbf", "utf-8"))
DOCUMENTATION_V4 = ("192.0.2", "198.51.100", "203.0.113")
DOCUMENTATION_V6 = ipaddress.IPv6Address("2001:db8::")


def _starts(characters: str) -> str:
    return rf"(?<!%)(?<!%[0-9A-Fa-f])(?:(?<![{characters}])|(?<=%[0-9A-Fa-f]{{2}}))"


# A whole word has no letter or digit just before or after it. A percent-encoded character before it (%40 for an
# at sign, %20 for a space) counts as a break, and a word never starts inside one. A domain label may hold hyphens,
# so it starts where the whole run of letters, digits and hyphens does, which also keeps the search linear.
WORD_START = _starts("A-Za-z0-9")
WORD_END = r"(?![A-Za-z0-9])"
DOMAIN = r"[A-Za-z0-9-]+(?:\.mail)?\.onmicrosoft\.(?:com|us)"
ONMICROSOFT = _starts("A-Za-z0-9-") + DOMAIN
LABEL = re.compile(_starts("A-Za-z0-9-") + r"([A-Za-z0-9-]+)(?:\.mail)?\.onmicrosoft\.(?:com|us)", re.IGNORECASE)
ANY_ONMICROSOFT = re.compile(r"(?<![A-Za-z0-9-])[A-Za-z0-9-]+(?:\.mail)?\.onmicrosoft\.(com|us)", re.IGNORECASE)
# What the scrubber itself writes; the guard does not count it as a denied value (a surname "Example" is not found in
# harborlab.example, nor an address "admin@..." in lab.admin).
OWN = re.compile(WORD_START + r"(?:harborlab(?:\.example)?|lab\.admin|lab|admin|redacted)" + WORD_END, re.IGNORECASE)
HEX = re.compile(r"[0-9A-Fa-f]")
IPV4 = re.compile(r"(?<!\d)(?<!\d\.)\d{1,3}(?:\.\d{1,3}){3}(?!\d)(?!\.\d)")
IPV6_RUN = re.compile(r"[0-9A-Fa-f:.]+")


class Refused(ValueError):
    """The capture cannot be scrubbed safely."""


class NotText(ValueError):
    """The bytes are not UTF-8 or UTF-16 text."""


def _ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _word(value: str) -> str:
    """A regular expression for this value standing as a whole word."""
    return WORD_START + re.escape(value) + WORD_END


def _spaced(tokens: Sequence[str]) -> str:
    """A regular expression for these words with any white space between them."""
    return r"\s+".join(re.escape(token) for token in tokens)


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) else None
    return ip.is_global or (mapped is not None and mapped.is_global)


def _address_in(run: str) -> tuple[int, int, ipaddress.IPv6Address] | None:
    """The IPv6 address in a run of hex digits, colons and dots, once sentence punctuation around it is trimmed."""
    lead = len(run) - len(run.lstrip(".:"))
    trail = len(run) - len(run.rstrip(".:"))
    cuts = sorted(((a, b) for a in range(min(lead, 3) + 1) for b in range(min(trail, 3) + 1)), key=sum)
    for a, b in cuts:
        piece = run[a:len(run) - b]
        if ":" in piece and HEX.search(piece) and isinstance(ip := _ip(piece), ipaddress.IPv6Address):
            return a, len(run) - b, ip
    return None


def _spans(text: str) -> list[tuple[int, int, ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    """Every valid address in the text, in order: where it starts and ends, and what it is."""
    found = []
    for run in IPV6_RUN.finditer(text):
        if ":" in run.group() and (hit := _address_in(run.group())) is not None:
            found.append((run.start() + hit[0], run.start() + hit[1], hit[2]))
    found += [(m.start(), m.end(), ip) for m in IPV4.finditer(text) if (ip := _ip(m.group())) is not None]
    spans, end = [], 0
    for span in sorted(found, key=lambda s: (s[0], -s[1])):
        if span[0] >= end:  # an IPv4 address inside an IPv6 one (::ffff:1.2.3.4) is part of it
            spans.append(span)
            end = span[1]
    return spans


def decode(raw: bytes) -> tuple[str, str, bytes]:
    """The text, the codec to write it back with, and the byte-order mark that went before it."""
    body, codec, mark = raw, "utf-8", b""
    for bom, bom_codec in BOMS:
        if raw.startswith(bom):
            body, codec, mark = raw[len(bom):], bom_codec, bom
            break
    try:
        text = body.decode(codec)
    except UnicodeDecodeError as error:
        raise NotText("not UTF-8 or UTF-16 text") from error
    if "\0" in text:  # UTF-16 without a byte-order mark, or a binary file, reads as NULs
        raise NotText("not UTF-8 or UTF-16 text")
    return text, codec, mark


class Scrubber:
    """Replaces what names the tenant or its owner; one address always becomes the same documentation address."""

    def __init__(self, tenant_id: str, admin_name: str, admin_address: str, domains: Sequence[str] = (),
                 also: Sequence[str] = ()):
        parts = admin_name.split()
        given, surname = parts[:-1], parts[-1:]
        local = admin_address.partition("@")[0] if "@" in admin_address else ""
        names = [part for part in dict.fromkeys(parts) if len(part) >= 3] if len(parts) > 1 else []
        surname_first = f"{surname[0]}, {' '.join(given)}" if given else ""
        dotted = ".".join(parts).lower() if len(parts) > 1 else ""
        self._denied = [v for v in (tenant_id, admin_name, admin_address, local, *names, surname_first, dotted,
                                    *domains, *also) if v]
        self._head = [(_word(admin_address), f"lab.admin@{LAB_DOMAIN}")] if admin_address else []
        self._head += [(re.escape(tenant_id), LAB_TENANT_ID)] if tenant_id else []
        self._head += [(re.escape(value), "redacted") for value in also if value]
        self._head += [(re.escape(domain), LAB_DOMAIN) for domain in domains if domain]
        if given:
            self._head.append((WORD_START + re.escape(surname[0]) + r"\s*,\s*" + _spaced(given) + WORD_END,
                               "Admin, Lab"))
        if parts:
            self._head.append((WORD_START + _spaced(parts) + WORD_END, "Lab Admin"))
        if dotted:
            self._head.append((WORD_START + r"\.".join(re.escape(p) for p in parts) + WORD_END, "lab.admin"))
        if local:  # as written, the local part is the alias, even where it is also the given name
            self._head.append((f"(?-i:{_word(local)})", "lab.admin"))
        self._head.append((ONMICROSOFT, LAB_DOMAIN))
        self._tail = [(_word(part), "Lab" if part in given else "Admin") for part in names]
        self._tail += [(_word(local), "lab.admin")] if local else []
        self.labels: list[str] = []
        self.addresses: dict[ipaddress.IPv4Address | ipaddress.IPv6Address, str] = {}
        self._compiled: re.Pattern[str] | None = None
        self._replacement: dict[str, str] = {}

    @property
    def denied(self) -> list[str]:
        return list(dict.fromkeys([*self._denied, *self.labels]))

    def learn(self, text: str) -> None:
        """Note the tenant label of every onmicrosoft domain in this text."""
        for found in LABEL.finditer(text):
            label = found.group(1).strip("-")
            if label and label.lower() not in {known.lower() for known in self.labels}:
                self.labels.append(label)
                self._compiled = None

    def scrub(self, text: str) -> str:
        self.learn(text)
        if self._compiled is None:
            labels = [(_word(label), LAB_LABEL) for label in sorted(self.labels, key=len, reverse=True)]
            rules = [*self._head, *labels, *self._tail]
            self._replacement = {f"r{i}": new for i, (_, new) in enumerate(rules)}
            alternatives = "|".join(f"(?P<r{i}>{old})" for i, (old, _) in enumerate(rules))
            self._compiled = re.compile(alternatives, re.IGNORECASE)
        text = self._compiled.sub(lambda m: self._replacement[m.lastgroup], text)
        clean, last = [], 0
        for start, end, ip in _spans(text):
            clean += [text[last:start], self._documentation(ip)]
            last = end
        return "".join(clean) + text[last:]

    def _documentation(self, ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
        if ip not in self.addresses:
            ordinal = len(self.addresses)
            if isinstance(ip, ipaddress.IPv6Address):
                self.addresses[ip] = str(DOCUMENTATION_V6 + ordinal + 1)
            else:
                pool, host = divmod(ordinal, 254)
                if pool >= len(DOCUMENTATION_V4):
                    raise Refused(f"more than {254 * len(DOCUMENTATION_V4)} distinct addresses: "
                                  "the documentation ranges are used up")
                self.addresses[ip] = f"{DOCUMENTATION_V4[pool]}.{host + 1}"
        return self.addresses[ip]


def leaks(text: str, deny: Iterable[str] = ()) -> list[str]:
    """What in this text could name the tenant or its owner."""
    found = [f"an onmicrosoft.{tld} domain" for tld in dict.fromkeys(m.group(1).lower()
                                                                      for m in ANY_ONMICROSOFT.finditer(text))]
    found += dict.fromkeys(f"public IP address {text[start:end]}" for start, end, ip in _spans(text) if _is_public(ip))
    theirs = OWN.sub("\0", text)
    return found + [f"denied value {v!r}" for v in deny if v and re.search(_word(v), theirs, re.IGNORECASE)]


def read_deny(path: Path = DENY) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line] if path.exists() else []


def committed_leaks(folder: Path, deny: Iterable[str] = ()) -> list[str]:
    """What under this folder could name the tenant or its owner, as "relative/path: leak"; a top-level raw/ is skipped.

    A file whose name leaks is reported too, and so is a file that is not UTF-8 or UTF-16 text, which cannot be checked.
    """
    deny = list(deny)
    files = []
    for current, folders, names in os.walk(folder):
        if Path(current) == folder:
            folders[:] = [name for name in folders if name != "raw"]
        files += [Path(current) / name for name in names]
    problems = []
    for path in sorted(files):
        name = path.relative_to(folder).as_posix()
        problems += [f"{name}: in its name, {leak}" for leak in leaks(name, deny)]
        try:
            text = decode(path.read_bytes())[0]
        except NotText as error:
            problems.append(f"{name}: {error}")
            continue
        problems += [f"{name}: {leak}" for leak in leaks(text, deny)]
    return problems


def scrub_capture(raw: Path, out: Path, scrubber: Scrubber, deny_file: Path = DENY) -> list[str]:
    """Write the scrubbed copy of raw to out and record the denied values; the problems, when the copy is refused."""
    if not raw.is_dir():
        return [f"{raw} is not an existing folder"]
    files = sorted(p for p in raw.rglob("*") if p.is_file())
    if not files:
        return [f"{raw} holds no files"]
    problems, captured = [], {}
    for src in files:
        name = src.relative_to(raw).as_posix()
        try:
            captured[name] = decode(src.read_bytes())
        except NotText as error:
            problems.append(f"{name}: {error}")
            continue
        if src.suffix.lower() not in CAPTURE_FILES:
            problems.append(f"{name}: not an export or a manifest")
    if problems:
        return problems
    for text, _, _ in captured.values():
        scrubber.learn(text)  # the label may stand in one file and be learned from another
    deny = sorted(set(read_deny(deny_file)) | set(scrubber.denied))
    deny_file.parent.mkdir(parents=True, exist_ok=True)
    deny_file.write_text("".join(f"{v}\n" for v in deny), encoding="utf-8")
    staging = out.parent / f".{out.name}.scrubbing"
    shutil.rmtree(staging, ignore_errors=True)  # left behind by a run that was killed
    try:
        for name, (text, codec, bom) in captured.items():
            problems += [f"{name}: in its name, {leak}" for leak in leaks(name, deny)]
            try:
                clean = scrubber.scrub(text)
            except Refused as error:
                problems.append(f"{name}: {error}")
                break
            problems += [f"{name}: {leak}" for leak in leaks(clean, deny)]
            dst = staging / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(bom + clean.encode(codec))
        if not problems:
            if out.exists():
                raise FileExistsError(f"{out} already exists")
            staging.replace(out)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return problems


def main(argv: list[str] | None = None, deny_file: Path = DENY) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("raw", type=Path, help="the raw capture folder, under firm/lab/raw/")
    parser.add_argument("out", type=Path, help="the folder to write, under firm/lab/")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--admin-name", required=True)
    parser.add_argument("--admin-address", required=True)
    parser.add_argument("--domain", action="append", default=[], help="a custom domain the tenant uses")
    parser.add_argument("--also", action="append", default=[], metavar="VALUE",
                        help="anything else to replace with 'redacted' and deny; repeat for each value")
    args = parser.parse_args(argv)
    if args.out.exists():
        print(f"{args.out} already exists; remove it first", file=sys.stderr)
        return 2
    scrubber = Scrubber(args.tenant_id, args.admin_name, args.admin_address, tuple(args.domain), tuple(args.also))
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
