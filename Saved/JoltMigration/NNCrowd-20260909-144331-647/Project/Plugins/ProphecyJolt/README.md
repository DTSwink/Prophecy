# Prophecy Jolt foundation

This plugin is under construction. Loading its runtime module registers pinned Jolt types and allocators; it does not replace any character, prop or world physics.

Run the dependency build explicitly from the project root before UBT:

```powershell
powershell -File Tools/Jolt/BuildJolt.ps1 -Configuration Development
```

The script verifies the exact upstream SHA and pristine checkout, then prepares a shared library, headers, license and manifest under `Intermediate/JoltMigration/Install`. Shipping uses a separate `-Configuration Shipping` dependency build. DebugGame uses the Development dependency and release CRT; debug CRT is explicitly unsupported by this initial recipe.

Initial configuration: UE 5.7.4, Win64, VS2022 toolset 14.44, SDK 10.0.22621.0, /MD, precise floating point, double world positions, SSE2 baseline, Jolt object streams, C++ exceptions enabled, RTTI disabled, no GPU compute/debug renderer/internal profiler. UE 5.7 forces exceptions for Editor, so this module and dependency use that setting consistently in game builds too. Development enables Jolt assertions; Shipping does not. Cross-platform determinism is not enabled. These are recorded foundation settings, not accepted performance tuning; exception support does not make Jolt fatal allocation/assert failures recoverable.

Jolt uses `ProphecyJolt_5_6_Development.dll` and `ProphecyJolt_5_6_Shipping.dll`, with matching `.lib` import libraries. Each name stays stable within its configuration so Live Coding patches and consumers share its process globals. Distinct names prevent an editor import from resolving to an assertion-disabled Shipping DLL in a shared host directory. The schema 2 dependency manifest records both filenames, and UBT checks them and the assertion setting against its selected configuration. Rebuild both dependencies and their UE consumers when adopting this naming contract; old artifacts are left in place and are no longer referenced by rebuilt consumers. Raw Jolt types stay private to the runtime module. Runtime ABI verification rejects feature mismatches. Do not rebuild/replace a dependency DLL while the editor or a game using it is running.

The read-only inventory commandlet and conversion automation are separate from production gameplay. Their results must be recorded before claiming foundation completion. The migration plan and capability ledger in `Docs` remain authoritative for the work still required.

`UProphecyJoltWorldSubsystem` is available only in Game/PIE worlds and allocates
its native simulation only when explicitly initialized. It has no automatic
tick. Its current C++ API covers small sphere/box fixtures, explicit steps,
generation-safe body handles, weak object identity, point impulses and
diagnostics. These fixture layers/settings do not define production collision
channels or stepping policy.

After building the main Editor target, run `Tools/Jolt/RunFoundationTests.ps1`.
The 14 tests cover units and signed rotations, primitives and constraints,
capsule dimensions/axis correction, offset COM and bone/body frames, complete
compound shape archives, world teardown and stale handles. Reports are created
under `Saved/JoltMigration`; the runner checks report results as well as process
exit and logs the loaded module/library paths. `-Filter Prophecy.Jolt.WorldSubsystem`
selects the three world tests when diagnosing that slice.

The isolated `Tools/Jolt/SmokeHost` project provides the early cook/package gate.
Prepare its editor executable and fixed compound asset as described in its
README, then use `Tools/Jolt/BuildSmokePackage.ps1 -Configuration Development`
or `Shipping`. Pass its returned direct executable to
`Tools/Jolt/RunPackagedFixture.ps1 -Executable <absolute path>`. The packaged
validator requires a fresh positive JSON result and stdout marker; OS exit code
alone cannot establish success. This verifies the plugin fixture, not packaging
or behavior of the full game.

The separate inventory commandlets are `ProphecyJoltInventory` (declared asset
closure) and `ProphecyJoltComponentAudit` (manual-agent CDO/SCS templates). They
write new JSON reports and do not save assets. Unreal PostLoad can still report
existing Blueprint errors; extraction status and process status must both be
recorded. Current evidence and limitations are in `Docs/JoltIntegrationStatus.md`.
