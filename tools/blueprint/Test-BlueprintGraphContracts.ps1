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
$validator = Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1'

& $validator -Path @($inputPath, $statePath) -AllowTokens | Write-Verbose

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

Write-Output 'Blueprint graph contracts valid: toggle-input, toggle-state'
