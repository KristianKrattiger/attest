import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

import attest.__main__ as cli
from attest.__main__ import main
from attest.compare import check, run
from attest.evidence import Evidence
from attest.model import Export, Span, Tag, Verdict
from attest.profile import load_profile
from attest.report import attestations, combined_status, render
from attest.tags import load_tags

ANN = "a0000000-0000-4000-8000-000000000001"
USERS = {"value": [{"id": ANN, "userPrincipalName": "ann@firm.example", "displayName": "Ann",
                    "accountEnabled": True, "userType": "Member"}]}
REGISTRATION = {"value": [{"id": ANN, "userPrincipalName": "ann@firm.example", "isMfaRegistered": True}]}
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


def spanned(quote, first=1):
    """A line range for a hand-built tag: its quote taken as whole lines, starting at line `first`."""
    lines = tuple(quote.split("\n"))
    return Span(first, first + len(lines) - 1, lines)


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
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
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
    tag = Tag("w1", "attest/wisp.txt", PROBE, "mfa", "all_users", spanned(PROBE))
    text = render("tiny", [(tag, Verdict("backed", "ok", population="2 accounts"))])
    lines = text.splitlines()
    assert [line for line in lines if line.startswith("##")] == ["## w1: BACKED"]
    start = lines.index("## w1: BACKED") + 2
    end = lines.index("- document: `attest/wisp.txt`") - 1
    assert lines[start:end] == ["> Access control", "> ## w9: BACKED", ">", "> - all staff use MFA."]


def test_a_reason_stays_on_one_line():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
    text = render("tiny", [(tag, Verdict("gap", "a\n## x"))])
    assert "- reason: a ## x\n" in text
    assert not any(line.startswith("## x") for line in text.splitlines())


def test_every_other_firm_text_stays_on_its_own_line():
    tag = Tag("w1\n## id", "attest/a\r\n## doc.txt", "All staff use MFA.", "mfa\n## control", "all\r## scope",
              spanned("All staff use MFA."))
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


def disk_full(src, dst):
    raise OSError("disk full")


def boom(path):
    raise RuntimeError("boom")


def test_a_stub_that_cannot_be_written_reports_both_errors(firm, monkeypatch, capsys):
    assert main(["check", str(firm)]) == 0
    monkeypatch.setattr(os, "replace", disk_full)
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    capsys.readouterr()
    assert main(["check", str(firm)]) == 2
    err = capsys.readouterr().err
    assert "attest: tags.yaml: tag 'w1': quote is not an exact substring" in err
    assert "attest: cannot write report.md: disk full" in err


def test_a_write_that_fails_part_way_keeps_the_earlier_report_whole(firm, monkeypatch, capsys):
    assert main(["check", str(firm)]) == 0
    before = (firm / "report.md").read_bytes()
    capsys.readouterr()
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
    (firm / "tags.yaml").write_text("tags:\n  - {id: w1, doc: attest/≥.txt, quote: All staff use MFA., control: mfa, "
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
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
    backed = Verdict("backed", "all 2 accounts registered", cited=("registration.json",),
                     population="2 enabled member accounts from users.json")
    text = render("tiny", [(tag, backed)])
    assert "## w1: BACKED" in text
    assert "- population: 2 enabled member accounts from users.json\n" in text


def test_a_verdict_the_report_cannot_state_is_refused():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
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


def test_an_unexpected_error_replaces_an_earlier_report_and_is_re_raised(firm, monkeypatch, capsys):
    assert main(["check", str(firm)]) == 0
    assert "## w1: BACKED" in (firm / "report.md").read_text(encoding="utf-8")
    monkeypatch.setattr(cli, "run", boom)
    with pytest.raises(RuntimeError, match="boom"):
        main(["check", str(firm)])
    report = (firm / "report.md").read_bytes()
    assert report == b"# Attestation check: tiny\n\nCHECK FAILED: internal error: RuntimeError: boom\n"
    assert b"BACKED" not in report
    assert sorted(p.name for p in firm.iterdir()) == ["attest", "exports", "report.md", "tags.yaml"]


def test_a_verdict_render_refuses_leaves_a_stub_not_an_earlier_report(firm, monkeypatch):
    assert main(["check", str(firm)]) == 0
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    monkeypatch.setattr(cli, "run", lambda path: ([(tag, Verdict("backed", "r"))], None))
    with pytest.raises(ValueError, match="population"):
        main(["check", str(firm)])
    assert (firm / "report.md").read_text(encoding="utf-8") == (
        "# Attestation check: tiny\n\nCHECK FAILED: internal error: ValueError: "
        "cannot report a backed verdict without its population\n")


def test_an_unexpected_error_stays_the_error_when_the_stub_cannot_be_written(firm, monkeypatch, capsys):
    assert main(["check", str(firm)]) == 0
    monkeypatch.setattr(os, "replace", disk_full)
    monkeypatch.setattr(cli, "run", boom)
    capsys.readouterr()
    with pytest.raises(RuntimeError, match="boom"):
        main(["check", str(firm)])
    assert "attest: cannot write report.md: disk full" in capsys.readouterr().err


def test_an_unexpected_error_with_no_firm_folder_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "run", boom)
    with pytest.raises(RuntimeError, match="boom"):
        main(["check", str(tmp_path / "nope")])
    assert not (tmp_path / "nope").exists()


