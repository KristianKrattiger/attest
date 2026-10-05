import io
import json
import os
import sys

import pytest

import attest.__main__ as cli
from attest.__main__ import main
from attest.compare import check
from attest.model import Tag, Verdict
from attest.report import render

USERS = {"value": [{"id": "u1", "userPrincipalName": "ann@firm.example", "displayName": "Ann",
                    "accountEnabled": True, "userType": "Member"}]}
REGISTRATION = {"value": [{"id": "u1", "userPrincipalName": "ann@firm.example", "isMfaRegistered": True}]}
CA = {"value": [{"id": "p1", "displayName": "All users MFA", "state": "enabled",
                 "conditions": {"users": {"includeUsers": ["All"]},
                                "applications": {"includeApplications": ["All"]},
                                "clientAppTypes": ["all"]},
                 "grantControls": {"operator": "OR", "builtInControls": ["mfa"]}}]}
SECURITY_DEFAULTS = {"isEnabled": False}

WISP = "All staff use MFA.\nRemote access uses a VPN with MFA.\n"
TAGS = """tags:
  - {id: w1, doc: attest/wisp.txt, quote: All staff use MFA., control: mfa, scope: all_users}
  - {id: w2, doc: attest/wisp.txt, quote: Remote access uses a VPN with MFA., control: mfa, scope: remote_access}
"""
MANIFEST = """exports:
  - {file: users.json, reader: entra_users, exported_at: 2026-10-01T15:00:00Z}
  - {file: registration.json, reader: entra_registration, exported_at: 2026-10-01T15:00:00Z}
  - {file: ca.json, reader: entra_ca_policies, exported_at: 2026-10-01T15:00:00Z}
  - {file: sd.json, reader: entra_security_defaults, exported_at: 2026-10-01T15:00:00Z}
"""


def stub(name, stderr):
    """The report a failed run leaves behind: the error stderr showed, without its 'attest: ' prefix."""
    error = stderr.removeprefix("attest: ").removesuffix("\n")
    return f"# Attestation check: {name}\n\nCHECK FAILED: {error}\n"


@pytest.fixture
def firm(tmp_path):
    root = tmp_path / "tiny"
    (root / "attest").mkdir(parents=True)
    (root / "exports").mkdir()
    (root / "attest" / "wisp.txt").write_text(WISP, encoding="utf-8")
    (root / "tags.yaml").write_text(TAGS, encoding="utf-8")
    (root / "exports" / "manifest.yaml").write_text(MANIFEST, encoding="utf-8")
    exports = {"users.json": USERS, "registration.json": REGISTRATION, "ca.json": CA, "sd.json": SECURITY_DEFAULTS}
    for name, data in exports.items():
        (root / "exports" / name).write_text(json.dumps(data), encoding="utf-8")
    return root


def test_check_runs_each_tag_through_its_scope_rule(firm):
    assert [(t.id, v.status) for t, v in check(firm)] == [("w1", "backed"), ("w2", "unchecked")]


def test_the_report_counts_verdicts_and_shows_each_attestation():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    gap = Verdict("gap", "not registered for MFA: bob@firm.example", ("bob@firm.example",),
                  ("registration.json:2",), "2 enabled member accounts from users.json")
    text = render("tiny", [(tag, gap)])
    assert text.startswith("# Attestation check: tiny\n")
    assert "backed 0, gap 1, unchecked 0" in text
    for line in ["## w1: GAP", "> All staff use MFA.", "- document: `attest/wisp.txt`",
                 "- control: `mfa.all_users`", "- reason: not registered for MFA: bob@firm.example",
                 "- population: 2 enabled member accounts from users.json",
                 "- entities: bob@firm.example", "- cited: `registration.json:2`"]:
        assert line in text


def test_the_cli_prints_and_writes_the_report(firm, capsys):
    assert main(["check", str(firm)]) == 0
    out = capsys.readouterr().out
    assert "backed 1, gap 0, unchecked 1" in out
    assert (firm / "report.md").read_text(encoding="utf-8") == out


