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
$emergencyPath = Join-Path $snippetRoot 'emergency-exit-drone-mode.eddgraph'
$eventGraphPath = Join-Path $snippetRoot 'client-director-event-graph.eddgraph'
$movementPath = Join-Path $snippetRoot 'apply-translation-input.eddgraph'
$rotationPath = Join-Path $snippetRoot 'apply-rotation-input.eddgraph'
$rollPath = Join-Path $snippetRoot 'apply-roll-and-horizon-input.eddgraph'
$speedPath = Join-Path $snippetRoot 'update-speed-controls.eddgraph'
$droneEventPath = Join-Path $snippetRoot 'drone-camera-event-graph.eddgraph'
$cachePawnPath = Join-Path $snippetRoot 'cache-original-pawn.eddgraph'
$possessDronePath = Join-Path $snippetRoot 'possess-drone-camera.eddgraph'
$restorePawnPath = Join-Path $snippetRoot 'restore-original-possession.eddgraph'
$validator = Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1'

& $validator -Path @(
    $inputPath,
    $statePath,
    $enterPath,
    $placePath,
    $activatePath,
    $switchPath,
    $exitPath,
    $emergencyPath,
    $eventGraphPath,
    $movementPath,
    $rotationPath,
    $rollPath,
    $speedPath,
    $droneEventPath,
    $cachePawnPath,
    $possessDronePath,
    $restorePawnPath
) -AllowTokens | Write-Verbose

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
if ($activateNodes -ne 13) {
    throw "Activate-drone-view contract expected 13 nodes; found $activateNodes."
}

$activateEntry = Get-NodeBlock $activate 'K2Node_FunctionEntry_1'
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
$cacheOriginalPawn = Get-NodeBlock $activate 'K2Node_CallFunction_7'

Assert-GraphMatch $activateEntry 'FunctionReference=\(MemberName="ActivateDroneView"\)' 'Activate-drone-view must implement the named function contract.'
Assert-GraphMatch $activateEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_7 ' 'ActivateDroneView entry must cache the original pawn before view-target work.'
Assert-GraphMatch $cacheOriginalPawn 'FunctionReference=\(MemberName="CacheOriginalPawn"' 'ActivateDroneView must delegate original-pawn capture to CacheOriginalPawn.'
Assert-GraphMatch $cacheOriginalPawn 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Original-pawn capture must complete before the original-view cache guard.'
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

$switchEntry = Get-NodeBlock $switch 'K2Node_FunctionEntry_1'
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
Assert-GraphMatch $switchBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'A valid camera must switch the local view target directly.'
Assert-GraphMatch $switchBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_Knot_0 ' 'An invalid camera must take the skipped-diagnostic reroute.'
Assert-GraphMatch $switchReroute 'PinName="InputPin"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Switch failure reroute must originate from the invalid branch.'
Assert-GraphMatch $switchReroute 'PinName="OutputPin"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Switch failure reroute must execute the skipped diagnostic.'
Assert-GraphMatch $switchController 'MemberName="GetPlayerController"' 'Switch-to-drone-view must resolve a local player controller.'
Assert-GraphMatch $switchController 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Switch-to-drone-view must use local Player Controller 0.'
Assert-GraphMatch $switchController 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'Local Player Controller must be SetViewTargetWithBlend Target.'
if ($switch -match 'PossessDroneCamera|MemberName="Possess"') {
    throw 'Switch-to-drone-view must remain client-local presentation state and must not possess the drone.'
}
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

$exitEntry = Get-NodeBlock $exit 'K2Node_FunctionEntry_1'
$exitBranch = Get-NodeBlock $exit 'K2Node_IfThenElse_0'
$exitOriginalGet = Get-NodeBlock $exit 'K2Node_VariableGet_0'
$exitOriginalValid = Get-NodeBlock $exit 'K2Node_CallFunction_0'
$exitController = Get-NodeBlock $exit 'K2Node_CallFunction_1'
$exitSetView = Get-NodeBlock $exit 'K2Node_CallFunction_2'
$exitSuccess = Get-NodeBlock $exit 'K2Node_CallFunction_3'
$exitSkipped = Get-NodeBlock $exit 'K2Node_CallFunction_4'
$exitReroute = Get-NodeBlock $exit 'K2Node_Knot_0'

Assert-GraphMatch $exitEntry 'FunctionReference=\(MemberName="ExitDroneMode"\)' 'Exit-drone-mode must implement the named function contract.'
Assert-GraphMatch $exitEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'ExitDroneMode entry must execute the original-view guard directly.'
if ($exit -match 'RestoreOriginalPossession|MemberName="Possess"|MemberName="UnPossess"') {
    throw 'ExitDroneMode must restore only the cached local view target and must not change possession.'
}
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

$cachePawn = [IO.File]::ReadAllText($cachePawnPath)
$cachePawnNodes = [regex]::Matches($cachePawn, '(?m)^Begin Object Class=').Count
if ($cachePawnNodes -ne 3) {
    throw "Cache-original-pawn contract expected 3 nodes; found $cachePawnNodes."
}
$cachePawnEntry = Get-NodeBlock $cachePawn 'K2Node_FunctionEntry_1'
$cachePawnGetter = Get-NodeBlock $cachePawn 'K2Node_CallFunction_0'
$cachePawnSetter = Get-NodeBlock $cachePawn 'K2Node_VariableSet_0'
Assert-GraphMatch $cachePawnEntry 'FunctionReference=\(MemberName="CacheOriginalPawn"\)' 'Cache-original-pawn must implement the named function contract.'
Assert-GraphMatch $cachePawnEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'CacheOriginalPawn entry must execute the OriginalPawnRef write.'
Assert-GraphMatch $cachePawnGetter 'MemberName="GetPlayerPawn"' 'CacheOriginalPawn must read local Player Pawn 0.'
Assert-GraphMatch $cachePawnGetter 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Original pawn capture must use local player index 0.'
Assert-GraphMatch $cachePawnGetter 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'GetPlayerPawn must feed OriginalPawnRef.'
Assert-GraphMatch $cachePawnSetter 'VariableReference=\(MemberName="OriginalPawnRef"' 'CacheOriginalPawn must write the typed original-pawn reference.'

