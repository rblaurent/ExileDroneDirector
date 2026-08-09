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
$placePath = Join-Path $snippetRoot 'place-drone-at-current-view.eddgraph'
$activatePath = Join-Path $snippetRoot 'activate-drone-view.eddgraph'
$switchPath = Join-Path $snippetRoot 'switch-to-drone-view.eddgraph'
$exitPath = Join-Path $snippetRoot 'exit-drone-mode.eddgraph'
$validator = Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1'

& $validator -Path @($inputPath, $statePath, $enterPath, $placePath, $activatePath, $switchPath, $exitPath) -AllowTokens | Write-Verbose

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
if ($enterNodes -ne 14) {
    throw "Enter-drone-mode contract expected 14 nodes; found $enterNodes."
}
if ($enter -match '(?m)^\s*Error(Type|Msg)=') {
    throw 'Enter-drone-mode source must not retain stale compiler error metadata.'
}

$enterEntry = Get-NodeBlock $enter 'K2Node_FunctionEntry_2'
$enterBranch = Get-NodeBlock $enter 'K2Node_IfThenElse_0'
$cameraGet = Get-NodeBlock $enter 'K2Node_VariableGet_0'
$cameraValid = Get-NodeBlock $enter 'K2Node_CallFunction_0'
$cameraSpawn = Get-NodeBlock $enter 'K2Node_SpawnActorFromClass_0'
$cameraSet = Get-NodeBlock $enter 'K2Node_VariableSet_0'
$spawnPrint = Get-NodeBlock $enter 'K2Node_CallFunction_1'
$validPrint = Get-NodeBlock $enter 'K2Node_CallFunction_2'
$makeTransform = Get-NodeBlock $enter 'K2Node_CallFunction_4'
$validActivate = Get-NodeBlock $enter 'K2Node_CallFunction_3'
$spawnActivate = Get-NodeBlock $enter 'K2Node_CallFunction_5'
$spawnReroute = Get-NodeBlock $enter 'K2Node_Knot_1'
$validPlace = Get-NodeBlock $enter 'K2Node_CallFunction_7'
$spawnPlace = Get-NodeBlock $enter 'K2Node_CallFunction_6'

Assert-GraphMatch $enterEntry 'FunctionReference=\(MemberName="EnterDroneMode"\)' 'Enter-drone-mode must implement the named function contract.'
Assert-GraphMatch $enterEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'EnterDroneMode entry must execute its validity guard.'
Assert-GraphMatch $cameraGet 'VariableReference=\(MemberName="DroneCameraRef"' 'Enter-drone-mode must read the cached camera reference.'
Assert-GraphMatch $cameraGet 'PinName="DroneCameraRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'DroneCameraRef must feed Is Valid.'
Assert-GraphMatch $cameraValid 'MemberName="IsValid"' 'Enter-drone-mode must validate the cached camera reference.'
Assert-GraphMatch $cameraValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Is Valid must drive the guard Branch.'
Assert-GraphMatch $enterBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'A valid camera must take the reuse path.'
Assert-GraphMatch $enterBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_Knot_1 ' 'An invalid camera must take the spawn path.'
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
Assert-GraphMatch $spawnPrint 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Spawn path must place the camera after reporting camera readiness.'
Assert-GraphMatch $validPrint 'DefaultValue="\[EDD\] Drone camera already valid"' 'Reuse path must expose its acceptance diagnostic.'
Assert-GraphMatch $validPrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Reuse acceptance diagnostic must be written to the log.'
Assert-GraphMatch $validPrint 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_7 ' 'Reuse path must place the camera after reporting camera readiness.'
Assert-GraphMatch $validPlace 'FunctionReference=\(MemberName="PlaceDroneAtCurrentView"' 'Valid-camera path must delegate placement to the named function.'
Assert-GraphMatch $validPlace 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Valid-camera placement must execute from the reuse diagnostic.'
Assert-GraphMatch $validPlace 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Valid-camera placement must complete before view activation.'
Assert-GraphMatch $spawnPlace 'FunctionReference=\(MemberName="PlaceDroneAtCurrentView"' 'Spawn path must delegate placement to the named function.'
Assert-GraphMatch $spawnPlace 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_1 ' 'Spawn-path placement must execute from the spawn diagnostic.'
Assert-GraphMatch $spawnPlace 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_5 ' 'Spawn-path placement must complete before view activation.'
Assert-GraphMatch $validActivate 'FunctionReference=\(MemberName="ActivateDroneView"' 'Valid-camera path must delegate view activation to the named function.'
Assert-GraphMatch $validActivate 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_7 ' 'Valid-camera activation must be entered from completed placement.'
Assert-GraphMatch $spawnActivate 'FunctionReference=\(MemberName="ActivateDroneView"' 'Spawn path must delegate view activation to the named function.'
Assert-GraphMatch $spawnActivate 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Spawn-path activation must be entered from completed placement.'

