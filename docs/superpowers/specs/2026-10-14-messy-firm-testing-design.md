# Spec: testing the check against messy, realistic Microsoft 365 exports

**Date:** 2026-10-14
**Status:** Approved in brainstorm, awaiting review of this file
**Repo:** attest

## Problem

Every export the check has read so far was written by `scripts/build_dev_firm.py`. That script writes the API shapes we assume, for a firm whose mess we planted by hand. No real tenant, PowerShell session or Veeam server has produced any of it.

A real firm is messier than the dev firm in ways nobody planted. It has break-glass accounts, Microsoft-managed Conditional Access policies, re-imaged laptops, printers that Defender discovered, a backup job someone paused. Each of those is a chance for a rule to say backed when the claim fails. Each is also a chance for a reader to refuse real data and stop the run.

The README states the property that matters: a false backed is the error the rules are built to refuse. We have tested that property on one made-up firm and on single mutations of it. We have not tested it on real shapes, or on several kinds of mess at once.

## Goal

1. Show, on real export shapes and on combinations of real-world mess, that the check never says backed for a scope that an applied mess is declared to break.
2. Find every place where a reader stops on data a real tenant produces, and decide each one.
3. Measure how often realistic mess that leaves the truth unchanged still costs a false gap or an unchecked.

Confirming the export formats (strategy register, next step 1) happens along the way, because the seed is a real capture. It is not the goal.

## Decisions (brainstorm, 2026-10-14)

- **Goal: rules survive messiness.** Chosen over confirming formats first and over rehearsing the export session.
- **Source: real seeds, synthetic spread.** A small tenant we control is set up clean, captured, then made messy and captured again. Synthetic operators, calibrated against those captures, spread the mess into many combinations.
- **Tenant: Microsoft 365 Business Premium trial.** It is the stack the target firms run: Entra ID P1 (no PIM), Intune, Defender for Business. An E5 developer sandbox would carry P2 and Defender for Endpoint P2, which the firms do not have.
- **Machines: Azure, in the same tenant.** This laptop runs Windows 11 Home 25H2 with 16 GB of RAM and no Hyper-V. Veeam's documented minimum is 16 GB on its own. Nothing is installed on the laptop beyond what the export commands need.
- **Approach A with pinned archetypes.** Operators that declare their effect, run alone and in seeded combinations over the seed, plus four named combinations with hand-checked truth. Chosen over a hand-built gallery of firms (B) and over a world model with its own oracle (C), which would re-implement Conditional Access and could share the rules' blind spots.
- **No new dependency.** Combinations come from `random.Random(seed)` and a small greedy shrinker, not Hypothesis.

## Non-goals