$possessDrone = [IO.File]::ReadAllText($possessDronePath)
$possessDroneNodes = [regex]::Matches($possessDrone, '(?m)^Begin Object Class=').Count
if ($possessDroneNodes -ne 6) {
    throw "Possess-drone-camera contract expected 6 nodes; found $possessDroneNodes."
}
$possessEntry = Get-NodeBlock $possessDrone 'K2Node_FunctionEntry_1'
$possessBranch = Get-NodeBlock $possessDrone 'K2Node_IfThenElse_0'
$possessCameraGet = Get-NodeBlock $possessDrone 'K2Node_VariableGet_0'
$possessValid = Get-NodeBlock $possessDrone 'K2Node_CallFunction_0'
$possessController = Get-NodeBlock $possessDrone 'K2Node_CallFunction_1'
$possessCall = Get-NodeBlock $possessDrone 'K2Node_CallFunction_2'
Assert-GraphMatch $possessEntry 'FunctionReference=\(MemberName="PossessDroneCamera"\)' 'Possess-drone-camera must implement the named function contract.'
Assert-GraphMatch $possessEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'PossessDroneCamera entry must execute its validity guard.'
Assert-GraphMatch $possessCameraGet 'VariableReference=\(MemberName="DroneCameraRef"' 'PossessDroneCamera must read DroneCameraRef.'
Assert-GraphMatch $possessCameraGet 'PinName="DroneCameraRef"[^\r\n]*K2Node_CallFunction_0 [^\r\n]*K2Node_CallFunction_2 ' 'DroneCameraRef must feed both Is Valid and Possess InPawn.'
Assert-GraphMatch $possessValid 'MemberName="IsValid"' 'PossessDroneCamera must guard the drone reference.'
Assert-GraphMatch $possessBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'Only a valid drone may be possessed.'
Assert-GraphMatch $possessController 'MemberName="GetPlayerController"' 'PossessDroneCamera must resolve local Player Controller 0.'
Assert-GraphMatch $possessCall 'MemberName="Possess"' 'PossessDroneCamera must call the engine controller possession API.'

$restorePawn = [IO.File]::ReadAllText($restorePawnPath)
$restorePawnNodes = [regex]::Matches($restorePawn, '(?m)^Begin Object Class=').Count
if ($restorePawnNodes -ne 7) {
    throw "Restore-original-possession contract expected 7 nodes; found $restorePawnNodes."
}
$restoreEntry = Get-NodeBlock $restorePawn 'K2Node_FunctionEntry_1'
$restoreBranch = Get-NodeBlock $restorePawn 'K2Node_IfThenElse_0'
$restorePawnGet = Get-NodeBlock $restorePawn 'K2Node_VariableGet_0'
$restoreValid = Get-NodeBlock $restorePawn 'K2Node_CallFunction_0'
$restoreController = Get-NodeBlock $restorePawn 'K2Node_CallFunction_1'
$restorePossess = Get-NodeBlock $restorePawn 'K2Node_CallFunction_2'
$restoreUnPossess = Get-NodeBlock $restorePawn 'K2Node_CallFunction_3'
Assert-GraphMatch $restoreEntry 'FunctionReference=\(MemberName="RestoreOriginalPossession"\)' 'Restore-original-possession must implement the named function contract.'
Assert-GraphMatch $restoreEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'RestoreOriginalPossession entry must execute its original-pawn guard.'
Assert-GraphMatch $restorePawnGet 'VariableReference=\(MemberName="OriginalPawnRef"' 'RestoreOriginalPossession must read OriginalPawnRef.'
Assert-GraphMatch $restoreValid 'MemberName="IsValid"' 'RestoreOriginalPossession must validate OriginalPawnRef.'
Assert-GraphMatch $restoreBranch 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_CallFunction_2 ' 'A valid original pawn must execute Possess.'
Assert-GraphMatch $restoreBranch 'PinFriendlyName=.*?"false".*?LinkedTo=\(K2Node_CallFunction_3 ' 'A missing original pawn must execute UnPossess.'
Assert-GraphMatch $restoreController 'MemberName="GetPlayerController"' 'RestoreOriginalPossession must resolve local Player Controller 0.'
Assert-GraphMatch $restorePossess 'MemberName="Possess"' 'RestoreOriginalPossession must possess a valid cached pawn.'
Assert-GraphMatch $restoreUnPossess 'MemberName="UnPossess"' 'RestoreOriginalPossession must safely unpossess when no cached pawn exists.'

$movement = [IO.File]::ReadAllText($movementPath)
$movementNodes = [regex]::Matches($movement, '(?m)^Begin Object Class=').Count
if ($movementNodes -ne 17) {
    throw "Apply-translation-input contract expected 17 nodes; found $movementNodes."
}
if ([regex]::Matches($movement, 'MemberName="GetInputAnalogKeyState"').Count -ne 6) {
    throw 'ApplyTranslationInput must sample exactly six translation keys.'
}
foreach ($key in @('W', 'S', 'D', 'A', 'E', 'Q')) {
    Assert-GraphMatch $movement ('PinName="Key"[^\r\n]*DefaultValue="{0}"' -f $key) "ApplyTranslationInput must sample $key."
}
if ([regex]::Matches($movement, 'MemberName="Subtract_DoubleDouble"').Count -ne 3) {
    throw 'ApplyTranslationInput must construct exactly three signed axis values.'
}
Assert-GraphMatch $movement 'MemberName="MakeVector"' 'ApplyTranslationInput must assemble the three signed local axes into one vector.'
Assert-GraphMatch $movement 'VariableReference=\(MemberName="CurrentMoveSpeed"' 'ApplyTranslationInput must consume the smoothed CurrentMoveSpeed.'
Assert-GraphMatch $movement 'MemberName="GetWorldDeltaSeconds"' 'ApplyTranslationInput must be frame-rate independent.'
if ([regex]::Matches($movement, 'OperationName="Multiply"').Count -ne 2) {
    throw 'ApplyTranslationInput must multiply once by speed and once by DeltaSeconds.'
}
$movementSpeedScale = Get-NodeBlock $movement 'K2Node_PromotableOperator_3'
$movementDeltaScale = Get-NodeBlock $movement 'K2Node_PromotableOperator_4'
Assert-GraphMatch $movementSpeedScale 'PinName="B"[^\r\n]*PinType\.PinCategory="real"[^\r\n]*PinType\.PinSubCategory="double"' 'The speed multiplier must use a scalar double-valued B pin.'
Assert-GraphMatch $movementDeltaScale 'PinName="B"[^\r\n]*PinType\.PinCategory="real"[^\r\n]*PinType\.PinSubCategory="double"' 'The DeltaSeconds multiplier must use a scalar double-valued B pin.'
if ([regex]::Matches($movement, 'MemberName="K2_AddActorLocalOffset"').Count -ne 1) {
    throw 'ApplyTranslationInput must issue exactly one local transform integration call.'
}
$movementEntry = Get-NodeBlock $movement 'K2Node_FunctionEntry_2'
$movementOffset = Get-NodeBlock $movement 'K2Node_CallFunction_15'
Assert-GraphMatch $movementEntry 'FunctionReference=\(MemberName="ApplyTranslationInput"\)' 'Movement must implement the named ApplyTranslationInput contract.'
Assert-GraphMatch $movementEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_15 ' 'ApplyTranslationInput entry must execute AddActorLocalOffset.'
Assert-GraphMatch $movementOffset 'PinName="DeltaLocation"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_4 ' 'AddActorLocalOffset must consume the speed-and-delta-scaled vector.'
Assert-GraphMatch $movementOffset 'PinName="bSweep"[^\r\n]*DefaultValue="false"' 'Freecam translation must not sweep against gameplay collision.'
Assert-GraphMatch $movementOffset 'PinName="bTeleport"[^\r\n]*DefaultValue="false"' 'Freecam translation must use ordinary local offsets.'