def test_the_cli_stops_with_exit_2_on_a_bad_input(firm, capsys):
    bad = TAGS.replace("quote: All staff use MFA.,", "quote: All staff always use MFA.,")
    (firm / "tags.yaml").write_text(bad, encoding="utf-8")
    assert main(["check", str(firm)]) == 2
    error = capsys.readouterr().err
    assert "attest: tags.yaml: tag 'w1': quote is not an exact substring" in error
    assert (firm / "report.md").read_text(encoding="utf-8") == stub("tiny", error)


PROBE = "Access control\n## w9: BACKED\n\n- all staff use MFA."


def test_a_multi_line_quote_stays_inside_its_blockquote():
    tag = Tag("w1", "attest/wisp.txt", PROBE, "mfa", "all_users")
    text = render("tiny", [(tag, Verdict("backed", "ok", population="2 accounts"))])
    lines = text.splitlines()
    assert [line for line in lines if line.startswith("##")] == ["## w1: BACKED"]
    start = lines.index("## w1: BACKED") + 2
    end = lines.index("- document: `attest/wisp.txt`") - 1
    assert lines[start:end] == ["> Access control", "> ## w9: BACKED", ">", "> - all staff use MFA."]


def test_a_reason_stays_on_one_line():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    text = render("tiny", [(tag, Verdict("gap", "a\n## x"))])
    assert "- reason: a ## x\n" in text
    assert not any(line.startswith("## x") for line in text.splitlines())


def test_every_other_firm_text_stays_on_its_own_line():
    tag = Tag("w1\n## id", "attest/a\r\n## doc.txt", "All staff use MFA.", "mfa\n## control", "all\r## scope")
    verdict = Verdict("gap", "r", ("bob\n## entity",), ("ca.json:1\n## cited",), "2 accounts\n## population")
    text = render("tiny\n## name", [(tag, verdict)])
    assert [line for line in text.splitlines() if line.startswith("#")] == [
        "# Attestation check: tiny ## name", "## w1 ## id: GAP"]
    assert "\r" not in text
    assert text.count("\n") == len(text.splitlines())
    for line in ["- population: 2 accounts ## population", "- entities: bob ## entity",
                 "- cited: `ca.json:1 ## cited`", "- control: `mfa ## control.all ## scope`"]:
        assert line in text


BAD_TAGS = TAGS.replace("quote: All staff use MFA.,", "quote: All staff always use MFA.,")


def test_a_failed_run_replaces_an_earlier_report_with_a_stub(firm, capsys):
    assert main(["check", str(firm)]) == 0
    assert "## w1: BACKED" in (firm / "report.md").read_text(encoding="utf-8")
    capsys.readouterr()
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    assert main(["check", str(firm)]) == 2
    error = capsys.readouterr().err
    assert "attest: tags.yaml: tag 'w1': quote is not an exact substring" in error
    report = (firm / "report.md").read_bytes()
    assert b"CHECK FAILED" in report and b"BACKED" not in report
    assert report == stub("tiny", error).encode("utf-8")


