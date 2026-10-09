# Dynamic compiler workers

Installed October 9, 2026 for this UE 5.7 installation. Normal builds and Live
Coding using UBT's local UBA executor automatically refresh their worker ceiling
every **500 ms**, including while a build is already running. The editor does
not need to restart for the build-tool change.

The ceiling is the smaller of the logical CPU count and the currently available
memory budget. The normal budget remains **1.5 GiB per worker**, using the smaller
of physical RAM and commit headroom, with a minimum of one worker for progress.
This is deliberately conservative: memory already used by compiler processes
is not added back to the available budget. It cannot guarantee no paging/OOM if
one job alone exceeds the available memory.

When other applications release RAM, additional queued jobs can start immediately;
when RAM tightens, already-running jobs finish and fewer new jobs are admitted.
The adapter never cancels a compiler to change the ceiling. It creates no game
tick or editor background monitor. Its timer is stopped and drained before the
native scheduler is destroyed.

This fixes the previous `MaxParallelActions=0` behavior that sampled RAM only
at startup. That startup value remains safe for fallback executors; the UBA
adapter intentionally replaces that stale cap with its own live calculation.
Old journal worker-count instructions and explicit `-AllCores` are unnecessary.
`[Dynamic RAM] Worker ceiling N/12` in the build output reports actual changes.

## Installation and recovery

Run `Tools/ConfigureBuildWorkers.ps1` once after restoring this project or
reinstalling/verifying Unreal. It is already installed on this laptop. Ordinary
editor, Live Coding and command-line UBT builds then use it without a wrapper.
No editor launcher is added.

The setup enables local UBA in `Saved/UnrealBuildTool/BuildConfiguration.xml`.
It patches three hooks in UE's `EpicGames.UBA/Impl/SchedulerImpl.cs`, copies the
project-owned `Tools/Build/DynamicMemoryScheduler.cs`, builds **only** the small
`EpicGames.UBA` C# library, and installs that DLL beside UnrealBuildTool.
Game modules, Blueprints and the editor executable are not rebuilt. Hash checks
make re-running setup a no-op when the installation matches. UE versions other
than 5.7 are rejected for review rather than blindly patched.

Original engine source/DLL backups and an installation manifest are under
`Saved/BuildTools/DynamicWorkers`. The original project XML is preserved beside
it as `BuildConfiguration.xml.before-dynamic-workers`. Roll back while no build
is running by restoring those original source/DLL/XML files and removing the
added engine `Impl/DynamicMemoryScheduler.cs` and installation manifest. Engine
verification/reinstallation can also replace the patched tool; re-run setup.

Optional process-local overrides (not needed for normal use):
`PROPHECY_BUILD_MAX_WORKERS` imposes a CPU ceiling;
`PROPHECY_BUILD_MEMORY_PER_ACTION_MB` changes the budget (256–16384 MiB).
Existing command-line `MaxParallelActions` sets the initial/fallback cap, not the
live adapter's ceiling. No overrides are set persistently on this machine.

## Verification

The actual UBT Execute mode successfully compiled three isolated trivial C++
objects through local UBA; no game code was compiled. A separate six-job test
used bounded real memory pressure and a process-local 1 GiB budget (timed jobs
use very little memory): the same scheduler increased from one worker to two
after memory was released, fell back to one under renewed pressure, then rose
to two again (1→2→1→2), with overlapping jobs and all six completing. UBT had
initially selected just one worker, confirming that its old startup cap was
actually overcome. No restart was involved.
The test script is `Tools/Build/TestDynamicWorkers.py`; it refuses unsuitable
RAM conditions rather than forcing large allocations. Production uses 1.5 GiB.
Receipts, including abandoned native-watchdog probes, are in
`Saved/Diagnostics/DynamicBuildWorkers`.

The initial native-watchdog-only approach did **not** demonstrate the required
RAM response in this installed build. It was replaced by the explicit Windows
physical/commit-memory sampler; no reliance on the native watchdog is claimed.
UBA configuration background: [Epic's build configuration reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/build-configuration-for-unreal-engine).