$place = [IO.File]::ReadAllText($placePath)
$placeNodes = [regex]::Matches($place, '(?m)^Begin Object Class=').Count
if ($placeNodes -ne 10) {
    throw "Place-drone-at-current-view contract expected 10 nodes; found $placeNodes."
}

$placeEntry = Get-NodeBlock $place 'K2Node_FunctionEntry_0'
$placeBranch = Get-NodeBlock $place 'K2Node_IfThenElse_0'
$placeCameraGet = Get-NodeBlock $place 'K2Node_VariableGet_0'
$placeCameraValid = Get-NodeBlock $place 'K2Node_CallFunction_0'
$placeSuccess = Get-NodeBlock $place 'K2Node_CallFunction_3'
$placeSkipped = Get-NodeBlock $place 'K2Node_CallFunction_4'
$placeCameraManager = Get-NodeBlock $place 'K2Node_CallFunction_1'
$placeCameraLocation = Get-NodeBlock $place 'K2Node_CallFunction_2'
$placeCameraRotation = Get-NodeBlock $place 'K2Node_CallFunction_5'
$placeTransform = Get-NodeBlock $place 'K2Node_CallFunction_6'

Assert-GraphMatch $placeEntry 'FunctionReference=\(MemberName="PlaceDroneAtCurrentView"\)' 'Placement must implement the named function contract.'
Assert-GraphMatch $placeEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Placement entry must execute its camera guard.'
Assert-GraphMatch $placeCameraGet 'VariableReference=\(MemberName="DroneCameraRef"' 'Placement must read the typed camera reference.'
Assert-GraphMatch $placeCameraGet 'PinName="DroneCameraRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'DroneCameraRef must feed the placement validity check.'
Assert-GraphMatch $placeCameraGet 'PinName="DroneCameraRef"[^\r\n]*K2Node_CallFunction_6 ' 'DroneCameraRef must be the actor moved by placement.'
Assert-GraphMatch $placeCameraValid 'MemberName="IsValid"' 'Placement must validate DroneCameraRef.'
Assert-GraphMatch $placeCameraValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Camera validity must drive the placement Branch.'
Assert-GraphMatch $placeBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_6 ' 'A valid camera must execute the transform write.'
Assert-GraphMatch $placeBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_CallFunction_4 ' 'An invalid camera must execute only the skipped diagnostic.'
Assert-GraphMatch $placeCameraManager 'MemberName="GetPlayerCameraManager"' 'Placement must resolve the live local camera manager.'
Assert-GraphMatch $placeCameraManager 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Placement must sample local Player Camera Manager 0.'
Assert-GraphMatch $placeCameraManager 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 [^\r\n]*K2Node_CallFunction_5 ' 'The same camera manager must feed both location and rotation sampling.'
Assert-GraphMatch $placeCameraLocation 'MemberName="GetCameraLocation"' 'Placement must sample the evaluated camera location.'
Assert-GraphMatch $placeCameraLocation 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Evaluated camera location must feed NewLocation.'
Assert-GraphMatch $placeCameraRotation 'MemberName="GetCameraRotation"' 'Placement must sample the evaluated camera rotation.'
Assert-GraphMatch $placeCameraRotation 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Evaluated camera rotation must feed NewRotation.'
Assert-GraphMatch $placeTransform 'MemberName="K2_SetActorLocationAndRotation"' 'Placement must perform one atomic actor location-and-rotation write.'
Assert-GraphMatch $placeTransform 'PinName="self"[^\r\n]*LinkedTo=\(K2Node_VariableGet_0 ' 'Placement transform target must be DroneCameraRef.'
Assert-GraphMatch $placeTransform 'PinName="NewLocation"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Placement NewLocation must come from GetCameraLocation.'
Assert-GraphMatch $placeTransform 'PinName="NewRotation"[^\r\n]*LinkedTo=\(K2Node_CallFunction_5 ' 'Placement NewRotation must come from GetCameraRotation.'
Assert-GraphMatch $placeTransform 'PinName="bSweep"[^\r\n]*DefaultValue="false"' 'Camera placement must not sweep through gameplay collision.'
Assert-GraphMatch $placeTransform 'PinName="bTeleport"[^\r\n]*DefaultValue="false"' 'Initial camera placement must preserve the normal engine move semantic.'
Assert-GraphMatch $placeTransform 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Placement success must be reported only after the transform write.'
Assert-GraphMatch $placeSuccess 'DefaultValue="\[EDD\] Drone placed at current view"' 'Placement success must expose its acceptance diagnostic.'
Assert-GraphMatch $placeSuccess 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Placement success must be written to the log.'
Assert-GraphMatch $placeSkipped 'DefaultValue="\[EDD\] Drone placement skipped: no camera"' 'Invalid placement must expose its guarded diagnostic.'
Assert-GraphMatch $placeSkipped 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Invalid-placement diagnostic must be written to the log.'