$speed = [IO.File]::ReadAllText($speedPath)
$speedNodes = [regex]::Matches($speed, '(?m)^Begin Object Class=').Count
if ($speedNodes -ne 31) {
    throw "Update-speed-controls contract expected 31 nodes; found $speedNodes."
}
if ([regex]::Matches($speed, 'MemberName="IsInputKeyDown"').Count -ne 2) {
    throw 'UpdateSpeedControls must sample exactly the boost and precision modifier keys.'
}
if ([regex]::Matches($speed, 'OperationName="Multiply"').Count -ne 4) {
    throw 'UpdateSpeedControls must contain exactly four multiplicative operations.'
}

$speedEntry = Get-NodeBlock $speed 'K2Node_FunctionEntry_0'
$speedSetCruise = Get-NodeBlock $speed 'K2Node_VariableSet_3'
$speedSetCurrent = Get-NodeBlock $speed 'K2Node_VariableSet_2'
$speedWheel = Get-NodeBlock $speed 'K2Node_CallFunction_9'
$speedClamp = Get-NodeBlock $speed 'K2Node_CallFunction_13'
$speedInterp = Get-NodeBlock $speed 'K2Node_CallFunction_4'
$speedBoostSelect = Get-NodeBlock $speed 'K2Node_CallFunction_7'
$speedPrecisionSelect = Get-NodeBlock $speed 'K2Node_CallFunction_8'
$speedCtrl = Get-NodeBlock $speed 'K2Node_CallFunction_5'
$speedShift = Get-NodeBlock $speed 'K2Node_CallFunction_6'
$speedTrimMultiply = Get-NodeBlock $speed 'K2Node_PromotableOperator_3'

Assert-GraphMatch $speedEntry 'FunctionReference=\(MemberName="UpdateSpeedControls"\)' 'Speed control must implement the named UpdateSpeedControls contract.'
Assert-GraphMatch $speedEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_VariableSet_3 ' 'Speed evaluation must persist the clamped cruise speed first.'
Assert-GraphMatch $speedSetCruise 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_VariableSet_2 ' 'Cruise trim must be stored before the smoothed current speed.'
Assert-GraphMatch $speedWheel 'MemberName="GetInputAnalogKeyState"' 'Speed trim must sample the mouse wheel as an analog axis.'
Assert-GraphMatch $speedWheel 'PinName="Key"[^\r\n]*DefaultValue="MouseWheelAxis"' 'Speed trim must use MouseWheelAxis.'
Assert-GraphMatch $speed 'MemberName="Loge"' 'Symmetric multiplicative trim must take the natural log of SpeedTrimRatio.'
Assert-GraphMatch $speed 'MemberName="Exp"' 'Symmetric multiplicative trim must exponentiate the signed wheel step.'
Assert-GraphMatch $speedTrimMultiply 'PinName="A"[^\r\n]*LinkedTo=\(K2Node_VariableGet_6 ' 'Trim must multiply the previous CruiseMoveSpeed.'
Assert-GraphMatch $speedTrimMultiply 'PinName="B"[^\r\n]*LinkedTo=\(K2Node_CallFunction_11 ' 'Trim must multiply cruise speed by the exponential wheel factor.'
Assert-GraphMatch $speedTrimMultiply 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_13 ' 'The computed trim value must feed the clamp; an unlinked clamp value collapses speed to its minimum.'
Assert-GraphMatch $speedClamp 'MemberName="FClamp"' 'Cruise trim must be clamped.'
Assert-GraphMatch $speedClamp 'PinName="Value"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_3 ' 'The clamp value must consume the multiplicatively trimmed cruise speed.'
Assert-GraphMatch $speedClamp 'PinName="Min"[^\r\n]*LinkedTo=\(K2Node_VariableGet_7 ' 'Cruise trim must respect MinMoveSpeed.'
Assert-GraphMatch $speedClamp 'PinName="Max"[^\r\n]*LinkedTo=\(K2Node_VariableGet_9 ' 'Cruise trim must respect MaxMoveSpeed.'
Assert-GraphMatch $speedClamp 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_3 ' 'The clamped trim must be persisted as CruiseMoveSpeed.'
Assert-GraphMatch $speedShift 'PinName="Key"[^\r\n]*DefaultValue="LeftShift"' 'Boost mode must use Left Shift.'
Assert-GraphMatch $speedShift 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_7 ' 'Shift must select the boost target.'
Assert-GraphMatch $speedCtrl 'PinName="Key"[^\r\n]*DefaultValue="LeftControl"' 'Precision mode must use Left Control.'
Assert-GraphMatch $speedCtrl 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'Control must drive the outer target selector so precision wins over boost.'
Assert-GraphMatch $speedBoostSelect 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'The boost-or-cruise result must feed the precision selector.'
Assert-GraphMatch $speedPrecisionSelect 'PinName="A"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'The outer selector must choose CruiseMoveSpeed times PrecisionMultiplier when Control is held.'
Assert-GraphMatch $speedInterp 'MemberName="FInterpTo"' 'CurrentMoveSpeed must ease toward the selected target.'
Assert-GraphMatch $speedInterp 'PinName="Current"[^\r\n]*LinkedTo=\(K2Node_VariableGet_0 ' 'FInterpTo must start from CurrentMoveSpeed.'
Assert-GraphMatch $speedInterp 'PinName="Target"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'FInterpTo must target the precision-precedence selector.'
Assert-GraphMatch $speedInterp 'PinName="DeltaTime"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'Speed easing must use world delta seconds.'
Assert-GraphMatch $speedInterp 'PinName="InterpSpeed"[^\r\n]*LinkedTo=\(K2Node_VariableGet_4 ' 'Speed easing must use the configurable SpeedResponse.'
Assert-GraphMatch $speedInterp 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_2 ' 'The interpolated value must be persisted as CurrentMoveSpeed.'

$rotation = [IO.File]::ReadAllText($rotationPath)
$rotationNodes = [regex]::Matches($rotation, '(?m)^Begin Object Class=').Count
if ($rotationNodes -ne 9) {
    throw "Apply-rotation-input contract expected 9 nodes; found $rotationNodes."
}
$rotationEntry = Get-NodeBlock $rotation 'K2Node_FunctionEntry_0'
$rotationController = Get-NodeBlock $rotation 'K2Node_CallFunction_0'
$rotationMake = Get-NodeBlock $rotation 'K2Node_CallFunction_1'
$rotationMouseDelta = Get-NodeBlock $rotation 'K2Node_CallFunction_2'
$rotationApply = Get-NodeBlock $rotation 'K2Node_CallFunction_3'
$rotationSensitivity = Get-NodeBlock $rotation 'K2Node_VariableGet_0'
$rotationYaw = Get-NodeBlock $rotation 'K2Node_PromotableOperator_0'
$rotationNegate = Get-NodeBlock $rotation 'K2Node_MacroInstance_0'
$rotationPitch = Get-NodeBlock $rotation 'K2Node_PromotableOperator_1'