UNRELATED = "my unrelated report\n"


def test_a_failed_run_in_a_folder_that_is_not_a_firm_leaves_an_unrelated_report_alone(tmp_path, capsys):
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "report.md").write_text(UNRELATED, encoding="utf-8")
    assert main(["check", str(folder)]) == 2
    assert "attest: " in capsys.readouterr().err
    assert (folder / "report.md").read_text(encoding="utf-8") == UNRELATED
    assert sorted(p.name for p in folder.iterdir()) == ["report.md"]


def test_a_failed_run_in_a_firm_leaves_an_unrelated_report_alone(firm):
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    (firm / "report.md").write_text(UNRELATED, encoding="utf-8")
    assert main(["check", str(firm)]) == 2
    assert (firm / "report.md").read_text(encoding="utf-8") == UNRELATED


def test_an_unexpected_error_leaves_an_unrelated_report_alone(firm, monkeypatch):
    (firm / "report.md").write_text(UNRELATED, encoding="utf-8")
    monkeypatch.setattr(cli, "run", boom)
    with pytest.raises(RuntimeError, match="boom"):
        main(["check", str(firm)])
    assert (firm / "report.md").read_text(encoding="utf-8") == UNRELATED


@pytest.mark.parametrize("content", [b"\xff\xfe\x00binary", b"", b"  # Attestation check: not at the start\n"])
def test_a_report_that_is_not_the_tools_own_is_left_alone_however_odd(firm, content):
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    (firm / "report.md").write_bytes(content)
    assert main(["check", str(firm)]) == 2
    assert (firm / "report.md").read_bytes() == content


def test_a_report_that_is_a_folder_is_left_alone_on_failure(firm):
    (firm / "tags.yaml").write_text(BAD_TAGS, encoding="utf-8")
    (firm / "report.md").mkdir()
    assert main(["check", str(firm)]) == 2
    assert (firm / "report.md").is_dir()
    assert sorted(p.name for p in firm.iterdir()) == ["attest", "exports", "report.md", "tags.yaml"]


def test_a_firm_with_no_report_yet_gets_a_stub_on_an_unexpected_error(firm, monkeypatch):
    monkeypatch.setattr(cli, "run", boom)
    with pytest.raises(RuntimeError):
        main(["check", str(firm)])
    assert (firm / "report.md").read_text(encoding="utf-8") == (
        "# Attestation check: tiny\n\nCHECK FAILED: internal error: RuntimeError: boom\n")


def test_the_tools_own_earlier_report_is_replaced_even_when_tags_yaml_is_gone(firm, capsys):
    assert main(["check", str(firm)]) == 0
    (firm / "tags.yaml").unlink()
    capsys.readouterr()
    assert main(["check", str(firm)]) == 2
    report = (firm / "report.md").read_text(encoding="utf-8")
    assert report.startswith("# Attestation check: tiny\n\nCHECK FAILED: ") and "BACKED" not in report


# Several tags on one quote: one section per attestation, headed by the worst of its tags' verdicts.

QUOTE = "All staff use MFA."
BACKED = Verdict("backed", "all 2 accounts registered", cited=("registration.json",),
                 population="2 enabled member accounts from users.json")
GAP = Verdict("gap", "not registered for MFA: bob@firm.example", ("bob@firm.example",), ("registration.json:2",),
              "2 enabled member accounts from users.json")
UNCHECKED = Verdict("unchecked", "no export in this stack shows VPN or firewall MFA")


def tag(id_, scope, quote=QUOTE, control="mfa", line=1):
    return Tag(id_, "attest/wisp.txt", quote, control, scope, spanned(quote, line))


def headings(text):
    return [line for line in text.splitlines() if line.startswith("#")]