$activate = [IO.File]::ReadAllText($activatePath)
$activateNodes = [regex]::Matches($activate, '(?m)^Begin Object Class=').Count
if ($activateNodes -ne 12) {
    throw "Activate-drone-view contract expected 12 nodes; found $activateNodes."
}

$activateEntry = Get-NodeBlock $activate 'K2Node_FunctionEntry_0'
$activateBranch = Get-NodeBlock $activate 'K2Node_IfThenElse_0'
$originalGet = Get-NodeBlock $activate 'K2Node_VariableGet_0'
$originalValid = Get-NodeBlock $activate 'K2Node_CallFunction_0'
$playerController = Get-NodeBlock $activate 'K2Node_CallFunction_1'
$viewTarget = Get-NodeBlock $activate 'K2Node_CallFunction_2'
$originalSet = Get-NodeBlock $activate 'K2Node_VariableSet_0'
$alreadyCachedPrint = Get-NodeBlock $activate 'K2Node_CallFunction_3'
$cachedPrint = Get-NodeBlock $activate 'K2Node_CallFunction_4'
$reuseSwitch = Get-NodeBlock $activate 'K2Node_CallFunction_5'
$cacheSwitch = Get-NodeBlock $activate 'K2Node_CallFunction_6'
$activateReroute = Get-NodeBlock $activate 'K2Node_Knot_1'