Assert-GraphMatch $rotationEntry 'FunctionReference=\(MemberName="ApplyRotationInput"\)' 'Rotation must implement the named ApplyRotationInput contract.'
Assert-GraphMatch $rotationEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'ApplyRotationInput entry must execute exactly one local rotation write.'
Assert-GraphMatch $rotationController 'MemberName="GetPlayerController"' 'Rotation input must resolve the local player controller.'
Assert-GraphMatch $rotationController 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Rotation input must sample Player Controller 0.'
Assert-GraphMatch $rotationController 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_2 ' 'The local controller must feed GetInputMouseDelta.'
Assert-GraphMatch $rotationMouseDelta 'MemberName="GetInputMouseDelta"' 'Rotation input must sample raw mouse delta once per dispatch.'
Assert-GraphMatch $rotationMouseDelta 'PinName="DeltaX"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_0 ' 'Mouse DeltaX must feed yaw scaling.'
Assert-GraphMatch $rotationMouseDelta 'PinName="DeltaY"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'Mouse DeltaY must feed pitch scaling.'
Assert-GraphMatch $rotationSensitivity 'VariableReference=\(MemberName="LookSensitivity"' 'Rotation input must read the configurable LookSensitivity.'
Assert-GraphMatch $rotationSensitivity 'PinName="LookSensitivity"[^\r\n]*LinkedTo=\(K2Node_MacroInstance_0 [^,]+,K2Node_PromotableOperator_0 ' 'LookSensitivity must feed both inverted pitch and yaw scaling.'
Assert-GraphMatch $rotationNegate 'StandardMacros:NegateFloat' 'Pitch sensitivity must be explicitly inverted.'
Assert-GraphMatch $rotationNegate 'PinName="Result"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'Inverted sensitivity must feed pitch scaling.'
Assert-GraphMatch $rotationYaw 'OperationName="Multiply"' 'Yaw must be a direct delta-by-sensitivity product.'
Assert-GraphMatch $rotationYaw 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_1 ' 'Scaled yaw must feed MakeRotator.'
Assert-GraphMatch $rotationPitch 'OperationName="Multiply"' 'Pitch must be a delta-by-inverted-sensitivity product.'
Assert-GraphMatch $rotationPitch 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_1 ' 'Scaled pitch must feed MakeRotator.'
Assert-GraphMatch $rotationMake 'MemberName="MakeRotator"' 'Rotation input must construct one explicit rotator.'
Assert-GraphMatch $rotationMake 'PinName="Roll"[^\r\n]*DefaultValue="0\.0"' 'Mouse look must not introduce roll.'
Assert-GraphMatch $rotationMake 'PinName="Pitch"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'MakeRotator pitch must consume the scaled DeltaY path.'
Assert-GraphMatch $rotationMake 'PinName="Yaw"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_0 ' 'MakeRotator yaw must consume the scaled DeltaX path.'
Assert-GraphMatch $rotationMake 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'The completed rotator must feed AddActorLocalRotation.'
Assert-GraphMatch $rotationApply 'MemberName="K2_AddActorLocalRotation"' 'Mouse look must use explicit actor-local rotation.'
Assert-GraphMatch $rotationApply 'PinName="bSweep"[^\r\n]*DefaultValue="false"' 'Freecam rotation must not sweep.'
Assert-GraphMatch $rotationApply 'PinName="bTeleport"[^\r\n]*DefaultValue="false"' 'Freecam rotation must use ordinary local rotation.'

$roll = [IO.File]::ReadAllText($rollPath)
$rollNodes = [regex]::Matches($roll, '(?m)^Begin Object Class=').Count
if ($rollNodes -ne 33) {
    throw "Apply-roll-and-horizon-input contract expected 33 nodes; found $rollNodes."
}
$rollEntry = Get-NodeBlock $roll 'K2Node_FunctionEntry_0'
$rollController = Get-NodeBlock $roll 'K2Node_CallFunction_0'
$rollHToggle = Get-NodeBlock $roll 'K2Node_CallFunction_1'
$rollToggleBranch = Get-NodeBlock $roll 'K2Node_IfThenElse_0'
$rollLockToggleGet = Get-NodeBlock $roll 'K2Node_VariableGet_0'
$rollLockNot = Get-NodeBlock $roll 'K2Node_CallFunction_2'
$rollLockSet = Get-NodeBlock $roll 'K2Node_VariableSet_0'
$rollSet = Get-NodeBlock $roll 'K2Node_VariableSet_1'
$rollC = Get-NodeBlock $roll 'K2Node_CallFunction_3'
$rollZ = Get-NodeBlock $roll 'K2Node_CallFunction_4'
$rollSubtract = Get-NodeBlock $roll 'K2Node_PromotableOperator_0'
$rollManualSpeed = Get-NodeBlock $roll 'K2Node_VariableGet_1'
$rollTarget = Get-NodeBlock $roll 'K2Node_PromotableOperator_1'
$rollCurrentSpeed = Get-NodeBlock $roll 'K2Node_VariableGet_2'
$rollDeltaSeconds = Get-NodeBlock $roll 'K2Node_CallFunction_5'
$rollResponse = Get-NodeBlock $roll 'K2Node_VariableGet_3'
$rollInterp = Get-NodeBlock $roll 'K2Node_CallFunction_6'
$rollDelta = Get-NodeBlock $roll 'K2Node_PromotableOperator_2'
$rollMake = Get-NodeBlock $roll 'K2Node_CallFunction_7'
$rollApply = Get-NodeBlock $roll 'K2Node_CallFunction_8'
$rollCDown = Get-NodeBlock $roll 'K2Node_CallFunction_9'
$rollCBranch = Get-NodeBlock $roll 'K2Node_IfThenElse_1'
$rollZDown = Get-NodeBlock $roll 'K2Node_CallFunction_10'
$rollZBranch = Get-NodeBlock $roll 'K2Node_IfThenElse_2'
$rollLockModeGet = Get-NodeBlock $roll 'K2Node_VariableGet_4'
$rollLockBranch = Get-NodeBlock $roll 'K2Node_IfThenElse_3'
$rollActorRotation = Get-NodeBlock $roll 'K2Node_CallFunction_11'
$rollForward = Get-NodeBlock $roll 'K2Node_CallFunction_12'
$rollWorldUp = Get-NodeBlock $roll 'K2Node_CallFunction_13'
$rollLevelTarget = Get-NodeBlock $roll 'K2Node_CallFunction_14'
$rollHorizonResponse = Get-NodeBlock $roll 'K2Node_VariableGet_5'
$rollRotationInterp = Get-NodeBlock $roll 'K2Node_CallFunction_15'
$rollSetRotation = Get-NodeBlock $roll 'K2Node_CallFunction_16'

