# Editor crash, 2026-09-11 04:55 local

## Confirmed evidence

- UE 5.7.4 editor process had been running for 9,422 seconds. Last PIE session ended at 04:52:23, before the 04:55:21 crash.
- Minidump exception: `0xc0000005`, read of address zero, thread 23636, instruction address `0x7ffa25b79769` in the real Windows `C:\Windows\System32\dxgi.dll` (base `0x7ffa25b00000`, RVA `0x79769`, file version `10.0.19041.5794`).
- Stack: DXGI -> `FD3D12Viewport::Init` -> Slate viewport creation -> `SWindow::ShowWindow` -> `FSlateNotificationManager::FRegionalNotificationList::Arrange` -> editor Slate tick. Local UE source at `WindowsD3D12Viewport.cpp:139` is the `CreateSwapChainForHwnd` call.
- The earlier 01:57 crash in `Saved/Diagnostics/CollisionChannels/CrashBackup-20260911-0157/Editor-crash.log` has the same fault address and notification-window stack. It preceded the mode-preserving backend change.
- No Jolt or Prophecy physics function appears on the crashing stack. This does not prove that earlier memory corruption is impossible; the evidence establishes the immediate failure location only.
- RHI: D3D12, RTX 4060 Laptop GPU, NVIDIA driver 566.14 dated 2024-11-06. Machine also has Intel UHD Graphics with driver 32.0.101.7088 dated 2026-06-17.
- Available physical memory recorded at crash: 375,197,696 bytes (about 358 MiB). Approximately 19 GiB virtual memory remained available; crash metadata explicitly says this was not an OOM failure. Low physical memory is context, not a proven cause.
- No matching display-reset/WHEA/resource-exhaustion event was returned from the System log query for 04:50–05:00. The dump module scan did not find the common RTSS/Nahimic/NVIDIA-capture/Discord hook names; the modules named Overlay are Unreal's own plugin DLLs. This does not establish that every possible hook is absent.

## Current conclusion and next diagnostic

This is a recurrent DXGI access violation while creating an editor notification window. The driver-versus-engine root cause is unresolved, and no crash fix has been applied. Do not label this a GPU timeout/device-removed crash: the observed exception is a CPU null read in DXGI.

A fresh normal Editor build is needed to retain the recent Live Coding changes when restarting. For a controlled reproduction, retain DX12 and launch once with `-d3ddebug`; inspect the debug-layer output around notification window creation. Review the graphics-driver installation before changing project rendering or physics behavior. Epic recommends separate debug runs rather than combining `-d3ddebug` with `-gpucrashdebugging`: [Epic debugging guidance](https://dev.epicgames.com/documentation/unreal-engine/how-to-fix-a-gpu-driver-crash-when-using-unreal-engine?application_version=5.3). This guidance supplies diagnostic tools, not a confirmed diagnosis for this access violation.

## Blueprint recovery

Both versions are preserved in this directory. On the user's subsequent reopen request, the newest 04:53 autosave was restored over Content, following their earlier preference to recover newer autosaves:
- `BP_ProphecyManualPoseAgent-saved.uasset`: Content version, 01:33:20 local, 904,909 bytes.
- `BP_ProphecyManualPoseAgent-0453-autosave.uasset`: newest autosave, 04:53:22 local, 950,979 bytes.

Original dump/log/context remain under `Saved/Crashes/UECC-Windows-5843FF024B103EDA671B6DB337EE3F28_0002/`.

## Two skeletons and bone queries

The editor has both inherited Mesh and PhysicalMesh assets assigned (read-only inspection found 90 socket/bone names on each placed component before Play). Manual-agent manager initialization empties and hides inherited Mesh. PhysicalMesh is the live skeleton. When `bShowKinematicDebugMesh` is enabled, the manager creates a separate `UPoseableMeshComponent` containing the interpolated NN reference pose; it has no collision and does not simulate. The runtime second skeleton is that reference visualization. Query PhysicalMesh for the actual character's bone/socket names. No mesh behavior or user asset was changed during this investigation.
