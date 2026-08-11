[CmdletBinding(DefaultParameterSetName = 'Keys')]
param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,

    [Parameter(Mandatory = $true, ParameterSetName = 'Keys')]
    [string]$Keys,

    [Parameter(Mandatory = $true, ParameterSetName = 'Click')]
    [int]$ClientX,

    [Parameter(Mandatory = $true, ParameterSetName = 'Click')]
    [int]$ClientY,

    [Parameter(Mandatory = $true, ParameterSetName = 'Drag')]
    [int]$StartClientX,

    [Parameter(Mandatory = $true, ParameterSetName = 'Drag')]
    [int]$StartClientY,

    [Parameter(Mandatory = $true, ParameterSetName = 'Drag')]
    [int]$EndClientX,

    [Parameter(Mandatory = $true, ParameterSetName = 'Drag')]
    [int]$EndClientY,

    [Parameter(ParameterSetName = 'Drag')]
    [ValidateRange(50, 5000)]
    [int]$DragMilliseconds = 400,

    [Parameter(Mandatory = $true, ParameterSetName = 'Wheel')]
    [int]$WheelClientX,

    [Parameter(Mandatory = $true, ParameterSetName = 'Wheel')]
    [int]$WheelClientY,

    [Parameter(Mandatory = $true, ParameterSetName = 'Wheel')]
    [ValidateRange(-20, 20)]
    [int]$WheelNotches,

    [Parameter(ParameterSetName = 'Click')]
    [ValidateRange(1, 3)]
    [int]$ClickCount = 1,

    [ValidateRange(0, 5000)]
    [int]$PostDelayMilliseconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

if (-not ('EddEnhancedEditorInput' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class EddEnhancedEditorInput {
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X; public int Y; }

    [DllImport("user32.dll")]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, IntPtr processId);

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("user32.dll")]
    private static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool attach);

    [DllImport("user32.dll")]
    private static extern bool BringWindowToTop(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hWnd, int command);

    public static bool FocusWindow(IntPtr hWnd) {
        if (GetForegroundWindow() == hWnd) return true;
        IntPtr foreground = GetForegroundWindow();
        uint currentThread = GetCurrentThreadId();
        uint foregroundThread = foreground == IntPtr.Zero ? 0 : GetWindowThreadProcessId(foreground, IntPtr.Zero);
        uint targetThread = GetWindowThreadProcessId(hWnd, IntPtr.Zero);
        bool attachedForeground = foregroundThread != 0 && foregroundThread != currentThread && AttachThreadInput(currentThread, foregroundThread, true);
        bool attachedTarget = targetThread != 0 && targetThread != currentThread && targetThread != foregroundThread && AttachThreadInput(currentThread, targetThread, true);
        try {
            ShowWindow(hWnd, 9);
            BringWindowToTop(hWnd);
            SetForegroundWindow(hWnd);
            return GetForegroundWindow() == hWnd;
        }
        finally {
            if (attachedTarget) AttachThreadInput(currentThread, targetThread, false);
            if (attachedForeground) AttachThreadInput(currentThread, foregroundThread, false);
        }
    }

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
if (-not [EddEnhancedEditorInput]::IsWindow($handle)) {
    throw "Window handle is not valid: $WindowHandle"
}
if (-not [EddEnhancedEditorInput]::FocusWindow($handle)) {
    throw "Could not focus window handle: $WindowHandle"
}
Start-Sleep -Milliseconds 150

if ($PSCmdlet.ParameterSetName -eq 'Keys') {
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    $result = "KEYS:$Keys"
}
elseif ($PSCmdlet.ParameterSetName -eq 'Click') {
    $point = New-Object EddEnhancedEditorInput+POINT
    $point.X = $ClientX
    $point.Y = $ClientY
    if (-not [EddEnhancedEditorInput]::ClientToScreen($handle, [ref]$point)) {
        throw "Could not convert client coordinates for window: $WindowHandle"
    }
    if (-not [EddEnhancedEditorInput]::SetCursorPos($point.X, $point.Y)) {
        throw "Could not position cursor at client coordinate $ClientX,$ClientY"
    }
    for ($index = 0; $index -lt $ClickCount; $index++) {
        [EddEnhancedEditorInput]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
        [EddEnhancedEditorInput]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
        if ($index + 1 -lt $ClickCount) {
            Start-Sleep -Milliseconds 80
        }
    }
    $result = "CLICK:${ClientX},${ClientY}:${ClickCount}"
}
elseif ($PSCmdlet.ParameterSetName -eq 'Drag') {
    $start = New-Object EddEnhancedEditorInput+POINT
    $start.X = $StartClientX
    $start.Y = $StartClientY
    $end = New-Object EddEnhancedEditorInput+POINT
    $end.X = $EndClientX
    $end.Y = $EndClientY
    if (-not [EddEnhancedEditorInput]::ClientToScreen($handle, [ref]$start)) {
        throw "Could not convert drag start coordinates for window: $WindowHandle"
    }
    if (-not [EddEnhancedEditorInput]::ClientToScreen($handle, [ref]$end)) {
        throw "Could not convert drag end coordinates for window: $WindowHandle"
    }
    if (-not [EddEnhancedEditorInput]::SetCursorPos($start.X, $start.Y)) {
        throw "Could not position cursor at drag start $StartClientX,$StartClientY"
    }
    [EddEnhancedEditorInput]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    $steps = [Math]::Max(2, [int]($DragMilliseconds / 20))
    for ($index = 1; $index -le $steps; $index++) {
        $x = [int]($start.X + (($end.X - $start.X) * $index / $steps))
        $y = [int]($start.Y + (($end.Y - $start.Y) * $index / $steps))
        [void][EddEnhancedEditorInput]::SetCursorPos($x, $y)
        Start-Sleep -Milliseconds ([Math]::Max(1, [int]($DragMilliseconds / $steps)))
    }
    [EddEnhancedEditorInput]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    $result = "DRAG:${StartClientX},${StartClientY}:${EndClientX},${EndClientY}"
}
else {
    $point = New-Object EddEnhancedEditorInput+POINT
    $point.X = $WheelClientX
    $point.Y = $WheelClientY
    if (-not [EddEnhancedEditorInput]::ClientToScreen($handle, [ref]$point)) {
        throw "Could not convert wheel coordinates for window: $WindowHandle"
    }
    if (-not [EddEnhancedEditorInput]::SetCursorPos($point.X, $point.Y)) {
        throw "Could not position cursor at wheel coordinate $WheelClientX,$WheelClientY"
    }
    $delta = [uint32]([int64]$WheelNotches * 120 -band 0xFFFFFFFFL)
    [EddEnhancedEditorInput]::mouse_event(0x0800, 0, 0, $delta, [UIntPtr]::Zero)
    $result = "WHEEL:${WheelClientX},${WheelClientY}:${WheelNotches}"
}

Start-Sleep -Milliseconds $PostDelayMilliseconds
Write-Output "EDD_EDITOR_INPUT|$result|WINDOW:$WindowHandle"
