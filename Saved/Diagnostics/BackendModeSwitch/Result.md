# Backend mode preservation

Live Coding compilation and both module patches succeeded in the existing editor. No restart, level save or Blueprint modification was performed.

Passed in isolated temporary game worlds inside the patched editor:
- `Prophecy.Jolt.BodyComponent.CharacterRuntimeChannels` at 2026-09-11 00:59:17 UTC: actual 22-body character, all collision-channel checks plus repeated Chaos/Jolt toggles, Kinematic/HalfSim preservation, backend selection and later Sim admission.
- `Prophecy.Jolt.Character.BackendPreferenceAcrossModes` at 2026-09-11 01:11:23 UTC: actual native ownership/body/joint counts, NN source identity, mode cycles, pose/velocity preservation on existing HalfSim-to-Jolt handoff, backend changes inside bone-finalizer callbacks, a later explicit Kinematic request, pending admission cancellation and cleanup.

The second fixture retains its existing `UWorld::CleanupWorld ... missing call to EndPlay` warning. First Live Coding reinstancing emitted handled RigVM access-detector ensures, then completed successfully; Unreal remained responsive and both tests passed. This is not a warning-free build/runtime claim or a packaged-build verification.

For the user's toggle Branch, replace `Is Jolt Physical Animation Enabled` with `Is Jolt Physical Animation Selected`. True connects to Disable; false connects to Enable. The old query continues to report actual rig activity. Full Sim changes solver; Kinematic stays Kinematic; HalfSim keeps its existing Chaos controller and remembers the selected solver for later full Sim.