Assert-GraphMatch $activateEntry 'FunctionReference=\(MemberName="ActivateDroneView"\)' 'Activate-drone-view must implement the named function contract.'
Assert-GraphMatch $activateEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'ActivateDroneView entry must execute its cache guard.'
Assert-GraphMatch $originalGet 'VariableReference=\(MemberName="OriginalViewTargetRef"' 'Activate-drone-view must read the cached original view target.'
Assert-GraphMatch $originalGet 'PinName="OriginalViewTargetRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'OriginalViewTargetRef must feed Is Valid.'
Assert-GraphMatch $originalValid 'MemberName="IsValid"' 'Activate-drone-view must validate the original view target reference.'
Assert-GraphMatch $originalValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Original-view validity must drive the cache Branch.'
Assert-GraphMatch $activateBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_3 ' 'A valid original view target must take the reuse path.'
Assert-GraphMatch $activateBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_Knot_1 ' 'An invalid original view target must take the cache-write reroute.'
Assert-GraphMatch $activateReroute 'PinName="InputPin"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Cache reroute input must originate from the invalid branch.'
Assert-GraphMatch $activateReroute 'PinName="OutputPin"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'Cache reroute output must execute the original-view write.'
Assert-GraphMatch $playerController 'MemberName="GetPlayerController"' 'Activate-drone-view must resolve local Player Controller 0.'
Assert-GraphMatch $playerController 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Original view capture must use local Player Controller 0.'
Assert-GraphMatch $playerController 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Local Player Controller must feed Get View Target.'
Assert-GraphMatch $viewTarget 'MemberName="GetViewTarget"' 'Activate-drone-view must read the controller current view target.'
Assert-GraphMatch $viewTarget 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'Current view target must feed OriginalViewTargetRef.'
Assert-GraphMatch $originalSet 'VariableReference=\(MemberName="OriginalViewTargetRef"' 'Activate-drone-view must cache the original view target.'
Assert-GraphMatch $originalSet 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_Knot_1 ' 'Original-view write must only execute through the invalid-branch reroute.'
Assert-GraphMatch $originalSet 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Cache diagnostic must run only after OriginalViewTargetRef is written.'
Assert-GraphMatch $alreadyCachedPrint 'DefaultValue="\[EDD\] Original view target already cached"' 'Original-view reuse path must expose its acceptance diagnostic.'
Assert-GraphMatch $alreadyCachedPrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Original-view reuse diagnostic must be written to the log.'
Assert-GraphMatch $alreadyCachedPrint 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_5 ' 'Original-view reuse path must switch only after reporting cache reuse.'
Assert-GraphMatch $cachedPrint 'DefaultValue="\[EDD\] Original view target cached"' 'Original-view cache path must expose its acceptance diagnostic.'
Assert-GraphMatch $cachedPrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Original-view cache diagnostic must be written to the log.'
Assert-GraphMatch $cachedPrint 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Original-view cache path must switch only after reporting the completed write.'
Assert-GraphMatch $reuseSwitch 'FunctionReference=\(MemberName="SwitchToDroneView"' 'Original-view reuse path must delegate to SwitchToDroneView.'
Assert-GraphMatch $reuseSwitch 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Reuse-path switch must execute from the reuse diagnostic.'
Assert-GraphMatch $cacheSwitch 'FunctionReference=\(MemberName="SwitchToDroneView"' 'Original-view cache path must delegate to SwitchToDroneView.'
Assert-GraphMatch $cacheSwitch 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Cache-path switch must execute from the cache diagnostic.'

$switch = [IO.File]::ReadAllText($switchPath)
$switchNodes = [regex]::Matches($switch, '(?m)^Begin Object Class=').Count
if ($switchNodes -ne 9) {
    throw "Switch-to-drone-view contract expected 9 nodes; found $switchNodes."
}

$switchEntry = Get-NodeBlock $switch 'K2Node_FunctionEntry_0'
$switchBranch = Get-NodeBlock $switch 'K2Node_IfThenElse_0'
$switchCameraGet = Get-NodeBlock $switch 'K2Node_VariableGet_0'
$switchCameraValid = Get-NodeBlock $switch 'K2Node_CallFunction_0'
$switchController = Get-NodeBlock $switch 'K2Node_CallFunction_1'
$switchSetView = Get-NodeBlock $switch 'K2Node_CallFunction_2'
$switchSuccess = Get-NodeBlock $switch 'K2Node_CallFunction_3'
$switchSkipped = Get-NodeBlock $switch 'K2Node_CallFunction_4'
$switchReroute = Get-NodeBlock $switch 'K2Node_Knot_0'

