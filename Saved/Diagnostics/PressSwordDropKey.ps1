Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class SwordKeyInput {
 public delegate bool EnumProc(IntPtr h, IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
'@
$script:swordGameWindow = [IntPtr]::Zero
$script:swordEditorIds = @(Get-Process UnrealEditor | ForEach-Object Id)
[SwordKeyInput]::EnumWindows({param($h,$p)
 $title=[System.Text.StringBuilder]::new(512)
 [void][SwordKeyInput]::GetWindowText($h,$title,512)
 [uint32]$ownerId=0
 [void][SwordKeyInput]::GetWindowThreadProcessId($h,[ref]$ownerId)
 if ([SwordKeyInput]::IsWindowVisible($h) -and $ownerId -in $script:swordEditorIds -and $title.ToString() -like '*GameAnimationSample3 Preview*') {
   $script:swordGameWindow=$h
   Write-Host ('Game window: '+$title.ToString())
 }
 return $true
},[IntPtr]::Zero) | Out-Null
if ($script:swordGameWindow -eq [IntPtr]::Zero) {throw 'No game preview window; no key sent'}
[void][SwordKeyInput]::SetForegroundWindow($script:swordGameWindow)
Start-Sleep -Milliseconds 200
if ([SwordKeyInput]::GetForegroundWindow() -ne $script:swordGameWindow) {throw 'Game not foreground; no key sent'}
[SwordKeyInput]::keybd_event(0xA1,0x36,0,[UIntPtr]::Zero)
Start-Sleep -Milliseconds 80
[SwordKeyInput]::keybd_event(0xA1,0x36,2,[UIntPtr]::Zero)
Write-Host 'Sent Right Shift press/release to game preview'
