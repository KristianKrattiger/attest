# Messy-firm run

Run 2026-10-14 on the dev seed: 5000 combinations of one to four operators from tests/messy/catalog.py, random seed 20261014.

- Property violations: 0
- Runs that stopped: 1173

## Stops

| Reason | Runs |
|---|---|
| defender-machines.json: row N field 'computerDnsName' must be a non-empty string, got None | 377 |
| users.json: the export is one page of several (it has @odata.nextLink) | 427 |
| veeam-users.json: row N field 'MailboxBackedUpTime' has no UTC offset: '2026-10-01T02:10:00' | 369 |

## Noise cost of "holds" operators

A run counts against an operator when a scope it declares left the seed's status while it was applied and no applied "breaks" operator breaks that scope. Every "holds" operator applied in that run with the same scope is charged.

| Operator | Runs applied | Runs degraded | Degraded to |
|---|---|---|---|
| Veeam Email is the primary SMTP address | 410 | 231 | gap 231 |
| admin role held by a group | 428 | 296 | unchecked 296 |
| admin role held by a service principal | 409 | 49 | gap 23, unchecked 26 |
| device renamed after onboarding | 410 | 0 | - |
| discovered device with no DNS name | 409 | 0 | - |
| discovered printer | 422 | 0 | - |
| grant through an authentication strength | 386 | 9 | gap 9 |
| laptop re-imaged | 463 | 0 | - |
| microsoft-managed admin-portals policy | 423 | 49 | gap 28, unchecked 22 |
| per-user MFA instead of Conditional Access | 402 | 293 | gap 291, unchecked 24 |