- Running the check against a real client firm.
- Rehearsing the export session with a firm (consent prompts, timing, the reviewer's script).
- Regional or government clouds, and Veeam versions other than the one installed.
- Changing any rule in this work. A false backed the suite finds is fixed in its own change, with the shrunk combination as its regression test.

## Design

### The lab tenant

A Business Premium trial, set up as a clean firm in which every provable scope (`mfa.email`, `mfa.all_users`, `mfa.admins`, `edr.all_endpoints`, `backup.m365_mailboxes`) is backed.

- **Accounts.** Ten licensed members, so all of them fit Veeam Community Edition's 10-user limit. Two of them hold admin roles. Also one disabled former employee, one shared mailbox and one guest.
- **MFA policies.** Security defaults off. Conditional Access policies for MFA for all users and for admins, and a block on legacy authentication. The Microsoft-managed policies a new tenant gets stay in. They are real noise and belong in the seed.
- **MFA registration.** Each member gets a phone method added through Graph (`POST /users/{id}/authentication/phoneMethods`), with fictional 555-01xx numbers. No one signs in ten times with ten phones.
- **Endpoints.** Three Windows 11 VMs in Azure. Each is Entra-joined, auto-enrolled in Intune, and onboarded to Defender for Business through an Intune EDR policy.
- **Backup.** One Windows Server VM in Azure runs Veeam Backup for Microsoft 365 Community Edition. It backs up all ten mailboxes into one repository.
- **Cost control.** Every VM is deallocated when not in use.

### Captures

- **When.** After the tenant has settled for a day, because the registration report and Defender's `lastSeen` both lag.
- **How.** All eight exports are taken with the exact commands in `docs/engineering/exports.md`, once from Windows PowerShell 5.1 and once from PowerShell 7. The two serialize JSON differently.
- **Manifest.** `exported_at` is recorded the way `exports.md` says: after the export finishes, with a UTC offset.
- **seed-clean.** That first capture.
- **real-messy-1..n.** Messes made in the tenant itself, then captured again, one or a few at a time. The ones planned are listed with the catalog (✓ below).

### Scrubbing and storage

- Raw captures go to `firm/lab/raw/`, which is gitignored.
- `scripts/scrub_lab_capture.py` replaces:
  - the tenant's `onmicrosoft.com` domain with `harborlab.example`
  - the tenant ID
  - the admin's real name and address
  - every IP address, including Defender's `lastIpAddress` and `lastExternalIpAddress`
- Random sandbox GUIDs are kept. They identify nothing outside the lab.
- The scrubbed copy goes to `firm/lab/<capture>/exports/`, with its `manifest.yaml`.
- A capture folder holds `exports/` only. `.gitignore` refuses `application.txt` and `wisp.txt` so that a firm's real documents cannot be committed. The harness assembles each test firm from `firm/dev/attest/`, `firm/dev/tags.yaml` and a capture's exports. The tags name controls and scopes, not people, so the dev firm's sentences fit the lab's exports.
- **Guard test.** It fails if any file under `firm/lab/` (outside `raw/`) contains any of these:
  - a public IPv4 address
  - `onmicrosoft.com`
  - an address on a deny-list kept in the test, beginning with the admin's real address

### Operators and their effects

An operator edits the parsed exports of a firm to make one real-world mess. It declares:

- `effect`, one of four:

  | Effect | Meaning | Checked as |
  |---|---|---|
  | `breaks` *scopes* | The truth fails for those scopes | **Hard:** never backed |
  | `holds` | The truth is unchanged; the rules may lose sight of it | Any verdict is allowed. A drop to gap or unchecked counts as noise cost |
  | `inert` | Serialization only | **Hard:** status and entities identical to the seed's |
  | `stops` | A refusal the docs promise | **Hard:** the run stops, and the reason contains the declared text |

- `why`: one line. **Required for `holds`.** It says why the truth is unchanged. A wrong `holds` label can hide a false backed, so review reads these first.
- `alone`: the exact status each provable scope gets when this operator is the only one applied to the seed. For a `holds` operator this pins today's behaviour, false gaps included, so a change is noticed.
- `needs`: the rows it requires (for example, "a laptop in both Intune and Defender"). An operator whose needs are not met is skipped in that combination.
- `touches`: the entities it edits. Two operators that touch the same entity are never combined.
- `twin`: the real capture that shows this mess, if there is one.
- `may_stop`: a reason text, set only after a stop on realistic data has been decided and the refusal kept (see Failures).

### The starting catalog

✓ means the mess is also made for real in the tenant and captured as a twin.

| Area | Operator | Effect |
|---|---|---|
| MFA | The Microsoft-managed policies a new tenant gets: admin portals, per-user MFA users, risky sign-ins. Already in seed-clean; this operator adds them to the dev seed | holds |
| MFA | Two break-glass accounts excluded by ID from every policy ✓ | breaks `mfa.all_users` |
| MFA | An "MFA exclusions" group excluded from the all-users policy ✓ | breaks `mfa.all_users` |
| MFA | The all-users policy limited to the Office 365 app group | breaks `mfa.all_users`; holds `mfa.email` |
| MFA | Grant through `authenticationStrength` instead of `builtInControls: ["mfa"]` | holds |
| MFA | Per-user MFA in place of Conditional Access | holds (no export shows per-user MFA) |
| MFA | An admin role held by a role-assignable group whose members are registered | holds |
| MFA | The same, with one unregistered member | breaks `mfa.admins` |
| MFA | An admin role held by a service principal | holds |
| MFA | A user created after the registration report last refreshed ✓ | breaks `mfa.all_users` (unchecked) |
| EDR | A laptop re-imaged: a stale and a fresh record under one name, in Intune and in Defender ✓ | holds |
| EDR | A VM left off for 8 days ✓ | breaks `edr.all_endpoints` |
| EDR | A VM whose sensor is cut off, reported `ImpairedCommunication` ✓ | breaks `edr.all_endpoints` |
| EDR | Devices Defender discovered but did not onboard: a printer, an unmanaged PC, one with a null `computerDnsName` ✓ | holds |
| EDR | A device renamed after onboarding ✓ | holds |
| EDR | An Intune device with no primary user (`userPrincipalName: ""`) | inert |
| Backup | An 11th mailbox user, over the Community Edition limit and not backed up ✓ | breaks `backup.m365_mailboxes` |
| Backup | The backup job paused for 2 days ✓ | breaks `backup.m365_mailboxes` |
| Backup | A shared mailbox listed by Veeam but not backed up ✓ | breaks `backup.m365_mailboxes` |
| Backup | A Veeam `Email` that is the primary SMTP address, not the UPN | holds (a documented false gap) |
| Format | The same capture from PowerShell 5.1 and from PowerShell 7 ✓ | inert |
| Format | UTF-16, UTF-8 with BOM, CRLF; fields and rows reordered; unknown fields added | inert |
| Format | A Veeam export of one user, written as one object | inert |
| Format | The users export fetched with `$top=5`, so it carries `@odata.nextLink` ✓ | stops |
| Format | A Veeam time with no UTC offset | stops |

The catalog grows. A new real-world mess gets a new operator, not an edit to an old one.

### Fidelity check

Every ✓ operator, applied to seed-clean, must produce the shape its twin capture shows:
- the same field names per record type
- the same JSON value types
- the same records added, removed or changed

IDs, times and IP addresses are ignored. A mismatch is fixed in the operator, never in the capture.

### The harness

- `tests/messy/operators.py`: the catalog.
- `tests/messy/compose.py`:
  - assembles a temporary firm from a seed's exports and the dev firm's text and tags
  - applies the operators
  - runs `attest.compare.check`
  - judges the result against the declared effects
- `tests/messy/archetypes/<name>.yaml`: the pinned combinations and their truth.
- **The seed.**
  - Until the tenant exists, the seed is the dev firm healed of its planted gaps. `HEAL` moves from `tests/test_dev_firm.py` to `tests/messy/` so both suites share it.
  - Once seed-clean is committed, it becomes the seed.
- **Combinations.** Each combination applies one to four operators, chosen by `random.Random(seed)` over a fixed list of seeds, so every failure replays.
- **Shrinking.** When a combination breaks a hard property, a greedy shrinker removes one operator at a time while the failure persists, and reports the smallest set.

Properties, for every run:

1. **No false backed.** No scope that an applied operator declares broken comes out backed.
2. **Inert is identical.** If every applied operator is `inert`, every tag's status and entities equal the seed's.
3. **Promised stops happen.** If any applied operator is `stops`, the run stops with that reason.
4. **No undecided stops.** A run stops only when an applied operator declares `stops` or `may_stop`.

Noise cost is measured, not asserted: for each `holds` operator, how often a scope it touches drops from backed, and to what.

### Tests

- **Default `pytest` run** (fast):
  - every operator alone on the seed, against its `alone`
  - the four archetypes
  - 200 seeded combinations under properties 1 to 4
  - the fidelity check for every twin capture present
  - the scrub guard
- **`pytest -m messy`** (on demand):
  - 5,000 combinations
  - writes `firm/lab/messy-summary.md`, dated, with:
    - the false-backed count, which must be 0
    - every stop and its reason
    - the noise cost of each `holds` operator
  - The engineering register cites that summary with its date, the way it cites the dev firm's results.

### Pinned archetypes

Each has a hand-checked truth file, in the same form as `firm/dev/truth.yaml`.

1. **The MSP-run firm:** break-glass exclusions, the Microsoft-managed policies, an `authenticationStrength` grant, an admin role held by a service principal.
2. **The re-imaged fleet:** a re-imaged laptop, a renamed device, a discovered printer, one VM gone stale.
3. **The backup over its limit:** the 11th user, a shared mailbox not backed up, a paused job.
4. **The PowerShell 5.1 admin:** UTF-16 files, `/Date(ms)/` times, a Veeam export of one object. Every verdict equals the seed's.

### Failures and what each means

- **A false backed:** a rules bug. The shrunk combination becomes a named regression test, and the rule is fixed to fail closed, in its own change.
- **A stop on data the tenant really produced, or an operator modelled on it:** the reader may be too strict for real exports. Decide case by case:
  - relax the reader and record why; or
  - keep the refusal, set `may_stop` on the operator, and change `exports.md` so the firm's export avoids it.
- **An `inert` operator that changes a verdict:** a serialization bug.
- **A fidelity mismatch:** fix the operator.
- **High noise cost on a `holds` operator:** a product decision, not a test failure. Either document it as a known false gap in the engineering register, or teach the rule.

### Limits

- One tenant, one Veeam version, one month. Regional clouds and other Veeam versions stay unconfirmed.
- Some things no export in this set shows:
  - an MSP's admins who come in through GDAP
  - per-user MFA
  - roles a user is only eligible for under PIM

  These are documented blind spots, not operators.
- Every effect label is a human judgment. The `why` line on each `holds` operator is the control on that.
- The spread covers the catalog and nothing else.

## Order of work

1. The harness and the catalog, with the healed dev firm as the seed. Operators with no twin run from day one.
2. The tenant:
   - set it up
   - capture seed-clean from PowerShell 5.1 and 7
   - scrub and commit it, with the guard test

   This settles most of strategy next step 1: Veeam's field names, and whether its `Email` is the UPN.
3. Switch the harness to seed-clean. Settle every stop it surfaces.
4. Make the real messes, capture the twins, and add the fidelity checks.
5. The 5,000-combination run, its summary, and the engineering register update.
6. Cancel the trial and delete the Azure resources before any billing.

Steps 2, 4 and 6 are done by hand in the tenant and the Azure portal. The implementation plan writes them as a runbook, `docs/engineering/lab.md`, so the lab can be rebuilt the same way after the trial lapses.

## Open questions

- **Do enrolled phones count as endpoints** for `edr.all_endpoints`? If an Intune-enrolled iPhone with no Defender record makes "EDR on all endpoints" a gap, every firm with managed phones gets that gap. This is a product decision. Until it is made, no operator adds a phone.
- **Does Defender's List machines API serve Defender for Business?** Microsoft's page for it did not confirm this. The lab tenant answers it on the first capture. If it does not, the EDR rule has no input for the firms we sell to, and that is a strategy finding before it is a test finding.
- **Windows 11 on Azure under Business Premium.** Confirm that Business Premium seats carry the right to run Windows 11 VMs on Azure before building the endpoints. If they do not, the endpoints run as Windows Server or as Azure Virtual Desktop hosts.
- **The trial's terms** (length, whether it needs a card, when billing starts) are confirmed at sign-up and noted here.

## Facts checked during the brainstorm

- **The free E5 developer sandbox** is for Visual Studio Professional or Enterprise subscribers and certain Microsoft partners. ([Microsoft 365 Developer Program](https://learn.microsoft.com/it-it/office/developer-program/microsoft-365-developer-program))
- **Veeam Backup for Microsoft 365 Community Edition** is free for up to 10 users. ([Veeam](https://veeam.com/free-backup-microsoft-office-365.html)) The current system requirements list 8 cores and 16 GB, and Windows 11 22H2 and earlier. ([requirements](https://helpcenter.veeam.com/docs/vbo365/guide/vbo_system_requirements.html))
- **Defender's List machines API** returns `404 Not Found` when there are no recent machines, not an empty list. Microsoft's example response has no `onboardingStatus` field. ([List machines API](https://learn.microsoft.com/en-us/defender-endpoint/api/get-machines)) Today's export command would throw on the 404 and write no file, so the check would read the EDR export as missing.
- **This laptop:** Windows 11 Home 10.0.26200, 15.7 GB of RAM, an i7-13700H, Windows PowerShell 5.1 only, no Graph PowerShell module, no VirtualBox.
