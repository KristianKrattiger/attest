# Engineering register

This file is the engineering register. A claim here is a statement about what is built and what was measured, and it is judged by the code, the tests, and the recorded measurements. Unmeasured means unmeasured.

## 3. Engineering register

### 3.1 What exists

| Piece | What it is | Status | License |
|---|---|---|---|
| **GIN** | The research engine: constrained answering (SEAR), a tiered document store, an evaluation harness, two-to-three-node federation, typed links between documents, a labeling tool | Phases 1 and 3 built and measured; training loop (Phase 4) designed, not built | Open, public |
| **Assay** (inside Receipts) | A model proposes quote pairs; a fixed rule keeps only quotes that appear word for word in the fetched source | Built, published, re-runnable | Open (MIT) |
| **Receipts** | Vendor claims set against independent sources on the live web | Built; runs on cloud browsers | Open (MIT) |
| **claim-record** | A local Assay with a web page: a Claim pile against a Record pile | Built | Copy of Assay |
| **SEAR proposer** | GIN's constrained local model serving as the Assay's proposer, so material never leaves the machine | Merged into GIN and pushed (2026-10-05); its relation decline failed its bar (3.3) | Open, in GIN |
| **attest** | The deterministic attestation check | Core built, reviewed and pushed to a private repository (2026-10-05) | Closed |

### 3.2 SEAR: answers that can only quote

SEAR (Sparse Epistemically Anchored Reasoning) constrains a language model while it generates, not after:

- **Retrieval** is hybrid: full-text and vector search over a Postgres store, merged by reciprocal rank fusion with a stable tie-break.
- **Decoding is copy-only.** A custom logits processor plugged into llama.cpp restricts each next token to ones that continue a passage present in the retrieved material. The model cannot write a sentence the material does not contain.
- **Refusal is a state, not a tone.** When retrieval confidence is too low or no passage can be started, SEAR returns an explicit "not supported" result instead of text.

Measured results:

- **Zero fabricated answers** on the 20-question evaluation set, on both CPU and GPU. The one difference between the two backends was a near-tie refuse-or-answer decision caused by floating-point non-determinism, not by the method.
- The same behavior holds across two different open base models (Mistral 7B and Qwen2.5 7B), so the guarantee comes from the constraint and not from the model.
- Federation was measured live across three nodes, with mutual TLS and streamed traces: questions route to the node that holds the answer, attribution survives the transfer, and nodes that hold nothing refuse honestly.

What SEAR does not do is judge whether two quoted passages *relate*. That is the subject of the next section.

### 3.3 Where the model-proposes approach fails: relations

The Assay works in two steps. A model proposes which claim and which evidence belong together and how they relate; a deterministic gate then re-derives every quoted span from the actual bytes and discards anything it cannot find. **The quoting step works. The relation step does not.**

- On the live run of 2026-09-25, **none of the 21 relational rows the gate admitted held up under blind labels.** Every quote was real; the pairings were topic matches, not relations.
- A follow-up let the local model answer "no relation" (`Relation: none`) and drop the pair. On 35 labeled rows it declined 25 of 30 non-relations (bar: 24) but **kept only 2 of 5 real relations (bar: 4)**. The result is recorded as a failure.

On a firm's files no outside verifier may run, so a local relational row cannot be checked by a stronger model. **Every local relational row is treated as unvetted; a person reviews it before it becomes a finding.** This is why the check does not pair claims with evidence through a model at all ([section 2.4](../conceptual/README.md#24-relatedness-is-not-relation)).

### 3.4 attest: the deterministic attestation check

**What goes in.** A firm folder holds three things:

