[CmdletBinding()]
param(
    [int]$ProcessId = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not ('EddWindowEnumeration' -as [type])) {
    Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class EddWindowEnumeration
{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll")]
    static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    static extern bool GetClientRect(IntPtr hWnd, out RECT rect);

    public sealed class WindowInfo
    {
        public long Handle { get; set; }
        public int ProcessId { get; set; }
        public string Title { get; set; }
        public int ClientWidth { get; set; }
        public int ClientHeight { get; set; }
    }

    public static WindowInfo[] GetVisible(int requestedProcessId)
    {
        var windows = new List<WindowInfo>();
        EnumWindows((window, state) =>
        {
            if (!IsWindowVisible(window)) return true;
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            if (requestedProcessId != 0 && owner != requestedProcessId) return true;
            var title = new StringBuilder(1024);
            GetWindowText(window, title, title.Capacity);
            if (title.Length == 0) return true;
            RECT client;
            GetClientRect(window, out client);
            windows.Add(new WindowInfo {
                Handle = window.ToInt64(),
                ProcessId = (int)owner,
                Title = title.ToString(),
                ClientWidth = client.Right - client.Left,
                ClientHeight = client.Bottom - client.Top
            });
            return true;
        }, IntPtr.Zero);
        return windows.ToArray();
    }
}
'@
}

[EddWindowEnumeration]::GetVisible($ProcessId) |
    Sort-Object ProcessId, Handle |
    Select-Object Handle, ProcessId, Title, ClientWidth, ClientHeight