Assert-GraphMatch $switchEntry 'FunctionReference=\(MemberName="SwitchToDroneView"\)' 'Switch-to-drone-view must implement the named function contract.'
Assert-GraphMatch $switchEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'SwitchToDroneView entry must execute its camera guard.'
Assert-GraphMatch $switchCameraGet 'VariableReference=\(MemberName="DroneCameraRef"' 'Switch-to-drone-view must read the typed camera reference.'
Assert-GraphMatch $switchCameraGet 'PinName="DroneCameraRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'DroneCameraRef must feed the switch validity check.'
Assert-GraphMatch $switchCameraGet 'PinName="DroneCameraRef"[^\r\n]*K2Node_CallFunction_2 ' 'DroneCameraRef must feed SetViewTargetWithBlend NewViewTarget.'
Assert-GraphMatch $switchCameraValid 'MemberName="IsValid"' 'Switch-to-drone-view must validate DroneCameraRef.'
Assert-GraphMatch $switchCameraValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Camera validity must drive the switch Branch.'
Assert-GraphMatch $switchBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'A valid camera must execute SetViewTargetWithBlend.'
Assert-GraphMatch $switchBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_Knot_0 ' 'An invalid camera must take the skipped-diagnostic reroute.'
Assert-GraphMatch $switchReroute 'PinName="InputPin"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Switch failure reroute must originate from the invalid branch.'
Assert-GraphMatch $switchReroute 'PinName="OutputPin"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Switch failure reroute must execute the skipped diagnostic.'
Assert-GraphMatch $switchController 'MemberName="GetPlayerController"' 'Switch-to-drone-view must resolve a local player controller.'
Assert-GraphMatch $switchController 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Switch-to-drone-view must use local Player Controller 0.'
Assert-GraphMatch $switchController 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Local Player Controller must be SetViewTargetWithBlend Target.'
Assert-GraphMatch $switchSetView 'MemberName="SetViewTargetWithBlend"' 'Switch-to-drone-view must use the engine view-target API.'
Assert-GraphMatch $switchSetView 'PinName="NewViewTarget"[^\r\n]*LinkedTo=\(K2Node_VariableGet_0 ' 'SetViewTargetWithBlend must target DroneCameraRef.'
Assert-GraphMatch $switchSetView 'PinName="BlendTime"[^\r\n]*DefaultValue="0\.000000"' 'Initial drone switching must be immediate and deterministic.'
Assert-GraphMatch $switchSetView 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Drone-view success must be reported only after the switch call.'
Assert-GraphMatch $switchSuccess 'DefaultValue="\[EDD\] Drone view active"' 'Successful drone switching must expose its acceptance diagnostic.'
Assert-GraphMatch $switchSuccess 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Drone-view success must be written to the log.'
Assert-GraphMatch $switchSkipped 'DefaultValue="\[EDD\] Drone view activation skipped: no camera"' 'Invalid-camera switching must expose its guarded diagnostic.'
Assert-GraphMatch $switchSkipped 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Invalid-camera diagnostic must be written to the log.'

$exit = [IO.File]::ReadAllText($exitPath)
$exitNodes = [regex]::Matches($exit, '(?m)^Begin Object Class=').Count
if ($exitNodes -ne 9) {
    throw "Exit-drone-mode contract expected 9 nodes; found $exitNodes."
}