Assert-GraphMatch $rollEntry 'FunctionReference=\(MemberName="ApplyRollAndHorizonInput"\)' 'Roll must implement the named ApplyRollAndHorizonInput contract.'
Assert-GraphMatch $rollEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'Roll function entry must execute the H-toggle branch.'
Assert-GraphMatch $rollToggleBranch 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_FunctionEntry_0 ' 'The H-toggle branch must retain the reciprocal entry link.'
Assert-GraphMatch $rollSet 'VariableReference=\(MemberName="CurrentRollSpeed"' 'Roll must persist its smoothed angular speed.'
Assert-GraphMatch $rollSet 'PinName="CurrentRollSpeed"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'CurrentRollSpeed must receive the interpolated value.'
Assert-GraphMatch $rollSet 'PinName="Output_Get"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_2 ' 'Per-frame roll must use the post-write speed value.'
Assert-GraphMatch $rollSet 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_1 ' 'The roll speed write must precede manual-input arbitration.'
Assert-GraphMatch $rollController 'MemberName="GetPlayerController"' 'Roll input must resolve the local player controller.'
Assert-GraphMatch $rollController 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'Roll input must sample Player Controller 0.'
Assert-GraphMatch $rollController 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 [^,]+,K2Node_CallFunction_4 [^,]+,K2Node_CallFunction_1 [^,]+,K2Node_CallFunction_9 [^,]+,K2Node_CallFunction_10 ' 'The same local controller must feed H, analog C/Z, and held C/Z polling.'
Assert-GraphMatch $rollHToggle 'MemberName="WasInputKeyJustPressed"' 'Horizon mode must use edge-triggered input.'
Assert-GraphMatch $rollHToggle 'PinName="Key"[^\r\n]*DefaultValue="H"' 'H must toggle horizon lock.'
Assert-GraphMatch $rollHToggle 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'The H edge must drive the toggle branch.'
Assert-GraphMatch $rollLockToggleGet 'VariableReference=\(MemberName="HorizonLockEnabled"' 'The toggle must read the current horizon-lock state.'
Assert-GraphMatch $rollLockNot 'MemberName="Not_PreBool"' 'The toggle must invert the current horizon-lock state.'
Assert-GraphMatch $rollLockNot 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'The inverted state must feed the horizon-lock setter.'
Assert-GraphMatch $rollLockSet 'VariableReference=\(MemberName="HorizonLockEnabled"' 'H must write HorizonLockEnabled.'
Assert-GraphMatch $rollLockSet 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_VariableSet_1 ' 'Toggling lock must continue through the roll update in the same frame.'
Assert-GraphMatch $rollToggleBranch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_VariableSet_1 ' 'A frame without an H edge must still update roll.'
Assert-GraphMatch $rollC 'MemberName="GetInputAnalogKeyState"' 'C roll must use analog-compatible key sampling.'
Assert-GraphMatch $rollC 'PinName="Key"[^\r\n]*DefaultValue="C"' 'Positive manual roll must use C.'
Assert-GraphMatch $rollC 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_0 ' 'C must feed the positive side of the signed roll axis.'
Assert-GraphMatch $rollZ 'MemberName="GetInputAnalogKeyState"' 'Z roll must use analog-compatible key sampling.'
Assert-GraphMatch $rollZ 'PinName="Key"[^\r\n]*DefaultValue="Z"' 'Negative manual roll must use Z.'
Assert-GraphMatch $rollZ 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_0 ' 'Z must feed the negative side of the signed roll axis.'
Assert-GraphMatch $rollSubtract 'OperationName="Subtract"' 'Manual roll must form the signed C-minus-Z input axis.'
Assert-GraphMatch $rollSubtract 'PinName="A"[^\r\n]*LinkedTo=\(K2Node_CallFunction_3 ' 'C must be the positive roll operand.'
Assert-GraphMatch $rollSubtract 'PinName="B"[^\r\n]*LinkedTo=\(K2Node_CallFunction_4 ' 'Z must be the negative roll operand.'
Assert-GraphMatch $rollSubtract 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'The signed input axis must feed target angular speed.'
Assert-GraphMatch $rollManualSpeed 'VariableReference=\(MemberName="ManualRollSpeed"' 'Target angular speed must use the configurable ManualRollSpeed.'
Assert-GraphMatch $rollManualSpeed 'PinName="ManualRollSpeed"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'ManualRollSpeed must scale the signed input axis.'
Assert-GraphMatch $rollTarget 'OperationName="Multiply"' 'Target roll speed must be axis times ManualRollSpeed.'
Assert-GraphMatch $rollTarget 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Target roll speed must feed FInterpTo.'
Assert-GraphMatch $rollCurrentSpeed 'VariableReference=\(MemberName="CurrentRollSpeed"' 'Roll easing must start from persisted CurrentRollSpeed.'
Assert-GraphMatch $rollCurrentSpeed 'PinName="CurrentRollSpeed"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'Persisted CurrentRollSpeed must feed FInterpTo Current.'
Assert-GraphMatch $rollDeltaSeconds 'MemberName="GetWorldDeltaSeconds"' 'Roll easing and integration must share world delta seconds.'
Assert-GraphMatch $rollDeltaSeconds 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 [^,]+,K2Node_PromotableOperator_2 [^,]+,K2Node_CallFunction_15 ' 'World delta seconds must feed roll easing, angular integration, and horizon easing.'
Assert-GraphMatch $rollResponse 'VariableReference=\(MemberName="RollInputResponse"' 'Roll easing must use the configurable RollInputResponse.'
Assert-GraphMatch $rollResponse 'PinName="RollInputResponse"[^\r\n]*LinkedTo=\(K2Node_CallFunction_6 ' 'RollInputResponse must feed FInterpTo InterpSpeed.'
Assert-GraphMatch $rollInterp 'MemberName="FInterpTo"' 'CurrentRollSpeed must ease toward the signed target.'
Assert-GraphMatch $rollInterp 'PinName="Current"[^\r\n]*LinkedTo=\(K2Node_VariableGet_2 ' 'FInterpTo Current must consume CurrentRollSpeed.'
Assert-GraphMatch $rollInterp 'PinName="Target"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_1 ' 'FInterpTo Target must consume the signed target angular speed.'
Assert-GraphMatch $rollInterp 'PinName="DeltaTime"[^\r\n]*LinkedTo=\(K2Node_CallFunction_5 ' 'FInterpTo must use world delta seconds.'
Assert-GraphMatch $rollInterp 'PinName="InterpSpeed"[^\r\n]*LinkedTo=\(K2Node_VariableGet_3 ' 'FInterpTo must use RollInputResponse.'
Assert-GraphMatch $rollInterp 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_VariableSet_1 ' 'FInterpTo must persist the new CurrentRollSpeed.'
Assert-GraphMatch $rollDelta 'OperationName="Multiply"' 'Roll integration must multiply speed by delta seconds.'
Assert-GraphMatch $rollDelta 'PinName="A"[^\r\n]*LinkedTo=\(K2Node_VariableSet_1 ' 'Roll integration must consume the post-write speed.'
Assert-GraphMatch $rollDelta 'PinName="B"[^\r\n]*LinkedTo=\(K2Node_CallFunction_5 ' 'Roll integration must consume world delta seconds.'
Assert-GraphMatch $rollDelta 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_7 ' 'The integrated angle must feed MakeRotator Roll.'
Assert-GraphMatch $rollMake 'MemberName="MakeRotator"' 'Roll input must construct one explicit delta rotator.'
Assert-GraphMatch $rollMake 'PinName="Roll"[^\r\n]*LinkedTo=\(K2Node_PromotableOperator_2 ' 'MakeRotator Roll must consume integrated angular speed.'
Assert-GraphMatch $rollMake 'PinName="Pitch"[^\r\n]*DefaultValue="0\.0"' 'Manual bank must not introduce pitch.'
Assert-GraphMatch $rollMake 'PinName="Yaw"[^\r\n]*DefaultValue="0\.0"' 'Manual bank must not introduce yaw.'
Assert-GraphMatch $rollMake 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'The roll-only delta rotator must feed AddActorLocalRotation.'
Assert-GraphMatch $rollApply 'MemberName="K2_AddActorLocalRotation"' 'Manual bank must use actor-local rotation.'
Assert-GraphMatch $rollApply 'PinName="bSweep"[^\r\n]*DefaultValue="false"' 'Manual bank must not sweep.'
Assert-GraphMatch $rollApply 'PinName="bTeleport"[^\r\n]*DefaultValue="false"' 'Manual bank must use ordinary local rotation.'
Assert-GraphMatch $rollCDown 'MemberName="IsInputKeyDown"' 'Manual C override must test the held state.'
Assert-GraphMatch $rollCDown 'PinName="Key"[^\r\n]*DefaultValue="C"' 'Positive held override must use C.'
Assert-GraphMatch $rollCBranch 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'Held C must execute manual bank instead of horizon stabilization.'
Assert-GraphMatch $rollCBranch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_2 ' 'Without C, arbitration must test Z.'
Assert-GraphMatch $rollZDown 'MemberName="IsInputKeyDown"' 'Manual Z override must test the held state.'
Assert-GraphMatch $rollZDown 'PinName="Key"[^\r\n]*DefaultValue="Z"' 'Negative held override must use Z.'
Assert-GraphMatch $rollZBranch 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'Held Z must execute manual bank instead of horizon stabilization.'
Assert-GraphMatch $rollZBranch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_3 ' 'Without manual input, arbitration must test horizon-lock mode.'
Assert-GraphMatch $rollLockModeGet 'VariableReference=\(MemberName="HorizonLockEnabled"' 'Idle arbitration must read HorizonLockEnabled.'
Assert-GraphMatch $rollLockBranch 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_16 ' 'Enabled horizon lock must use absolute stabilized rotation.'
Assert-GraphMatch $rollLockBranch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_CallFunction_8 ' 'Disabled horizon lock must preserve bank while residual roll speed decays.'
Assert-GraphMatch $rollActorRotation 'MemberName="K2_GetActorRotation"' 'Horizon easing must start from current world rotation.'
Assert-GraphMatch $rollActorRotation 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_15 ' 'Current world rotation must feed RInterpTo Current.'
Assert-GraphMatch $rollForward 'MemberName="GetActorForwardVector"' 'Horizon target must preserve the current viewing direction.'
Assert-GraphMatch $rollForward 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_14 ' 'Current forward must feed MakeRotFromXZ X.'
Assert-GraphMatch $rollWorldUp 'MemberName="MakeVector"' 'Horizon stabilization must construct an explicit world-up vector.'
Assert-GraphMatch $rollWorldUp 'PinName="X"[^\r\n]*DefaultValue="0\.0"' 'World up X must be zero.'
Assert-GraphMatch $rollWorldUp 'PinName="Y"[^\r\n]*DefaultValue="0\.0"' 'World up Y must be zero.'
Assert-GraphMatch $rollWorldUp 'PinName="Z"[^\r\n]*DefaultValue="1\.0"' 'World up Z must be explicitly one.'
Assert-GraphMatch $rollWorldUp 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_14 ' 'Explicit world up must feed MakeRotFromXZ Z.'
Assert-GraphMatch $rollLevelTarget 'MemberName="MakeRotFromXZ"' 'The level target must preserve forward while constraining world up.'
Assert-GraphMatch $rollLevelTarget 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_15 ' 'The level target must feed RInterpTo Target.'
Assert-GraphMatch $rollHorizonResponse 'VariableReference=\(MemberName="HorizonLockResponse"' 'Horizon easing must use the configurable response.'
Assert-GraphMatch $rollHorizonResponse 'PinName="HorizonLockResponse"[^\r\n]*LinkedTo=\(K2Node_CallFunction_15 ' 'HorizonLockResponse must feed RInterpTo InterpSpeed.'
Assert-GraphMatch $rollRotationInterp 'MemberName="RInterpTo"' 'Horizon lock must ease rotation rather than snap.'
Assert-GraphMatch $rollRotationInterp 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_CallFunction_16 ' 'The eased world rotation must feed SetActorRotation.'
Assert-GraphMatch $rollSetRotation 'MemberName="K2_SetActorRotation"' 'Horizon stabilization must apply an absolute world rotation.'
Assert-GraphMatch $rollSetRotation 'PinName="bTeleportPhysics"[^\r\n]*DefaultValue="false"' 'Horizon stabilization must use ordinary actor rotation.'
if ($roll -match '(?m)^\s*Error(Type|Msg)=') {
    throw 'Apply-roll-and-horizon-input source must not retain stale compiler error metadata.'
}

