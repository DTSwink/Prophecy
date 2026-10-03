Add-Type @"
using System; using System.Runtime.InteropServices;
public static class HotkeyProbe {
 [DllImport("user32.dll",SetLastError=true)] public static extern bool RegisterHotKey(IntPtr h,int id,uint mods,uint key);
 [DllImport("user32.dll")] public static extern bool UnregisterHotKey(IntPtr h,int id);
}
"@
foreach($mods in @(0,1,2,4,8,9)) {
 $free=[HotkeyProbe]::RegisterHotKey([IntPtr]::Zero,30291,$mods,135)
 if($free){[void][HotkeyProbe]::UnregisterHotKey([IntPtr]::Zero,30291)}
 [pscustomobject]@{Key='F24';Modifiers=$mods;Available=$free;Error=[Runtime.InteropServices.Marshal]::GetLastWin32Error()}
}
