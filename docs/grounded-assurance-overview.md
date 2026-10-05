# Grounded assurance for small professional firms

**Concept, engineering and strategy** · 2026-10-05 · companion to the business-model document

This document describes the idea in more depth than the business plan does. It covers why the idea holds together, what the technology actually does and how far it is built, and which commercial bets it rests on. It leaves out the specific people and first contacts; where the plan names them, this document speaks of "the founders" and "a first pilot firm".

---

## How to read this document

The work behind this business already keeps three kinds of claims apart, and this document keeps them apart too:

| Register | What a claim in it is | How it is judged |
|---|---|---|
| **Conceptual** | An argument about mechanism or values | On the merits of the argument |
| **Engineering** | A statement about what is built and what was measured | By the code, the tests and the recorded measurements; unmeasured means unmeasured |
| **Strategy** | A bet about buyers, prices, timing and competitors | Stated as a bet, with its assumption, what would confirm or refute it, and a date |

The boundary runs one way. A strategy bet never borrows the authority of a measurement, and a concept is never presented as something already built. Where a section mixes registers, it says which sentence is which.

---

## 1. The idea in one page

Small professional firms that hold client secrets (accounting and tax practices, law offices, wealth advisors) face two trust problems that turn out to be the same problem:

1. **Every year they sign statements about their own security.** Cyber insurance applications, the written information security plan (WISP) that tax preparers are legally required to keep, and privacy-rule attestations for registered advisors all ask the firm to say what is in place. A statement that is wrong can void the insurance the firm is relying on. In *Travelers v. ICS* (2022), the insurer had a policy rescinded after a ransomware attack because the application said multi-factor login was used everywhere when it was only on the firewall.
2. **They are starting to use AI on client material.** For these firms a fluent wrong answer is the expensive failure, more than a slow or missing one.

In both cases the valuable thing is the same: **a statement that only says what the evidence proves, cites the evidence, and says "not proven" plainly when the evidence is missing.**

The business sells that property in two forms, in this order:

| | Service | What the firm gets | Built? |
|---|---|---|---|
| 1 | **Yearly attestation check** | Each sentence in the insurance application and the WISP marked *backed*, *gap* or *unchecked* against what the firm's own systems export, with the export rows cited | The deterministic core is built and reviewed (section 3.4) |
| 2 | **Private grounded AI node** | Search over the firm's own documents that quotes its source for every answer and refuses when nothing supports one | The answering engine is built and measured; reading the firm's files, permissions, logging and a staff web client are not |

Four commitments run through both:

- **We never report "backed" without proof that covers everything the sentence claims.** Missing evidence is "unchecked"; evidence of a failure is a "gap".
- **We never hold the firm's passwords.** The firm runs read-only exports while we watch.
- **Nothing leaves the firm's environment.** No documents, questions or staff labels; only aggregate counts the firm has seen first.
- **No firm's data trains anything used by another firm.**

---

## 2. Conceptual register

### 2.1 One constraint: grounded confidence and loud refusal

Everything in this work rests on one small claim: **every claim the system emits traces to a passage that provably exists in the material it was given, and where nothing grounds an answer, the system marks the silence instead of filling it.**

The research project this business draws on, GIN (Grounded Intelligence Network), wraps that constraint in federation, governance and a tiered corpus. Receipts, a public tool that checks vendors' claims against independent sources on the live web, ships it thin. Strip both of their situational layers and the same object is left in both hands: a function from a set of documents and a question to one of three outputs:

- a **grounded answer**, every load-bearing part citing a location in the supplied material;
- a **divergence**, two grounded statements that disagree, shown together with their citations rather than reconciled;
- a **refusal**, a statement that the material does not support an answer.

That object is called the Assay. The attestation check is the Assay pointed at one question: does what the firm says match what its systems show? Its three verdicts map onto the Assay's three outputs. *Backed* is a grounded answer. *Gap* is a divergence between what the document says and what an export shows. *Unchecked* is a refusal: the evidence in hand does not settle it.

### 2.2 Structural fidelity, not truth

Grounding guarantees that every statement traces to its evidence. It does not guarantee that the evidence is true. If the material is wrong, a faithful system reproduces the error with full citations. This limit is stated up front because it defines what kind of system this is.

For the check, that limit decides what counts as evidence. **A policy document cannot back up an attestation; only a report generated by the system itself can.** The WISP saying "all staff use MFA" is the claim being tested, never the proof. The proof is the identity system's own export of its policies, accounts and registrations.