$exitEntry = Get-NodeBlock $exit 'K2Node_FunctionEntry_0'
$exitBranch = Get-NodeBlock $exit 'K2Node_IfThenElse_0'
$exitOriginalGet = Get-NodeBlock $exit 'K2Node_VariableGet_0'
$exitOriginalValid = Get-NodeBlock $exit 'K2Node_CallFunction_0'
$exitController = Get-NodeBlock $exit 'K2Node_CallFunction_1'
$exitSetView = Get-NodeBlock $exit 'K2Node_CallFunction_2'
$exitSuccess = Get-NodeBlock $exit 'K2Node_CallFunction_3'
$exitSkipped = Get-NodeBlock $exit 'K2Node_CallFunction_4'
$exitReroute = Get-NodeBlock $exit 'K2Node_Knot_0'

Assert-GraphMatch $exitEntry 'FunctionReference=\(MemberName="ExitDroneMode"\)' 'Exit-drone-mode must implement the named function contract.'
Assert-GraphMatch $exitEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'ExitDroneMode entry must execute its original-target guard.'
Assert-GraphMatch $exitOriginalGet 'VariableReference=\(MemberName="OriginalViewTargetRef"' 'Exit-drone-mode must read the cached original target.'
Assert-GraphMatch $exitOriginalGet 'PinName="OriginalViewTargetRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'OriginalViewTargetRef must feed the exit validity check.'
Assert-GraphMatch $exitOriginalGet 'PinName="OriginalViewTargetRef"[^\r\n]*K2Node_CallFunction_2 ' 'OriginalViewTargetRef must feed the restoration NewViewTarget.'
Assert-GraphMatch $exitOriginalValid 'MemberName="IsValid"' 'Exit-drone-mode must validate OriginalViewTargetRef.'
Assert-GraphMatch $exitOriginalValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Original-target validity must drive the exit Branch.'
Assert-GraphMatch $exitBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'A valid original target must execute SetViewTargetWithBlend.'
Assert-GraphMatch $exitBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_Knot_0 ' 'An invalid original target must take the skipped-diagnostic reroute.'
Assert-GraphMatch $exitReroute 'PinName="InputPin"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Exit failure reroute must originate from the invalid branch.'
Assert-GraphMatch $exitReroute 'PinName="OutputPin"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Exit failure reroute must execute the skipped diagnostic.'
Assert-GraphMatch $exitController 'MemberName="GetPlayerController"' 'Exit-drone-mode must resolve a local player controller.'
Assert-GraphMatch $exitController 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Exit-drone-mode must use local Player Controller 0.'
Assert-GraphMatch $exitController 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Local Player Controller must be restoration SetViewTargetWithBlend Target.'
Assert-GraphMatch $exitSetView 'MemberName="SetViewTargetWithBlend"' 'Exit-drone-mode must restore through the engine view-target API.'
Assert-GraphMatch $exitSetView 'PinName="NewViewTarget"[^\r\n]*LinkedTo=\(K2Node_VariableGet_0 ' 'Restoration must target OriginalViewTargetRef.'
Assert-GraphMatch $exitSetView 'PinName="BlendTime"[^\r\n]*DefaultValue="0\.000000"' 'Initial restoration must be immediate and deterministic.'
Assert-GraphMatch $exitSetView 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'Restoration success must be reported only after the view call.'
Assert-GraphMatch $exitSuccess 'DefaultValue="\[EDD\] Player view restored"' 'Successful restoration must expose its acceptance diagnostic.'
Assert-GraphMatch $exitSuccess 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Restoration success must be written to the log.'
Assert-GraphMatch $exitSkipped 'DefaultValue="\[EDD\] View restoration skipped: no original target"' 'Invalid restoration must expose its guarded diagnostic.'
Assert-GraphMatch $exitSkipped 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Invalid-restoration diagnostic must be written to the log.'

foreach ($viewGraph in @($place, $activate, $switch, $exit)) {
    if ($viewGraph -match '(?m)^\s*Error(Type|Msg)=') {
        throw 'View-lifecycle graph source must not retain stale compiler error metadata.'
    }
}

Write-Output 'Blueprint graph contracts valid: toggle-input, toggle-state, enter-drone-mode, place-drone-at-current-view, activate-drone-view, switch-to-drone-view, exit-drone-mode'
