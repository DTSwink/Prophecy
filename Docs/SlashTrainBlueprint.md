# Viewer train in the pose Blueprint

`BP_ProphecyManualPoseAgent` → `codex slash train` replays the 30 requests from **seed2026092223**, complete variant, predictive pin×5 refresh2 step184064. The seed is the user's screenshot selection, not the2211 default in the supplied URL.

The existing caller remains responsible for possessed-agent filtering and starting after tick30. The function uses gameplay Blueprint nodes and four variables in **Codex Slash Train**. A development-only starting-pose node loads the initial two-frame fixture once; there is no native playback scheduler or loading of future reference poses.

## Progression and targets

- `Codex Slash Train Index` starts at0 and advances only after a successful `Trigger NN Attack`. While `Get NN Attack State` reports active, the function does nothing. `On NN Attack Ended` calls it immediately on actual completion, guarded by possession and Index>0, avoiding an intervening locomotion prediction. The user explicitly chose local completion rather than recorded viewer frame deadlines.
- First request selects **Predictive Pin x5 Refresh2 (184064)** and maps the source's root-local target through the current agent mesh carrier. Subsequent requests use the source target relative to its initial pelvis and map it through **Current World Transform** from `Get Authored Body World Target(pelvis)`. This is the training generator's `mapped_target` rule, including pelvis rotation, using the published pose rather than physical lag or display interpolation.
- The target is sampled once into `Codex Slash Train World Target` at entry, then held. The arrays `Codex Slash Train Attacks` and `Codex Slash Train Local Targets` contain all30 requests in source order. Target0 is carrier-local; the others are pelvis-local. Local training metres convert to Unreal centimetres as `(X,-Y,Z)*100`.
- These are full attacks with no victim. There is no Stop/retrigger of an active attack, timer, forced Hit/Armed, pose reset between attacks, locomotion-input modification, or intentional wait between requests.
- Index30 stops further work before querying attack state or targets. Reset Index to0 while idle to replay. A failed checkpoint selection, pelvis read or attack trigger halts the train and prints an error once rather than skipping/retrying a request.

## Scope and known comparison differences

For the authorized1:1 investigation, first entry calls `Set Slash Train Starting Pose`, matching both history frames and the viewer's stationary reference frame for30 full attacks. The reference-frame override expires afterward. `Set Trim Attack` with allzero values runs at function entry, overriding ordinary per-tick trim configuration only while this comparison function is called. The ordinary trim setter is preserved. The user's kinematic mode, attack-start pelvis-inertia disable and kick-checkpoint override disable remain; kicks therefore use184064 too. Explicit forearm/calf roll controls default enabled and are not disabled in the Blueprint. New attack entry uses the existing cancellation rules for recovery/end handlers. Cancellation by another system also advances the chain; this is not a prerecorded playback that conceals local behavior. See [comparison conditions and measured residuals](SlashTrainParity.md).

## Provenance and verification

Source: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/latest_predictive_pin_x5_20260924_refresh2/seed_2026092223/complete`.

`Tools/NN/ExtractSlashTrainBlueprintData.py` verifies every original NPZ SHA256 against the manifest and checks the target transplantation against all30 recorded conditioning pelvis poses. Maximum reconstructed target error **0.00004783cm**. Extracted requests/provenance: `Tools/NN/Fixtures/SlashTrain2026092223.json`. It reads training files without changing them.

`Prophecy.Editor.BuildSlashTrain` is an explicit editor-only, undoable graph builder. It refuses Play, nonempty functions and conflicting variables; never runs automatically or saves an asset. `SeedSlashTrain` and `ChainSlashTrainAtEnd` add the comparison initialization/zero trims and the guarded end-event call. These helpers preserve existing user wiring and refuse unsafe replacement. Readback verifies all30 attack names and vector defaults (maximum copy error4.98e-13cm). Latest Blueprint compile status3; editor changes remain unsaved. The complete449-step runtime comparison and limitations are recorded in [SlashTrainParity](SlashTrainParity.md).