### 2.3 Three answers, and an asymmetry between errors

Most tools have two outcomes: pass or fail. The check has three, and the third is the honest one. *Unchecked* means "the evidence in hand does not settle this". It is information, not a malfunction. A firm that learns its remote-access MFA cannot be shown from any export it has has learned something true about its attestation.

The two possible errors are not symmetric:

- A **false "backed"** tells a firm it may sign something that is not true. It is the *Travelers v. ICS* failure, and it is the business's liability. It is the one error driven to zero.
- A **false "gap"** costs a reviewer some minutes to annotate a known exception.

Every design choice in the check leans toward the second error when it cannot avoid both. That is the meaning of "fail closed" throughout this document.

### 2.4 Relatedness is not relation

The most important lesson from the research is that **finding two passages about the same thing is not the same as knowing how they relate.** A model can reliably notice that a vendor's marketing sentence and an incident report are about the same product. Whether the incident report actually contradicts the marketing claim, or merely shares its topic with the opposite tone, is a different and much harder question.

The research has measured this repeatedly:

- the reasoning gate in GIN filters for relevance, not for the type of relation;
- off-the-shelf judges up to frontier scale could not reproduce a curated "contradicts" label, and did not get better as they got larger;
- the local proposer that suggests evidence pairs for the Assay, even with an explicit option to decline, kept only 2 of 5 real relations, and the unrelated pairs it let through were same-topic pairs with opposite sentiment.

The consequence for the business is a design rule: **where a relation can be made structural, make it structural.** An attestation about MFA and an export row about one user's MFA registration do not need a model to pair them. Both are keyed to a *control* (MFA, backup, endpoint protection) and a *scope* (all users, admins, mailboxes). Pairing becomes a join on that key, and the verdict becomes a comparison of state and coverage. The only judgment left is which control and scope a sentence is about. That is a closed-set label a person can confirm in seconds and a model can later suggest. Models suggest; people confirm; rules decide.

### 2.5 Non-extraction at the smallest scale

GIN was conceived as a federation of independent nodes that each keep their own material, with a hard line against extractive automation: knowledge held for the people it came from, never enclosed and rented back to them. A business has to square that line with selling software.

It squares it like this. **A thin slice of GIN running for one firm, with the firm's data flowing only into a tool the firm controls, is not extractive.** It is the project's sovereignty idea at the smallest possible scale. The plain-language promise is "your files never train anyone's model, including ours", and the node can do more than promise it: it can show that the data has no outbound path to take.

Three boundaries keep it that way:

- **Federation stops at the firm's own offices.** Connecting different firms is the scaled, governed network, which needs each institution's consent and its own governance. It is never sold as an add-on.
- **Training stays on the box or stays synthetic.** A model trained on a firm's data stays on that firm's node. Anything shared across firms trains only on synthetic or public material, and firm data is used only to measure, on site.
- **The firm owns its data, the index built from it, and the findings.**

### 2.6 Lineage

The ideas have older names, and naming them sharpens the design:

- **The right to opacity** (Édouard Glissant): a node does not owe outsiders its material. Federation makes the *relation* between nodes legible while each keeps its own contents opaque. At the scale of one firm, that is simply confidentiality.
- **Technodiversity** (Yuk Hui): there is no single technical trajectory everyone must converge on. Many small, situated systems are a design choice, not a stage on the way to one large one.
- **The pharmakon** (Bernard Stiegler): memory moved into technical systems can cure or poison, depending on who keeps it. Here the firm keeps its own.
- **Data dignity** (Jaron Lanier): the refusal to build systems that harvest the people who feed them.
- **The apophatic discipline**: saying only what can be anchored and marking the silence, rather than affirming everything fluently. A refusal is not the system failing; it is the system being honest.

---

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

On a firm's files no outside verifier may run, so a local relational row cannot be checked by a stronger model. **Every local relational row is treated as unvetted; a person reviews it before it becomes a finding.** This is why the check does not pair claims with evidence through a model at all (2.4).

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

**How the proof rules fail closed.** These are the principles the rules share, each one a path to a false "backed" that review found and closed:

