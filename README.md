# attest

Checks a firm's insurance application and written information security plan
(WISP) against what its Microsoft 365 and Veeam exports show. Each attestation
comes out **backed**, **gap** or **unchecked**, with the export rows cited.
It never reports backed without proof that covers the whole attested
population: missing evidence is unchecked, a shown failure is a gap.

    py -3.12 -m venv venv
    venv/Scripts/python.exe -m pip install -r requirements.txt
    venv/Scripts/python.exe -m pytest
    venv/Scripts/python.exe -m attest check firm/dev

Design: `docs/superpowers/specs/2026-10-04-attestation-core-design.md`.
How the firm produces each export: `docs/exports.md`.

## Firm folder

    firm/<name>/
      attest/            the attestation documents, plain UTF-8 text
                         (application.txt, wisp.txt, ...); tags may quote only these
      exports/
        manifest.yaml    each export file with its reader and exported_at
        *.json           the export files (see docs/exports.md)
      tags.yaml          the confirmed tags
      truth.yaml         dev firm only: the expected verdict of each tag
      report.md          written by the check

## `tags.yaml`

```yaml
tags:
  - id: wisp-edr
    doc: attest/wisp.txt
    quote: "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts."
    control: edr
    scope: all_endpoints
  - id: wisp-edr-alerts
    doc: attest/wisp.txt
    quote: "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts."
    control: edr
    scope: alert_monitoring
```

Each tag has exactly these fields: `id` (unique), `doc` (a file under
`attest/`), `quote` (the attested words, exactly as the document has them),
and `control` and `scope` (a pair from `profile/controls.yaml`).

- **Every claim in a quote gets a tag.** Several tags may share one quote, as
  above, or quote different clauses of one passage. A claim no export speaks
  to still gets a tag, on one of the always-unchecked scopes
  (`mfa.remote_access`, `edr.alert_monitoring`, `backup.m365_files`,
  `backup.servers`, `backup.offline_copy`, `backup.restore_tested`).
- **An attestation is the lines its tags touch.** Tags in one document whose
  quotes touch a common line, directly or through a tag whose quote spans
  several lines, are one attestation. The report quotes those whole lines,
  heads them with the worst of the tags' verdicts (any gap, else any
  unchecked, else backed) and lists each tag with its own; the count line
  counts attestations. So tags on one passage share one verdict, and a WISP
  written as one long paragraph per line rolls all of that paragraph's
  sentences into one attestation.
- A quote must appear exactly once in its document and contain at least three
  words. Quote enough to be unique.
- An application answer of "No" is a disclosure, not an attestation, and is
  not tagged.

## Running

`venv/Scripts/python.exe -m attest check firm/<name>` writes
`firm/<name>/report.md` and prints it. Exit codes:

- `0`: the check ran and the report was written.
- `2`: an input problem (a bad tag, a malformed export, a missing field; the
  message names the file and row, or the tag), or the report could not be
  written.

A run that fails replaces the report with a stub that begins
`# Attestation check: <name>` and says `CHECK FAILED: <why>`, so an earlier
run's verdicts never look current. Only the tool's own `report.md` (one that
begins with that title) is replaced, or a new one written in a folder that has
a `tags.yaml`; any other file is left alone. An unexpected error leaves the
same stub and shows its traceback.

## Known limitations

- A Conditional Access policy that targets groups (`includeGroups`) can only
  produce gaps: v1 has no group-membership export, so it cannot show who such
  a policy covers.
- Unlicensed or service accounts are permanent backup gaps: every enabled
  member account counts, mailbox or not, and the reviewer annotates them.
- The three-word rule cannot be met inside text written without spaces
  between words (Chinese, Japanese): such a quote has to span spaces, or the
  passage cannot be tagged.
- The two symlink tests skip on a machine without symlink privilege (as on
  the development machine); run the suite once on a machine that has it.
- The Veeam field names (`Email`, `IsMailboxBackedUp`, `MailboxBackedUpTime`)
  come from Veeam's published examples, not its reference documentation:
  confirm them, and that `Email` is the UPN, on the first real export.
