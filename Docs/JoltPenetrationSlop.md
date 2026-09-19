# Jolt penetration allowance

**Set Jolt Penetration Slop** takes **Slop Cm** (default **2.0**) and returns success. **Get Jolt Penetration Slop** reads the current value in centimetres. The world context is supplied automatically in an actor Blueprint.

Call once on BeginPlay, or whenever the desired setting changes. Try **0.1** for the sword/cube overlap. Set **2.0** to restore the existing Jolt default. Zero is accepted; negative or nonfinite values fail without changing the current setting.

This is a **shared-world setting**: it affects all Jolt characters, swords and scene bodies in that world. The last successful setter wins. It can be configured before native physics initialization and survives an explicit simulation shutdown/reinitialization within the same world. It resets for a new world/PIE session.

The setting controls contact penetration allowance in the solver. It does not guarantee zero overlap, enable CCD, alter substeps, or prevent deep startup overlap. Smaller values can make contact resolution more demanding. There is no new Tick, per-body loop or per-step lookup; only setting/getting, initialization and teardown access the optional override.

Blueprint nodes live in the separate `ProphecyJoltContactSettingsLibrary`; native implementation is in the world subsystem, with no new retained native fields. No Blueprint or map is automatically edited.

Focused validation: `Prophecy.Jolt.ContactSettings.PenetrationSlop` checks default, pre-initialization configuration, native readback, live updates, invalid input, zero and reset/reinitialization.

Build history: the first attempt put reflected functions directly on the existing world subsystem. Live Coding compiled but world creation then hit the known `Ret->IsA` subsystem-CDO assertion, before the setting test ran. Reflected functions were moved to a separate Blueprint library; recovery requires a normal build and fresh editor. Do not make reflected Live Coding edits to `ProphecyJoltWorldSubsystem` again.

Installed after normal-build recovery (522.58s). Fresh editor reflection verified both nodes; `Prophecy.Jolt.ContactSettings.PenetrationSlop` passed at2026-09-18 04:55:22UTC, including native world creation and setting readback. Editor returned to `/Game/testNN`; no authored assets edited/saved or gameplay tuning changed.
