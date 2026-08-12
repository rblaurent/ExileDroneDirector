[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),

    [string]$ScratchRoot = $(
        if ($env:REDLEAF_SCRATCH_DIR) { $env:REDLEAF_SCRATCH_DIR }
        else { [IO.Path]::GetTempPath() }
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$helper = Join-Path $ProjectRoot 'tools\unreal\Enable-EnhancedEditorRemoteExecution.ps1'
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) {
    throw "Remote-execution helper is missing: $helper"
}

$nonce = [guid]::NewGuid().ToString('N')
$fixtureRoot = Join-Path $ScratchRoot "edd-remote-config-$nonce"
New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null

$section = '[/Script/PythonScriptPlugin.PythonScriptPluginSettings]'
$required = [ordered]@{
    bRemoteExecution = 'True'
    RemoteExecutionMulticastGroupEndpoint = '239.0.0.1:6766'
    RemoteExecutionMulticastBindAddress = '127.0.0.1'
    RemoteExecutionSendBufferSizeBytes = '2097152'
    RemoteExecutionReceiveBufferSizeBytes = '2097152'
    RemoteExecutionMulticastTtl = '0'
}

function Assert-ConfiguredFixture {
    param([Parameter(Mandatory = $true)][string]$Path)

    $text = [IO.File]::ReadAllText($Path)
    if ([regex]::Matches($text, "(?m)^$([regex]::Escape($section))\s*$").Count -ne 1) {
        throw "Expected exactly one Python settings section: $Path"
    }
    foreach ($entry in $required.GetEnumerator()) {
        $pattern = "(?m)^$([regex]::Escape($entry.Key))=$([regex]::Escape($entry.Value))\s*$"
        if ([regex]::Matches($text, $pattern).Count -ne 1) {
            throw "Remote setting contract failed for $($entry.Key): $Path"
        }
    }
}

try {
    $existing = Join-Path $fixtureRoot 'existing.ini'
    $existingText = @(
        '[Unrelated.Section]'
        'KeepThis=untouched'
        ''
        $section
        'CustomSetting=also-untouched'
        'bRemoteExecution=False'
        'RemoteExecutionMulticastGroupEndpoint=239.9.9.9:9999'
        ''
        '[Trailing.Section]'
        'TrailingValue=preserved'
    ) -join "`r`n"
    [IO.File]::WriteAllText($existing, "$existingText`r`n", [Text.UTF8Encoding]::new($false))

    & $helper -ConfigPath $existing | Out-Null
    Assert-ConfiguredFixture -Path $existing
    $firstHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $existing).Hash
    & $helper -ConfigPath $existing | Out-Null
    $secondHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $existing).Hash
    if ($firstHash -ne $secondHash) {
        throw 'Remote configurator is not idempotent for an existing section.'
    }
    $existingResult = [IO.File]::ReadAllText($existing)
    foreach ($preserved in @('KeepThis=untouched', 'CustomSetting=also-untouched', 'TrailingValue=preserved')) {
        if (-not $existingResult.Contains($preserved)) {
            throw "Remote configurator removed unrelated content: $preserved"
        }
    }
    if (-not $existingResult.Contains("`r`n")) {
        throw 'Remote configurator did not preserve CRLF newlines.'
    }

    $missing = Join-Path $fixtureRoot 'missing.ini'
    [IO.File]::WriteAllText($missing, "[Only.Section]`nValue=preserved`n", [Text.UTF8Encoding]::new($false))
    & $helper -ConfigPath $missing | Out-Null
    Assert-ConfiguredFixture -Path $missing
    if (-not [IO.File]::ReadAllText($missing).Contains("[Only.Section]`nValue=preserved")) {
        throw 'Remote configurator did not preserve an existing LF-only section.'
    }

    $duplicateSection = Join-Path $fixtureRoot 'duplicate-section.ini'
    [IO.File]::WriteAllText(
        $duplicateSection,
        "$section`nbRemoteExecution=True`n$section`nbRemoteExecution=True`n",
        [Text.UTF8Encoding]::new($false)
    )
    $rejectedDuplicateSection = $false
    try { & $helper -ConfigPath $duplicateSection | Out-Null }
    catch { $rejectedDuplicateSection = $_.Exception.Message -like 'Duplicate Python settings section*' }
    if (-not $rejectedDuplicateSection) {
        throw 'Remote configurator did not reject duplicate Python settings sections.'
    }

    $duplicateKey = Join-Path $fixtureRoot 'duplicate-key.ini'
    [IO.File]::WriteAllText(
        $duplicateKey,
        "$section`nbRemoteExecution=True`nbRemoteExecution=False`n",
        [Text.UTF8Encoding]::new($false)
    )
    $rejectedDuplicateKey = $false
    try { & $helper -ConfigPath $duplicateKey | Out-Null }
    catch { $rejectedDuplicateKey = $_.Exception.Message -like 'Duplicate bRemoteExecution*' }
    if (-not $rejectedDuplicateKey) {
        throw 'Remote configurator did not reject duplicate required settings.'
    }

    Write-Output 'EDD_REMOTE_CONFIG_TEST|RESULT|PASS'
}
finally {
    if (Test-Path -LiteralPath $fixtureRoot) {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
    }
}
