# Producing the exports

The firm runs these read-only while the reviewer watches. Write each file into
the firm's `exports/` folder and record the UTC time it was taken as its
`exported_at` in `exports/manifest.yaml`:

```yaml
exports:
  - {file: users.json, reader: entra_users, exported_at: 2026-10-01T15:00:00Z}
```

Every reader stops the run on a missing field, so a wrong export fails loudly.

## Microsoft Graph (Entra ID and Intune)

Use Microsoft Graph PowerShell and sign in with read-only scopes:

```powershell
Connect-MgGraph -Scopes "User.Read.All","AuditLog.Read.All","Policy.Read.All","RoleManagement.Read.Directory","DeviceManagementManagedDevices.Read.All"
```

`Invoke-MgGraphRequest -OutputType Json` returns the API's JSON unchanged.
Write it with `-Encoding utf8`. If a response carries `@odata.nextLink`, it is
one page of several and the reader refuses it, because v1 does not page.

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
`Machine.Read.All` (an application permission on WindowsDefenderATP). The
secret belongs to the firm's own app registration and is entered by the firm's
admin; it is never stored in the check's files. Get the token with the client
credentials flow:

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
time as UTC and a server east of UTC would look fresher than it is.

Reader `veeam_users`. One repository per export: a mailbox kept in another
repository shows as missing, which is a gap and never a false backed. The field
names come from Veeam's published examples, not its reference documentation;
check them against the first real export.