$droneEvent = [IO.File]::ReadAllText($droneEventPath)
$droneEventNodes = [regex]::Matches($droneEvent, '(?m)^Begin Object Class=').Count
if ($droneEventNodes -ne 3) {
    throw "Drone-camera EventGraph contract expected 3 nodes; found $droneEventNodes."
}
$droneBeginPlay = Get-NodeBlock $droneEvent 'K2Node_Event_3'
$droneSetReplicates = Get-NodeBlock $droneEvent 'K2Node_CallFunction_0'
$droneSetReplicateMovement = Get-NodeBlock $droneEvent 'K2Node_CallFunction_1'
Assert-GraphMatch $droneBeginPlay 'MemberName="ReceiveBeginPlay"' 'The drone must enforce local-only state at BeginPlay.'
Assert-GraphMatch $droneBeginPlay 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'Drone BeginPlay must disable actor replication first.'
Assert-GraphMatch $droneSetReplicates 'MemberName="SetReplicates"' 'The drone must explicitly disable inherited SpectatorPawn replication.'
Assert-GraphMatch $droneSetReplicates 'PinName="bInReplicates"[^\r\n]*DefaultValue="false"' 'Drone actor replication must be false.'
Assert-GraphMatch $droneSetReplicates 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_1 ' 'Actor replication disablement must precede movement replication disablement.'
Assert-GraphMatch $droneSetReplicateMovement 'MemberName="SetReplicateMovement"' 'The drone must explicitly disable inherited movement replication.'
Assert-GraphMatch $droneSetReplicateMovement 'PinName="bInReplicateMovement"[^\r\n]*DefaultValue="false"' 'Drone movement replication must be false.'