1. the attestation documents as plain text (the insurance application's questions with their answers, and the WISP);
2. the firm's system exports, with a manifest giving each export's reader and the UTC time it was taken;
3. a list of **tags**. Each tag points at an exact quote in one document and names the control and scope that quote makes a claim about.

**The exports**, all read-only, all from documented APIs:

| Export | Source | Used for |
|---|---|---|
| Users | Microsoft Graph users | the population of accounts |
| MFA registration | Graph authentication-method registration details | whether each account has registered MFA |
| Conditional Access policies | Graph Conditional Access | whether MFA is enforced, for whom and when |
| Security defaults | Graph security-defaults policy | the tenant-wide MFA baseline |
| Role assignments | Graph directory role assignments, with principals | the population of admin accounts, and excluded roles |
| Managed devices | Intune | the population of endpoints |
| Defender machines | Defender for Endpoint API | onboarding, health and last-seen time of each machine |
| Mailbox backups | Veeam Backup for Microsoft 365 PowerShell | whether each mailbox was backed up, and when |

**The controls it checks:**

| Control | Scope | Can be backed by these exports? |
|---|---|---|
| MFA | all users · email · admins | Yes |
| MFA | remote access (VPN, firewall) | No: always unchecked, with the reason |
| Endpoint protection | all endpoints | Yes |
| Endpoint protection | alerts are monitored | No: always unchecked |
| Backup | Microsoft 365 mailboxes | Yes |
| Backup | Microsoft 365 files · servers · offline copy · restore tested | No: always unchecked |

The always-unchecked scopes exist so that **every claim in a sentence gets a tag**, including claims no export speaks to. Otherwise a sentence such as "every laptop runs Defender, which is monitored for alerts" could come out backed on the Defender evidence alone, with the monitoring claim silently ignored.

**The pipeline:**

1. **Ground the tags.** Each quote must appear exactly once in its document and hold at least three words. The document must be named by its one canonical path inside the firm's attestation folder. Another spelling of the path, or a second name for the same file, stops the run.
2. **Read the exports.** One reader per export turns rows into facts and keeps each fact's source as `file:row`. A missing field, a value of the wrong kind, a duplicate record, or a timestamp without a UTC offset stops the run with the file and row named. Nothing is guessed.
3. **Apply the scope's proof rule** to produce a verdict, a one-line reason and the cited rows.
4. **Group and report.** Tags whose quotes touch the same line or lines of a document form one attestation. The report quotes those whole lines, heads them with the worst of their tags' verdicts (any gap, else any unchecked, else backed) and lists each tag with its own verdict. A table of the exports and their times closes the report.

**How the proof rules fail closed.** The principles, and the module that implements each one, are in [architecture.md](architecture.md).

How to run a check is in [using.md](using.md). How the firm produces each export is in [exports.md](exports.md).

**Measured state (2026-10-05):**

- 749 automated tests pass. Two symlink tests need one run on a machine that permits symlinks.
- A made-up firm with planted truth (Microsoft 365 Business Premium plus Veeam) comes out **2 backed, 6 gap, 4 unchecked**, with **no false "backed"**. Its "healed" variant, and mutations of it that each break one thing, are tested end to end.
- The code went through task-by-task review and then four rounds of independent whole-branch review. Each round found and closed paths to a false "backed", from policies whose exclusions were spelled in unexpected ways to clause-level tags that let half of a compound sentence pass on its own.

**Known limits.** The limits stated for operators are in [using.md](using.md#known-limitations).

### 3.5 What the node still lacks

| Part of the node | Where it stands |
|---|---|
| Search that quotes sources and refuses | Built and measured (3.2) |
| Tracking when one document replaces another | Partly built, as a link type |
| Reading the firm's files: PDF, Word, Excel, email, scanned images | Missing; the engine reads structured text only |
| Logins, and walls between client files | Missing |
| A log of who asked what | Missing |
| A web client for staff | Missing |

Two measurements matter before any pilot, and neither exists yet:

- **Permissions filtering before the search runs.** Because answers are verbatim quotes, a permissions mistake hands someone another client's exact words. Filtering must happen before retrieval, with its own tests, before any client file loads.
- **The false "not found" rate.** The research has shown the engine does not invent answers. What decides whether staff keep using it is the opposite error: how often it says "not found" when the answer is sitting in a bad scan. That has to be measured on scanned documents first, then in the pilot.

### 3.6 The delivery is part of the security posture

A tool that reads a firm's security posture becomes part of it. Four rules apply to how the service itself is delivered:

- **Read-only exports run by the firm**, with us watching. We never hold admin passwords; admin access to Microsoft 365 opens every mailbox.
- **Access is opened by the firm**, limited in time and logged. Standing remote access into several firms would be the most tempting target the business could create.
- **No live web browsing from the node.** Outbound requests reveal what the firm is researching and add attack surface.
- **The node belongs in the firm's own WISP and insurance application.** It holds a copy of client files, so it is something new to protect.
