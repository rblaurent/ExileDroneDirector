[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-GraphMatch {
    param([string]$Text, [string]$Pattern, [string]$Failure)
    if ($Text -notmatch $Pattern) {
        throw $Failure
    }
}

function Get-NodeBlock {
    param([string]$Text, [string]$NodeName)
    $escapedName = [regex]::Escape($NodeName)
    $match = [regex]::Match(
        $Text,
        ('(?ms)^Begin Object Class=[^\r\n]* Name="{0}"[^\r\n]*\r?\n.*?^End Object\s*$' -f $escapedName)
    )
    if (-not $match.Success) {
        throw "Expected node '$NodeName' was not found."
    }
    return $match.Value
}

$snippetRoot = Join-Path $ProjectRoot 'tools\blueprint\snippets'
$inputPath = Join-Path $snippetRoot 'toggle-input.eddgraph'
$statePath = Join-Path $snippetRoot 'toggle-state.eddgraph'
$enterPath = Join-Path $snippetRoot 'enter-drone-mode.eddgraph'
$validator = Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1'

& $validator -Path @($inputPath, $statePath, $enterPath) -AllowTokens | Write-Verbose

$input = [IO.File]::ReadAllText($inputPath)
$inputNodes = [regex]::Matches($input, '(?m)^Begin Object Class=').Count
if ($inputNodes -ne 5) {
    throw "Toggle-input contract expected 5 nodes; found $inputNodes."
}
Assert-GraphMatch $input 'MemberName="WasInputKeyJustPressed"' 'Toggle-input must use edge-triggered key polling.'
Assert-GraphMatch $input 'MemberName="GetPlayerController"' 'Toggle-input must resolve the local player controller.'
Assert-GraphMatch $input 'DefaultValue="\{\{INPUT_KEY\}\}"' 'Toggle-input must expose the INPUT_KEY token.'
Assert-GraphMatch $input 'DefaultValue="\{\{DIAGNOSTIC_TEXT\}\}"' 'Toggle-input must expose the DIAGNOSTIC_TEXT token.'
Assert-GraphMatch $input 'PinName="Condition"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Toggle-input Branch condition must consume WasInputKeyJustPressed.'
Assert-GraphMatch $input 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_3 ' 'Toggle-input true path must execute its diagnostic.'

$state = [IO.File]::ReadAllText($statePath)
$stateNodes = [regex]::Matches($state, '(?m)^Begin Object Class=').Count
if ($stateNodes -ne 5) {
    throw "Toggle-state contract expected 5 nodes; found $stateNodes."
}

$stateGet = Get-NodeBlock $state 'K2Node_VariableGet_0'
$stateNot = Get-NodeBlock $state 'K2Node_CallFunction_4'
$stateSet = Get-NodeBlock $state 'K2Node_VariableSet_0'
$stateToString = Get-NodeBlock $state 'K2Node_CallFunction_38'
$statePrint = Get-NodeBlock $state 'K2Node_CallFunction_3'

Assert-GraphMatch $stateGet 'VariableReference=\(MemberName="DroneModeActive"' 'Toggle-state must read DroneModeActive.'
Assert-GraphMatch $stateGet 'LinkedTo=\(K2Node_CallFunction_4 ' 'DroneModeActive getter must feed Boolean NOT.'
Assert-GraphMatch $stateNot 'MemberName="Not_PreBool"' 'Toggle-state must compute the complement of the previous value.'
Assert-GraphMatch $stateNot 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'Boolean NOT must feed the DroneModeActive setter.'
Assert-GraphMatch $stateSet 'VariableReference=\(MemberName="DroneModeActive"' 'Toggle-state must write DroneModeActive.'
Assert-GraphMatch $stateSet 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Toggle-state must report only after the state write completes.'
Assert-GraphMatch $stateSet 'PinName="Output_Get"[^\r\n]*LinkedTo=\(K2Node_CallFunction_38 ' 'Toggle-state diagnostic must consume the post-set value.'

$setExecute = [regex]::Match($stateSet, '(?m)^\s*CustomProperties Pin \([^\r\n]*PinName="execute"[^\r\n]*$')
if (-not $setExecute.Success -or $setExecute.Value -match 'LinkedTo=') {
    throw 'Toggle-state execute pin is the public entry point and must not retain an external link.'
}
Assert-GraphMatch $stateToString 'MemberName="Conv_BoolToString"' 'Toggle-state must convert the resulting Boolean to a diagnostic string.'
Assert-GraphMatch $stateToString 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Converted state must feed Print String.'
Assert-GraphMatch $statePrint 'MemberName="PrintString"' 'Toggle-state must expose a development diagnostic.'
Assert-GraphMatch $statePrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Toggle-state acceptance signal must be written to the log.'

$enter = [IO.File]::ReadAllText($enterPath)
$enterNodes = [regex]::Matches($enter, '(?m)^Begin Object Class=').Count
if ($enterNodes -ne 10) {
    throw "Enter-drone-mode contract expected 10 nodes; found $enterNodes."
}
if ($enter -match '(?m)^\s*Error(Type|Msg)=') {
    throw 'Enter-drone-mode source must not retain stale compiler error metadata.'
}

$enterEntry = Get-NodeBlock $enter 'K2Node_FunctionEntry_0'
$enterBranch = Get-NodeBlock $enter 'K2Node_IfThenElse_0'
$cameraGet = Get-NodeBlock $enter 'K2Node_VariableGet_0'
$cameraValid = Get-NodeBlock $enter 'K2Node_CallFunction_0'
$cameraSpawn = Get-NodeBlock $enter 'K2Node_SpawnActorFromClass_0'
$cameraSet = Get-NodeBlock $enter 'K2Node_VariableSet_0'
$spawnPrint = Get-NodeBlock $enter 'K2Node_CallFunction_1'
$validPrint = Get-NodeBlock $enter 'K2Node_CallFunction_2'
$makeTransform = Get-NodeBlock $enter 'K2Node_CallFunction_4'
$spawnReroute = Get-NodeBlock $enter 'K2Node_Knot_3'

Assert-GraphMatch $enterEntry 'FunctionReference=\(MemberName="EnterDroneMode"\)' 'Enter-drone-mode must implement the named function contract.'
Assert-GraphMatch $enterEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'EnterDroneMode entry must execute its validity guard.'
Assert-GraphMatch $cameraGet 'VariableReference=\(MemberName="DroneCameraRef"' 'Enter-drone-mode must read the cached camera reference.'
Assert-GraphMatch $cameraGet 'PinName="DroneCameraRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'DroneCameraRef must feed Is Valid.'
Assert-GraphMatch $cameraValid 'MemberName="IsValid"' 'Enter-drone-mode must validate the cached camera reference.'
Assert-GraphMatch $cameraValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Is Valid must drive the guard Branch.'
Assert-GraphMatch $enterBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'A valid camera must take the reuse path.'
Assert-GraphMatch $enterBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_Knot_3 ' 'An invalid camera must take the spawn path.'
Assert-GraphMatch $spawnReroute 'PinName="InputPin"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Spawn reroute input must originate from the false guard branch.'
Assert-GraphMatch $spawnReroute 'PinName="OutputPin"[^\r\n]*LinkedTo=\(K2Node_SpawnActorFromClass_0 ' 'Spawn reroute output must execute Spawn Actor.'
Assert-GraphMatch $cameraSpawn 'PinName="Class"[^\r\n]*DefaultObject="/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera\.BP_EDD_DroneCamera_C"' 'Enter-drone-mode must spawn exactly BP_EDD_DroneCamera.'
Assert-GraphMatch $cameraSpawn 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'Spawn completion must execute the camera-reference write.'
Assert-GraphMatch $cameraSpawn 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'Spawned camera must feed DroneCameraRef.'
Assert-GraphMatch $cameraSpawn 'PinName="SpawnTransform"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Spawn Actor must receive an explicit transform value.'
Assert-GraphMatch $cameraSet 'VariableReference=\(MemberName="DroneCameraRef"' 'Enter-drone-mode must cache the spawned camera.'
Assert-GraphMatch $cameraSet 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_1 ' 'Spawn diagnostic must run only after DroneCameraRef is written.'
Assert-GraphMatch $makeTransform 'MemberName="MakeTransform"' 'Enter-drone-mode must use the standard Make Transform function.'
Assert-GraphMatch $makeTransform 'PinName="Location"[^\r\n]*DefaultValue="0, 0, 0"' 'Initial isolated spawn contract must use identity translation.'
Assert-GraphMatch $makeTransform 'PinName="Rotation"[^\r\n]*DefaultValue="0, 0, 0"' 'Initial isolated spawn contract must use identity rotation.'
Assert-GraphMatch $makeTransform 'PinName="Scale"[^\r\n]*DefaultValue="1\.000000,1\.000000,1\.000000"' 'Initial isolated spawn contract must use unit scale.'
Assert-GraphMatch $makeTransform 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_SpawnActorFromClass_0 ' 'Make Transform output must feed Spawn Actor.'
Assert-GraphMatch $spawnPrint 'DefaultValue="\[EDD\] Drone camera spawned"' 'Spawn path must expose its acceptance diagnostic.'
Assert-GraphMatch $spawnPrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Spawn acceptance diagnostic must be written to the log.'
Assert-GraphMatch $validPrint 'DefaultValue="\[EDD\] Drone camera already valid"' 'Reuse path must expose its acceptance diagnostic.'
Assert-GraphMatch $validPrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Reuse acceptance diagnostic must be written to the log.'

Write-Output 'Blueprint graph contracts valid: toggle-input, toggle-state, enter-drone-mode'