$emergency = [IO.File]::ReadAllText($emergencyPath)
$emergencyNodes = [regex]::Matches($emergency, '(?m)^Begin Object Class=').Count
if ($emergencyNodes -ne 4) {
    throw "Emergency-exit contract expected 4 nodes; found $emergencyNodes."
}

$emergencyEntry = Get-NodeBlock $emergency 'K2Node_FunctionEntry_0'
$emergencyExit = Get-NodeBlock $emergency 'K2Node_CallFunction_0'
$emergencySet = Get-NodeBlock $emergency 'K2Node_VariableSet_0'
$emergencyPrint = Get-NodeBlock $emergency 'K2Node_CallFunction_1'

Assert-GraphMatch $emergencyEntry 'FunctionReference=\(MemberName="EmergencyExitDroneMode"\)' 'Emergency exit must implement the named function contract.'
Assert-GraphMatch $emergencyEntry 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_0 ' 'Emergency entry must delegate restoration to ExitDroneMode.'
Assert-GraphMatch $emergencyExit 'FunctionReference=\(MemberName="ExitDroneMode"' 'Emergency exit must use the normal idempotent restoration primitive.'
Assert-GraphMatch $emergencyExit 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_VariableSet_0 ' 'Emergency exit must clear active state only after restoration returns.'
Assert-GraphMatch $emergencySet 'VariableReference=\(MemberName="DroneModeActive"' 'Emergency exit must write DroneModeActive.'
Assert-GraphMatch $emergencySet 'PinName="DroneModeActive"[^\r\n]*,DefaultValue="false",AutogeneratedDefaultValue=' 'Emergency exit must force DroneModeActive false.'
Assert-GraphMatch $emergencySet 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_1 ' 'Emergency completion must be reported only after active state is cleared.'
Assert-GraphMatch $emergencyPrint 'MemberName="PrintString"' 'Emergency exit must expose a development diagnostic.'
Assert-GraphMatch $emergencyPrint 'DefaultValue="\[EDD\] Emergency exit complete"' 'Emergency exit must expose its acceptance diagnostic.'
Assert-GraphMatch $emergencyPrint 'PinName="bPrintToLog"[^\r\n]*DefaultValue="true"' 'Emergency-exit acceptance must be written to the log.'

$eventGraph = [IO.File]::ReadAllText($eventGraphPath)
$eventGraphNodes = [regex]::Matches($eventGraph, '(?m)^Begin Object Class=/Script/BlueprintGraph\.').Count
if ($eventGraphNodes -ne 32) {
    throw "Client-director EventGraph contract expected 32 executable nodes; found $eventGraphNodes."
}
if ([regex]::Matches($eventGraph, '(?m)^Begin Object Class=/Script/UnrealEd\.EdGraphNode_Comment').Count -ne 1) {
    throw 'Client-director EventGraph must retain exactly one design comment node.'
}
if ([regex]::Matches($eventGraph, 'EventReference=\([^\r\n]*MemberName="ReceiveTick"').Count -ne 1) {
    throw 'Client-director EventGraph must contain exactly one ReceiveTick event.'
}
if ([regex]::Matches($eventGraph, 'MemberName="EmergencyExitDroneMode"').Count -ne 2) {
    throw 'Client-director EventGraph must contain exactly two emergency-exit callers.'
}

$tickEvent = Get-NodeBlock $eventGraph 'K2Node_Event_1'
$f10Branch = Get-NodeBlock $eventGraph 'K2Node_IfThenElse_0'
$f10Poll = Get-NodeBlock $eventGraph 'K2Node_CallFunction_2'
$f9Branch = Get-NodeBlock $eventGraph 'K2Node_IfThenElse_2'
$f9Poll = Get-NodeBlock $eventGraph 'K2Node_CallFunction_8'
$manualEmergency = Get-NodeBlock $eventGraph 'K2Node_CallFunction_9'
$activeBranch = Get-NodeBlock $eventGraph 'K2Node_IfThenElse_3'
$activeGet = Get-NodeBlock $eventGraph 'K2Node_VariableGet_1'
$cameraBranch = Get-NodeBlock $eventGraph 'K2Node_IfThenElse_4'
$cameraGet = Get-NodeBlock $eventGraph 'K2Node_VariableGet_2'
$cameraValid = Get-NodeBlock $eventGraph 'K2Node_CallFunction_10'
$invalidEmergency = Get-NodeBlock $eventGraph 'K2Node_CallFunction_11'
$translationInput = Get-NodeBlock $eventGraph 'K2Node_CallFunction_12'
$rotationInput = Get-NodeBlock $eventGraph 'K2Node_CallFunction_13'
$rollInput = Get-NodeBlock $eventGraph 'K2Node_CallFunction_39'
$speedInput = Get-NodeBlock $eventGraph 'K2Node_CallFunction_17'
$ownerGet = Get-NodeBlock $eventGraph 'K2Node_CallFunction_14'
$localControllerGet = Get-NodeBlock $eventGraph 'K2Node_CallFunction_15'
$ownerEquals = Get-NodeBlock $eventGraph 'K2Node_CallFunction_16'
$ownerGate = Get-NodeBlock $eventGraph 'K2Node_IfThenElse_5'

