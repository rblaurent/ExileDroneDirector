[CmdletBinding()]
param(
    [string]$DevKitRoot = 'F:\CEUE5Devkit'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$invoke = Join-Path $projectRoot 'tools\Invoke-UnrealPython.ps1'
$logPath = Join-Path $DevKitRoot 'UE4\Saved\Logs\ConanSandbox.log'

& python (Join-Path $projectRoot 'tools\repository\test_blueprint_repository_service_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Repository service schema contracts failed with exit code $LASTEXITCODE."
}

$steps = @(
    @{
        Script = 'tools\unreal\Configure-RepositoryService.py'
        Marker = 'EDD_REPOSITORY_SERVICE_CONFIG:COMPLETE:True'
    },
    @{
        Script = 'tools\unreal\Validate-RepositoryJsonCodec.py'
        Marker = 'EDD_REPOSITORY_JSON_CODEC:COMPLETE:True'
    }
)

foreach ($step in $steps) {
    & $invoke -ScriptPath (Join-Path $projectRoot $step.Script) -DevKitRoot $DevKitRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Repository service step failed: $($step.Script)"
    }
    if (-not (Select-String -LiteralPath $logPath -SimpleMatch $step.Marker | Select-Object -Last 1)) {
        throw "Repository service marker missing: $($step.Marker)"
    }
    Write-Output "Observed: $($step.Marker)"
}

Write-Output 'Repository service seam acceptance passed.'
