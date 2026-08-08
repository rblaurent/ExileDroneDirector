[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string]$DevKitRoot = 'F:\CEUE5Devkit',

    [switch]$AllowEditorRunning,

    [switch]$WithRendering
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedRoot = (Resolve-Path -LiteralPath $DevKitRoot).Path
$resolvedScript = (Resolve-Path -LiteralPath $ScriptPath).Path
$buildVersionPath = Join-Path $resolvedRoot 'Engine\Build\Build.version'
$projectPath = Join-Path $resolvedRoot 'UE4\ConanSandbox.uproject'
$editorCommand = Join-Path $resolvedRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'

foreach ($requiredPath in @($buildVersionPath, $projectPath, $editorCommand)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Enhanced DevKit file is missing: $requiredPath"
    }
}

$buildVersion = Get-Content -LiteralPath $buildVersionPath -Raw | ConvertFrom-Json
if ($buildVersion.MajorVersion -ne 5 -or $buildVersion.MinorVersion -ne 6) {
    throw "Wrong DevKit engine version $($buildVersion.MajorVersion).$($buildVersion.MinorVersion). Exile Drone Director requires UE 5.6."
}

$runningEditor = Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue
if ($runningEditor -and -not $AllowEditorRunning) {
    throw 'UnrealEditor is running. Close it before executing an asset-mutating script, or pass -AllowEditorRunning only for a read-only probe.'
}

$arguments = @(
    $projectPath,
    '-run=pythonscript',
    "-script=$resolvedScript",
    '-ModDevKit',
    '-EnablePlugin=PythonScriptPlugin',
    '-EnablePlugin=EditorScriptingUtilities',
    '-unattended',
    '-nop4',
    '-nosplash',
    '-stdout',
    '-FullStdOutLogOutput'
)
if (-not $WithRendering) {
    $arguments += '-NullRHI'
}

Write-Output "Enhanced DevKit: $resolvedRoot"
Write-Output "Python script: $resolvedScript"
Write-Output "Engine: $($buildVersion.MajorVersion).$($buildVersion.MinorVersion).$($buildVersion.PatchVersion) CL $($buildVersion.Changelist)"

& $editorCommand @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Unreal Python commandlet failed with exit code $LASTEXITCODE."
}

