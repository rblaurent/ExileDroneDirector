[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [long]$MaximumTrackedBytes = 1GB,
    [long]$MaximumFileBytes = 100MB
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $resolvedRoot '.git'))) {
    throw "Not a Git checkout: $resolvedRoot"
}

$allowedRootFiles = @(
    '.gitattributes',
    '.gitignore',
    'LICENSE',
    'README.md',
    'project.json'
)
$allowedPrefixes = @(
    'DevKitContent/ExileDroneDirector/',
    'docs/',
    'tools/'
)
$forbiddenSegments = @(
    '/Binaries/',
    '/Cooked/',
    '/DerivedDataCache/',
    '/Intermediate/',
    '/Saved/',
    '/StagedBuilds/'
)
$lfsExtensions = @('.uasset', '.umap', '.ubulk', '.uexp')

$trackedPaths = @(& git -C $resolvedRoot ls-files --cached --others --exclude-standard)
if ($LASTEXITCODE -ne 0) {
    throw 'git ls-files failed.'
}

$violations = [System.Collections.Generic.List[string]]::new()
$totalBytes = 0L

foreach ($gitPath in $trackedPaths) {
    $normalizedPath = $gitPath.Replace('\', '/')
    $isAllowed = ($allowedRootFiles -contains $normalizedPath) -or
        ($allowedPrefixes | Where-Object { $normalizedPath.StartsWith($_, [System.StringComparison]::Ordinal) })
    if (-not $isAllowed) {
        $violations.Add("Path is outside the repository allowlist: $normalizedPath")
    }

    $sentinelPath = "/$normalizedPath/"
    foreach ($segment in $forbiddenSegments) {
        if ($sentinelPath.IndexOf($segment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $violations.Add("Generated DevKit path must not be tracked: $normalizedPath")
        }
    }

    $physicalPath = Join-Path $resolvedRoot $gitPath
    if (-not (Test-Path -LiteralPath $physicalPath -PathType Leaf)) {
        continue
    }

    $file = Get-Item -LiteralPath $physicalPath
    $totalBytes += $file.Length
    if ($file.Length -gt $MaximumFileBytes) {
        $violations.Add("File exceeds the $MaximumFileBytes-byte limit: $normalizedPath ($($file.Length) bytes)")
    }

    if ($lfsExtensions -contains $file.Extension.ToLowerInvariant()) {
        $attributeLine = (& git -C $resolvedRoot check-attr filter -- $normalizedPath) -join ''
        if ($LASTEXITCODE -ne 0 -or $attributeLine -notmatch ': filter: lfs$') {
            $violations.Add("Unreal binary is not covered by Git LFS: $normalizedPath")
        }
    }
}

if ($totalBytes -gt $MaximumTrackedBytes) {
    $violations.Add("Tracked worktree exceeds the $MaximumTrackedBytes-byte repository budget: $totalBytes bytes")
}

Write-Output "Tracked files: $($trackedPaths.Count)"
Write-Output "Tracked bytes: $totalBytes"
Write-Output "Repository budget: $MaximumTrackedBytes bytes"
Write-Output "Maximum individual file: $MaximumFileBytes bytes"

if ($violations.Count -gt 0) {
    $violations | ForEach-Object { Write-Error $_ }
    throw "Repository budget validation failed with $($violations.Count) violation(s)."
}

Write-Output 'Repository budget valid: only Exile Drone Director source is tracked.'
