#!/usr/bin/env python3
"""Copy a raw lab capture into firm/lab with everything that names the tenant or its owner replaced.

The replacement is made on the text, so each file keeps its encoding, byte-order mark and line endings: they are
part of what a PowerShell 5.1 or 7 capture shows. A file that is not UTF-8 or UTF-16 text is refused, by name.

Every file is scrubbed in one pass, so a replacement is never rewritten by a later rule. Replaced: every
<label>.onmicrosoft.com, <label>.mail.onmicrosoft.com and .onmicrosoft.us domain, and each --domain, with
harborlab.example; the tenant label itself, learned from those domains in every file of the capture before anything
is replaced, with harborlab; and the --tenant-id. The label is replaced as a whole word wherever it stands, not only as
a DNS label (contosolab.sharepoint.com, contosolab-admin.sharepoint.com, but also a URL path or a display name). The
owner, from --admin-name and --admin-address, is replaced in every form Graph writes: the full name (to "Lab Admin"),
"Surname, Given" (to "Admin, Lab"), each name part of three or more characters (the given names to "Lab", the surname
to "Admin"), the dotted lower-case form such as pat.example, the address and its local part (to lab.admin), and the
owner's user name in the tenant, from the required --admin-user, to lab.admin too (a whole UPN may be passed: only the
part before the @ is kept). Each --also VALUE, a repeatable option for anything else the owner spots, such as a phone
number or a device name, is replaced with "redacted" and denied. Names, name parts, the local part, the user name and
the tenant label are replaced as whole words only, in any case, so replacing "Pat" leaves "Patch" alone and a user name
"admin" leaves isAdmin alone; the tenant ID, each --domain and each --also value are replaced wherever they stand,
inside other words too.

The value after "$skiptoken=" (any case, also as %24skiptoken=), up to the next "&", quote, backslash or white space,
is replaced with REDACTED: Graph builds the token of a paged export's @odata.nextLink from the last record's user
principal name, base64-encoded, so it names the tenant and the reader needs only the link to be there.

Every IPv4 and IPv6 address is replaced wherever it stands in the text, including before a sentence's full stop and
inside a CIDR range, a URL or key=value text. Each candidate is checked with the ipaddress module, so a time, a MAC
address, a GUID, a version string with a part over 255 or of more than three digits, and a word such as Cache::get or
std::string are left alone. Anything else that is a valid address is replaced even when it is not one, which can only
over-scrub: a four-part version whose parts are all at most 255 (5.0.5.0), or an eight-octet identifier such as
00:1A:2B:FF:FE:3C:4D:5E. The Nth distinct address becomes a documentation address: for IPv4 192.0.2.1 to 254, then
198.51.100.1 to 254, then 203.0.113.1 to 254 (a capture with more is refused), and for IPv6 2001:db8::N. Two spellings
of one IPv6 address become one. Random object GUIDs are kept: they identify nothing outside the lab.

The values replaced are added to firm/lab/raw/deny.txt, which is gitignored with the rest of raw/ and which the
guard test (tests/messy/test_lab_guard.py) reads. The scrubbed copy is written to a staging folder beside the output
and moved into place only when every file was scrubbed and none still holds anything that could name the tenant or its
owner: an onmicrosoft.com domain, a public IP address, or a value deny.txt lists as a whole word, unless the value lies
wholly inside a word the scrubber itself wrote (the surname "Example" in harborlab.example). Otherwise the staging
folder is removed, so the output never holds a partial copy. Exit status: 0 written, 1 refused, 2 the output
already exists.

The guard looks further than the scrubber does. It reads inside base64: every run of 24 or more base64 characters
(either alphabet, padding optional, percent-escapes undone) is decoded and checked for an onmicrosoft domain and for
a public IP address written with three numbers or more, which binary does not hold by chance. A run that decodes to
mostly printable text is checked for any public address and for the denied values too. A hit is reported with
"(inside base64)". And its net for an IPv6 address is looser: one glued to a letter or an underscore
(addr2606:4700::1111) or to a percent-escape is reported, though the scrubber leaves it, so the capture is refused for
the owner to look at; passed with --also as the refusal names it, the address is replaced.

Run from the repo root:
  python scripts/scrub_lab_capture.py firm/lab/raw/seed-clean firm/lab/seed-clean \\
      --tenant-id <tenant GUID> --admin-name "<your name>" --admin-address <your sign-up address> \\
      --admin-user <your UPN user name> [--domain <custom domain>] [--also <anything else to replace>]
"""
from __future__ import annotations

