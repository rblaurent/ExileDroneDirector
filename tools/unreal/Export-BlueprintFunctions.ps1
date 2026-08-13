[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [Parameter(Mandatory = $true)]
    [string[]]$FunctionSpec,

    [int]$SearchX = 375,
    [int]$SearchY = 144,
    [int]$ResultX = 350,
    [int]$ResultY = 238,
    [int]$CanvasX = 900,
    [int]$CanvasY = 500
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inputHelper = Join-Path $PSScriptRoot 'Invoke-EnhancedEditorInput.ps1'
$exportHelper = Join-Path $PSScriptRoot '..\blueprint\Export-BlueprintGraphClipboard.ps1'
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null

foreach ($spec in $FunctionSpec) {
    $parts = $spec.Split(':')
    if ($parts.Count -ne 3 -or $parts[0] -notmatch '^[A-Za-z][A-Za-z0-9_]*$' -or
        $parts[1] -notmatch '^[1-9][0-9]*$' -or $parts[2] -notmatch '^[a-z0-9][a-z0-9-]*$') {
        throw "Invalid function spec '$spec'. Expected FunctionName:NodeCount:file-stem."
    }

    $functionName = $parts[0]
    $nodeCount = [int]$parts[1]
    $destination = Join-Path $resolvedOutput ($parts[2] + '.eddgraph')

    & $inputHelper -WindowHandle $WindowHandle -ClientX $SearchX -ClientY $SearchY -PostDelayMilliseconds 60
    & $inputHelper -WindowHandle $WindowHandle -Keys '^a' -PostDelayMilliseconds 40
    & $inputHelper -WindowHandle $WindowHandle -Keys $functionName -PostDelayMilliseconds 180
    # Enhanced does not refresh Find Results merely because the query text
    # changed. Execute the search explicitly before opening the result; without
    # this, a valid-looking automation run can silently reopen the prior graph.
    & $inputHelper -WindowHandle $WindowHandle -Keys '{ENTER}' -PostDelayMilliseconds 550
    & $inputHelper -WindowHandle $WindowHandle -ClientX $ResultX -ClientY $ResultY -ClickCount 2 -PostDelayMilliseconds 280
    & $inputHelper -WindowHandle $WindowHandle -ClientX $CanvasX -ClientY $CanvasY -PostDelayMilliseconds 60
    & $inputHelper -WindowHandle $WindowHandle -Keys '^a' -PostDelayMilliseconds 40
    & $inputHelper -WindowHandle $WindowHandle -Keys '^c' -PostDelayMilliseconds 180
    & $exportHelper -DestinationPath $destination -ExpectedGraph $functionName -ExpectedNodeCount $nodeCount -Force
}

Write-Output "EDD_BLUEPRINT_FUNCTION_EXPORT|COUNT|$($FunctionSpec.Count)|OUTPUT|$resolvedOutput"
