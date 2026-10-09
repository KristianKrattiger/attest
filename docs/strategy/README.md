# Strategy register

This file is the strategy register. A claim here is a bet about buyers, prices, timing, and competitors, stated with its assumption, what would confirm or refute it, and a date.

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
| Relation judgments | No local model reliably judges whether two passages relate ([section 3.3](../engineering/README.md#33-where-the-model-proposes-approach-fails-relations)) | Keep pairing structural; a person reviews any model-made relation |
| IT provider pushback | The gap report grades the firm's current provider | Bring providers in early; treat them as a sales channel |
| Support load | The founders have other jobs | Respect the tax calendar; IT providers as first-line support |
| Cross-border privacy law | A firm run or hosted abroad may fall under other privacy regimes | A question for the lawyer, per firm |
| Ownership and rights | The engine predates the company; Assay was written under a challenge's terms | Founders' agreement; read the challenge terms; keep attest free of Assay code |
| Building sprawl | Research directions compete with the check for the same evenings | The two-client rule applies to our own building |

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
