param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CatalogFolderWindow {
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int x, y; }
    [StructLayout(LayoutKind.Sequential)] struct MSG {
        public IntPtr hwnd; public uint message; public UIntPtr wParam;
        public IntPtr lParam; public uint time; public POINT pt; public uint lPrivate;
    }
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, IntPtr pid);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern bool PeekMessage(out MSG msg, IntPtr hwnd, uint min, uint max, uint remove);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint from, uint to, bool attach);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr hwnd, int command);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
    public static bool Activate(IntPtr hwnd) {
        ShowWindowAsync(hwnd, IsIconic(hwnd) ? 9 : 5);
        SetForegroundWindow(hwnd);
        if (GetForegroundWindow() == hwnd) return true;
        // The click belongs to the browser, while this worker has no input queue.
        // Connect the queues only for this user-requested activation, then detach.
        MSG msg; PeekMessage(out msg, IntPtr.Zero, 0, 0, 0);
        uint current = GetCurrentThreadId();
        uint foreground = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero);
        uint target = GetWindowThreadProcessId(hwnd, IntPtr.Zero);
        bool attachedForeground = false, attachedTarget = false;
        try {
            if (foreground != 0 && foreground != current)
                attachedForeground = AttachThreadInput(current, foreground, true);
            if (target != 0 && target != current && target != foreground)
                attachedTarget = AttachThreadInput(current, target, true);
            BringWindowToTop(hwnd);
            SetForegroundWindow(hwnd);
        } finally {
            if (attachedTarget) AttachThreadInput(current, target, false);
            if (attachedForeground) AttachThreadInput(current, foreground, false);
        }
        return GetForegroundWindow() == hwnd;
    }
}
'@
$folderPath = [IO.Path]::GetFullPath($Folder)
if (-not [IO.Directory]::Exists($folderPath)) { throw 'Folder no longer exists.' }
$shell = New-Object -ComObject Shell.Application
function Find-ProjectWindow {
    foreach ($window in $shell.Windows()) {
        try {
            if ([IO.Path]::GetFileName($window.FullName) -ine 'explorer.exe') { continue }
            $shownPath = [IO.Path]::GetFullPath($window.Document.Folder.Self.Path).TrimEnd('\')
            if ($shownPath -ieq $folderPath.TrimEnd('\')) { return [long]$window.HWND }
        } catch { } # A closing/unrelated shell tab is not the requested folder.
    }
    return 0
}
$before = [CatalogFolderWindow]::GetForegroundWindow().ToInt64()
$windowHandle = Find-ProjectWindow
$reused = $windowHandle -ne 0
if (-not $reused) {
    $launch = [Diagnostics.ProcessStartInfo]::new()
    $launch.FileName = Join-Path $env:WINDIR 'explorer.exe'
    $launch.Arguments = '"' + $folderPath + '"'
    $launch.UseShellExecute = $true
    $launch.WindowStyle = [Diagnostics.ProcessWindowStyle]::Normal
    [void][Diagnostics.Process]::Start($launch)
}
$deadline = [Diagnostics.Stopwatch]::StartNew()
while (-not $windowHandle -and $deadline.ElapsedMilliseconds -lt 7000) {
    Start-Sleep -Milliseconds 100
    $windowHandle = Find-ProjectWindow
}
if (-not $windowHandle) { throw 'Explorer did not display the requested folder.' }
$active = [CatalogFolderWindow]::Activate([IntPtr]$windowHandle)
# Give an asynchronous restore its next message, then check actual foreground.
if (-not $active) {
    Start-Sleep -Milliseconds 100
    $active = [CatalogFolderWindow]::Activate([IntPtr]$windowHandle)
}
@{opened=$true; foreground=$active; hwnd=$windowHandle; reused=$reused;
  path=$folderPath; foreground_before=$before;
  foreground_after=[CatalogFolderWindow]::GetForegroundWindow().ToInt64()} | ConvertTo-Json -Compress
