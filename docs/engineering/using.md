# Running a check

This is how to run a check.

    py -3.12 -m venv venv
    venv/Scripts/python.exe -m pip install -r requirements.txt
    venv/Scripts/python.exe -m pytest
    venv/Scripts/python.exe -m attest check firm/dev

Design: `../superpowers/specs/2026-10-04-attestation-core-design.md`.
How the firm produces each export: `exports.md`.

## Firm folder

    firm/<name>/
      attest/            the attestation documents, plain UTF-8 text
                         (application.txt, wisp.txt, ...); tags may quote only these.
                         A document intake read from a PDF, Word file or scan has
                         its sidecar beside it (wisp.txt.map.json)
      sources/           the originals intake read (WISP.pdf, ...); never quoted
      exports/
        manifest.yaml    each export file with its reader and exported_at
        *.json           the export files (see exports.md)
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
`attest/`, written as its path from the firm folder with forward slashes and
the file's own letter case, such as `attest/wisp.txt`; any other spelling,
such as `attest/./wisp.txt` or `attest/WISP.txt`, is refused, and so is a
second name, such as a hard link, for a file another tag names), `quote` (the
attested words, exactly as the document has them), and `control` and `scope`
(a pair from `profile/controls.yaml`).

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
- **Grouping goes by lines, so tag wrapped sentences whole.** A sentence
  wrapped across lines, tagged with one quote per clause, stays split into
  separate attestations, one per line its clauses sit on. Tag a wrapped
  sentence with a quote that spans its lines, or keep one sentence or question
  per line.
- **Tags group only within one document.** A claim must be tagged in the
  document it is quoted from, and a copy of a document under another name is a
  separate document: tags on the copy never join tags on the original.
- A quote must appear exactly once in its document and contain at least three
  words. Quote enough to be unique.
- An application answer of "No" is a disclosure, not an attestation, and is
  not tagged.

## Documents read by intake

A firm's WISP and insurance application usually arrive as PDF or Word. intake, a separate private package,
reads them into the text attest quotes and a sidecar that says where each line came from and how it was read:

    intake read firm/<name>/sources/WISP.pdf --out firm/<name>/attest/wisp.txt

Tags name `attest/wisp.txt` as before. With the sidecar beside it, attest also:

- **stops the run** if the text was edited after it was read (its hash no longer matches the sidecar; a CRLF
  checkout still matches), if the reading is incomplete, if the sidecar is not intake's format 1, or if the
  sidecar is damaged: a field missing or of the wrong type, or a quoted line with text on it but no entry;
- **refuses a tag** whose quote touches a line read by OCR, a quoted earlier email, a table row read without its
  headers, a line read in a way attest does not know, a line on a page that the reading does not list, or a line
  on a page whose parse or OCR grade is below good or is not a grade attest knows. attest vouches only for what
  it recognises, and an absent grade is not a refusal. Docling's OCR grade stayed "excellent" on scans that lost
  a quarter of their words (intake's RESULTS.md), so attest never vouches for OCR text: tag a born-digital copy,
  or a plain-text document a person has checked against the original;
- **cites the original** in the report: `- source: WISP.pdf (sha256 cc5d02b898ad), p. 1`.

A document with no sidecar is checked as plain text, and the report says `- source: plain text, no source
location`. A tag may never name a `.map.json` file.

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
- A shared mailbox the backup job never covered is not counted. A shared
  mailbox is a disabled user object, and a disabled account joins the backup
  population only when the Veeam export lists it, so backup can come out
  backed while that mailbox holds unprotected mail. This is a known false
  backed (`tests/messy/backup.py`, "shared mailbox Veeam never saw"), to be
  fixed in the backup rule in its own change.
- The three-word rule cannot be met inside text written without spaces
  between words (Chinese, Japanese): such a quote has to span spaces, or the
  passage cannot be tagged.
- The two symlink tests skip on a machine without symlink privilege (as on
  the development machine); run the suite once on a machine that has it.
- The Veeam field names (`Email`, `IsMailboxBackedUp`, `MailboxBackedUpTime`)
  come from Veeam's published examples, not its reference documentation:
  confirm them, and that `Email` is the UPN, on the first real export.
