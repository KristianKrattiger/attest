<#
.SYNOPSIS
Take the lab tenant's exports exactly as docs/engineering/exports.md gives them, into one capture folder.

.DESCRIPTION
One part per run. Run -Part Graph and -Part Defender on the admin machine, in the PowerShell the capture is for
(pwsh for PowerShell 7, powershell.exe for Windows PowerShell 5.1). Run -Part Veeam on the Veeam server, then copy
veeam-users.json, veeam-user-properties.json and the manifest line it prints into the same folder.

Each part appends one manifest line per export to <Out>/manifest.yaml, with exported_at taken after that export
finished, in UTC with a Z (docs/engineering/exports.md, Recording exported_at). The lab procedure is
docs/engineering/lab.md.

.EXAMPLE
pwsh -File scripts/lab_capture.ps1 -Out firm/lab/raw/seed-clean/exports -Part Graph
#>
param(
    [Parameter(Mandatory)] [string] $Out,
    [Parameter(Mandatory)] [ValidateSet('Graph', 'Defender', 'Veeam')] [string] $Part,
    [string] $TenantId,
    [string] $AppId,
    [string] $Repository
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$manifest = Join-Path $Out 'manifest.yaml'
if (-not (Test-Path $manifest)) { Set-Content -Path $manifest -Value 'exports:' -Encoding ascii }

function Add-Entry([string] $File, [string] $Reader) {
    $at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $line = "  - {file: $File, reader: $Reader, exported_at: $at}"
    Add-Content -Path $manifest -Value $line -Encoding ascii
    Write-Output $line
}

function Save-Graph([string] $Uri, [string] $File, [string] $Reader) {
    Invoke-MgGraphRequest -Method GET -Uri $Uri -OutputType Json | Out-File (Join-Path $Out $File) -Encoding utf8
    Add-Entry $File $Reader
}

if ($Part -eq 'Graph') {
    Connect-MgGraph -NoWelcome -Scopes 'User.Read.All', 'AuditLog.Read.All', 'Policy.Read.All',
        'RoleManagement.Read.Directory', 'DeviceManagementManagedDevices.Read.All'
    Save-Graph 'v1.0/users?$select=id,userPrincipalName,displayName,accountEnabled,userType&$top=999' `
        'users.json' 'entra_users'
    Save-Graph 'v1.0/reports/authenticationMethods/userRegistrationDetails' 'registration.json' 'entra_registration'
    Save-Graph 'v1.0/identity/conditionalAccess/policies' 'ca-policies.json' 'entra_ca_policies'
    Save-Graph 'v1.0/policies/identitySecurityDefaultsEnforcementPolicy' 'security-defaults.json' `
        'entra_security_defaults'
    Save-Graph 'v1.0/roleManagement/directory/roleAssignments?$expand=principal' 'role-assignments.json' `
        'entra_role_assignments'
    Save-Graph ('v1.0/deviceManagement/managedDevices?$select=id,deviceName,azureADDeviceId,operatingSystem,' +
        'userPrincipalName') 'intune-devices.json' 'intune_devices'
}

if ($Part -eq 'Defender') {
    if (-not $TenantId -or -not $AppId) { throw '-Part Defender needs -TenantId and -AppId' }
    $secret = Read-Host -AsSecureString 'Client secret of the lab app registration'
    $plain = [System.Net.NetworkCredential]::new('', $secret).Password
    $token = (Invoke-RestMethod -Method Post -Uri "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token" `
        -Body @{ client_id = $AppId; client_secret = $plain; grant_type = 'client_credentials'
                 scope = 'https://api.securitycenter.microsoft.com/.default' }).access_token
    Invoke-RestMethod -Uri 'https://api.security.microsoft.com/api/machines' `
        -Headers @{ Authorization = "Bearer $token" } |
        ConvertTo-Json -Depth 6 | Out-File (Join-Path $Out 'defender-machines.json') -Encoding utf8
    Add-Entry 'defender-machines.json' 'defender_machines'
}

if ($Part -eq 'Veeam') {
    if (-not $Repository) { throw '-Part Veeam needs -Repository' }
    $repo = Get-VBORepository -Name $Repository
    Get-VBOEntityData -Type User -Repository $repo |
        Select-Object Email, DisplayName, IsMailboxBackedUp,
            @{ Name = 'MailboxBackedUpTime'; Expression = {
                if ($_.MailboxBackedUpTime) { $_.MailboxBackedUpTime.ToUniversalTime().ToString('o') } } } |
        ConvertTo-Json | Out-File (Join-Path $Out 'veeam-users.json') -Encoding utf8
    Add-Entry 'veeam-users.json' 'veeam_users'
    # Every property of one user as Veeam names them: the evidence for the reader's unconfirmed field names.
    Get-VBOEntityData -Type User -Repository $repo | Select-Object -First 1 -Property * |
        ConvertTo-Json -Depth 3 | Out-File (Join-Path $Out 'veeam-user-properties.json') -Encoding utf8
}
