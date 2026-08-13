[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,

    [Parameter(Mandatory = $true)]
    [string]$DestinationPath,

    [switch]$PreserveForeground
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not ('EddWindowCapture' -as [type])) {
    Add-Type -AssemblyName System.Drawing
    Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class EddWindowCapture
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@
}

$handle = [IntPtr]$WindowHandle
if (-not [EddWindowCapture]::IsWindow($handle)) {
    throw "Window handle is not valid: $WindowHandle"
}
if (-not $PreserveForeground) {
    if (-not [EddWindowCapture]::SetForegroundWindow($handle)) {
        throw "Could not focus window handle: $WindowHandle"
    }
    Start-Sleep -Milliseconds 120
}
$rect = New-Object EddWindowCapture+RECT
if (-not [EddWindowCapture]::GetWindowRect($handle, [ref]$rect)) {
    throw "Could not read window bounds: $WindowHandle"
}
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) {
    throw "Window has invalid bounds: ${width}x${height}"
}

$destination = [IO.Path]::GetFullPath($DestinationPath)
$parent = Split-Path -Parent $destination
if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$bitmap = New-Object Drawing.Bitmap($width, $height)
$graphics = [Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($destination, [Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
Write-Output "EDD_WINDOW_SCREENSHOT|$WindowHandle|${width}x${height}|$destination"
