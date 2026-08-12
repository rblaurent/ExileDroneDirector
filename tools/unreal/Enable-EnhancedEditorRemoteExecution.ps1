[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$DevKitRoot = 'F:\CEUE5Devkit',

    [string]$ConfigPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$usingDefaultConfig = [string]::IsNullOrWhiteSpace($ConfigPath)
if ($usingDefaultConfig) {
    $ConfigPath = Join-Path $DevKitRoot 'UE4\Saved\Config\WindowsEditor\Engine.ini'
}
$resolvedConfig = [IO.Path]::GetFullPath($ConfigPath)
if (-not [IO.File]::Exists($resolvedConfig)) {
    throw "Enhanced editor Engine.ini is missing: $resolvedConfig"
}

# Unreal persists the in-memory settings object during shutdown. Editing the
# live Engine.ini first appears to succeed, then the closing editor silently
# writes its stale copy over the new bRemoteExecution value. The real DevKit
# configuration must therefore be provisioned only across a closed-editor
# boundary. Fixture ConfigPath calls remain available to the contract tests.
if ($usingDefaultConfig) {
    $resolvedDevKitRoot = [IO.Path]::GetFullPath($DevKitRoot).TrimEnd('\')
    $liveEditors = @(Get-Process UnrealEditor -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and [IO.Path]::GetFullPath($_.Path).StartsWith($resolvedDevKitRoot, [StringComparison]::OrdinalIgnoreCase) }
        catch { $false }
    })
    if ($liveEditors.Count -gt 0) {
        throw "Close the Enhanced editor before provisioning remote execution; live settings would overwrite Engine.ini on shutdown (PID(s): $($liveEditors.Id -join ', '))."
    }
}

$section = '[/Script/PythonScriptPlugin.PythonScriptPluginSettings]'
$required = [ordered]@{
    bRemoteExecution = 'True'
    RemoteExecutionMulticastGroupEndpoint = '239.0.0.1:6766'
    RemoteExecutionMulticastBindAddress = '127.0.0.1'
    RemoteExecutionSendBufferSizeBytes = '2097152'
    RemoteExecutionReceiveBufferSizeBytes = '2097152'
    RemoteExecutionMulticastTtl = '0'
}

$text = [IO.File]::ReadAllText($resolvedConfig)
$newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
$lines = [Collections.Generic.List[string]]::new()
foreach ($line in ($text -split '\r?\n')) { $lines.Add($line) }

$sectionStart = -1
for ($index = 0; $index -lt $lines.Count; $index++) {
    if ($lines[$index].Trim() -eq $section) {
        if ($sectionStart -ge 0) { throw "Duplicate Python settings section in $resolvedConfig" }
        $sectionStart = $index
    }
}

if ($sectionStart -lt 0) {
    if ($lines.Count -gt 0 -and $lines[$lines.Count - 1] -ne '') { $lines.Add('') }
    $lines.Add($section)
    foreach ($entry in $required.GetEnumerator()) {
        $lines.Add("$($entry.Key)=$($entry.Value)")
    }
}
else {
    $sectionEnd = $lines.Count
    for ($index = $sectionStart + 1; $index -lt $lines.Count; $index++) {
        if ($lines[$index].Trim() -match '^\[.+\]$') {
            $sectionEnd = $index
            break
        }
    }
    foreach ($entry in $required.GetEnumerator()) {
        $matchingIndexes = @()
        for ($index = $sectionStart + 1; $index -lt $sectionEnd; $index++) {
            if ($lines[$index] -match "^\s*$([regex]::Escape($entry.Key))\s*=") {
                $matchingIndexes += $index
            }
        }
        if ($matchingIndexes.Count -gt 1) {
            throw "Duplicate $($entry.Key) in $resolvedConfig"
        }
        if ($matchingIndexes.Count -eq 1) {
            $lines[$matchingIndexes[0]] = "$($entry.Key)=$($entry.Value)"
        }
        else {
            $lines.Insert($sectionEnd, "$($entry.Key)=$($entry.Value)")
            $sectionEnd++
        }
    }
}

$updated = [string]::Join($newline, $lines)
if (-not $updated.EndsWith($newline)) { $updated += $newline }
if ($updated -ne $text -and $PSCmdlet.ShouldProcess($resolvedConfig, 'Enable Unreal Python remote execution')) {
    [IO.File]::WriteAllText($resolvedConfig, $updated, [Text.UTF8Encoding]::new($false))
}

$verified = [IO.File]::ReadAllText($resolvedConfig)
foreach ($entry in $required.GetEnumerator()) {
    $pattern = "(?m)^$([regex]::Escape($entry.Key))=$([regex]::Escape($entry.Value))\s*$"
    if ([regex]::Matches($verified, $pattern).Count -ne 1) {
        throw "Remote setting verification failed for $($entry.Key): $resolvedConfig"
    }
}
Write-Output "EDD_REMOTE_CONFIG|PASS|$resolvedConfig"
