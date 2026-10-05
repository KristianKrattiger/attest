# Producing the exports

The firm runs these read-only while the reviewer watches. Write each file into
the firm's `exports/` folder and record the time it was taken as its
`exported_at` in `exports/manifest.yaml`:

```yaml
exports:
  - {file: users.json, reader: entra_users, exported_at: 2026-10-01T15:00:00Z}
```

Every reader stops the run on a missing field, so a wrong export fails loudly.

## Recording `exported_at`

- Write it with a UTC offset (`Z`, or `-05:00`); a time without one stops the
  run, because read as UTC a local time east of UTC looks fresher than it is.
- Record it **after** the export finishes, and never round it down. Every
  staleness window ("last backup within 24 hours", "last seen within 7 days")
  is measured back from it: a time earlier than the real export makes old
  evidence look fresh, and a backup or check-in later than it is a gap.
- Take all the exports within 24 hours of one another. A verdict whose exports
  were taken further apart is unchecked: an account list from one month and a
  backup report from another describe different firms.

## What the readers refuse

- Duplicate rows (two rows for one user, policy, device or mailbox), and
  addresses (`userPrincipalName`, Veeam `Email`) with leading or trailing
  whitespace. Two records for one entity can disagree, and a padded address
  would pass as another account.
- Object IDs that are not GUIDs. User, group and role IDs (in the users,
  registration and role-assignment exports, and in Conditional Access policies)
  must be GUIDs, as Graph emits them; the reader compares them in canonical
  lower case, so an upper-case or braced copy still matches. Do not edit or
  retype them.
- A page with `@odata.nextLink` (one page of several), and a population export
  (users, Intune devices, role assignments) that is a single object instead of
  the list Graph returns.
- A time without a UTC offset (see above).

## Microsoft Graph (Entra ID and Intune)

Use Microsoft Graph PowerShell and sign in with read-only scopes:

```powershell
Connect-MgGraph -Scopes "User.Read.All","AuditLog.Read.All","Policy.Read.All","RoleManagement.Read.Directory","DeviceManagementManagedDevices.Read.All"
```

`Invoke-MgGraphRequest -OutputType Json` returns the API's JSON unchanged.
Write it with `-Encoding utf8`. If a response carries `@odata.nextLink`, it is
one page of several and the reader refuses it, because v1 does not page.

Run the Intune export as an administrator whose Intune role has no scope tags.
An exporter whose role carries scope tags sees only part of the fleet, and the
export does not say so: the EDR population silently shrinks to the devices
that role can see.

The role-assignment export lists active assignments only. Roles a user is
merely eligible for under Privileged Identity Management (Entra ID P2) are
absent from `roleAssignments`, so on a P2 tenant that uses PIM the admin
population does not include eligible administrators.

| Reader | Command | Fields documented at |
|---|---|---|
| `entra_users` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/users?$select=id,userPrincipalName,displayName,accountEnabled,userType&$top=999' -OutputType Json \| Out-File users.json -Encoding utf8` | [user](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0) |
| `entra_registration` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/reports/authenticationMethods/userRegistrationDetails' -OutputType Json \| Out-File registration.json -Encoding utf8` | [userRegistrationDetails](https://learn.microsoft.com/en-us/graph/api/resources/userregistrationdetails?view=graph-rest-1.0) |
| `entra_ca_policies` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/identity/conditionalAccess/policies' -OutputType Json \| Out-File ca-policies.json -Encoding utf8` | [conditionalAccessPolicy](https://learn.microsoft.com/en-us/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0) |
| `entra_security_defaults` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/policies/identitySecurityDefaultsEnforcementPolicy' -OutputType Json \| Out-File security-defaults.json -Encoding utf8` | [identitySecurityDefaultsEnforcementPolicy](https://learn.microsoft.com/en-us/graph/api/resources/identitysecuritydefaultsenforcementpolicy?view=graph-rest-1.0) |
| `entra_role_assignments` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/roleManagement/directory/roleAssignments?$expand=principal' -OutputType Json \| Out-File role-assignments.json -Encoding utf8` | [unifiedRoleAssignment](https://learn.microsoft.com/en-us/graph/api/resources/unifiedroleassignment?view=graph-rest-1.0) |
| `intune_devices` | `Invoke-MgGraphRequest -Method GET -Uri 'v1.0/deviceManagement/managedDevices?$select=id,deviceName,azureADDeviceId,operatingSystem,userPrincipalName' -OutputType Json \| Out-File intune-devices.json -Encoding utf8` | [managedDevice](https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice?view=graph-rest-1.0) |

## Defender for Endpoint

The Defender API needs a token from an Entra app registration granted
`Machine.Read.All` (an application permission on WindowsDefenderATP). An
application permission needs admin consent: a Global Administrator (or another
role allowed to consent) grants it once for the tenant. The secret belongs to
the firm's own app registration and is entered by the firm's admin; it is
never stored in the check's files. Get the token with the client credentials
flow:

```powershell
$token = (Invoke-RestMethod -Method Post -Uri "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token" -Body @{
  client_id = $appId; client_secret = $secret; grant_type = 'client_credentials'
  scope = 'https://api.securitycenter.microsoft.com/.default' }).access_token
```

`Invoke-RestMethod` parses the JSON, so write it back with enough depth:

```powershell
Invoke-RestMethod -Uri 'https://api.security.microsoft.com/api/machines' -Headers @{ Authorization = "Bearer $token" } |
  ConvertTo-Json -Depth 6 | Out-File defender-machines.json -Encoding utf8
```

The hosts above are the commercial cloud's. Government and regional clouds
use other sign-in and API hosts; take them from Microsoft's Defender for
Endpoint API documentation for the tenant's cloud.

Reader `defender_machines`. Fields: [Machine](https://learn.microsoft.com/en-us/defender-endpoint/api/machine).

## Veeam Backup for Microsoft 365

On the Veeam server, for the repository that holds the firm's mailboxes:

```powershell
Get-VBOEntityData -Type User -Repository (Get-VBORepository -Name '<repository>') |
  Select-Object Email, DisplayName, IsMailboxBackedUp,
    @{ Name = 'MailboxBackedUpTime'; Expression = { if ($_.MailboxBackedUpTime) { $_.MailboxBackedUpTime.ToUniversalTime().ToString('o') } } } |
  ConvertTo-Json | Out-File veeam-users.json -Encoding utf8
```

The reader refuses a backup time with no UTC offset, because it would take that
time as UTC and a server east of UTC would look fresher than it is. It also
refuses an `Email` with leading or trailing whitespace, and two rows for one
`Email` (in any case).

The rule matches each Veeam `Email` to an Entra `userPrincipalName`, without
regard to case. Check on the first real export that `Email` holds the UPN and
not a different primary SMTP address: where they differ, the account shows as
having no mailbox in Veeam, a gap and never a false backed. Disabled accounts
that Veeam lists (shared mailboxes are disabled user objects) are counted in
the backup population.

Reader `veeam_users`. One repository per export: a mailbox kept in another
repository shows as missing, which is a gap and never a false backed. The field
names come from Veeam's published examples, not its reference documentation;
check them against the first real export.
