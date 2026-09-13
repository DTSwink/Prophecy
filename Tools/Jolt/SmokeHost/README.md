# Prophecy Jolt smoke host

This isolated UE 5.7 host checks Jolt fixture cooking, DLL staging and runtime
archive restoration. It does not validate packaging of the production game.

Build the main project's Editor target after changing plugin code, then build the
host's Editor target as needed. With UE5.7 `AdditionalPluginDirectories`, the
original plugin's editor module manifest can shadow modules built into the
host's Binaries directory. The main editor build is the canonical editor module
for these checks; use `Module List` to record the loaded paths. A host-only editor
build does not prove that its newly built DLL was loaded. Packaged Game targets
are monolithic and do not have this editor module collision.

The dependency import names are separate from those editor module names:
Editor and Game Development use `ProphecyJolt_5_6_Development.dll`; Game Shipping
uses `ProphecyJolt_5_6_Shipping.dll`, each with a matching `.lib` import library.
The names remain stable within each configuration for Live Coding. This prevents
UE's dependency search from selecting a Shipping DLL in the host's Binaries
directory when loading an editor module from the original plugin. Build both
dependency configurations and rebuild their UE consumers after a naming change.
The dependency manifest checks the filenames and assertion mode. Packaged Game
builds stage their selected DLL beside the executable; editor imports use the
Development dependency staged in the original plugin's Binaries directory.

The project enables the shared plugin through `../../../Plugins`. Its explicit
cook roots are `/Engine/Maps/Entry` and
`/Game/Fixture/DA_CompoundFixture.DA_CompoundFixture`, plus their required engine
dependencies. No production maps or content directories are included.
The exact fixture is an Asset Manager `SpecificAssets` entry in `DefaultGame.ini`
with `AlwaysCook`; manager-provided IDs support the existing `UDataAsset` class.
Editor ID inference also covers a fixture saved before those registry tags exist.

Run the editor commandlet `-run=ProphecyJoltCookFixture` against
`ProphecyJoltSmokeHost.uproject` to create the fixture. It refuses other project
names and refuses to overwrite an existing fixture unless `-OverwriteFixture`
is supplied. It writes only the fixed fixture package.

Launch the packaged host with `-ProphecyJoltValidateFixture -stdout` and
`-ProphecyJoltFixtureResult=<absolute, unused JSON filename>`. Create the report's
parent directory first. The runtime validator is compiled in Shipping and does
not use automation tests. It removes its initialization delegate, reports the
result and requests a normal engine shutdown.

A pass requires `PROPHECY_JOLT_FIXTURE_VALIDATION_SUCCESS` in captured output
and `success: true` in the newly created JSON report. Treat a missing marker,
missing/invalid report, failed report write or `success: false` as failure.
On UE 5.7 Windows, graceful `RequestExitWithStatus(false, status)` from engine
initialization can still yield process exit code zero; exit code alone is not
validation evidence. Existing result files are never overwritten.

Verified on 9 September 2026: both Development and Shipping BuildCookRun and
actual packaged fixture restoration passed. Raw package and runner evidence is
linked from `Docs/JoltIntegrationStatus.md`. This covers the compound fixture,
not production content or a complete skeletal rig cook.
