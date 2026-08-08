[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$RequireMvpAssets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$requiredFiles = @(
    'README.md',
    'project.json',
    'docs\product-design.md',
    'docs\architecture.md',
    'docs\event-system.md',
    'docs\devkit-findings.md',
    'docs\blueprint-workflow.md',
    'docs\visual-design-system.md',
    'docs\implementation-plan.md',
    '.gitattributes',
    '.gitignore',
    'tools\Sync-DevKitContent.ps1',
    'tools\Test-RepositoryBudget.ps1',
    'tools\Invoke-UnrealPython.ps1',
    'tools\unreal\Probe-EnhancedApi.py',
    'tools\unreal\Inspect-BlueprintApi.py',
    'tools\unreal\Inspect-GraphApi.py',
    'tools\unreal\Configure-ClientDirectorVariables.py',
    'tools\unreal\Generate-MvpScaffold.py',
    'tools\blueprint\Export-BlueprintGraphClipboard.ps1',
    'tools\blueprint\Set-BlueprintGraphClipboard.ps1',
    'tools\blueprint\Test-BlueprintGraphSnippet.ps1',
    'tools\blueprint\Test-BlueprintGraphContracts.ps1',
    'tools\blueprint\snippets\toggle-input.eddgraph',
    'tools\blueprint\snippets\toggle-state.eddgraph',
    'tools\blueprint\snippets\enter-drone-mode.eddgraph',
    'tools\blueprint\snippets\activate-drone-view.eddgraph',
    'tools\blueprint\snippets\switch-to-drone-view.eddgraph',
    'tools\blueprint\snippets\exit-drone-mode.eddgraph'
)

$missing = @(
    $requiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
    }
)

if ($missing.Count -gt 0) {
    throw "Missing scaffold files: $($missing -join ', ')"
}

$manifestPath = Join-Path $ProjectRoot 'project.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.modFolder -ne 'ExileDroneDirector') {
    throw "Unexpected modFolder in project.json: $($manifest.modFolder)"
}

$contentRoot = Join-Path $ProjectRoot "DevKitContent\$($manifest.modFolder)"
if (-not (Test-Path -LiteralPath $contentRoot -PathType Container)) {
    throw "Missing DevKit content mirror: $contentRoot"
}

if ($RequireMvpAssets) {
    $missingAssets = @(
        $manifest.mvpAssets | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $contentRoot $_) -PathType Leaf)
        }
    )
    if ($missingAssets.Count -gt 0) {
        throw "Missing MVP assets: $($missingAssets -join ', ')"
    }
}

Write-Output "Scaffold valid: $($manifest.name) $($manifest.version)"
Write-Output "Content mirror: $contentRoot"
if (-not $RequireMvpAssets) {
    Write-Output 'MVP asset presence was not required for this pre-DevKit validation.'
}

& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphContracts.ps1') `
    -ProjectRoot $ProjectRoot
