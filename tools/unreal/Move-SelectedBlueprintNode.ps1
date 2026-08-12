[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,

    [Parameter(Mandatory = $true)]
    [int]$ExpectedStartX,

    [Parameter(Mandatory = $true)]
    [int]$ExpectedStartY,

    [Parameter(Mandatory = $true)]
    [int]$TargetX,

    [Parameter(Mandatory = $true)]
    [int]$TargetY,

    [string]$ExpectedNodeMarker = '',

    [int]$HeaderClientX = 630,
    [int]$HeaderClientY = 440
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inputHelper = Join-Path $PSScriptRoot 'Invoke-EnhancedEditorInput.ps1'

function Get-SelectedNodePosition {
    & $inputHelper -WindowHandle $WindowHandle -Keys '^c' -PostDelayMilliseconds 100 | Out-Null
    $clipboard = Get-Clipboard -Raw
    if ($ExpectedNodeMarker -and -not $clipboard.Contains($ExpectedNodeMarker)) {
        throw "Selected Blueprint node no longer matches marker '$ExpectedNodeMarker'. Selection likely transferred to an overlapping node."
    }
    $xMatches = [regex]::Matches($clipboard, '(?m)^\s*NodePosX=(-?\d+)\s*$')
    $yMatches = [regex]::Matches($clipboard, '(?m)^\s*NodePosY=(-?\d+)\s*$')
    if ($xMatches.Count -ne 1 -or $yMatches.Count -ne 1) {
        throw "Expected exactly one selected Blueprint node; clipboard contained $($xMatches.Count) X positions and $($yMatches.Count) Y positions."
    }
    return @([int]$xMatches[0].Groups[1].Value, [int]$yMatches[0].Groups[1].Value)
}

if (($TargetX % 16) -ne 0 -or ($TargetY % 16) -ne 0) {
    throw 'Blueprint graph targets must be aligned to the 16-unit editor grid.'
}

$position = Get-SelectedNodePosition
if ($position[0] -ne $ExpectedStartX -or $position[1] -ne $ExpectedStartY) {
    throw "Selected node began at $($position[0]),$($position[1]); expected $ExpectedStartX,$ExpectedStartY."
}

$moves = 0
while ($position[0] -ne $TargetX -or $position[1] -ne $TargetY) {
    if ($moves -ge 32) {
        throw "Move budget exhausted at $($position[0]),$($position[1]); target is $TargetX,$TargetY."
    }

    $remainingX = $TargetX - $position[0]
    $remainingY = $TargetY - $position[1]
    $deltaX = [Math]::Max(-416, [Math]::Min(416, $remainingX))
    $deltaY = [Math]::Max(-304, [Math]::Min(304, $remainingY))
    $deltaX = [int]([Math]::Round($deltaX / 16.0) * 16)
    $deltaY = [int]([Math]::Round($deltaY / 16.0) * 16)

    & $inputHelper -WindowHandle $WindowHandle -Keys '{HOME}' -PostDelayMilliseconds 250 | Out-Null
    & $inputHelper -WindowHandle $WindowHandle `
        -StartClientX $HeaderClientX -StartClientY $HeaderClientY `
        -EndClientX ($HeaderClientX + $deltaX) -EndClientY ($HeaderClientY + $deltaY) `
        -DragMilliseconds 650 -PostDelayMilliseconds 100 | Out-Null

    $previous = $position
    $previousDistance = [Math]::Abs($TargetX - $previous[0]) + [Math]::Abs($TargetY - $previous[1])
    $position = Get-SelectedNodePosition
    $actualDeltaX = $position[0] - $previous[0]
    $actualDeltaY = $position[1] - $previous[1]
    $currentDistance = [Math]::Abs($TargetX - $position[0]) + [Math]::Abs($TargetY - $position[1])
    if (($position[0] % 16) -ne 0 -or ($position[1] % 16) -ne 0) {
        throw "Blueprint node left the 16-unit editor grid at $($position[0]),$($position[1])."
    }
    if ($currentDistance -ge $previousDistance) {
        throw "Blueprint node move did not converge: requested $deltaX,$deltaY; observed $actualDeltaX,$actualDeltaY and distance changed from $previousDistance to $currentDistance."
    }
    $moves++
}

Write-Output "EDD_BLUEPRINT_NODE_MOVED|$ExpectedStartX,$ExpectedStartY|$TargetX,$TargetY|MOVES:$moves"
