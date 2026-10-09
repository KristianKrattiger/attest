# attest

Attest checks a small firm's insurance application and its written information security plan against read-only exports from Microsoft 365 and Veeam. Each claim comes out **backed**, **gap**, or **unchecked**, and the report cites the export rows it rests on.

The check runs on a folder on disk. It reads the firm's text and exports and writes `report.md`. It makes no network call.

## What it is for

Accounting and tax practices, law offices, and wealth advisors sign statements about their own security every year. A cyber insurance application asks what is in place. A tax preparer is required to keep a written information security plan. An answer that is wrong can void the policy the firm is counting on.

In *Travelers v. ICS* (2022), the application said multi-factor login was used everywhere. It was only on the firewall. After a ransomware attack, the insurer had the policy rescinded.

The firm already has to have the plan. The product is the verification of that plan and of the insurance application, sentence by sentence, against the systems the firm already runs.

## The three answers

- **Backed.** The exports show the claim holds for the whole population it names.
- **Gap.** The exports show a failure, and they name who or what failed.
- **Unchecked.** The exports in hand do not settle the claim. Unchecked is a finding. It means the evidence does not settle it.

A false backed tells a firm it may sign something the exports do not support. That is the error the rules are built to refuse. A false gap costs a reviewer a few minutes to annotate a known exception. Missing evidence is unchecked. A shown failure is a gap. Backed requires proof that covers the whole claim.

## How a check works

The firm's sentences go in as plain text: the application and the written plan.

The exports go in beside them. The firm runs them read-only while the reviewer watches, and the check never holds admin credentials. The exports are the user list, MFA registration, Conditional Access policies, security defaults, directory role assignments, Intune devices, Defender for Endpoint machines, and Veeam's mailbox backup report. A manifest names each file, the reader that parses it, and the UTC time it was taken.

Tags a person has confirmed go in next. Each tag quotes one claim and names the control and the scope that claim is about. The scopes a current export can back are MFA for all users, for email, and for admins; endpoint protection for all endpoints; and backup of Microsoft 365 mailboxes. Remote-access MFA, alert monitoring, Microsoft 365 file backup, server backup, an offline copy, and a tested restore are tagged too, and they come out unchecked, because no export in this set speaks to them. A model may later suggest a tag. A person confirms it. A rule decides the verdict.

The rule for that control and scope compares the claim to the exports. The population comes from the account list or the device list, not from whoever happened to show up in the evidence file. A Conditional Access policy the rule does not fully understand does not count as proof.

One sentence shows why the unchecked scopes exist. "Every company laptop runs Microsoft Defender for Business, which is monitored for alerts." That is two claims. Laptop coverage can be backed or a gap, from the Intune device list joined to the Defender machine list. Alert monitoring is unchecked, because no export shows that anyone watches the alerts. A tag on only the Defender half would let the sentence come out backed, with the monitoring claim never tested.

The report quotes the lines those tags touch. It heads them with the worst verdict on that passage: any gap, else any unchecked, else backed. Under the quotation it lists each tag with its own verdict and the cited rows.

The mechanics, the component diagram, and the level 0 data-flow diagram are in [the architecture note](docs/engineering/architecture.md).

## What is built

The check is built. Readers turn each export into facts and keep each fact's row. Proof rules produce the verdict. The report groups claims that share a line. A made-up firm with planted truth is checked end to end, and the review of the rules was aimed at paths to a false backed. The measured state, with its test count and its date, is in the [engineering register](docs/engineering/README.md#34-attest-the-deterministic-attestation-check).

What comes after the check is a bet, and it is not running. It is a private search tool over the firm's own files: every answer quotes a source, and when nothing supports an answer the tool refuses. The commitment that bet is meant to keep is that a firm's data does not train a model used by another firm. That later tool is the node. Nothing leaves the firm's environment except aggregate counts the firm has seen first. Reading the firm's files, walls between clients, and a staff client are not built. The sequence, the check first and that tool only after paid checks, is in the [strategy register](docs/strategy/README.md#43-sequence).

## Where the rest is

Three registers sit beside this account. A conceptual claim is judged on the argument. An engineering claim is judged by the code, the tests, and the recorded measurements. A strategy claim is a bet, with its assumption and what would confirm or refute it. A bet does not borrow the authority of a measurement.

- **[Conceptual](docs/conceptual/README.md).** Why two passages about the same thing are not yet a relation, and why a model does not decide whether a sentence and an export row agree.
- **[Engineering](docs/engineering/README.md).** What is built and what was measured, [how to run a check](docs/engineering/using.md), [how the firm produces each export](docs/engineering/exports.md), and the [architecture](docs/engineering/architecture.md) of the check.
- **[Strategy](docs/strategy/README.md).** Who would pay, the prices, the sequence, and the risks. Each one is written as a bet.

The map of those files is [docs/README.md](docs/README.md).
