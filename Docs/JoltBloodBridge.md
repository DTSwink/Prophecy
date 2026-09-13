# Functional Jolt blood bridge

**9 September 2026.** Source/manifest-backed implementation order for the user's current priority: physical animation, solid bodies/joints, and persistent blood on meshes, instanced objects and characters, with useful performance. Exact Chaos/Jolt trajectory equivalence is not this feature's acceptance criterion. Other retained project functionality remains in scope. This note changes no source, assets or configuration and launches no build or UE process.

## Reuse the current paint and presentation paths

| Existing entry point | Retained contract |
|---|---|
| [TryPaintFromHit](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:246>) | Resolve component/material/UV, obtain the component's RT/MID, queue the world-sized stamp. |
| [ResolveMaterialSlot / FindPaintUV](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:564>) | Static hits need the source component and valid collision-face mapping or an explicit resolved UV/material adapter. |
| [FindSkinnedMeshPaintUV](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:667>) | Use Hit.BoneName, the currently published bone pose and cached reference triangles to find approximate persistent character UVs. This is not exact skinned-triangle collision. |
| [FlushPendingBloodStamps](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:346>) | Retain RT batching and explicit counters. Current native defaults are 128 active RTs, 128 stamps/frame and 64 stamps/RT/frame; inspect queue growth under load. |
| [AddBloodHit / AddBloodParticleData](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodStainRenderer.cpp:70>) | Collision-free procedural stain presentation. Native particle input uses Position + SimulationPositionOffset, Velocity as normal and Size-derived radius. These world-space triangles do not attach to moving limbs. |
| [AddFloorHitToGrid](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyFoliageDecalGridComponent.cpp:194>) | Blocking-hit point/normal feeds the existing ground/foliage grid. |

Blood placement itself does not require a solved NormalImpulse. The first bridge needs valid receiver identity and surface placement. Sword damage/impact semantics are separate retained work.

## Verified producer wiring and exact trace boundary

Evidence: [AssetManifest.json](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Inventory-20260909-051135/AssetManifest.json>), schema 1, UE 5.7.4, exporter errors zero. These are connected graph records from that export, not a claim that the current placed actor has been exercised. Earlier inventory context is in [JoltAssetInventoryFindings.md](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/JoltAssetInventoryFindings.md:116>).

In `/Game/_mygame/blood2/A_DecalManager.A_DecalManager`:

1. `EventGraph.K2Node_Event_3`, **ReceiveParticleData**, GUID `3CAB16E54063F4AB688CC4B67A27B3CB`, executes `K2Node_CallFunction_33`, **NewFunction**, GUID `058326F0451F4C3FAC30329954FD9C74`.
2. `NewFunction.K2Node_MacroInstance_0`, **For Each Loop**, GUID `A379BFD14F0DE69438F5EC86E026D1DA`, executes **LineTraceSingle**, `K2Node_CallFunction_3`, GUID **`A06F947D429D70F945A024B2BC393B2C`**.
3. Its connected endpoints are **Particle.Position + Particle.Velocity** and **Particle.Position − Particle.Velocity**. `bTraceComplex=true`, `bIgnoreSelf=true`. `K2Node_Select_0`, GUID `399BD16143A98E2E73A0589E03A6DFC0`, selects **TraceTypeQuery4 when Size==1**, otherwise **TraceTypeQuery1**. Preserve these inputs and resolve trace enums through UE's channel mapping; do not infer their meaning from Niagara property names.

**This `NewFunction.K2Node_CallFunction_3` is the exact first Blueprint replacement point for a project blood-query wrapper.** Keep its start/end/channel/complex/ignore behavior and return the nearest eligible result with complete UE-facing identity. The wrapper may combine retained UE queries for static/instanced receivers with Jolt queries for migrated bodies, but must avoid duplicate representations of the same receiver and choose the nearest compatible hit. Preserve the downstream branches initially.

The alternative is synchronized **query-only UE proxies** for Jolt-driven bodies, leaving this LineTraceSingle intact. Proxies must follow the completed Jolt pose without running a second dynamic Chaos simulation. They also offer a path for stock CPU Niagara queries. Choose one authoritative query representation per migrated receiver; the wrapper alone does not make upstream CPU Niagara collision see Jolt bodies.

There is also a connected character/mesh paint call in `/Game/_mygame/sword/A_Sword.A_Sword:handle cuts f.K2Node_CallFunction_36`, GUID **`D2D55AA246037281D7AE1CAF2118E6AA`**, reached from `K2Node_IfThenElse_10.then`. Preserve its `TryPaintFromHit` contract when adapting sword queries/hits. The decal manager's separate `TryPaintFromHit` debug copy `K2Node_CallFunction_31`, GUID `B0A1C99E48C703C38E4B53ABAD6E652E`, has no input Exec connection and is not evidence of an active general-mesh paint route.

## Preserve existing instance-to-actor promotion first

The native manager does **not** have an independent receiver-instance mask. [MakeStateKey](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:502>) keys only component UniqueID + material slot; [EnsurePaintState](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:1325>) installs one component MID/RT. Directly accepting an ISM as its UStaticMeshComponent base does not give each instance independent paint. The journal explicitly lists unique ISM masks as remaining work: [ProjectJournal.md](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/ProjectJournal.md:239>).

However, the exported decal manager already has a connected promotion workaround. For a hit whose actor differs from its `floor` variable, the graph attempts the following:

