[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z][A-Za-z0-9_]*$')]
    [string]$FunctionName,

    [int]$SearchX = 500,
    [int]$SearchY = 834,
    [int]$ResultX = 170,
    [int]$ResultY = 887
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inputHelper = Join-Path $PSScriptRoot 'Invoke-EnhancedEditorInput.ps1'

# Find Results is the stable fallback when a saved Blueprint layout has no
# My Blueprint panel. Enter explicitly executes the search; merely replacing
# the text leaves the previous result tree active.
& $inputHelper -WindowHandle $WindowHandle -ClientX $SearchX -ClientY $SearchY `
    -PostDelayMilliseconds 40
& $inputHelper -WindowHandle $WindowHandle -Keys '^a' -PostDelayMilliseconds 20
& $inputHelper -WindowHandle $WindowHandle -Keys $FunctionName -PostDelayMilliseconds 40
& $inputHelper -WindowHandle $WindowHandle -Keys '{ENTER}' -PostDelayMilliseconds 550
& $inputHelper -WindowHandle $WindowHandle -ClientX $ResultX -ClientY $ResultY `
    -ClickCount 2 -PostDelayMilliseconds 500

Write-Output "EDD_BLUEPRINT_FUNCTION_OPEN|$FunctionName|WINDOW:$WindowHandle"