- **The population never comes from the evidence.** "All users" means every enabled member account in the users export, not every account the registration export happens to mention. Admins come from the role assignments, never from a field in the registration report.
- **Anything a rule does not understand narrows.** A Conditional Access policy counts as enforcing MFA only if nothing limits when it applies: no location exception ("MFA except at the office"), no device filter, no risk condition, no unknown condition. Recognition is an allow-list, so a new Microsoft condition makes the policy not count rather than count by default.
- **"MFA or a compliant device" is not MFA.** A grant that a compliant device satisfies alone does not require MFA.
- **Exclusions are resolved or presumed.** An excluded group, whose members no v1 export shows, makes the verdict a gap, never backed. So does excluding guests in any spelling, or a role held by a principal the exports cannot resolve to accounts.
- **Role-targeted policies count only tenant-wide assignments**, matching how Conditional Access actually evaluates roles scoped to an administrative unit.
- **Matching is one-to-one and conservative.** Each Intune device pairs with at most one Defender machine. The latest Defender record decides, a tie is a gap, and two different Entra devices are never paired by name.
- **Evidence outside the population still counts.** A recently seen, unhealthy machine that only Defender knows about makes endpoint protection a gap. Disabled accounts that the backup tool still lists join the backup population. Backup rows that match no account are listed.
- **Time is checked, not assumed.** Staleness is measured against the export time in the manifest. A time later than the export time is a gap. Exports taken more than 24 hours apart make the verdict unchecked.
- **An empty population is unchecked**, never a vacuous "backed".
- **A failed run cannot look like a current report.** A run that fails replaces its own earlier report with a stub that says why, so verdicts from an old run are never mistaken for today's.

**Measured state (2026-10-05):**

- 749 automated tests pass. Two symlink tests need one run on a machine that permits symlinks.
- A made-up firm with planted truth (Microsoft 365 Business Premium plus Veeam) comes out **2 backed, 6 gap, 4 unchecked**, with **no false "backed"**. Its "healed" variant, and mutations of it that each break one thing, are tested end to end.
- The code went through task-by-task review and then four rounds of independent whole-branch review. Each round found and closed paths to a false "backed", from policies whose exclusions were spelled in unexpected ways to clause-level tags that let half of a compound sentence pass on its own.

**Known limits, stated in the tool's own documentation:**

- A policy that targets groups can only produce gaps, because v1 has no group-membership export.
- Unlicensed and service accounts show as permanent backup gaps for the reviewer to annotate.
- The three-word rule cannot be met inside text written without spaces between words.
- The Veeam field names come from Veeam's published examples. The first real export must confirm them, and must confirm whether Veeam's address matches each account's sign-in name. A mismatch fails closed, as a gap.

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

---

## 4. Strategy register

Everything in this section is a bet. Each one names its assumption and what would confirm or refute it. All are dated 2026-10-05, to be scored against what happens.

### 4.1 Buyers and why now

**Bet: small confidentiality-bound firms will pay for verification of what they already attest to.**

- **Who:** accounting and tax practices, law offices and wealth advisors, under about 20 people.
- **Why they attest every year:**
  - **Cyber insurance renewal**, with a yearly questionnaire. A false answer can cost the claim.
  - **Tax-preparer registration renewal** (IRS Form W-12, opening mid-October). Line 11 asks whether the preparer knows a written security plan is legally required. It asks about knowing, not having, so many firms have ticked a box they cannot back.
  - **The amended privacy rule for registered advisors** (SEC Reg S-P), in force for smaller firms since June 3, 2026, with exam attention promised.
  - **Service-provider oversight duties** in Reg S-P and the FTC Safeguards Rule, which small firms rarely have anyone to carry out.
- **Timing:** the check sells best 60 to 90 days before the firm's insurance renewal. The renewal date is the first thing to learn about a prospect.
- **Confirms:** firms book and pay for a check at a quoted price. **Refutes:** firms say the free IRS template is enough, or that their IT provider already covers it.

### 4.2 Positioning

**Bet: "does your security plan and insurance application match what is really in place?" is an easier sale than a general security review.**

