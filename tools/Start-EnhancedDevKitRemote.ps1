[CmdletBinding()]
param(
    [string]$DevKitRoot = 'F:\CEUE5Devkit'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedRoot = (Resolve-Path -LiteralPath $DevKitRoot).Path
$buildVersionPath = Join-Path $resolvedRoot 'Engine\Build\Build.version'
$projectPath = Join-Path $resolvedRoot 'UE4\ConanSandbox.uproject'
$editorPath = Join-Path $resolvedRoot 'Engine\Binaries\Win64\UnrealEditor.exe'

foreach ($requiredPath in @($buildVersionPath, $projectPath, $editorPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Enhanced DevKit file is missing: $requiredPath"
    }
}

$buildVersion = Get-Content -LiteralPath $buildVersionPath -Raw | ConvertFrom-Json
if ($buildVersion.MajorVersion -ne 5 -or $buildVersion.MinorVersion -ne 6) {
    throw "Wrong DevKit engine version $($buildVersion.MajorVersion).$($buildVersion.MinorVersion). Exile Drone Director requires UE 5.6."
}

$runningEditors = @(
    Get-Process -Name UnrealEditor,ConanSandbox -ErrorAction SilentlyContinue
)
if ($runningEditors.Count -ne 0) {
    $identity = ($runningEditors | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ', '
    throw "An Unreal editor is already running ($identity). Refusing to launch an ambiguous second remote node."
}

$arguments = @(
    $projectPath,
    '-ModDevKit',
    '-EnablePlugin=PythonScriptPlugin',
    '-EnablePlugin=EditorScriptingUtilities',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=True',
    '-nop4',
    '-nosplash'
)

$process = Start-Process -FilePath $editorPath -ArgumentList $arguments -PassThru
Write-Output "Enhanced DevKit remote editor started: PID $($process.Id)"
Write-Output "Engine: $($buildVersion.MajorVersion).$($buildVersion.MinorVersion).$($buildVersion.PatchVersion) CL $($buildVersion.Changelist)"
Write-Output 'EDD_REMOTE_EDITOR|STARTED'