import argparse
import base64
import bisect
import ipaddress
import os
import re
import shutil
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from urllib.parse import unquote

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
# What the scrubber itself writes. A denied value found entirely inside one of these is not a leak (a surname "Example"
# in harborlab.example, an address local part "admin" in lab.admin); one that reaches beyond it is (lab.example).
OWN = re.compile(WORD_START + r"(?:harborlab(?:\.example)?|lab\.admin|lab|admin|redacted)" + WORD_END, re.IGNORECASE)
HEX = re.compile(r"[0-9A-Fa-f]")
NUMBERS = re.compile(r"[0-9A-Fa-f]+")  # the groups of an address as written, and the parts of an IPv4 address in it
GLUED = re.compile(r"[G-Zg-z_]")
IPV4 = re.compile(r"(?<!\d)(?<!\d\.)\d{1,3}(?:\.\d{1,3}){3}(?!\d)(?!\.\d)")
IPV6_RUN = re.compile(r"[0-9A-Fa-f:.]+")
# The value of a paged export's token: Graph builds it from the last record's user principal name. It runs to the next
# "&", quote, backslash (an escaped quote) or white space, and the equals sign before it stays where it is.
SKIPTOKEN = r'(?:(?<=\$skiptoken=)|(?<=%24skiptoken=))[^&"\\\s]+'
SKIPTOKEN_PLACEHOLDER = "REDACTED"
BASE64_MIN = 24
BASE64_RUN = re.compile(rf"[A-Za-z0-9+/_=-]{{{BASE64_MIN},}}")
BASE64_PRINTABLE = 0.75  # the share of a decoded token's bytes that must be printable for a denied value in it to count


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


def user_name(value: str) -> str:
    """The user name in what was passed as one: white space around it dropped, and only the part before an @."""
    return value.strip().partition("@")[0]


def _spaced(tokens: Sequence[str]) -> str:
    """A regular expression for these words with any white space between them."""
    return r"\s+".join(re.escape(token) for token in tokens)


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) else None
    return ip.is_global or (mapped is not None and mapped.is_global)


def _address_in(run: str, before: str = "", after: str = "") -> tuple[int, int, ipaddress.IPv6Address] | None:
    """The IPv6 address in a run of hex digits, colons and dots, once sentence punctuation around it is trimmed.

    The characters just before and after the run are given too. An address glued to a letter outside a to f or to an
    underscore is part of a word (Cache::get, std::string), not an address, unless a one-character label such as the 6
    of ip6: or IPv6: comes first, in which case the address starts after that label.
    """
    lead = len(run) - len(run.lstrip(".:"))
    trail = len(run) - len(run.rstrip(".:"))
    cuts = sorted(((a, b) for a in range(min(lead, 3) + 1) for b in range(min(trail, 3) + 1)), key=sum)
    for a, b in cuts:
        piece = run[a:len(run) - b]
        left, right = (run[a - 1] if a else before), (run[len(run) - b] if b else after)
        if GLUED.match(left) or GLUED.match(right):
            continue
        if ":" in piece and HEX.search(piece) and isinstance(ip := _ip(piece), ipaddress.IPv6Address):
            return a, len(run) - b, ip
    if len(run) > 2 and run[1] == ":" and HEX.match(run[0]) and GLUED.match(before):
        hit = _address_in(run[2:], ":", after)
        return None if hit is None else (hit[0] + 2, hit[1] + 2, hit[2])
    return None


def _glued_address_in(run: str) -> tuple[int, int, ipaddress.IPv6Address] | None:
    """The IPv6 address in a run of at least three groups that _address_in refused for what stands against it.

    This is the guard's net. A letter or an underscore against the run is ignored (addr2606:4700::1111,
    ip_2606:4700::1111), and so are up to two leading hex characters (ip62606:4700::1111, or the 20 of a %20 before the
    address).
    """
    if sum(1 for group in run.split(":") if group) < 3:
        return None
    for dropped in range(3):
        if (hit := _address_in(run[dropped:])) is not None:
            return hit[0] + dropped, hit[1] + dropped, hit[2]
    return None


