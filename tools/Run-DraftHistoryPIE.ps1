[CmdletBinding()]
param(
    [string]$DevKitRoot = 'F:\CEUE5Devkit',
    [int]$StartupTimeoutSeconds = 300,
    [int]$InputTimeoutSeconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$harnessPath = Join-Path $repoRoot 'tools\unreal\Validate-DraftHistoryShortcutsPIE.py'
$editorPath = Join-Path $DevKitRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$projectPath = Join-Path $DevKitRoot 'UE4\ConanSandbox.uproject'
$logPath = Join-Path $DevKitRoot 'UE4\Saved\Logs\ConanSandbox.log'
$runId = [Guid]::NewGuid().ToString('N')
$prefix = "EDD_HISTORY_SHORTCUT_PIE:${runId}:"
$bootstrap = "-ExecCmds=`"py exec(open(r'$harnessPath').read())`""
$editorProcess = $null

foreach ($requiredPath in @($harnessPath, $editorPath, $projectPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file is missing: $requiredPath"
    }
}
if (Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue) {
    throw 'UnrealEditor is already running. Close it before starting the isolated PIE acceptance run.'
}

function Wait-RunMarker {
    param(
        [Parameter(Mandatory = $true)][string]$Marker,
        [int]$TimeoutSeconds = $InputTimeoutSeconds
    )

    $expected = "$prefix$Marker"
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($editorProcess -and $editorProcess.HasExited) {
            throw "Unreal exited while waiting for $expected"
        }
        if (Test-Path -LiteralPath $logPath) {
            $match = Select-String -LiteralPath $logPath -SimpleMatch $expected | Select-Object -Last 1
            if ($match) {
                Write-Output "Observed: $expected"
                return
            }
            $failure = Select-String -LiteralPath $logPath -SimpleMatch "${prefix}AUTOMATIC_RESULT:FAIL" | Select-Object -Last 1
            if ($failure) {
                throw "Harness reported failure before $expected"
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Timed out waiting for $expected"
}

try {
    $arguments = @(
        $projectPath,
        '-ModDevKit',
        "-EDDPIERunId=$runId",
        $bootstrap
    )
    $editorProcess = Start-Process -FilePath $editorPath -ArgumentList $arguments -PassThru
    Write-Output "Run ID: $runId"
    Write-Output "Unreal PID: $($editorProcess.Id)"

    Wait-RunMarker -Marker 'ARMED:True' -TimeoutSeconds $StartupTimeoutSeconds
    Wait-RunMarker -Marker 'SOURCE_LEVEL_READY:/Game/Dev/AlmostEmpty' -TimeoutSeconds $StartupTimeoutSeconds
    Wait-RunMarker -Marker 'PIE_START_REQUESTED:True' -TimeoutSeconds $StartupTimeoutSeconds
    Wait-RunMarker -Marker 'SURVIVAL_GUARD_REQUESTED:True' -TimeoutSeconds $StartupTimeoutSeconds

    Wait-RunMarker -Marker 'PIE_END_REQUESTED:True'
    Wait-RunMarker -Marker 'AUTOMATIC_RESULT:PASS'
    Write-Output 'Draft-history PIE acceptance passed.'
}
finally {
    if ($editorProcess -and -not $editorProcess.HasExited) {
        $liveProcess = Get-Process -Id $editorProcess.Id -ErrorAction SilentlyContinue
        if ($liveProcess) {
            $null = $liveProcess.CloseMainWindow()
            $liveProcess.WaitForExit(30000)
        }
        if ($liveProcess -and -not $liveProcess.HasExited) {
            Write-Warning 'Graceful editor close timed out; stopping the runner-owned, non-mutating test process.'
            Stop-Process -Id $liveProcess.Id -Force
            $liveProcess.WaitForExit(10000)
        }
    }
    Write-Output 'UnrealEditor closed.'
}
