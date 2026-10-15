# The lab tenant

The lab is a small Microsoft 365 tenant we control, set up as a clean firm, captured, then made messy one mess at a
time and captured again. Its captures are the seed and the twins of the messy-firm tests (`tests/messy/`). The design
is in [the spec](../superpowers/specs/2026-10-14-messy-firm-testing-design.md).

Nothing here is ever done in a client's tenant. Every step below is done by a person, in the lab tenant, from this
machine or the lab's Azure VMs.

## Cost and clock

- **Microsoft 365 Business Premium trial.** It is the stack the target firms run. Confirm the trial's length, whether
  it needs a card, and when billing starts at sign-up, and note them in the spec's open questions.
- **Azure.** A subscription in the same tenant pays for the VMs. Deallocate every VM when you are not using it.
- **The clock.** All of this happens inside the trial. [Teardown](#6-teardown) cancels everything before billing.

## Before you start, on this machine

- PowerShell 7 beside Windows PowerShell 5.1: `winget install --id Microsoft.PowerShell --source winget`
- The Graph module, once in each shell (`pwsh` and `powershell`):
  `Install-Module Microsoft.Graph.Authentication -Scope CurrentUser`
- The Python environment from [using.md](using.md).

Windows PowerShell may refuse to run scripts. Every `powershell` command below passes `-ExecutionPolicy Bypass`, which
applies to that one process only.

## 1. The tenant

1. Sign up for the Business Premium trial with a new tenant. Record its tenant ID (Entra admin center, Overview). The
   account you sign up with is the first member and holds Global Administrator. Register MFA for it before step 7.
2. Connect for setup, in `pwsh`:

   ```powershell
   Connect-MgGraph -TenantId <tenant ID> -Scopes 'User.ReadWrite.All', 'Directory.ReadWrite.All',
       'RoleManagement.ReadWrite.Directory', 'Policy.ReadWrite.ConditionalAccess', 'Policy.Read.All',
       'UserAuthenticationMethod.ReadWrite.All'
   if ((Get-MgContext).TenantId -ne '<tenant ID>') { throw 'Not signed in to the lab tenant' }
   function Send-Graph($Method, $Uri, $Body) {
       Invoke-MgGraphRequest -Method $Method -Uri $Uri -Body ($Body | ConvertTo-Json -Depth 8) -ContentType 'application/json'
   }
   ```

   Stop if it throws: every step below writes to whichever tenant you are signed in to.

3. Turn security defaults off:

   ```powershell
   Send-Graph PATCH 'v1.0/policies/identitySecurityDefaultsEnforcementPolicy' @{ isEnabled = $false }
   ```

4. Create eight more members and a former employee, each licensed. With you, that is nine members and ten mailboxes,
   the most Veeam Community Edition backs up. The passwords are random and never kept: no one signs in as these
   accounts.

   ```powershell
   $domain = ((Invoke-MgGraphRequest GET 'v1.0/domains').value | Where-Object isDefault).id
   $sku = ((Invoke-MgGraphRequest GET 'v1.0/subscribedSkus').value | Where-Object skuPartNumber -eq 'SPB').skuId
   $names = 'Avery Lane', 'Blake Moss', 'Casey Hart', 'Drew Ellis', 'Emery Stone', 'Finley Park', 'Gray Holt',
       'Harper Quinn', 'Former Employee'
   $made = @{}
   foreach ($name in $names) {
       $nick = $name.ToLower().Replace(' ', '.')
       $user = Send-Graph POST 'v1.0/users' @{
           accountEnabled = $true; displayName = $name; mailNickname = $nick.Replace('.', '')
           userPrincipalName = "$nick@$domain"; usageLocation = 'US'
           passwordProfile = @{ forceChangePasswordAtNextSignIn = $true; password = "$([guid]::NewGuid())Aa1!" } }
       Send-Graph POST "v1.0/users/$($user.id)/assignLicense" @{ addLicenses = @(@{ skuId = $sku }); removeLicenses = @() }
       $made[$name] = $user.id
   }
   ```

5. Disable the former employee (the mailbox stays while the license does), and make Avery Lane an Exchange
   Administrator:

   ```powershell
   Send-Graph PATCH "v1.0/users/$($made['Former Employee'])" @{ accountEnabled = $false }
   Send-Graph POST 'v1.0/roleManagement/directory/roleAssignments' @{
       principalId = $made['Avery Lane']; roleDefinitionId = '29232cdf-9323-42fd-ade2-1d097af3e4de'; directoryScopeId = '/' }
   ```

6. A shared mailbox and a guest. Create the shared mailbox "Front Office" in the Exchange admin center (Recipients,
   Mailboxes, Add a shared mailbox); it appears in Entra as a disabled user. Invite the guest without sending mail
   (`example.com` delivers nothing):

   ```powershell
   Send-Graph POST 'v1.0/invitations' @{ invitedUserEmailAddress = 'auditor@example.com'
       inviteRedirectUrl = 'https://myapps.microsoft.com'; sendInvitationMessage = $false }
   ```

7. Register every member for MFA with a phone method. The numbers are in the fictional 555-0100 to 555-0199 range.
   Your own account may refuse a second phone; that is fine, it is registered already.

   ```powershell
   $n = 100
   $users = (Invoke-MgGraphRequest GET 'v1.0/users?$select=id,accountEnabled,userType').value
   foreach ($u in $users | Where-Object { $_.accountEnabled -and $_.userType -eq 'Member' }) {
       $n++
       try { Send-Graph POST "v1.0/users/$($u.id)/authentication/phoneMethods" @{
           phoneNumber = "+1 2065550$n"; phoneType = 'mobile' } } catch { Write-Warning $_ }
   }
   ```

8. The Conditional Access policies a clean firm has:

   ```powershell
   $ga = '62e90394-69f5-4237-9190-012177145e10'; $exchange = '29232cdf-9323-42fd-ade2-1d097af3e4de'
   $everyone = @{ includeUsers = @('All') }; $admins = @{ includeRoles = @($ga, $exchange) }
   $policies = @(
       @{ name = 'Require MFA for all users'; users = $everyone; clients = @('all'); grant = @('mfa') },
       @{ name = 'Require MFA for administrators'; users = $admins; clients = @('all'); grant = @('mfa') },
       @{ name = 'Block legacy authentication'; users = $everyone; clients = @('exchangeActiveSync', 'other')
          grant = @('block') })
   foreach ($p in $policies) {
       Send-Graph POST 'v1.0/identity/conditionalAccess/policies' @{ displayName = $p.name; state = 'enabled'
           conditions = @{ users = $p.users; applications = @{ includeApplications = @('All') }
                           clientAppTypes = $p.clients }
           grantControls = @{ operator = 'OR'; builtInControls = $p.grant } }
   }
   ```

   Microsoft may also have created its own managed policies in the tenant. Leave them: they are real noise.

## 2. Machines in Azure

1. Create an Azure subscription in this tenant (portal.azure.com, signed in as the tenant's admin), and one resource
   group, `attest-lab`, for everything below.
2. Intune automatic enrollment: Intune admin center, Devices, Windows, Enrollment, Automatic Enrollment: MDM user
   scope All.
3. **Before you build the endpoints**, settle the spec's open question on Windows 11 in Azure: the image asks you to
   confirm a license with multi-tenant hosting rights. If Business Premium seats do not carry it, build the endpoints
   from a Windows Server image instead, and note that in the spec.
4. Three endpoints, `lab-lt-01` to `lab-lt-03`: Windows 11 Enterprise, size Standard_B2s, in `attest-lab`. On the
   Management tab, turn on "Login with Microsoft Entra ID" and "Enroll the VM with Intune". Within an hour each should
   appear in Intune (Devices, Windows) with an Entra device ID.
5. Onboard them to Defender for Business through Intune:
   - Defender portal, Settings, Endpoints, Advanced features: Microsoft Intune connection On.
   - Intune admin center, Endpoint security, Microsoft Defender for Endpoint: connect Windows devices On.
   - Intune admin center, Endpoint security, Endpoint detection and response: a policy for Windows with the package
     type "Auto from connector", assigned to all devices.

   Within a day each VM should show in the Defender portal (Assets, Devices) as Onboarded and Active. If the policy
   does not take, onboard with the local script instead (Defender portal, Settings, Endpoints, Onboarding).
6. The Veeam server, `lab-veeam`: Windows Server 2022 Datacenter, Standard_D8s_v5 (Veeam's documented minimum is 8
   cores and 16 GB), a 128 GB data disk. Not Entra-joined, not enrolled, not onboarded: it is outside the firm's
   population. On it:
   - Install Veeam Backup for Microsoft 365 (from veeam.com). With no license installed it runs as the Community
     Edition, for up to 10 users.
   - Add the organization: Microsoft 365, modern app-only authentication, and let Veeam register a new Entra
     application (sign in as Global Administrator when it asks).
   - Add a repository on the data disk, and record its name.
   - A backup job: the entire organization, mailboxes and archives, daily at 02:00. Run it once now.
   - Confirm the job backed up ten users and the shared mailbox. If Veeam counts the shared mailbox against its ten,
     remove the license from the former employee, so it becomes a disabled account without a mailbox.
7. An app registration for the Defender API: Entra admin center, App registrations, New, `attest-lab-export`. API
   permissions: APIs my organization uses, WindowsDefenderATP, Application permissions, Machine.Read.All; grant admin
   consent. Certificates & secrets: a client secret that expires before the trial ends. Record the app ID. The secret
   is typed at each capture and stored nowhere.

## 3. Capturing seed-clean

Wait a day after the last change, so the registration report and Defender's `lastSeen` have caught up. Then take the
same capture from both shells, minutes apart:

```powershell
pwsh -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean/exports -Part Graph -TenantId <tenant ID>
pwsh -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean/exports -Part Defender -TenantId <tenant ID> -AppId <app ID>
powershell -ExecutionPolicy Bypass -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean-ps51/exports -Part Graph -TenantId <tenant ID>
powershell -ExecutionPolicy Bypass -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean-ps51/exports -Part Defender -TenantId <tenant ID> -AppId <app ID>
```

A retake goes into an empty folder: the script refuses a folder that already holds one of its exports.

On `lab-veeam`, with a copy of `scripts/lab_capture.ps1`:

```powershell
powershell -ExecutionPolicy Bypass -File lab_capture.ps1 -Out C:\capture\exports -Part Veeam -Repository '<repository>'
```

Copy `veeam-users.json` and `veeam-user-properties.json` into both `firm/lab/raw/seed-clean/exports/` and
`firm/lab/raw/seed-clean-ps51/exports/`, and add the manifest line it printed to both `manifest.yaml` files.

**Confirm the Veeam fields.** `veeam-user-properties.json` lists every property of one user as Veeam names them.
Check that `Email`, `IsMailboxBackedUp` and `MailboxBackedUpTime` are among them, and that each `Email` in
`veeam-users.json` is the account's UPN. Write what you found into `exports.md` (Veeam section) and `using.md` (Known
limitations). This settles the strategy register's next step 1.

Scrub both captures into `firm/lab/` (the values you pass are added to the gitignored `firm/lab/raw/deny.txt`):

```bash
venv/Scripts/python.exe scripts/scrub_lab_capture.py firm/lab/raw/seed-clean firm/lab/seed-clean --tenant-id <tenant ID> --admin-name "<your display name>" --admin-address <the address you signed up with>
venv/Scripts/python.exe scripts/scrub_lab_capture.py firm/lab/raw/seed-clean-ps51 firm/lab/seed-clean-ps51 --tenant-id <tenant ID> --admin-name "<your display name>" --admin-address <the address you signed up with>
```

Add `--also <value>` (repeatable) for anything else that names you or the tenant, such as a phone number or a device
name; a capture that still holds a value the scrubber knows to deny is refused and nothing is written.

Once `firm/lab/seed-clean/exports/manifest.yaml` exists, the messy-firm tests use it as their seed.

## 4. The twins

Each twin is two captures: `before`, then the mess, then `after`. Capture `before` with all three parts into
`firm/lab/raw/<twin>/before/exports`, make the mess, wait as long as the table says, capture `after` into
`firm/lab/raw/<twin>/after/exports`, then undo the mess. Scrub `firm/lab/raw/<twin>` into `firm/lab/<twin>` with the
same arguments as above. One mess at a time: a twin whose `after` shows two messes cannot be compared with either
operator.

Capture each `before` and `after` the way section 3 captures `seed-clean`, with the same three parts: Graph and Defender
from `pwsh` (with `-TenantId`, and `-AppId` for Defender), Veeam on `lab-veeam`.

| Twin | Operator | Make the mess | Wait | Undo |
|---|---|---|---|---|
| `real-messy-break-glass` | break-glass accounts excluded | Two unlicensed accounts `break.glass1`, `break.glass2` with Global Administrator and a phone method each; add both IDs to `excludeUsers` of every policy | 1 day (registration) | Delete both, remove the exclusions |
| `real-messy-exclusion-group` | MFA exclusions group | A security group "MFA exclusions" with one member, in `excludeGroups` of the all-users policy | none | Remove the exclusion, delete the group |
| `real-messy-new-user` | user created after the registration report | A licensed member; capture `after` within the hour, before the report refreshes and before the next backup | none | Delete the user |
| `real-messy-reimaged` | laptop re-imaged | Reset `lab-lt-01` (Settings, System, Recovery, Reset this PC, Remove everything) and let it re-join, re-enroll and re-onboard; retire its old Intune record | 1 to 2 days | None: the re-imaged laptop is the new normal |
| `real-messy-vm-off` | VM off for 8 days | Deallocate `lab-lt-02` | 8 days | Start it |
| `real-messy-sensor-cut` | sensor cut off | A network security group rule on `lab-lt-03` that denies outbound traffic to the Internet service tag | 1 day | Remove the rule |
| `real-messy-discovered` | discovered unmanaged PC | An Ubuntu VM in the same virtual network, never onboarded; Defender's device discovery may find it | 1 to 2 days | Delete the VM |
| `real-messy-renamed` | device renamed after onboarding | `Rename-Computer -NewName lab-lt-03b -Restart` on `lab-lt-03` | 1 day | Rename it back |
| `real-messy-over-limit` | 11th user over the Veeam limit | An 11th licensed mailbox user; let the nightly job run | 1 day | Delete the user |
| `real-messy-paused` | backup job paused for 2 days | Disable the backup job | 2 days | Enable it |
| `real-messy-shared-mailbox` | shared mailbox Veeam never saw | A second shared mailbox "Front Desk", excluded from the backup job | 1 day | Delete it |
| `real-messy-paged` | users export is one page of several | No change in the tenant: copy `before` to `after`, then replace `after`'s `users.json` with the command below | none | none |

The paged users export, in `pwsh`, after signing in to the lab tenant with the one scope it needs:

```powershell
Connect-MgGraph -NoWelcome -TenantId <tenant ID> -Scopes 'User.Read.All'
Invoke-MgGraphRequest -Method GET -Uri 'v1.0/users?$select=id,userPrincipalName,displayName,accountEnabled,userType&$top=5' `
    -OutputType Json | Out-File firm/lab/raw/real-messy-paged/after/exports/users.json -Encoding utf8
```

What the twins can show that the operators guess:

- **The sensor cut.** The health status Defender reports for a sensor that cannot reach it may not be
  `ImpairedCommunication`. The fidelity check compares which fields change, not their values, and any status but
  Active is a gap.
- **Discovery.** It may find nothing in an Azure network. Then there is no `real-messy-discovered`, and the operator
  stays without a twin.
- **A nameless device.** If a discovered device comes back with a null `computerDnsName`, the reader stops the run.
  The "discovered device with no DNS name" operator keeps that refusal for now (`may_stop`); a real capture showing it
  is the prompt to decide whether the reader should read such a device instead.

## 5. When a capture disagrees

- **A run stops on a capture.** Decide, case by case, whether the reader is too strict for what the API really writes,
  or whether the refusal stays and `exports.md` changes the export so the firm avoids it.
- **A fidelity mismatch.** Fix the operator so it makes the mess the way the tenant did. Never edit the capture.
- **A false backed.** Fix the rule in its own change, with the operator as the regression test.

## 6. Teardown

1. Delete the `attest-lab` resource group. Cancel the Azure subscription if it was made for the lab.
2. Delete the `attest-lab-export` app registration.
3. Microsoft 365 admin center, Billing, Your products: cancel the Business Premium trial before it bills.
4. Keep `firm/lab/raw/deny.txt` so the guard test can keep checking for the tenant's names; delete the rest of
   `firm/lab/raw/`.
