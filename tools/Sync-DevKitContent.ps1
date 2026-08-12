[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('FromDevKit', 'ToDevKit')]
    [string]$Direction,

    [Parameter(Mandatory = $true)]
    [string]$DevKitRoot,

    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$modName = 'ExileDroneDirector'
$assetExtensions = @('.uasset', '.umap', '.ubulk', '.uexp')
$metadataNames = @('modinfo.json')

$resolvedRoot = (Resolve-Path -LiteralPath $DevKitRoot).Path
$buildVersionPath = Join-Path $resolvedRoot 'Engine\Build\Build.version'
if (-not (Test-Path -LiteralPath $buildVersionPath -PathType Leaf)) {
    throw "No Unreal Engine Build.version was found beneath '$resolvedRoot'."
}

$buildVersion = Get-Content -LiteralPath $buildVersionPath -Raw | ConvertFrom-Json
if ($buildVersion.MajorVersion -ne 5 -or $buildVersion.MinorVersion -ne 6) {
    throw "Wrong DevKit engine version $($buildVersion.MajorVersion).$($buildVersion.MinorVersion).$($buildVersion.PatchVersion) at '$resolvedRoot'. Exile Drone Director requires the Conan Exiles Enhanced UE 5.6 DevKit; the similarly named UE 4.15 kit is Legacy."
}

$candidateModRoots = @(
    (Join-Path $resolvedRoot 'UE4\Content\Mods'),
    (Join-Path $resolvedRoot 'Games\ConanSandbox\Content\Mods')
)
$devKitModsRoot = $candidateModRoots | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $devKitModsRoot) {
    throw "No Conan DevKit Content/Mods directory was found beneath '$resolvedRoot'."
}

$workspaceMod = Join-Path $ProjectRoot "DevKitContent\$modName"
$devKitMod = Join-Path $devKitModsRoot $modName

if ($Direction -eq 'FromDevKit') {
    $source = $devKitMod
    $destination = $workspaceMod
} else {
    $source = $workspaceMod
    $destination = $devKitMod
}

if (-not (Test-Path -LiteralPath $source)) {
    throw "Source mod directory does not exist: $source"
}

if (-not (Test-Path -LiteralPath $destination)) {
    if ($PSCmdlet.ShouldProcess($destination, 'Create destination mod directory')) {
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
    }
}

$copied = 0
$unchanged = 0
$conflicts = [System.Collections.Generic.List[string]]::new()
$sourceFiles = @()
$sourceLocal = Join-Path $source 'Local'
if (Test-Path -LiteralPath $sourceLocal -PathType Container) {
    $sourceFiles += Get-ChildItem -LiteralPath $sourceLocal -File -Recurse |
        Where-Object { $assetExtensions -contains $_.Extension.ToLowerInvariant() }
}
foreach ($metadataName in $metadataNames) {
    $metadataPath = Join-Path $source $metadataName
    if (Test-Path -LiteralPath $metadataPath -PathType Leaf) {
        $sourceFiles += Get-Item -LiteralPath $metadataPath
    }
}

foreach ($file in $sourceFiles) {
    $relativePath = $file.FullName.Substring($source.Length).TrimStart([char[]]@('\', '/'))
    $targetPath = Join-Path $destination $relativePath
    $targetDirectory = Split-Path -Parent $targetPath

    if (Test-Path -LiteralPath $targetPath) {
        $sourceHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash
        if ($sourceHash -eq $targetHash) {
            $unchanged++
            continue
        }
        if (-not $Force) {
            $conflicts.Add($relativePath)
            continue
        }
    }

    if ($PSCmdlet.ShouldProcess($targetPath, "Copy $relativePath")) {
        if (-not (Test-Path -LiteralPath $targetDirectory)) {
            New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $targetPath -Force
        $copied++
    }
}

Write-Output "Direction: $Direction"
Write-Output "Source: $source"
Write-Output "Destination: $destination"
Write-Output "Copied: $copied"
Write-Output "Unchanged: $unchanged"
Write-Output "Conflicts skipped: $($conflicts.Count)"

if ($conflicts.Count -gt 0) {
    $conflicts | ForEach-Object { Write-Warning "Different destination asset: $_" }
    throw 'Asset conflicts were skipped. Review them, close the DevKit, and rerun with -Force if replacement is intended.'
}
