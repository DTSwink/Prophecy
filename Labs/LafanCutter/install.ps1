$ErrorActionPreference = 'Stop'
$cutterRoot = $PSScriptRoot
$cutterPython = 'C:\Users\singerie\Documents\Cursor\stepper\.tools\python310\pythonw.exe'
if (-not (Test-Path -LiteralPath $cutterPython)) { throw 'The Stepper Python runtime was not found.' }
$cutterDesktop = [Environment]::GetFolderPath('Desktop')
$cutterLinkPath = Join-Path $cutterDesktop 'Lafan Cutter.lnk'
$cutterShell = New-Object -ComObject WScript.Shell
$cutterLink = $cutterShell.CreateShortcut($cutterLinkPath)
$cutterLink.TargetPath = $cutterPython
$cutterLink.Arguments = '"' + (Join-Path $cutterRoot 'app.py') + '"'
$cutterLink.WorkingDirectory = $cutterRoot
$cutterLink.IconLocation = (Join-Path $cutterRoot 'icon.ico') + ',0'
$cutterLink.Description = 'Preview LAFAN motions, collect trims and save named datasets'
$cutterLink.Save()
# Match the running process identity so Windows gives it its own taskbar group.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
public static class CutterShortcutIdentity {
  [StructLayout(LayoutKind.Sequential, Pack=4)] public struct Key { public Guid fmtid; public uint pid; }
  [StructLayout(LayoutKind.Explicit, Size=24)] public struct Variant {
    [FieldOffset(0)] public ushort vt;
    [FieldOffset(8)] public IntPtr ptr;
  }
  [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface Store {
    [PreserveSig] int GetCount(out uint c);
    [PreserveSig] int GetAt(uint i, out Key k);
    [PreserveSig] int GetValue(ref Key k, out Variant v);
    [PreserveSig] int SetValue(ref Key k, ref Variant v);
    [PreserveSig] int Commit();
  }
  public static string SetAndRead(string path,string id) {
    object link=Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("00021401-0000-0000-C000-000000000046")));
    var file=(IPersistFile)link; file.Load(path,2);
    var store=(Store)link;
    var key=new Key {fmtid=new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"),pid=5};
    var value=new Variant {vt=31,ptr=Marshal.StringToCoTaskMemUni(id)};
    try { Marshal.ThrowExceptionForHR(store.SetValue(ref key,ref value)); Marshal.ThrowExceptionForHR(store.Commit()); file.Save(path,true); }
    finally { Marshal.FreeCoTaskMem(value.ptr); }
    Variant result; Marshal.ThrowExceptionForHR(store.GetValue(ref key,out result));
    string actual=Marshal.PtrToStringUni(result.ptr); Marshal.FreeCoTaskMem(result.ptr);
    Marshal.FinalReleaseComObject(link);return actual;
  }
}
'@
$cutterIdentity = [CutterShortcutIdentity]::SetAndRead($cutterLinkPath,'Prophecy.LafanCutter.Desktop.1')
if ($cutterIdentity -ne 'Prophecy.LafanCutter.Desktop.1') { throw 'Shortcut AppUserModelID did not persist.' }
[pscustomobject]@{Shortcut=$cutterLinkPath;AppUserModelID=$cutterIdentity;Icon=$cutterLink.IconLocation}
