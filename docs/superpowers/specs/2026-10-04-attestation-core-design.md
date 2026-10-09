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
  tags.yaml                  confirmed tags, one per claim, several per
                               attestation: {id, doc, quote, control, scope}
  truth.yaml                 dev firm only: expected verdict per tag id,
                               and the entities each gap must cite
profile/controls.yaml        controls, their scopes, and the proof rule
                             each scope uses
```

`exported_at` lives in the manifest because the API exports do not record
when they were taken. Staleness ("last backup within 24 hours", "last seen
within 7 days") is measured against it.

### Pipeline

1. **Load tags.** Each tag's `quote` must be an exact substring of its
   `doc`. If not, the run stops with an error naming the tag. A tag whose
   control or scope is not in the profile also stops the run.
2. **Read exports.** One deterministic reader per format turns rows into
   facts. Every fact keeps its source as `file:row`. A reader that finds a
   required field missing, or a value of the wrong kind, stops the run with
   an error naming the file, row and field; it never guesses.
3. **Apply the scope's proof rule** to produce the verdict, a one-line
   reason, and the cited facts.
4. **Write the report** (Markdown; also printed): per attestation the quote
   and its document, control and scope, verdict, reason and cited rows. A
   **backed** verdict also states the population's size and source. A
   summary line counts backed, gap and unchecked.

### Exports (v1)

*Amended 2026-10-04 during planning.* The first draft named portal CSV
downloads. Microsoft does not document those column headers; it documents
the API resources exactly. Every Microsoft export is therefore the JSON of
a documented API call, which the firm runs read-only (Microsoft Graph
PowerShell or Graph Explorer) while the reviewer watches. Each reader
accepts a bare JSON list, a single object, or a Graph/Defender page
`{"value": [...]}`, in UTF-8 or the UTF-16 that Windows PowerShell 5.1
writes by default.

| Reader | Source | Fields used | Used for |
|---|---|---|---|
| `entra_users` | Graph `GET /users?$select=id,userPrincipalName,displayName,accountEnabled,userType` ([user](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0)) | `id`, `userPrincipalName`, `displayName`, `accountEnabled`, `userType` | population of accounts |
| `entra_registration` | Graph `GET /reports/authenticationMethods/userRegistrationDetails` ([userRegistrationDetails](https://learn.microsoft.com/en-us/graph/api/resources/userregistrationdetails?view=graph-rest-1.0)) | `id`, `userPrincipalName`, `isMfaRegistered` | MFA registration |
| `entra_ca_policies` | Graph `GET /identity/conditionalAccess/policies` ([conditionalAccessPolicy](https://learn.microsoft.com/en-us/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0)) | `id`, `displayName`, `state`, `conditions`, `grantControls` | MFA enforcement |
| `entra_security_defaults` | Graph `GET /policies/identitySecurityDefaultsEnforcementPolicy` | `isEnabled` | MFA enforcement |
| `entra_role_assignments` | Graph `GET /roleManagement/directory/roleAssignments?$expand=principal` ([unifiedRoleAssignment](https://learn.microsoft.com/en-us/graph/api/resources/unifiedroleassignment?view=graph-rest-1.0)) | `principalId`, `roleDefinitionId`, `directoryScopeId`, `principal` (`@odata.type`, `userPrincipalName`, `displayName`) | population of admin accounts; excluded roles |
| `intune_devices` | Graph `GET /deviceManagement/managedDevices` ([managedDevice](https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice?view=graph-rest-1.0)) | `id`, `deviceName`, `azureADDeviceId`, `operatingSystem` | population of endpoints |
| `defender_machines` | Defender for Endpoint API `GET /api/machines` ([Machine](https://learn.microsoft.com/en-us/defender-endpoint/api/machine)) | `id`, `computerDnsName`, `aadDeviceId`, `onboardingStatus`, `healthStatus`, `lastSeen` | EDR state |
| `veeam_users` | Veeam Backup for Microsoft 365 PowerShell: `Get-VBOEntityData -Type User -Repository <repo>`, selected and `ConvertTo-Json` | `Email`, `IsMailboxBackedUp`, `MailboxBackedUpTime` | mailbox backup state |

The `veeam_users` field names come from Veeam's published PowerShell
examples, not its reference documentation; the documented REST form of the
same data carries no backup timestamps, so it cannot prove a daily backup.
**The first real export must be checked against these names before any
paid check relies on this reader.** A reader that finds a field missing
stops the run, so a mismatch is loud, never silent.

`docs/engineering/exports.md` in the repo gives, per reader, the command that produces
the export and the documentation page for its fields.

### Populations

- **Accounts:** enabled member accounts from the users export. Guests and
  disabled accounts are excluded and listed in the report as excluded.
- **Admin accounts:** principals holding an admin role, from the
  role-assignments export, never from the registration export's `isAdmin` field.
  Any assignment counts, tenant-wide or scoped. A role held by a group
  makes `mfa.admins` **unchecked** (its members are unknown in v1); so does
  a user principal missing from the users export. Disabled holders are not
  counted. Service principals are not accounts and are not counted.
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

*Amended 2026-10-04 during planning.* What "requires MFA" and "applies to
all users" mean, from the documented Conditional Access resources:

- **Requires MFA.** The grant controls contain `mfa`, or an authentication
  strength that is one of Microsoft's three built-in MFA strengths
  (Multifactor authentication, Passwordless MFA, Phishing-resistant MFA);
  and either the operator is `AND` or there is no alternative control. A
  grant of "MFA **or** a compliant device" (operator `OR`) does not require
  MFA: a compliant device satisfies it alone. A policy whose controls
  include `block` does not count.
- **No narrowing condition.** A policy counts only if nothing limits when
  it applies beyond its users and applications: no client app types other
  than `all`, no location include other than All and no location exclude
  (the "MFA except at the office" case), no platform include other than
  all and no platform exclude, no device filter, no sign-in, user,
  service-principal or insider risk levels, no authentication flows, no
  client applications, and no excluded applications, application filter,
  user actions or authentication contexts.
- **Security defaults** count as enforcement, as decided in the
  brainstorm. The report states what that means: Microsoft prompts for MFA
  when it judges it necessary, not on every sign-in.
- **An empty population** (an export with no counted accounts or devices)
  is **unchecked**, never a vacuous **backed**.
- **Enforcement unknown:** when no Conditional Access policy enforces MFA
  and there is no security-defaults export to rule security defaults out,
  the verdict is **unchecked**, not **gap**.

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
- Readers: each parses a fixture built on its documented API fields, and a
  missing required field stops the run naming file, row and field.

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

## Results

Dev firm (`firm/dev`, Harbor & Pine CPA, generated by
`scripts/build_dev_firm.py`): 14 tags on 12 attestations, `backed 2, gap 6,
unchecked 4` (the count line counts attestations), every tag's verdict
matching `truth.yaml` and every gap citing exactly its planted entities.
**Zero false "backed".** Suite: 749 passed, 2 skipped (the 2 symlink tests
skip on a machine without symlink privilege). The report lists the eight
exports, all taken at 2026-10-01T15:00:00+00:00.

- Backed: both admin-MFA attestations (4.3 and the WISP line). The owner's
  exclusion from the all-users policy does not touch them because she holds
  no admin role. Both role holders are enforced by both policies, the
  all-users policy and the admin policy, as the report says ("enforced by
  'Require MFA for all users', 'Require MFA for administrators'").
- Gap: email and all-staff MFA (owner excluded, new hire unregistered), over
  "12 enabled member accounts from users.json; not counted: guests
  audit.partner_auditfirm.example#EXT#@harborpine.example; disabled
  sam.lowe@harborpine.example"; EDR (the new hire's laptop is missing from
  Defender; the reason also records that 10 devices matched Defender by Entra
  device ID and 1 by device name, and that the file server, in Defender but
  not Intune and healthy, sits outside the population); mailbox backup (one
  mailbox not backed up), over "12 enabled member accounts from users.json;
  plus disabled accounts Veeam lists: sam.lowe@harborpine.example; not
  counted: guests audit.partner_auditfirm.example#EXT#@harborpine.example":
  the former employee's mailbox is still in Veeam, so it is counted, and it
  is backed up.
- The two WISP lines that make two claims each carry a second tag on an
  always-unchecked scope (alert monitoring; OneDrive and SharePoint backups),
  and each line's verdict is the worse of its tags': both are gaps.
- Unchecked: VPN MFA (both documents), because no export in this stack shows
  VPN or firewall MFA, and immutable backups (both documents), because no
  export in v1 speaks to offline or immutable backup copies.

`tests/test_dev_firm.py` also checks the firm end to end on copied files:
healed of every planted gap, every tag whose scope can be proven is backed,
every always-unchecked scope is unchecked, and both compound lines are
unchecked; nine single mutations of the healed firm (an excluded GUID
upper-cased or braced, an excluded role GUID upper-cased, an admin excluded
from the all-users policy, an unhealthy Defender-only machine, an unprotected
disabled account in Veeam, a users export two days older, an offset-less
`lastSeen`, a single-object users export) each give the verdict, or the input
error, they should; and each compound WISP line tagged by clause instead of
whole is still one unchecked attestation quoting the whole line, with no
section showing a fragment.

This is a regression check, not a blind test: the builder wrote the firm and
the rules are deterministic. The blind firm of sub-project 2 tests the rules
on data written by someone who has not seen the code.

## Amended 2026-10-05 (review fixes and decisions)

The review of each task and the final whole-branch review added the
behaviours below, and the user's four decisions of 2026-10-05 settled the
rest (marked "decision 1" to "decision 4"). Where they differ from the
sections above, these win. Each line says what the tool does, then why.

**Registration**

- An account the registration export has no row for is missing evidence:
  the verdict is **unchecked** ("the registration export has no record of"),
  unless another account already shows a gap, which then also names the
  accounts with no record. Why: absence is not a shown failure, but it must
  not hide a failure shown elsewhere.

**Times**

- A Defender `lastSeen` or Veeam backup time later than its export's
  `exported_at` is a gap, never recent or fresh. Why: a time after the export
  cannot be true, so it cannot show a recent check-in or backup.
- Every time must carry a UTC offset: the manifest's `exported_at`,
  Defender's `lastSeen` and Veeam's backup time (a PowerShell `/Date(ms)/`
  counts as UTC). A time with none, or whose UTC moment is out of range,
  stops the run naming file, row (or manifest entry) and field. Why: read as
  UTC, a local time east of UTC looks fresher than it is.
- The exports one verdict reads must be taken within 24 hours of one another
  (latest `exported_at` minus earliest at most 24 hours), or the verdict is
  **unchecked**, naming the earliest and latest (decision 4). MFA reads the
  population's exports, registration, security defaults when exported,
  Conditional Access unless security defaults are on, and role assignments
  when it reads them; EDR reads Intune and Defender; backup reads users and
  Veeam. Why: an account list from January checked against an October backup
  report misses every account added since.

**Reader input**

- Duplicate rows stop the run, naming both rows, in six readers:
  `entra_users` (by `id`, and by `userPrincipalName` case folded),
  `entra_registration` (by `id`), `entra_ca_policies` (by policy `id`),
  `intune_devices` (by `id`), `defender_machines` (by `id`) and `veeam_users`
  (by `Email`, case folded); object IDs are compared in canonical form.
  `entra_security_defaults` must hold exactly one policy. Why: two records
  for one entity can disagree, and a rule that picked one would pick
  silently. `entra_role_assignments` is exempt: a repeated assignment grants
  nothing a single one does not, so it cannot change who is counted or
  excluded.
- A `userPrincipalName` or Veeam `Email` with leading or trailing whitespace
  stops the run. Why: a padded copy of an address passes as another account.
- Object IDs (users and registration `id`, role assignment `principalId` and
  `roleDefinitionId`, and the Conditional Access user, group and role lists)
  must be GUIDs and are stored in canonical lower case; device IDs must be
  GUIDs or null, the all-zero GUID meaning not joined. The Conditional Access
  user lists recognise Graph's keywords in any case and store Graph's
  spelling: `includeUsers` takes `All`, `None` and `GuestsOrExternalUsers`,
  `excludeUsers` only `GuestsOrExternalUsers`; group and role lists take
  GUIDs only; anything else stops the run. Why: an exclusion spelled unlike
  the users export (upper case, braces, `All`) matched no account and so
  excluded nobody, a false backed.
- An export that is one page of several (`@odata.nextLink`) stops the run.
  Why: a truncated list shrinks the population.
- A population export (users, Intune devices, role assignments) must be a
  list or a Graph page; a single object stops the run. Why: a
  `GET /users/{id}` response read as the population is a firm of one.
- An optional field of the wrong type (a numeric `userType`, a principal
  `displayName` of 7) stops the run naming the field; Intune
  `operatingSystem` is optional, as no rule reads it. Why: a bad value must
  stop the run at its row, not fail inside a rule.

**Roles**

- A Conditional Access role condition targets only assignments whose
  `directoryScopeId` is `"/"` (tenant-wide); an assignment at any scope (an
  administrative unit, or an `appScopeId`, kept apart as the assignment's
  app scope) still counts for exclusion. Why: a role policy does not apply
  to a scoped assignment, and over-excluding can only cost a false gap.
- An admin role held by a principal no export resolves to accounts (a group,
  or a kind Graph adds later) makes `mfa.admins` **unchecked**, and an
  excluded role held by one counts as excluding every account; so does an
  excluded role when there is no role-assignments export. A role holder
  missing from the users export makes `mfa.admins` unchecked. Why: such a
  principal's accounts are unknown in v1.

**Guests**

- An exclusion of guest or external user types (`excludeGuestsOrExternalUsers`,
  or the legacy `GuestsOrExternalUsers` in `excludeUsers`, in any case) counts
  as an exclusion: `internalGuest` and `b2bCollaborationGuest` exclude the
  accounts whose `userType` is Guest; any other type, an exclusion naming no
  type, or the legacy keyword excludes every account. Why: only a guest
  `userType` identifies those types in the exports; the other types name
  accounts no export identifies.

**Conditional Access reader**

- Narrowing is an allow-list: a condition key the reader does not know (in
  the conditions, or inside users, applications, locations or platforms)
  that carries a value narrows the policy, as "unknown condition <key>";
  OData annotations never do. Why: a condition Graph adds later must not pass
  unseen.
- A grant key the reader does not know counts as another way through the
  grant, so with operator OR the policy does not require MFA. Why: the same,
  for grant controls.
- An empty or missing `clientAppTypes` stops the run, and so does any field
  of the wrong shape. Why: Graph marks `clientAppTypes` required; an empty
  one is missing evidence, not "all".

**EDR matching**

- Matching is one-to-one: a Defender machine never covers two Intune
  devices, and a name that fits two machines, or one machine two devices
  want, matches none. Why: at most one of them can be that machine, and
  nothing says which.
- When Defender holds several records for one Entra device, the latest
  `lastSeen` decides; a tie for the latest is a gap. Why: a re-imaged device
  leaves an old record, and a tie says nothing about which is the device.
- Two different Entra devices are never paired by name. Why: one name on two
  Entra devices is two machines.
- A Defender machine no Intune device could be, whose onboarding status is
  not `Unsupported` (case folded), last seen within 7 days of the export or
  after it, and not onboarded and Active, is a gap naming it ("in Defender
  but not Intune and not healthy"); one seen earlier or never is listed with
  when it was last seen and changes nothing (decision 3), and so is a healthy
  one seen after the export, since only onboarding and health decide the gap
  (final re-review). Why: it is an endpoint Defender shows unprotected now,
  whatever Intune knows, and a time after the export cannot show it healthy.

**Backup population**

- Every disabled account whose UPN matches a Veeam row joins the population,
  and the population description names them ("plus disabled accounts Veeam
  lists") (decision 3). Why: shared mailboxes are disabled user objects, and
  Veeam listing one shows it holds mail.
- Veeam rows that match no account at all are listed in the reason with their
  state ("Veeam rows matching no account") and change nothing. Why: they lie
  outside the population, but a reviewer should see them, as EDR lists its
  Defender-only machines.

**Tags**

- A tag's document must be a UTF-8 file under the firm's `attest/` folder; a
  leading byte-order mark is dropped and line endings are read as LF. Why:
  `tags.yaml`, the exports and an earlier report hold the very quotes they
  would be asked to ground.
- A tag must name its document in one canonical form, its resolved path
  relative to the firm folder in forward slashes and on-disk letter case
  (`attest/wisp.txt`); any other spelling (`attest/./wisp.txt`,
  `attest\wisp.txt`, `attest/WISP.txt`, `attest/../attest/wisp.txt`) is
  refused, naming the form to write, and never rewritten (third review G1).
  Why: attestations group tags by document, so one document under two names
  split one passage into two attestations, and a clause on a provable scope
  came out backed on its own.
- A tag must not name, under another name, a file another tag already names
  (same `st_dev` and `st_ino`): a hard link, or a letter case that a
  case-insensitive filesystem other than Windows' does not resolve, passes as
  canonical yet names one file twice; it is refused, naming the first name
  (fourth review N1). A filesystem that reports no file identity is not
  compared. Why: the same split as two spellings.
- Every field must be a string with a letter or digit in it, and an id, doc,
  control or scope must not begin or end with whitespace or an invisible
  character. Why: a blank or invisible value grounds in nearly any document,
  and an invisible edge makes a lookalike id.
- A repeated key in any YAML file (tags, manifest, profile) stops the run.
  Why: plain YAML keeps the last and silently drops the rest.
- A quote must appear exactly once in its document (overlapping occurrences
  counted, in the same LF text grounding uses) and contain at least three
  words, a word being a whitespace-separated token with a letter or digit in
  it (decision 2). Why: a short or repeated quote does not say which passage
  is attested.
- Several tags may share one quote, and every claim in a quote gets a tag
  (decision 1). An attestation is the set of document lines its tags touch:
  grounding records the line range each quote touches, in the same LF text,
  and tags in one document whose ranges meet, directly or through other tags,
  are one attestation (final re-review). Its verdict is the worst of its
  tags' (any gap, else any unchecked, else backed), so tags on one passage
  share one verdict, and a WISP written as one long paragraph per line rolls
  all of that paragraph's sentences into one attestation. Why: a quote that
  makes two claims, tagged with one scope, would come out backed on evidence
  for only one of them, and tagging its clauses separately must not show a
  backed fragment of a passage that also makes another claim.
- Grouping has two limits the tagger must respect (third review M2, M3). A
  sentence wrapped across lines, tagged with one quote per clause, stays split
  into separate attestations, one per line its clauses touch; tag a wrapped
  sentence with a quote that spans its lines, or keep one sentence or
  question per line. Tags group only within one document: a claim must be
  tagged in the document it is quoted from, and a copy of a document under
  another name is a separate document. Why: grouping knows lines and
  documents, not sentences or content.
- The report refuses a tag with no line range (one built by hand, never
  grounded by `load_tags`), naming it (third review M1). Why: grouping such
  tags by their exact quote instead was the hole line grouping closed, and
  later sub-projects may build tags directly.
- Two always-unchecked scopes take the claims no v1 export speaks to:
  `edr.alert_monitoring` ("no export in v1 shows that alerts are monitored")
  and `backup.m365_files` ("no export in v1 shows OneDrive or SharePoint
  backups") (decision 1). Why: a claim with no evidence must still be tagged,
  and must come out unchecked.

**CLI**

- Exit code 0 when the check ran and its report was written; 2 for an input
  problem (an error naming the file and row, or the tag) or a report that
  cannot be written; an unexpected error is re-raised with its traceback.
  Why: a script must tell a checked firm from a failed run.
- A run that fails replaces the report with a stub ("CHECK FAILED: <why>"),
  and a report is written whole or not at all, before it is printed. Why: an
  earlier run's verdicts must never look current, a failed write must not
  leave half a report, and a console that cannot print it must not lose it.
- Only the tool's own report is replaced: an existing `report.md` that begins
  with "# Attestation check:", or a new one in a folder that has a
  `tags.yaml`. Why: a typo in the path must not cost anyone an unrelated file.

**Report**

- One section per attestation quotes its whole lines, is headed by its
  combined verdict, and lists each of its tags with its control and scope,
  verdict, reason, population, entities and cited rows; the count line counts
  attestations. Firm text stays on one
  line, and a quote stays inside its blockquote. Why: a firm's words must not
  start a heading or list of the report.
- Under the count line, an exports table gives each export's reader, file,
  `exported_at` in UTC and row count (final review I2). Why: a reader of the
  report must see which exports, taken when, the verdicts rest on.

## Amended 2026-10-08 (documents read by intake)

- Attestation documents may come from intake (intake `docs/format.md`, format 1): `attest/<name>.txt` with
  `attest/<name>.txt.map.json` beside it, the original under `sources/`. attest reads the sidecar with the
  standard library and imports no intake code (intake spec, decision 3).
- The run stops on a sidecar of another format, a text edited after it was read (the hash is taken on the LF
  text, so a CRLF checkout still matches) or an incomplete reading. It also stops on a damaged sidecar: a field
  attest reads missing or of the wrong type, or a quoted line with text on it that has no entry. Why: a damaged
  reading must not vouch for anything, and the stop names the field or the line.
- A tag is refused (the run stops with the tag and the reason named, like the other grounding refusals) when its
  quote touches a line read by OCR (`how` is `ocr` or `rescanned`), a `quoted` line, a `no_header` table row, a
  line read in a way attest does not know (`how` is neither `text_layer` nor `native`), a line on a page the
  reading does not list, or a line on a page whose parse or OCR grade is below GOOD or is not a grade attest
  knows (an absent grade is not a refusal); and every table row when intake's table-fidelity bar is missed
  (`REFUSE_TABLE_ROWS` in `attest/reading.py`). attest vouches only for what it recognises.
- Two departures from the intake spec's wording, with their evidence (intake RESULTS.md; scratch run of
  2026-10-08): the OCR rule replaces "any grade below GOOD" for OCR text, because Docling's OCR grade stayed
  EXCELLENT on pages that lost up to 27% of their words; and the layout grade is not a reason to refuse, because
  a born-digital form's layout was graded FAIR (0.68) while its text layer read exactly.
- Each attestation in the report gets a `- source:` line: the original's name, the first 12 hex digits of its
  hash and the pages, slides or cells its lines came from, or `plain text, no source location`.
