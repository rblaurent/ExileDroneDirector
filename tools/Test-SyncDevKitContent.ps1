[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scratchRoot = $env:REDLEAF_SCRATCH_DIR
if ([string]::IsNullOrWhiteSpace($scratchRoot)) {
    throw 'REDLEAF_SCRATCH_DIR is required.'
}
$caseRoot = Join-Path $scratchRoot ("edd-sync-contract-" + [guid]::NewGuid().ToString('N'))
$devKitRoot = Join-Path $caseRoot 'DevKit'
$fakeProject = Join-Path $caseRoot 'Project'
$modRoot = Join-Path $devKitRoot 'UE4\Content\Mods\ExileDroneDirector'
$localAsset = Join-Path $modRoot 'Local\Core\Client\Expected.uasset'
$managedAsset = Join-Path $modRoot 'KitContent\ExileDroneDirector\Local\Forbidden.uasset'
$metadata = Join-Path $modRoot 'modinfo.json'

try {
    New-Item -ItemType Directory -Path (Join-Path $devKitRoot 'Engine\Build') -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $localAsset) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $managedAsset) -Force | Out-Null
    New-Item -ItemType Directory -Path $fakeProject -Force | Out-Null
    '{"MajorVersion":5,"MinorVersion":6,"PatchVersion":1}' | Set-Content -LiteralPath (Join-Path $devKitRoot 'Engine\Build\Build.version') -Encoding utf8
    'authored' | Set-Content -LiteralPath $localAsset -Encoding utf8
    'managed' | Set-Content -LiteralPath $managedAsset -Encoding utf8
    '{}' | Set-Content -LiteralPath $metadata -Encoding utf8

    & (Join-Path $ProjectRoot 'tools\Sync-DevKitContent.ps1') `
        -Direction FromDevKit -DevKitRoot $devKitRoot -ProjectRoot $fakeProject

    $mirror = Join-Path $fakeProject 'DevKitContent\ExileDroneDirector'
    if (-not (Test-Path -LiteralPath (Join-Path $mirror 'Local\Core\Client\Expected.uasset') -PathType Leaf)) {
        throw 'Authored Local asset was not mirrored.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $mirror 'modinfo.json') -PathType Leaf)) {
        throw 'Root modinfo.json was not mirrored.'
    }
    if (Test-Path -LiteralPath (Join-Path $mirror 'KitContent')) {
        throw 'DevKit-managed KitContent escaped the sync allowlist.'
    }
    $mirroredFiles = @(Get-ChildItem -LiteralPath $mirror -File -Recurse)
    if ($mirroredFiles.Count -ne 2) {
        throw "Expected exactly two allowlisted files, found $($mirroredFiles.Count)."
    }
    Write-Output 'EDD_SYNC_BOUNDARY|LOCAL_AND_METADATA|PASS'
    Write-Output 'EDD_SYNC_BOUNDARY|MANAGED_DIRECTORIES_EXCLUDED|PASS'
}
finally {
    $resolvedScratch = [IO.Path]::GetFullPath($scratchRoot).TrimEnd('\')
    $resolvedCase = [IO.Path]::GetFullPath($caseRoot)
    if ($resolvedCase.StartsWith($resolvedScratch + '\', [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedCase)) {
        Remove-Item -LiteralPath $resolvedCase -Recurse -Force
    }
}