| `NewFunction` node | GUID | Connected behavior |
|---|---|---|
| `K2Node_DynamicCast_0` | `2B361258420BEBE314E6EBBDEAFC52C8` | Cast hit component to ISM; successful Exec enters promotion. |
| `K2Node_CallFunction_24` | `A23E3DDB4751EC7B4E45DF9720CBB039` | Get the original **HitItem** instance transform in world space. |
| `K2Node_SpawnActorFromClass_0` | `BC39FE1A4BC51AB007B56D834ECF890A` | Spawn StaticMeshActor at that transform, AlwaysSpawn. |
| `K2Node_CallFunction_18` | `EBE341E94CFE6657B2DB1FBF712424DB` | Copy the source ISM mesh to the actor's static mesh component. The actor is made Movable during assignment, then Static. |
| `K2Node_CallArrayFunction_1` | `CF849C7B41D955A0E2DDD7A3A0F369CD` | Store the actor in `SM impostors`. |
| `K2Node_CallFunction_25` | `F387C70E43AD9B478812CDB32508D1D1` | Update the original HitItem to **scale (0,0,0)**, preserving location/rotation; world-space, render-dirty and teleport inputs are true. |
| `K2Node_CallFunction_1` | `8CB8208D4F306D26A97EB7B390843A31` | Reconstruct the original hit, replacing actor/component with the promoted receiver while preserving point, normals, face index, item and other fields. |
| `K2Node_CallFunction_5` | `1349876449570DB375D5E681B54B0214` | Paint the reconstructed hit through the existing manager. |

Thus instanced objects have an existing **individual painted actor** path. Efficient in-place per-instance masks remain absent. An atlas is not required to preserve the present path and is not the first implementation here.

The Jolt bridge must preserve this promotion transaction:

- Retain **source ISM/HISM component + Hit.Item + generation/lifetime** until promotion finishes. A Jolt subshape identifier is not a UE instance index. Check stale/remapped indices after instance removal, PCG regeneration or streaming.
- Preserve the selected instance's world transform and collision/receiver identity. On the scale-zero update, retire/invalidate its original Jolt collision/query entry; do not attempt to cook a zero-scale solid or leave an invisible duplicate collider.
- Register the promoted actor as the replacement Jolt static body and/or authoritative query receiver, according to the selected world ownership path. Perform source retirement and replacement registration between physics steps.
- Preserve source face correspondence for the same mesh, and ensure `Hit.Location`, `ImpactPoint`, actor and component all describe the promoted receiver. UE's [FindCollisionUV](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/GameplayStatics.cpp:1449>) transforms **Hit.Location by the hit component transform**, then uses its BodySetup and FaceIndex. An arbitrary Jolt face/subshape index cannot be copied into FaceIndex.
- Validate materials on the promoted receiver. The observed Blueprint copies the mesh; it does not establish copying all source component material overrides. Use the existing blood-enabled material mappings and verify overridden/material-slot cases explicitly. Runtime painting cannot rely on editor-only material generation. See [material eligibility](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:507>) and [material/RT setup](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:1325>).
- Preserve promotion ownership/cleanup and repeated-hit identity: subsequent hits must reach the same promoted receiver, not repeatedly spawn copies. Check original-instance updates, promoted-body removal and stain cleanup together.

The failed ISM cast currently routes to `AddFloorHitToFoliageDecalGrid`, GUID `B536F57A421B54C367F414A78227FBAD`. Do not infer that this branch calls the disconnected general-mesh paint node. Character staining has the separate sword path above; deliberate additions to decal-manager routing should be explicit functional work.

## Minimal implementation sequence and acceptance

1. **Publish physical presentation, then translate hits on the game thread.** Carry generation-checked source component, actor, bone name, instance item, point/normal, source face/material or resolved UV. Keep Jolt workers free of UObject access, paint operations and material creation. For character hits, publish Jolt-driven bone transforms before calling the existing skinned fallback. Delayed exports need a retained bone-local point or collision-time transform so the stain stays on the contacted region.
2. **Prove static mesh and moving-character paint with the existing manager.** Use blood-enabled materials already prepared for the cook. For static Jolt hits, map retained source triangles to UE collision faces, or add an explicit resolved-UV/material entry point sharing the existing stamp/RT code. Do not fabricate a FaceIndex. Retain the [48-pixel skinned stamp cap](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyBloodTexturePaintManager.cpp:1477>).
3. **Adapt the exact decal-manager trace boundary and sword hit producer.** Preserve the verified graph flow and channel selection. Prove the chosen Jolt query wrapper or synchronized query proxies can identify a moving character and return its BoneName. CPU/GPU emitter targets are known, but their collision/export modules still need bounded inspection; see [inventory](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/JoltAssetInventoryFindings.md:116>). The current decal callback's SimulationPositionOffset pin is unconnected, whereas the native procedural renderer adds it; retain this as an observed baseline distinction rather than silently rewriting particle semantics.
4. **Preserve and exercise ISM promotion.** Two instances sharing a mesh/material must stain independently through two correct promoted receivers, with untouched neighbors, one active collider per promoted object, no re-promotion on repeated hits, and valid cleanup. Include HISM/PCG-generated receivers and an instance transform with rotation/positive scale.
5. **Measure the complete functional path.** Record query time, promotion count/time, active RTs, pending stamps, flush cost and frame time with characters moving and blood arriving. Reuse [existing flush budgets/counters](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Public/ProphecyBloodTexturePaintManager.h:207>); don't claim fast behavior from physics-only timing. If actor promotion is a measured bottleneck, evaluate an instance-mask optimization after this functioning baseline is preserved.

Acceptance is visible persistent placement on static meshes, the selected instanced objects and moving characters, together with solid collision/joints and measured frame cost. Packaged CPU-readable UV/skinning data, generated material availability, Nanite collision-source mapping and actual Niagara producer visibility must be checked in that vertical slice. No Chaos replay equivalence gate is substituted for those functional checks.