def test_two_tags_on_one_quote_render_one_section_with_both_tags():
    text = render("tiny", [(tag("w1", "all_users"), BACKED), (tag("w2", "remote_access"), UNCHECKED)])
    assert headings(text) == ["# Attestation check: tiny", "## w1, w2: UNCHECKED"]
    assert text.count("> All staff use MFA.") == 1
    section = text.split("## w1, w2: UNCHECKED\n")[1]
    assert section == (
        "\n> All staff use MFA.\n\n"
        "- document: `attest/wisp.txt`\n"
        "- tag w1: BACKED\n"
        "  - control: `mfa.all_users`\n"
        "  - reason: all 2 accounts registered\n"
        "  - population: 2 enabled member accounts from users.json\n"
        "  - cited: `registration.json`\n"
        "- tag w2: UNCHECKED\n"
        "  - control: `mfa.remote_access`\n"
        "  - reason: no export in this stack shows VPN or firewall MFA\n")


@pytest.mark.parametrize("verdicts, heading", [
    ((BACKED, UNCHECKED), "UNCHECKED"), ((UNCHECKED, BACKED), "UNCHECKED"),
    ((GAP, UNCHECKED), "GAP"), ((UNCHECKED, GAP), "GAP"), ((BACKED, GAP), "GAP"),
    ((BACKED, BACKED), "BACKED"),
])
def test_an_attestation_is_headed_by_the_worst_verdict_of_its_tags(verdicts, heading):
    first, second = verdicts
    text = render("tiny", [(tag("w1", "all_users"), first), (tag("w2", "email"), second)])
    assert headings(text)[1:] == [f"## w1, w2: {heading}"]
    assert f"- tag w1: {first.status.upper()}" in text and f"- tag w2: {second.status.upper()}" in text


def test_the_count_line_counts_attestations_not_tags():
    other = "Remote access uses a VPN with MFA."
    results = [(tag("w1", "all_users"), BACKED), (tag("w2", "remote_access"), UNCHECKED),
               (tag("w3", "all_users", quote=other, line=2), BACKED)]
    assert "\nbacked 1, gap 0, unchecked 1\n" in render("tiny", results)


def test_attestations_keep_the_order_each_quote_first_appears_in():
    other = "Remote access uses a VPN with MFA."
    results = [(tag("w1", "all_users"), BACKED), (tag("w2", "remote_access", quote=other, line=2), UNCHECKED),
               (tag("w3", "email"), GAP)]
    assert [(quote, [t.id for t, _ in tagged]) for _, quote, tagged in attestations(results)] == [
        (QUOTE, ["w1", "w3"]), (other, ["w2"])]
    assert headings(render("tiny", results))[1:] == ["## w1, w3: GAP", "## w2: UNCHECKED"]


@pytest.mark.parametrize("statuses, combined", [
    (["backed"], "backed"), (["backed", "backed"], "backed"), (["backed", "unchecked"], "unchecked"),
    (["unchecked", "gap", "backed"], "gap"), (["gap"], "gap"), (["unchecked"], "unchecked"),
])
def test_the_combined_verdict_is_the_worst(statuses, combined):
    assert combined_status(statuses) == combined


def test_the_cli_counts_a_quote_with_two_tags_once(firm, capsys):
    (firm / "tags.yaml").write_text(TAGS + "  - {id: w1b, doc: attest/wisp.txt, quote: All staff use MFA., "
                                           "control: mfa, scope: remote_access}\n", encoding="utf-8")
    assert main(["check", str(firm)]) == 0
    out = capsys.readouterr().out
    assert "\nbacked 0, gap 0, unchecked 2\n" in out
    assert headings(out)[1:] == ["## w1, w1b: UNCHECKED", "## w2: UNCHECKED"]


# The report lists the exports it rests on (final review I2).

EXPORTS_TABLE = """Exports:

| reader | file | exported_at (UTC) | rows |
|---|---|---|---|
| `entra_users` | `users.json` | 2026-10-01T15:00:00+00:00 | 1 |
| `entra_registration` | `registration.json` | 2026-10-01T15:00:00+00:00 | 1 |
| `entra_ca_policies` | `ca.json` | 2026-10-01T15:00:00+00:00 | 1 |
| `entra_security_defaults` | `sd.json` | 2026-10-01T15:00:00+00:00 | 1 |
"""


