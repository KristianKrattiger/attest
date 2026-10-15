"""Nothing committed under firm/lab names the lab tenant or its owner (spec 2026-10-14, Scrubbing and storage)."""
from messy.firm import LAB
from scripts.scrub_lab_capture import decode, leaks, read_deny


def test_nothing_committed_under_firm_lab_names_the_tenant_or_its_owner():
    deny = read_deny()  # firm/lab/raw/deny.txt, on the machine that took the captures; absent elsewhere
    problems = []
    for path in sorted(LAB.rglob("*")) if LAB.exists() else []:
        relative = path.relative_to(LAB)
        if path.is_file() and relative.parts[0] != "raw":
            problems += [f"{relative.as_posix()}: {leak}" for leak in leaks(decode(path.read_bytes())[0], deny)]
    assert problems == []