Assert-GraphMatch $tickEvent 'EventReference=.*MemberName="ReceiveTick"' 'Emergency polling must run from the component tick.'
Assert-GraphMatch $tickEvent 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_5 ' 'ReceiveTick must enter the owning-local-controller gate first.'
Assert-GraphMatch $ownerGet 'MemberName="GetOwner"' 'The locality gate must resolve the component owner.'
Assert-GraphMatch $localControllerGet 'MemberName="GetPlayerController"' 'The locality gate must resolve local Player Controller 0.'
Assert-GraphMatch $localControllerGet 'PinName="PlayerIndex"[^\r\n]*DefaultValue="0"' 'The locality gate must compare against local player index 0.'
Assert-GraphMatch $ownerEquals 'MemberName="ObjectEquals"' 'The locality gate must compare owner identity exactly.'
Assert-GraphMatch $ownerEquals 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_5 ' 'Owner equality must drive the locality branch.'
Assert-GraphMatch $ownerGate 'PinFriendlyName=.*?"true".*?LinkedTo=\(K2Node_IfThenElse_0 ' 'Only the owning local controller may enter F10/F9 polling.'
$ownerFalse = [regex]::Match($ownerGate, '(?m)^\s*CustomProperties Pin \([^\r\n]*PinName="else"[^\r\n]*$')
if (-not $ownerFalse.Success -or $ownerFalse.Value -match 'LinkedTo=') {
    throw 'Non-local director components must terminate without side effects.'
}
Assert-GraphMatch $f10Poll 'MemberName="WasInputKeyJustPressed"' 'F10 entry must use edge-triggered polling.'
Assert-GraphMatch $f10Poll 'PinName="Key"[^\r\n]*DefaultValue="F10"' 'The normal-mode hotkey must remain F10.'
Assert-GraphMatch $f10Poll 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_0 ' 'F10 polling must drive the normal-mode branch.'
Assert-GraphMatch $f10Branch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_2 ' 'A tick without F10 must continue to the F9 emergency branch.'
Assert-GraphMatch $f9Poll 'MemberName="WasInputKeyJustPressed"' 'F9 emergency exit must use edge-triggered polling.'
Assert-GraphMatch $f9Poll 'PinName="Key"[^\r\n]*DefaultValue="F9"' 'The emergency hotkey must remain F9.'
Assert-GraphMatch $f9Poll 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_2 ' 'F9 polling must drive the emergency branch.'
Assert-GraphMatch $f9Branch 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_9 ' 'F9 must immediately execute the manual emergency caller.'
Assert-GraphMatch $manualEmergency 'FunctionReference=\(MemberName="EmergencyExitDroneMode"' 'The manual F9 path must delegate to EmergencyExitDroneMode.'
Assert-GraphMatch $f9Branch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_3 ' 'A tick without F9 must continue to the active-mode recovery guard.'
Assert-GraphMatch $activeGet 'VariableReference=\(MemberName="DroneModeActive"' 'Automatic recovery must read DroneModeActive.'
Assert-GraphMatch $activeGet 'PinName="DroneModeActive"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_3 ' 'DroneModeActive must drive the active-mode guard.'
Assert-GraphMatch $activeBranch 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_4 ' 'Only active Drone Mode may enter the camera-validity guard.'
Assert-GraphMatch $cameraGet 'VariableReference=\(MemberName="DroneCameraRef"' 'Automatic recovery must read the typed camera reference.'
Assert-GraphMatch $cameraGet 'PinName="DroneCameraRef"[^\r\n]*LinkedTo=\(K2Node_CallFunction_10 ' 'DroneCameraRef must feed the recovery validity check.'
Assert-GraphMatch $cameraValid 'MemberName="IsValid"' 'Automatic recovery must validate DroneCameraRef.'
Assert-GraphMatch $cameraValid 'PinName="ReturnValue"[^\r\n]*LinkedTo=\(K2Node_IfThenElse_4 ' 'Camera validity must drive the recovery branch.'
Assert-GraphMatch $cameraBranch 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_17 ' 'A valid active camera must update speed controls before movement.'
Assert-GraphMatch $cameraBranch 'PinName="else"[^\r\n]*LinkedTo=\(K2Node_CallFunction_11 ' 'An invalid active camera must execute automatic emergency restoration.'
Assert-GraphMatch $invalidEmergency 'FunctionReference=\(MemberName="EmergencyExitDroneMode"' 'The invalid-camera path must delegate to EmergencyExitDroneMode.'
Assert-GraphMatch $speedInput 'FunctionReference=.*MemberName="UpdateSpeedControls"' 'Active-mode input must delegate to BP_EDD_DroneCamera.UpdateSpeedControls.'
Assert-GraphMatch $speedInput 'PinName="self"[^\r\n]*LinkedTo=\(K2Node_VariableGet_2 ' 'Speed control must target the validated DroneCameraRef.'
Assert-GraphMatch $speedInput 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_12 ' 'Speed control must complete before translation executes.'
Assert-GraphMatch $translationInput 'FunctionReference=.*MemberName="ApplyTranslationInput"' 'Active-mode movement must delegate to BP_EDD_DroneCamera.ApplyTranslationInput.'
Assert-GraphMatch $translationInput 'PinName="self"[^\r\n]*LinkedTo=\(K2Node_VariableGet_2 ' 'Translation input must target the validated DroneCameraRef.'
Assert-GraphMatch $translationInput 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_13 ' 'Translation input must complete before rotation input executes.'
Assert-GraphMatch $rotationInput 'FunctionReference=.*MemberName="ApplyRotationInput"' 'Active-mode look must delegate to BP_EDD_DroneCamera.ApplyRotationInput.'
Assert-GraphMatch $rotationInput 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_12 ' 'Rotation input must execute after translation on the same active tick.'
Assert-GraphMatch $rotationInput 'PinName="self"[^\r\n]*LinkedTo=\(K2Node_VariableGet_2 ' 'Rotation input must target the validated DroneCameraRef.'
Assert-GraphMatch $rotationInput 'PinName="then"[^\r\n]*LinkedTo=\(K2Node_CallFunction_39 ' 'Rotation input must complete before manual roll executes.'
Assert-GraphMatch $rollInput 'FunctionReference=.*MemberName="ApplyRollAndHorizonInput"' 'Active-mode bank must delegate to BP_EDD_DroneCamera.ApplyRollAndHorizonInput.'
Assert-GraphMatch $rollInput 'PinName="execute"[^\r\n]*LinkedTo=\(K2Node_CallFunction_13 ' 'Roll input must execute after mouse rotation on the same active tick.'
Assert-GraphMatch $rollInput 'PinName="self"[^\r\n]*LinkedTo=\(K2Node_VariableGet_2 ' 'Roll input must target the validated DroneCameraRef.'

$inactivePath = [regex]::Match($activeBranch, '(?m)^\s*CustomProperties Pin \([^\r\n]*PinName="else"[^\r\n]*$')
if (-not $inactivePath.Success -or $inactivePath.Value -match 'LinkedTo=') {
    throw 'Inactive Drone Mode must bypass the camera recovery guard without side effects.'
}
foreach ($emergencyGraph in @($emergency, $eventGraph)) {
    if ($emergencyGraph -match '(?m)^\s*Error(Type|Msg)=') {
        throw 'Emergency-recovery graph source must not retain stale compiler error metadata.'
    }
}

foreach ($viewGraph in @($place, $activate, $switch, $exit, $movement, $rotation, $roll, $speed, $droneEvent)) {
    if ($viewGraph -match '(?m)^\s*Error(Type|Msg)=') {
        throw 'View-lifecycle graph source must not retain stale compiler error metadata.'
    }
}

Write-Output 'Blueprint graph contracts valid: toggle-input, toggle-state, enter-drone-mode, place-drone-at-current-view, activate-drone-view, switch-to-drone-view, exit-drone-mode, emergency-exit-drone-mode, client-director-event-graph, apply-translation-input, apply-rotation-input, apply-roll-and-horizon-input, update-speed-controls, drone-camera-event-graph (legacy possession helpers also remain structurally validated)'
