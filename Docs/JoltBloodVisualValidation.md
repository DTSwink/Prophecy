# Blood validation — 10 September 2026

Movement is accepted by the user; this pass checks blood receivers and runtime setup. Evidence lives in `Saved/Diagnostics/BloodVisual-20260910/` and `Saved/Diagnostics/BloodVisual/`. Rendered images come from Unreal SceneCapture2D with actual RHI/material shaders, not synthesized illustrations. Test staging used an unsaved Entry world; production setup changes below are deliberate and saved.

## Fixes found by the rendered/runtime checks

- Material generation could crash when `SetMaterialUsage` compiled an injected blood function before the duplicated material refreshed its texture cache. Recompile the completed graph before requesting usages. Normal Editor build passed, and the formerly failing WorldGrid generation completed.
- With editor generation disabled, the first stain replaced the clean material with a MID which subsequent hits rejected. `TryPaintFromHit` and `DebugPaintUV` now recognize their own exact component/slot MID and validate its stored original material. Live Coding compiled successfully; four exact-bone character hits, repeated DebugPaintUV calls, unchanged MID/RT identity, and rejection of an unrelated unmapped receiver passed (`repeat-regression.json`).
- `testNN` had no placed blood manager. Sword startup spawned `A_DecalManager` with `paint manager=None` and `floor=None`. The map now contains one configured `BP_BloodPaintManager` and one `A_DecalManager`, referencing the existing Static Floor. Both spawned swords reuse it; the next PIE confirmed exactly one of each manager and valid references (`production-verified.json`). The sword cutting loop remains disconnected.
- Five preserving material pairs are saved on the placed manager and its Blueprint defaults: WorldGrid, the Megascans rock, sword, original mannequin, and the actual fighter's masked bicolor mannequin material. Editor generation is disabled for these runtime checks. These are hard cook references through the placed Blueprint; this pass does not claim a fresh packaged build.
- The paint-manager Blueprint had mask visualization enabled. Actual blood renders use `DebugShowBloodMask=0`; the black receiver in earlier diagnostic captures was the mask debug view, not lost source-material colors.

## Completed receiver evidence

| Receiver | Check and evidence |
|---|---|
| Static cube / original WorldGrid | Real complex UE hit, persistent UV paint, rendered original material. `static_jolt_painted.png`. |
| Nanite Megascans rock | Real complex UE collision-face/UV paint and original preserving material. `nanite_jolt_painted.png`. Shader loading completed before capture. |
| Moving cube and sword | Jolt ownership true; Chaos simulation off; retained UE component QueryOnly. Each moved approximately 45 cm and rotated 28.65 degrees over 120 ticks. Same MID/RT and byte-identical decoded mask pixels before/after. Equivalent attachment check passed under Chaos. `moving-bodies-jolt.json`, `moving-bodies-chaos.json`, `pixel-comparison.json`, `*_moving_*.png`. |
| Actual moving fighter | Live `BP_ProphecyManualPoseAgent_C_1.PhysicalMesh`, Jolt enabled, Chaos off and QueryOnly. Four real NiagaraWound-channel traces returned exactly head, spine_03, upperarm_l and calf_r; all four paint calls accepted with generation disabled, one state, four flushed stamps, zero unsupported hits. Body-following rendered closeups show red localized stains. Actor translated about 540 cm in 180 ticks; same MID/RT and identical decoded mask pixels after movement. Chaos physical mode passed the corresponding four hits and attachment check. `fighter-{jolt,chaos}.json`, `fighter_*_{region}_*.png`. Character placement uses the existing approximate bone-local UV resolver. |
| ISM and HISM | Actual decal-manager particle callback promotes two instances to independent painted actors; neighbor remains clean. Jolt source collider retirement/replacement, repeat no duplicate, and cleanup verified. The three-actor row images are pixel-identical to the matching Chaos baseline. |
| CPU PCG managed ISM output | Actual PCG helper, component and managed ISM resource exercised; same promotion/independence/cleanup checks. This does not claim PCG graph execution or GPU procedural ISM coverage. `PCG_CPU_jolt_painted.png`, `PCG_CPU_chaos_painted.png`. |
| Floor decal grid | Actual downward floor hit accepted 52 cells with both backends. Saved material uses default color texture and opaque grid cells; debug outlines come from the existing decal-manager Tick. Captures disable fixture debug drawing and use consistent exposure. This is the existing block-shaped grid appearance, not textured spatter. |

Instance reports: `Saved/Diagnostics/BloodVisual/instances-{jolt,chaos}.json`. Jolt cleanup retired nine remaining native handles. The existing Blueprint callback avoids another promotion on a repeated hit, but does not queue another texture stamp on a promoted StaticMeshActor; this baseline behavior was preserved.

## Remaining / limits

- The independent procedural-stain API accepted a triangle. Its opaque unlit triangle renders almost black in this isolated capture; this has not been accepted as a successful blood appearance. Current inspected gameplay routing does not call this renderer. Do not confuse it with attached mesh painting.
- No new verification of live Niagara simulation/export, GPU collision, GPU PCG, the separate historical grass world mask, or packaged cooking is claimed by these receiver tests. Instance tests invoke the real Blueprint particle callback, not a running emitter.
- Hit-event parity is a separate follow-up. Existing contact/depenetration fixtures do not prove `OnComponentHit`/`OnActorHit`; the native Jolt world currently has no contact-event delivery bridge.

The original `testNN` map and paint-manager Blueprint are backed up under `Saved/Diagnostics/BloodVisual-20260910/Backups/` before these setup changes.
