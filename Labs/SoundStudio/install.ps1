param([string]$Python = 'C:\Users\singerie\Documents\Cursor\stepper\.tools\python310\python.exe')
$ErrorActionPreference = 'Stop'
$studioRoot = $PSScriptRoot
$studioProject = Split-Path (Split-Path $studioRoot -Parent) -Parent
$studioEnvironment = Join-Path $studioProject 'Saved\SoundStudio\env'
$studioPython = Join-Path $studioEnvironment 'Scripts\python.exe'
$studioPythonw = Join-Path $studioEnvironment 'Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $studioPython)) {
    & $Python -m venv $studioEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the dedicated Sound Studio Python environment.' }
}
& $studioPython -m pip install -r (Join-Path $studioRoot 'requirements.txt') --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Sound Studio dependency installation failed.' }
$studioFFmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
$studioFilterList = & $studioFFmpeg -hide_banner -filters 2>&1 | Out-String
foreach ($studioFilter in @('rubberband', 'afftdn', 'equalizer', 'aresample')) {
    if (-not $studioFilterList.Contains($studioFilter)) { throw "FFmpeg is missing the required $studioFilter filter." }
}
$studioConfig = @{ffmpeg=$studioFFmpeg; python=$studioPython; pythonw=$studioPythonw} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $studioRoot 'runtime.json'), $studioConfig, [Text.UTF8Encoding]::new($false))
& $studioPython (Join-Path $studioRoot 'create_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Sound Studio icon generation failed.' }
$studioDesktop = [Environment]::GetFolderPath('Desktop')
$studioLinkPath = Join-Path $studioDesktop 'Prophecy Sound Studio.lnk'
$studioShell = New-Object -ComObject WScript.Shell
$studioLink = $studioShell.CreateShortcut($studioLinkPath)
$studioLink.TargetPath = $studioPythonw
$studioLink.Arguments = '"' + (Join-Path $studioRoot 'app.py') + '"'
$studioLink.WorkingDirectory = $studioRoot
$studioLink.IconLocation = (Join-Path $studioRoot 'icon.ico') + ',0'
$studioLink.Description = 'Local WAV studio: pitch, EQ, trim, fades, reverb and polish'
$studioLink.Save()
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
public static class SoundStudioShortcutIdentity {
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
$studioIdentity = [SoundStudioShortcutIdentity]::SetAndRead($studioLinkPath,'Prophecy.SoundStudio.Desktop.1')
if ($studioIdentity -ne 'Prophecy.SoundStudio.Desktop.1') { throw 'Shortcut AppUserModelID did not persist.' }
[pscustomobject]@{Shortcut=$studioLinkPath; AppUserModelID=$studioIdentity; Icon=$studioLink.IconLocation; Runtime=$studioPythonw}
