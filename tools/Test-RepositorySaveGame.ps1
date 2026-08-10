[CmdletBinding()]
param(
    [string]$DevKitRoot = 'F:\CEUE5Devkit'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$invoke = Join-Path $projectRoot 'tools\Invoke-UnrealPython.ps1'
$logPath = Join-Path $DevKitRoot 'UE4\Saved\Logs\ConanSandbox.log'
$steps = @(
    @{
        Script = 'tools\unreal\Configure-RepositorySaveGame.py'
        Marker = 'EDD_REPOSITORY_SAVEGAME_CONFIG:COMPLETE:True'
    },
    @{
        Script = 'tools\unreal\Write-RepositorySaveGameProbe.py'
        Marker = 'EDD_REPOSITORY_SAVEGAME_WRITE:SAME_PROCESS_VERIFIED:'
    },
    @{
        Script = 'tools\unreal\Read-RepositorySaveGameProbe.py'
        Marker = 'EDD_REPOSITORY_SAVEGAME_READ:FRESH_PROCESS_VERIFIED:'
    }
)

foreach ($step in $steps) {
    $scriptPath = Join-Path $projectRoot $step.Script
    & $invoke -ScriptPath $scriptPath -DevKitRoot $DevKitRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Repository SaveGame step failed: $($step.Script)"
    }
    $observed = Select-String -LiteralPath $logPath -SimpleMatch $step.Marker | Select-Object -Last 1
    if (-not $observed) {
        throw "Repository SaveGame marker missing after $($step.Script): $($step.Marker)"
    }
    Write-Output "Observed: $($step.Marker)"
}

$cleanup = Select-String -LiteralPath $logPath -SimpleMatch 'EDD_REPOSITORY_SAVEGAME_READ:CLEANUP_VERIFIED:True' | Select-Object -Last 1
if (-not $cleanup) {
    throw 'Repository SaveGame cleanup marker missing.'
}
Write-Output 'Repository SaveGame cross-process acceptance passed.'