- The firm is already required to have the plan. The IRS gives a template away, so the product is **verification, not the document**.
- The output speaks the firm's own language: its own sentences, each marked backed, gap or unchecked, with the evidence attached.
- **Against general-purpose AI assistants** (Microsoft's Copilot at about $21 per user per month, working on the same data where it already sits), the node's edge is proof and refusal, **not where it runs**. If a firm's files already live in Microsoft 365 and cloud tax software, "data never leaves the building" argues against something that has already happened.
- **Confirms:** firms point to the citations and the "unchecked" verdicts as the reason they would pay. **Refutes:** firms treat the node as a slower Copilot.

### 4.3 Sequence

**Bet: selling the check first builds the trust and the revenue that the node needs.**

1. **The check**, on code that already exists. No hardware in anyone's office, no client documents beyond read-only exports.
2. **Tag suggestions** (attest sub-project 2). A local GIN model suggests the control and scope for each sentence, and a person confirms. It is tested on a firm whose documents the model has never seen, so the result is not in-sample.
3. **A review page** (attest sub-project 3), where the reviewer confirms tags and annotates gaps.
4. **The node**, only after paid checks, and only after file reading, permissions and the false "not found" measurement exist.

Other research directions (federation across institutions, the training loop, governance) wait until a paid job needs them. The two-client rule that governs add-ons applies to the founders' own building too: a piece of work goes ahead when a paying use needs it.

### 4.4 Revenue model (starting guesses)

| Stream | Billed | Starting guess | Recurring |
|---|---|---|---|
| Attestation check | Flat fee per check | $1,500–3,000 for a firm under 20 people | Yearly |
| Node subscription | Monthly per firm | $800–1,500 for a 10-person firm | Monthly |
| Setup | Once per install | Hardware at cost plus installation time; waivable if a pilot converts | No |
| One-off work | Per job | Priced per job | No |

- The node price works back from 3 to 6 support hours a month at $150 an hour. That is 4 to 7 times what Copilot costs, so whether search with proof is worth that much more is the real demand question. Firms hear the number in the first conversation.
- Ten checks a year bring in $15,000 to $30,000: good side income. Growing past it needs node subscriptions, or **IT providers who resell**: they handle hardware and first-line support, and we license the software.
- AI-tool testing is a section of the yearly check, not a monthly service. A small firm's AI tools do not change month to month.

### 4.5 Licensing and ownership

**Decided: the engine stays open; the business code stays closed for now.**

- **Open:** GIN, and Assay inside Receipts (MIT). Being open helps sell to cautious firms: the method can be inspected.
- **Closed:** attest, file reading, permissions, deployment scripts and the check's profiles. That code is what stops a provider from copying the service while the business is small. It can be opened later; it cannot be closed again once public.
- **attest contains no Assay code**, so the check does not depend on the terms of the research challenge under which Receipts was written. Those terms must still be read before Assay itself goes into paid work.
- **The contract follows the split.** The open engine keeps its own license, our code is licensed to the client, and the client owns its data, the index built from it, and the findings. Lawyers will strike any clause that suggests otherwise.
- **Before the first paid job:** a founders' agreement (moving the engine into the company, the ownership split, what happens to the code if a founder leaves), confirmation that no current or past employer has a claim on the engine, and a check of outside-work rules in the founders' employment terms.

### 4.6 The evidence bar

- **Five paid checks** are the evidence. Five firms saying they would pay prove nothing.
- **A node pilot is agreed before anything is installed:**
  - 20 to 30 real questions staff asked in the previous month;
  - scoring: answered correctly, honestly not found, or wrong (the goal for wrong is zero), plus time saved against how they search now;
  - the price, and the date at which the pilot becomes paid or the hardware leaves.
- A pilot on non-sensitive documents only proves the node installs and runs. Procedures, templates and public guidance are exactly where general assistants look best. That feedback is not demand.
- **Testing our own node is not independent assurance.** The firm sees the test questions and adds its own.

### 4.7 Calendar constraints

- Tax firms are swamped until mid-October (extensions) and from January to April 15. **No installs between January and April 15.** An outage in early April could end a client relationship.
- The natural rhythm: first conversations after mid-October, checks in the following months, building over the winter, a node pilot after tax season at the earliest.

### 4.8 Risks

| Risk | Why it matters | What we do |
|---|---|---|
| Files already in the cloud | The "nothing leaves the building" pitch fails if data already sits with outside services | Ask where files live first; lead with proof and refusal, not location. Offer a server in the firm's own cloud account instead of a box in the office |
| A false "backed" | A gap we miss could sit behind a denied insurance claim | Fail-closed rules, planted-truth tests, independent review; professional liability insurance before the first check |
| Export field names | The Veeam names are unconfirmed against a real export | The first real export is checked before any paid check relies on it; a mismatch stops the run or fails closed |
| Engine gap | File reading, permissions, logging and the web client are missing | Build them while the check is the only product |
| False "not found" | Staff stop using the node if answers in bad scans come back as not found | Measure on assembled scans, then in the pilot |
| Permissions | Verbatim quoting makes a permissions mistake worse | Filter by who is asking before the search runs, with its own tests |
| Reach | Returns and workpapers sit inside tax software the node may not reach | Ask how much searching happens outside the tax software |
| Relation judgments | No local model reliably judges whether two passages relate (3.3) | Keep pairing structural; a person reviews any model-made relation |
| IT provider pushback | The gap report grades the firm's current provider | Bring providers in early; treat them as a sales channel |
| Support load | The founders have other jobs | Respect the tax calendar; IT providers as first-line support |
| Cross-border privacy law | A firm run or hosted abroad may fall under other privacy regimes | A question for the lawyer, per firm |
| Ownership and rights | The engine predates the company; Assay was written under a challenge's terms | Founders' agreement; read the challenge terms; keep attest free of Assay code |
| Building sprawl | Research directions compete with the check for the same evenings | The two-client rule applies to our own building |

---

## 5. How the business and the research relate

The research question underneath all of this is how much honesty can be enforced *outside* a model (constraints, gates, structural joins) and how much can be trained *into* one. The research's own answer so far is that training buys cost, not trust: it can make a constrained system cheaper and less stiff, but the guarantees come from the constraints.

The business is the deep, narrow version of that research. It takes one form of the idea and makes it survive messy scans, permissions, uptime during tax season and a liability that is real. The research gets three things back:

- **Measured failures from real conditions**, which the research values more than its successes.
- **Pressure toward structure.** The attestation check is a working example of replacing a model's relation judgment with a join wherever the domain allows it.
- **A clean boundary for training.** Firm data is never training data for anyone else. If the training loop is ever built, it runs per firm on the firm's own node, or on synthetic and public material only.

The scaled network (many institutions, each keeping its own material, linked by consent and governed in the open) stays outside the business and stays non-extractive. The business sells a thin, local slice of it. It must never become the side door into the larger network.

---

## 6. Open questions and next steps

**Open questions:**

- Do the starting prices hold when a firm hears them?
- How much of a typical firm's searching happens outside its tax software?
- What does support really cost per firm per month?
- Who leads which service, and how is ownership split?
- Which certifications are worth taking, and by whom? (Security+ is the entry point; CISA is the audit credential, with an associate designation available before the experience requirement is met.)

**Next steps:**

1. **Confirm the export formats** on a real tenant (read-only, run by the firm): the Veeam field names, and whether its address matches the sign-in name.
2. **Tag suggestions** (attest sub-project 2), measured on a firm whose documents the model has never seen.
3. **The review page** (attest sub-project 3).
4. **The first conversations**, questions only: where the files live, the insurance renewal date, whether there is a written security plan and an IT provider, and who makes technology decisions.
5. **Before the first check:** professional liability insurance, the founders' agreement, the employer and challenge-terms checks, and a lawyer-reviewed contract template.

---

## Sources

The deadlines, prices and case law come from a review of the business plan and have not been re-checked here.

- IRS Form W-12 (preparer number renewal): https://irs.gov/pub//irs-pdf/fw12.pdf
- Verito on line 11: https://verito.com/blog/?p=8115
- AICPA on the required security plan: https://www.aicpa-cima.com/resources/article/wisp-required-by-federal-law-for-tax-practitioners
- Velosio on Copilot Business pricing: https://velosio.com/blog/m365-copilot-pricing-calculator
- Aldridge on the Copilot price cut: https://aldridge.com/microsoft-lowers-copilot-pricing-for-small-and-midsize-businesses/
- Davis Wright Tremaine on the Reg S-P deadline: https://www.dwt.com/blogs/privacy--security-law-blog/2026/05/reg-sp-smaller-entities-june-2026-deadline
- Sidley on Reg S-P: https://datamatters.sidley.com/2026/04/30/u-s-sec-regulation-s-p-compliance-deadline-approaching-for-smaller-entities/
- Lockton on Travelers v. ICS: https://global.lockton.com/us/en/news-insights/travelers-v-ics-underscores-need-to-respond-carefully-to-cyber-insurance
- Reed Smith on Travelers v. ICS: https://www.reedsmith.com/en/perspectives/2022/07/insurance-applications-under-scrutiny-lessons-from-travelers-v-ics
- ISACA on CISA requirements: https://isaca.org/credentialing/cisa/get-cisa-certified

Technical claims come from the GIN repository (concept and engineering documents, evaluation records) and the attest repository (design spec, README, test suite).