def test_the_cli_report_lists_every_manifest_entry_under_the_count_line(firm, capsys):
    assert main(["check", str(firm)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Attestation check: tiny\n\nbacked 1, gap 0, unchecked 1\n\n" + EXPORTS_TABLE + "\n## w1: ")


def test_run_returns_check_s_results_and_the_evidence_they_rest_on(firm):
    results, evidence = run(firm)
    assert results == check(firm)
    assert [(e.file, len(e.items)) for e in (evidence.entra_users, evidence.entra_ca_policies)] == [
        ("users.json", 1), ("ca.json", 1)]


def test_without_evidence_the_report_has_no_exports_table():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
    assert "Exports" not in render("tiny", [(tag, Verdict("unchecked", "r"))])


def test_evidence_with_no_exports_says_so():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
    assert "\nExports: none\n" in render("tiny", [(tag, Verdict("unchecked", "r"))], Evidence())


def test_a_file_name_cannot_break_the_exports_table_and_the_time_is_shown_in_utc():
    tag = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users", spanned("All staff use MFA."))
    users = Export("a|b\n## x.json", datetime(2026, 10, 1, 10, tzinfo=timezone(timedelta(hours=-5))), ())
    text = render("tiny", [(tag, Verdict("unchecked", "r"))], Evidence(entra_users=users))
    assert "\n| `entra_users` | `a\\|b ## x.json` | 2026-10-01T15:00:00+00:00 | 0 |\n" in text


# An attestation is the set of document lines its tags touch (final re-review): tags in one document whose line ranges
# meet, transitively, are one attestation, quoted as those whole lines.

LINES = ("Line one says all staff use MFA on every account.\n"
         "Line two says every laptop runs EDR at all times.\n"
         "Line three says backups run every single night.\n")


def grounded(tmp_path, *quotes):
    """Tags w1, w2, ... on these quotes of a three-line document, grounded by load_tags, so with their spans."""
    (tmp_path / "attest").mkdir()
    (tmp_path / "attest" / "doc.txt").write_text(LINES, encoding="utf-8")
    entries = [f"  - {{id: w{i}, doc: attest/doc.txt, quote: {json.dumps(quote)}, control: mfa, "
               "scope: remote_access}\n" for i, quote in enumerate(quotes, start=1)]
    (tmp_path / "tags.yaml").write_text("tags:\n" + "".join(entries), encoding="utf-8")
    return load_tags(tmp_path, load_profile())


def groups(tags):
    return [[t.id for t, _ in tagged] for _, _, tagged in attestations([(t, UNCHECKED) for t in tags])]


def test_tags_on_different_lines_stay_separate_attestations(tmp_path):
    tags = grounded(tmp_path, "all staff use MFA", "every laptop runs EDR")
    assert groups(tags) == [["w1"], ["w2"]]
    assert "\nbacked 0, gap 0, unchecked 2\n" in render("tiny", [(t, UNCHECKED) for t in tags])


@pytest.mark.parametrize("other", ["Line one says", "Line two says every"])
def test_a_quote_spanning_two_lines_groups_with_a_tag_on_either_line(tmp_path, other):
    tags = grounded(tmp_path, "every account.\nLine two", other, "backups run every single night")
    assert groups(tags) == [["w1", "w2"], ["w3"]]
    (_, passage, _), _ = attestations([(t, UNCHECKED) for t in tags])
    assert passage == "\n".join(LINES.splitlines()[:2])


def test_tags_join_one_attestation_through_a_tag_that_touches_both(tmp_path):
    tags = grounded(tmp_path, "Line one says", "Line two says every", "every account.\nLine two")
    assert groups(tags) == [["w1", "w2", "w3"]]


def test_tags_in_different_documents_never_join(tmp_path):
    tags = grounded(tmp_path, "all staff use MFA", "every laptop runs EDR")
    moved = Tag("w2", "attest/other.txt", tags[0].quote, "mfa", "remote_access", tags[0].span)
    assert groups([tags[0], moved]) == [["w1"], ["w2"]]


def test_an_attestation_quotes_the_whole_lines_its_tags_touch_under_their_worst_verdict(tmp_path):
    tags = grounded(tmp_path, "staff use MFA", "every account.\nLine two")
    text = render("tiny", [(tags[0], BACKED), (tags[1], UNCHECKED)])
    assert headings(text)[1:] == ["## w1, w2: UNCHECKED"]
    assert ("\n\n> Line one says all staff use MFA on every account.\n"
            "> Line two says every laptop runs EDR at all times.\n\n- document: `attest/doc.txt`\n") in text
    assert "\nbacked 0, gap 0, unchecked 1\n" in text
    assert "> staff use MFA\n" not in text


def test_a_tag_with_no_line_range_is_refused():
    # Third review M1: grouping by exact quote was the hole line grouping closed (N1), so it has no fallback left.
    unranged = Tag("w1", "attest/wisp.txt", "All staff use MFA.", "mfa", "all_users")
    message = "cannot report tag 'w1' without its line range"
    with pytest.raises(ValueError, match=message):
        render("tiny", [(unranged, UNCHECKED)])
    with pytest.raises(ValueError, match=message):
        attestations([(tag("w0", "all_users"), UNCHECKED), (unranged, UNCHECKED)])