def test_a_failed_run_with_no_firm_folder_writes_nothing(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope")]) == 2
    assert "attest: " in capsys.readouterr().err
    assert not (tmp_path / "nope").exists()


def test_a_report_that_cannot_be_written_is_an_error_not_a_traceback(firm, capsys):
    (firm / "report.md").mkdir()
    assert main(["check", str(firm)]) == 2
    assert "attest: cannot write report.md: " in capsys.readouterr().err
    assert sorted(p.name for p in firm.iterdir()) == ["attest", "exports", "report.md", "tags.yaml"]


def test_a_stub_that_cannot_be_written_reports_both_errors(firm, capsys):
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    (firm / "report.md").mkdir()
    assert main(["check", str(firm)]) == 2
    err = capsys.readouterr().err
    assert "attest: tags.yaml: tag 'w1': quote is not an exact substring" in err
    assert "attest: cannot write report.md: " in err


def test_a_write_that_fails_part_way_keeps_the_earlier_report_whole(firm, monkeypatch, capsys):
    assert main(["check", str(firm)]) == 0
    before = (firm / "report.md").read_bytes()
    capsys.readouterr()

    def disk_full(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", disk_full)
    (firm / "tags.yaml").write_text(TAGS.split("  - {id: w2")[0], encoding="utf-8")  # one tag fewer: a new report
    assert main(["check", str(firm)]) == 2
    assert "attest: cannot write report.md: disk full" in capsys.readouterr().err
    assert (firm / "report.md").read_bytes() == before
    assert sorted(p.name for p in firm.iterdir()) == ["attest", "exports", "report.md", "tags.yaml"]


def console(encoding="cp1252"):
    """A stream that, like a Windows console, raises UnicodeEncodeError for what its encoding cannot hold."""
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding=encoding, errors="strict", newline="\n", write_through=True)


def test_printing_falls_back_to_replacement_characters():
    raw, stream = console()
    with pytest.raises(UnicodeEncodeError):
        stream.write("x ≥ 1\n")
    cli._emit("x ≥ 1\n", stream)
    assert raw.getvalue() == b"x ? 1\n"


def test_printing_text_the_stream_can_hold_is_unchanged():
    raw, stream = console()
    cli._emit("café\n", stream)
    assert raw.getvalue() == "café\n".encode("cp1252")


def firm_quoting(firm, quote):
    (firm / "attest" / "wisp.txt").write_text(f"{quote}\n", encoding="utf-8")
    (firm / "tags.yaml").write_text(f"tags:\n  - {{id: w1, doc: attest/wisp.txt, quote: '{quote}', "
                                    "control: mfa, scope: all_users}\n", encoding="utf-8")


def test_a_console_that_cannot_show_the_report_still_gets_it_and_the_file_keeps_it(firm, monkeypatch):
    firm_quoting(firm, "MFA for ≥ 1 account.")
    raw, stream = console()
    monkeypatch.setattr(sys, "stdout", stream)
    assert main(["check", str(firm)]) == 0
    assert "> MFA for ? 1 account." in raw.getvalue().decode("cp1252")
    assert "> MFA for ≥ 1 account." in (firm / "report.md").read_text(encoding="utf-8")


def test_a_console_that_cannot_show_the_error_still_gets_it(firm, monkeypatch):
    (firm / "tags.yaml").write_text("tags:\n  - {id: w1, doc: attest/≥.txt, quote: x, control: mfa, "
                                    "scope: all_users}\n", encoding="utf-8")
    raw, stream = console()
    monkeypatch.setattr(sys, "stderr", stream)
    assert main(["check", str(firm)]) == 2
    assert "document attest/?.txt not found" in raw.getvalue().decode("cp1252")
    assert "attest/≥.txt not found" in (firm / "report.md").read_text(encoding="utf-8")


def test_the_report_is_written_before_it_is_printed(firm, monkeypatch):
    seen = []

    class Spy:
        encoding = "utf-8"

        def write(self, text):
            seen.append((firm / "report.md").exists())

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", Spy())
    assert main(["check", str(firm)]) == 0
    assert seen and all(seen)


def test_a_backed_verdict_shows_its_population():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    backed = Verdict("backed", "all 2 accounts registered", cited=("registration.json",),
                     population="2 enabled member accounts from users.json")
    text = render("tiny", [(tag, backed)])
    assert "## w1: BACKED" in text
    assert "- population: 2 enabled member accounts from users.json\n" in text


def test_a_verdict_the_report_cannot_state_is_refused():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    with pytest.raises(ValueError, match="status"):
        render("tiny", [(tag, Verdict("maybe", "r"))])
    with pytest.raises(ValueError, match="population"):
        render("tiny", [(tag, Verdict("backed", "r"))])
    with pytest.raises(ValueError, match="population"):
        render("tiny", [(tag, Verdict("backed", "r", population=""))])


def test_check_dot_names_the_folder_it_is_run_in(firm, monkeypatch, capsys):
    monkeypatch.chdir(firm)
    assert main(["check", "."]) == 0
    assert capsys.readouterr().out.startswith("# Attestation check: tiny\n")
    assert (firm / "report.md").read_text(encoding="utf-8").startswith("# Attestation check: tiny\n")
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    assert main(["check", "."]) == 2
    assert (firm / "report.md").read_text(encoding="utf-8").startswith("# Attestation check: tiny\n\nCHECK FAILED")
