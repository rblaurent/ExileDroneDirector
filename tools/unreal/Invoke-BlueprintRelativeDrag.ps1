[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,

    [Parameter(Mandatory = $true)]
    [int]$ClientX,

    [Parameter(Mandatory = $true)]
    [int]$ClientY,

    [Parameter(Mandatory = $true)]
    [ValidateRange(-4000, 4000)]
    [int]$DeltaX,

    [Parameter(Mandatory = $true)]
    [ValidateRange(-4000, 4000)]
    [int]$DeltaY,

    [ValidateSet('Left', 'Right')]
    [string]$Button = 'Right',

    [ValidateRange(50, 2000)]
    [int]$DurationMilliseconds = 500
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not ('EddBlueprintRelativeDrag' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class EddBlueprintRelativeDrag {
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X; public int Y; }

    [DllImport("user32.dll")]
    public static extern bool IsWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
}
'@
}

$handle = [IntPtr]$WindowHandle
if (-not [EddBlueprintRelativeDrag]::IsWindow($handle)) {
    throw "Window handle is not valid: $WindowHandle"
}
[void][EddBlueprintRelativeDrag]::SetForegroundWindow($handle)
Start-Sleep -Milliseconds 120

$point = New-Object EddBlueprintRelativeDrag+POINT
$point.X = $ClientX
$point.Y = $ClientY
if (-not [EddBlueprintRelativeDrag]::ClientToScreen($handle, [ref]$point)) {
    throw "Could not convert graph coordinate $ClientX,$ClientY"
}
if (-not [EddBlueprintRelativeDrag]::SetCursorPos($point.X, $point.Y)) {
    throw "Could not position cursor over graph canvas"
}

$buttonDown = if ($Button -eq 'Left') { 0x0002 } else { 0x0008 }
$buttonUp = if ($Button -eq 'Left') { 0x0004 } else { 0x0010 }
try {
    # Enhanced's graph editor consumes raw relative mouse movement while a
    # button is held. SetCursorPos-only drags can look valid to automation while
    # leaving the viewport or selected node unchanged.
    [EddBlueprintRelativeDrag]::mouse_event($buttonDown, 0, 0, 0, [UIntPtr]::Zero)
    $steps = [Math]::Max(2, [int]($DurationMilliseconds / 20))
    $sentX = 0
    $sentY = 0
    for ($index = 1; $index -le $steps; $index++) {
        $nextX = [int][Math]::Round($DeltaX * $index / $steps)
        $nextY = [int][Math]::Round($DeltaY * $index / $steps)
        $moveX = $nextX - $sentX
        $moveY = $nextY - $sentY
        $encodedX = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$moveX), 0)
        $encodedY = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$moveY), 0)
        [EddBlueprintRelativeDrag]::mouse_event(0x0001, $encodedX, $encodedY, 0, [UIntPtr]::Zero)
        $sentX = $nextX
        $sentY = $nextY
        Start-Sleep -Milliseconds ([Math]::Max(1, [int]($DurationMilliseconds / $steps)))
    }
}
finally {
    [EddBlueprintRelativeDrag]::mouse_event($buttonUp, 0, 0, 0, [UIntPtr]::Zero)
}

Start-Sleep -Milliseconds 200
Write-Output "EDD_BLUEPRINT_RELATIVE_DRAG|$Button|$DeltaX,$DeltaY|WINDOW:$WindowHandle"
