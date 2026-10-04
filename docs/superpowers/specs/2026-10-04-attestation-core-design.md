# Spec: the attestation check's deterministic core

**Date:** 2026-10-04
**Status:** Approved for planning
**Repo:** `attest` (private, local only; closed business code per the business plan's licensing split)
**Sub-project:** 1 of 3 (see "Decomposition")

## Problem

The security check the business sells asks one question: do a firm's
insurance application and its written information security plan (WISP)
match what its systems really show? The Assay way of answering, where a
model proposes quote pairs and a gate admits grounded ones, fails at the
step that matters. Grounding works, but the pairs are not real relations.
On GIN's SEAR proposer, 0 of 21 admitted relational rows held under blind
labels (2026-09-25). With a decline option added, the local model still
kept only 2 of 5 real relations, and the five unrelated pairs it let
through were same-topic pairs with opposite sentiment that do not measure
the same thing (GIN `docs/superpowers/specs/2026-10-04-sear-relation-decline-design.md`).
On a firm's files no frontier verifier may run.

For attestations against system exports, the pairing does not need a model
at all. Both sides can be keyed to a **control**: an attestation is about
MFA, backups or EDR, at some scope; an export row is a fact about one user,
device or mailbox for one control. Pairing becomes a join on the control,
and the verdict becomes a deterministic comparison of state and coverage.
The only judgment left is which control and scope an attestation is about.
That is closed-set tagging, which a person can confirm in seconds and a
model can suggest.

## Goal

Build the deterministic core: given confirmed tags on a firm's attestations
and the firm's system exports, compute **backed**, **gap** or **unchecked**
for each attestation, with the cited export rows. Never report **backed**
without proof computed from an export that covers the whole attested
scope. Measure it on a made-up firm whose truth is planted.

## Decisions (brainstorm, 2026-10-04)

1. **Target the attestation profile first**, not the general Assay engine.
2. **A false "backed" is the error to drive to zero.** It is the
   Travelers v. ICS failure (an application said MFA everywhere; it was on
   the firewall only) and it is the business's liability. A false "gap"
   costs review time.
3. **First controls: MFA, backups, EDR.** Claim side: both the insurance
   application (question plus Yes answer) and the WISP (prose).
4. **Approach: control-keyed join; the model only suggests tags, a person
   confirms them.** Rejected: Assay pairing plus a control gate (a scope
   claim such as "MFA for all users" is a statement about every row, which
   no single quote pair can back); tags by hand only (kept as the v1 input
   format and as the confirmation step, not as the end state).
5. **New private Python repo**, `attest`. No Assay code, so the product does
   not depend on the Pinetree Research challenge terms that govern Assay.
   GIN stays open and domain-free.
6. **Stack of the made-up firm: Microsoft 365 Business Premium (Entra ID,
   Intune, Defender for Business) plus Veeam Backup for Microsoft 365.**
7. **Break-glass accounts excluded from Conditional Access are cited as
   gaps.** The attestation says all users; the report shows the exception
   and the reviewer annotates it.
8. **Local repo only.** The user creates a private remote when ready.

## Decomposition

| # | Sub-project | Where | Proves |
|---|---|---|---|
| 1 | **Deterministic core** (this spec): profile data, export readers, proof rules, report, a made-up dev firm. Tags come from a hand-written file. | `attest` | The join works, with zero false "backed" on planted truth, before any model is involved. |
| 2 | **Tag suggestions**: a generic "quote and tag from this list" mode in GIN's SEAR sidecar (labels sent by the caller), and a client here. Scored on tag accuracy against a blind firm written by someone who has not seen the code. | GIN (open) + `attest` | How much tagging work the 7B removes. |
| 3 | **Review page**: shows each suggested tag beside its quote, records confirm or correct; only confirmed tags reach the comparator. | `attest` | The product loop. |

Sub-project 1 is useful on its own: a reviewer who tags 20 to 40
attestations by hand gets a working check.

## Non-goals

- Any model call (sub-project 2).
- A review UI (sub-project 3).
- PDF, Word or scanned input. Attestation documents are plain text in v1.
- Live API access to a tenant. The firm runs read-only exports; the check
  reads files.
- Controls other than MFA, backups and EDR; backup products other than
  Veeam Backup for Microsoft 365.
- Application answers of "No". They are disclosures, not attestations to
  check, and are not tagged.

## Design

### Firm folder and profile

```
firm/<name>/
  attest/application.txt     insurer-style questions with their answers
  attest/wisp.txt            the WISP, prose
  exports/manifest.yaml      for each export file: reader name, exported_at (UTC)
  exports/...                the export files themselves
  tags.yaml                  confirmed tags, one per attestation:
                               {id, doc, quote, control, scope}
  truth.yaml                 dev firm only: expected verdict per tag id,
                               and the entities each gap must cite
profile/controls.yaml        controls, their scopes, and the proof rule
                             each scope uses
```

`exported_at` lives in the manifest because the CSV exports do not carry
their own timestamp. Staleness ("last backup within 24 hours", "last seen
within 7 days") is measured against it.

### Pipeline

1. **Load tags.** Each tag's `quote` must be an exact substring of its
   `doc`. If not, the run stops with an error naming the tag. A tag whose
   control or scope is not in the profile also stops the run.
2. **Read exports.** One deterministic reader per format turns rows into
   facts. Every fact keeps its source as `file:row`. A reader that finds a
   missing required column stops the run with an error naming the file and
   column; it never guesses.
3. **Apply the scope's proof rule** to produce the verdict, a one-line
   reason, and the cited facts.
4. **Write the report** (Markdown; also printed): per attestation the quote
   and its document, control and scope, verdict, reason and cited rows. A
   **backed** verdict also states the population's size and source. A
   summary line counts backed, gap and unchecked.

### Exports (v1)

| Export | Source | Format | Used for |
|---|---|---|---|
| Users | Entra admin center, "Download users" | CSV | population of accounts |
| Conditional Access policies | Microsoft Graph `GET /identity/conditionalAccess/policies` | JSON | MFA enforcement |
| Security defaults | Microsoft Graph `GET /policies/identitySecurityDefaultsEnforcementPolicy` | JSON | MFA enforcement |
| User registration details | Entra admin center, Authentication methods, "User registration details", Download | CSV (`UserPrincipalName`, `IsAdmin`, `IsMfaRegistered`, `IsMfaCapable`, `MethodsRegistered`, ...) | MFA registration |
| Admin role assignments | Entra admin center, Roles and administrators, download assignments | CSV | population of admin accounts |
| Managed devices | Intune admin center, Devices, All devices, Export | CSV | population of endpoints |
| Device inventory | Defender portal, Device inventory, Export | CSV (onboarding status, health state, last seen) | EDR state |
| Mailbox Protection Report | Veeam Backup for Microsoft 365 (`Get-VBOMailboxProtectionReport` or the console's report, CSV) | CSV (mailbox, protection status, last backup) | mailbox backup state |

The plan pins every reader's exact column headers from the vendors'
documentation and records the doc page next to each reader. The dev firm's
files use those headers.

### Populations

- **Accounts:** enabled member accounts from the users export. Guests and
  disabled accounts are excluded and listed in the report as excluded.
- **Admin accounts:** principals holding an admin role, from the
  role-assignments export, never from the `IsAdmin` column of the evidence.
- **Endpoints:** devices from the Intune export.

A population never comes from the export that supplies the evidence for
the same verdict.

### Proof rules

**MFA**

| Scope | Backed only if | Otherwise |
|---|---|---|
| `mfa.all_users` | Security defaults are enabled, **or** a Conditional Access policy with state `enabled` (not `enabledForReportingButNotEnforced`, not `disabled`) includes All users and All cloud apps and requires MFA in its grant controls; **and** no population account is excluded from that policy, directly, through an excluded role, or through an excluded group; **and** every population account has `IsMfaRegistered` true. | **Gap**, citing every excluded or unregistered account; or, when the exports are present and no policy qualifies, "no enforcement", naming any report-only or disabled policy that would otherwise have qualified. **Unchecked** when the users or registration export is missing, or when the CA export is missing and security defaults are not shown enabled. |
| `mfa.email` | As `mfa.all_users`, with the policy's applications All or Office 365. | As above. |
| `mfa.admins` | As `mfa.all_users` over the admin-account population; a policy that includes those admin roles also counts as enforcement. | As above, plus **unchecked** when the role-assignments export is missing. |
| `mfa.remote_access` | Never in this stack. | Always **unchecked**: "no export in this stack shows VPN or firewall MFA". |

Excluded roles are resolved to accounts through the role-assignments
export. Excluded groups cannot be resolved in v1 (no group-membership
export), so a policy that excludes any group is treated as excluding
unknown accounts: the verdict is **gap**, naming the group, never
**backed**. The same holds for an excluded role when the role-assignments
export is missing.

Every population account counts, including accounts that have no mailbox
or never sign in (service accounts, for example). They show up as gaps for
the reviewer to annotate rather than being filtered out by a rule.

**EDR**

| Scope | Backed only if | Otherwise |
|---|---|---|
| `edr.all_endpoints` | Every population device matches a Defender device that is onboarded, has health state `Active`, and was last seen within 7 days of the Defender export's `exported_at`. | **Gap**, citing every population device that is missing from Defender, not onboarded, not `Active`, or stale. Defender devices with no Intune match are listed as outside the population. **Unchecked** when either export is missing. |

Device matching uses the Entra device ID when both exports carry it, and
otherwise the device name compared case-insensitively with any domain
suffix removed; the report states which key it used. A failed match makes
a gap, never a backed verdict, so a matching error can only cost a false
gap.

**Backup**

| Scope | Backed only if | Otherwise |
|---|---|---|
| `backup.m365_mailboxes` | Every account in the population has a mailbox in the report that is protected, with a last backup within 24 hours of the report's `exported_at`. | **Gap**, citing every account whose mailbox is unprotected, stale, or absent from the report. **Unchecked** when the report or the users export is missing. |
| `backup.servers`, `backup.offline_copy`, `backup.restore_tested` | Never in v1. | Always **unchecked**, with the reason ("no export in v1 speaks to ..."). |

## Testing

**Unit tests**, at least one for every branch of every rule, on small
synthetic exports:

- MFA: security defaults on; policy `enabled`, report-only and `disabled`;
  an excluded account; an excluded unresolved group; an unregistered
  account; guests and disabled accounts left out of the population; each
  missing export.
- EDR: a device missing from Defender; not onboarded; inactive; last seen
  more than 7 days before `exported_at`; a Defender-only device; matching
  by device ID and by name.
- Backup: an unprotected mailbox; a stale backup; an account absent from
  the report; each missing export.
- Always-unchecked scopes stay unchecked whatever exports exist.
- Grounding: a tag whose quote is not in its document stops the run; an
  unknown control or scope stops the run.
- Readers: each parses a fixture built on its documented headers, and a
  missing required column stops the run naming file and column.

**Adversarial false-"backed" cases**, one test each:

- every account registered for MFA, but no enforcement;
- an enabled policy that excludes a group;
- Defender reports every one of its devices healthy while Intune holds one
  more device;
- the Veeam report lists only protected mailboxes and simply omits the
  unprotected account.

**Dev firm**: a made-up 12-person accounting firm with an insurer-style
application, a prose WISP, all eight exports, `tags.yaml` and `truth.yaml`.
Planted cases include an owner's account excluded from Conditional Access,
one account not registered for MFA, a laptop never onboarded to Defender,
one unprotected mailbox, WISP lines about VPN MFA and immutable backups
(must be unchecked), and several attestations that are genuinely backed.

**Bar:** every verdict matches `truth.yaml`; every planted gap cites the
right entities; **zero false "backed"** (hard). The dev firm is written by
the builder and the rules are deterministic, so this is a regression check,
not a blind test. Running the rules on a firm written by someone who has
not seen the code (the blind firm of sub-project 2) is what tests them.

## Repo

- `C:\Users\krist\Projects\attest`, its own git repo, local only.
- Python 3.12, its own venv, pytest. Third-party dependency: PyYAML only.
- No GIN import in sub-project 1; in sub-project 2 it talks to the SEAR
  sidecar over HTTP only.
- Layout: `attest/profile.py`, `attest/readers/` (one module per export
  format), `attest/rules/` (one module per control), `attest/compare.py`,
  `attest/report.py`, `attest/__main__.py` (`python -m attest check
  firm/<name>` prints the report and writes `firm/<name>/report.md`),
  `profile/controls.yaml`, `firm/dev/`, `tests/`.
- `LICENSE`: all rights reserved, for now.