def _spans(text: str, loose: bool = False) -> list[tuple[int, int, ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    """Every valid address in the text, in order: where it starts and ends, and what it is.

    With `loose`, an IPv6 address that a word is glued to counts too (_glued_address_in); the scrubber does not ask.
    """
    found = []
    for run in IPV6_RUN.finditer(text):
        if ":" not in run.group():
            continue
        before = text[run.start() - 1] if run.start() else ""
        after = text[run.end()] if run.end() < len(text) else ""
        hit = _address_in(run.group(), before, after)
        if hit is None and loose:
            hit = _glued_address_in(run.group())
        if hit is not None:
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
                 also: Sequence[str] = (), admin_user: str = ""):
        parts = admin_name.split()
        given, surname = parts[:-1], parts[-1:]
        local = admin_address.partition("@")[0] if "@" in admin_address else ""
        aliases = [alias for alias in dict.fromkeys((local, user_name(admin_user))) if alias]
        names = [part for part in dict.fromkeys(parts) if len(part) >= 3] if len(parts) > 1 else []
        surname_first = f"{surname[0]}, {' '.join(given)}" if given else ""
        dotted = ".".join(parts).lower() if len(parts) > 1 else ""
        self._denied = [v for v in (tenant_id, admin_name, admin_address, *aliases, *names, surname_first, dotted,
                                    *domains, *also) if v]
        self._head = [(SKIPTOKEN, SKIPTOKEN_PLACEHOLDER)]
        self._head += [(_word(admin_address), f"lab.admin@{LAB_DOMAIN}")] if admin_address else []
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
        # As written, the local part and the user name are the alias, even where one is also the given name.
        self._head += [(f"(?-i:{_word(alias)})", "lab.admin") for alias in aliases]
        self._head.append((ONMICROSOFT, LAB_DOMAIN))
        self._tail = [(_word(part), "Lab" if part in given else "Admin") for part in names]
        self._tail += [(_word(alias), "lab.admin") for alias in aliases]
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


def _stands_outside(value: str, text: str, spans: Sequence[tuple[int, int]]) -> bool:
    """Whether the value stands as a whole word somewhere other than wholly inside one of these spans of the text.

    The spans are in order and do not overlap, so the only one that can hold a match is the last to start at or
    before it.
    """
    starts = [a for a, _ in spans]
    for m in re.finditer(_word(value), text, re.IGNORECASE):
        i = bisect.bisect_right(starts, m.start()) - 1
        if i < 0 or spans[i][1] < m.end():
            return True
    return False


def _decoded(token: str) -> tuple[str, bool] | None:
    """The text a base64 token holds, in either alphabet and with or without padding, and whether it is mostly
    printable.

    None when the token is too short or is not base64.
    """
    if len(token) < BASE64_MIN:
        return None
    token = token.replace("-", "+").replace("_", "/")
    token = token[:-1] if len(token) % 4 == 1 else token + "=" * (-len(token) % 4)
    try:
        raw = base64.b64decode(token, validate=True)
    except ValueError:
        return None
    printable = sum(0x20 <= byte < 0x7F or byte in (9, 10, 13) for byte in raw)
    return raw.decode("utf-8", errors="replace"), printable >= BASE64_PRINTABLE * len(raw)


def _base64_texts(text: str) -> list[tuple[str, bool]]:
    """The text inside every run of base64 characters in this text, as it stands and with percent-escapes undone,
    and whether it is mostly printable."""
    sources = [text]
    if "%" in text and (unquoted := unquote(text)) != text:
        sources.append(unquoted)
    return [decoded for source in sources for run in BASE64_RUN.finditer(source)
            for token in re.split("=+", run.group())  # padding is optional, so an equals sign ends a token
            if (decoded := _decoded(token)) is not None]


def _named_in(text: str, deny: Sequence[str], printable: bool = True) -> list[str]:
    """What in this text, as it stands, could name the tenant or its owner.

    Text decoded from base64 that is mostly not printable is searched only for what binary does not hold by chance:
    an onmicrosoft domain, and an address written with three numbers or more. Random bytes hold a short IPv6 address
    such as b:: about once in a million, and the ipaddress module calls it global.
    """
    found = [f"an onmicrosoft.{tld} domain" for tld in dict.fromkeys(m.group(1).lower()
                                                                      for m in ANY_ONMICROSOFT.finditer(text))]
    found += dict.fromkeys(f"public IP address {text[start:end]}" for start, end, ip in _spans(text, loose=True)
                           if _is_public(ip) and (printable or len(NUMBERS.findall(text, start, end)) >= 3))
    if not printable:
        return found
    own = [(m.start(), m.end()) for m in OWN.finditer(text)]
    return found + [f"denied value {v!r}" for v in deny if v and _stands_outside(v, text, own)]


def leaks(text: str, deny: Iterable[str] = ()) -> list[str]:
    """What in this text could name the tenant or its owner, including what base64 in it holds.

    Every run of base64 is searched for what binary does not hold by chance, so the domain in a paged export's token is
    found even where the binary beside a short user name leaves the run less than mostly printable (_named_in).
    """
    deny = list(deny)
    inside = dict.fromkeys(f"{leak} (inside base64)" for decoded, printable in _base64_texts(text)
                           for leak in _named_in(decoded, deny, printable))
    return [*_named_in(text, deny), *inside]


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
    parser.add_argument("--admin-user", required=True, metavar="NAME",
                        help="your user name in the tenant, the part of your UPN before the @")
    parser.add_argument("--domain", action="append", default=[], help="a custom domain the tenant uses")
    parser.add_argument("--also", action="append", default=[], metavar="VALUE",
                        help="anything else to replace with 'redacted' and deny; repeat for each value")
    args = parser.parse_args(argv)
    if not user_name(args.admin_user):
        parser.error("--admin-user needs your user name, the part of your UPN before the @")
    if args.out.exists():
        print(f"{args.out} already exists; remove it first", file=sys.stderr)
        return 2
    scrubber = Scrubber(args.tenant_id, args.admin_name, args.admin_address, tuple(args.domain), tuple(args.also),
                        args.admin_user)
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
