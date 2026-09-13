# Jolt asset inventory findings

**The export substantially narrows the compatibility inventory, but does not establish the effective gameplay baseline.** In the exported Blueprint graphs, no connected `NormalImpulse` consumer or `RetrieveVelAngVel` call was found. Current boat controls include additional velocity damping/clamping beyond the earlier journal shorthand. Two authored 22-body/21-constraint agent rigs contain soft angular limits and Chaos-specific settings whose effective runtime use still needs verification.

This is a read-only analysis of [AssetManifest.json](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Inventory-20260909-051135/AssetManifest.json>) on 9 September 2026: **186,943,460 bytes**, SHA-256 **`ee378bce8f54d2371c379c876b726beda2569f07ad86059e3f3cf51ff3ffa20f`**, schema 1, UE 5.7.4 CL 51494982. It contains **109 Blueprints, 27 Physics Assets, seven Niagara systems and 4,080 packages**. The exporter reports `successWithinDeclaredScope=true`, `errors=[]`, and `assetsSavedOrModifiedByExporter=false`.

**The overall commandlet run failed despite the completed manifest.** [Unreal.log:1138](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Inventory-20260909-051135/Unreal.log:1138>) records an existing handled ensure in `/Game/_mygame/NewFunctionLibrary`, function `Ang Spring`: a WorldContext entry pin already exists. [Unreal.log:1763](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Inventory-20260909-051135/Unreal.log:1763>) records the existing A_Sword `get depth of location` call being pruned because its Exec pin is unconnected. These are source-asset/load findings, **not Jolt migration regressions**. No asset was saved by the exporter or by this analysis; normal load/PostLoad may reconstruct or dirty in-memory objects. The findings must not be described as a clean commandlet pass.

## How to interpret graph evidence

Nodes were matched by member reference and inspected through their actual pin links. An input Exec link establishes a local connection; it does not prove event reachability or that a runtime branch executes. Empty links are reported literally. This analysis did not execute Blueprint bytecode, inspect placed actors/SCS templates, resolve dynamic string invocation, or infer that a variable named “impulse” contains a physics impulse. Each GUID below identifies the exported node within its stated asset and graph.

| Alias | Exact asset path |
|---|---|
| Sword | `/Game/_mygame/sword/A_Sword.A_Sword` |
| Boat | `/Game/_mygame/assets/boat/StaticMeshes/BP_Boat.BP_Boat` |
| Potence | `/Game/_mygame/assets/hanging/A_Potence.A_Potence` |
| Agent | `/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent` |
| Decal manager | `/Game/_mygame/blood2/A_DecalManager.A_DecalManager` |
| Function library | `/Game/_mygame/NewFunctionLibrary.NewFunctionLibrary` |

## Hit impulse and sword graph

The only pin whose normalized name matches `NormalImpulse` is **Sword `EventGraph.K2Node_Event_3`**, GUID **`494F931242B819670C601E8BDD95C46E`**, member `ReceiveHit`. Both its `then` output and its `NormalImpulse` output have **zero links**. No member-reference/title match for `RetrieveVelAngVel` exists in the 109 exported Blueprint graphs. Thus this manifest does not demonstrate a current Blueprint dependency on a solved contact impulse. The native public `RetrieveVelAngVel` API and native `OnPhysicalHit` forwarding still exist; their compatibility requirement is not erased by an absent Blueprint call.

The misleadingly named **`impulse cut threshold`** variable is connected to **velocity-derived** expressions:

| Sword EventGraph comparison | Actual upstream data links |
|---|---|
| `K2Node_PromotableOperator_11`, GUID `DEA79FE04A8734F7157C20A0F92271E9` | A comes through knot `1ED27CB748877C44AFEB86BD5AA58BEC` from `Dot_VectorVector` `8CEE3B174B6C9A42DE00E3AD4B55C1CB`; its vector input derives from `current tip vel` through a multiply with scalar default 1, and its other input is `GetUpVector`. B comes from threshold variable-get `39F79FAD4EBA03E454F04BBC9F04CE69`. The result feeds Branch `D5AB7EF741260D8D0C8B6CB7E2072809`. |
| `K2Node_PromotableOperator_19`, GUID `C55FC3FC43819C6960122A912A17C5C1` | A comes from `Abs` `71E4CFC74FBBE67EBA59EC956D56FE00` of dot `A7F557314A23920C4C50869CC25AE969`; inputs are `mean v(current vel,current tip vel)` and the `rrrrrrrrr` direction helper. B comes from threshold variable-get `28904C0F4509AF5FA3C088BEAFDB3C60`. The result feeds Branch `4190C77949B89918D4D0C489278B5190`. |

In Sword `tick start`, `current vel` is assigned from **`GetComponentVelocity`** (`K2Node_CallFunction_52`, GUID `775597FA401E73665FCF4FAA99C044C2`); `current tip vel` is assigned from **`GetPhysicsLinearVelocityAtPoint`** (`K2Node_CallFunction_3`, GUID `431487C44F89DF0C848AD7BB44F06085`). Correct Jolt readback must cover both APIs and their evaluation phase; the variable name alone must not cause a new solved-impulse algorithm to be substituted.

The retained cutting operations include:

| Graph / node | Confirmed local operation |
|---|---|
| `handle cuts f.K2Node_CallFunction_38`, GUID `C5E27C9A4DD5FE9E41D3F38BCC05AA97` | `LineTraceSingle` has input/output Exec links. `BuildBladeDepthSweepSamples` is separately present at `K2Node_CallFunction_7`, GUID `CC1A975F40571EA95C56BEB970AC2016`. |
| `EventGraph.K2Node_CallFunction_9`, GUID `5BA1AB654DD9CC057199209FBB472477` | `SetConstrainedComponents`: Component1 comes through victim reroutes with `temp bonename`; Component2 is the sword. Its Exec predecessor is AttachToComponent, preceded by `SetDisableCollision` `16878F0249EB4BA6260B6EA9DA91C0C8`; its successor sets Linear X limit. This is a real backend-dependent constraint chain. |
| `change sword-skel collision and spawn NS.K2Node_CallFunction_0`, GUID `67B913F643D94CB23234E281391D539F` | Connected collision object-type write; the same graph contains connected response-channel writes and additional object-type writes. Preserve paired sword/victim filtering and effect ordering. |
| `change cut depth limit.K2Node_CallFunction_38`, GUID `AC83576F4E60E2604A398D93409252C2`; `_36`, GUID `06C2029C4EBB7CF1C55DB5959D053383` | Connected calls to project `GetLinearZLimit`. Engine limit setters and simulation setters also occur; replacing only traces does not migrate cutting. |

**Event reachability remains unresolved.** Sword `ReceiveTick`, GUID `A46ED8C24E6D38438E7F12A9A1B2DC66`, has no `then` link. Tracing backward from the connected `tick start` call (`3EDE4FD4454FA7D5747A879E23997356`) reaches `EventGraph.K2Node_ExecutionSequence_2`, GUID `2D65C23E4B5ABA5D58C76B99623C0F98`, whose input Exec has no links. A threshold-chain ancestor, `K2Node_IfThenElse_16`, GUID `8B476C894EDFC2B2D964CFA7A532618C`, also has an empty input Exec. These serialized disconnected chains cannot be labeled active gameplay merely because downstream nodes are linked. Verify current compiled/external invocation and intended retained use before selecting a behavioral baseline; do not reconnect them automatically.

Two `get depth of location` call nodes have empty input Exec: EventGraph `_126`, GUID `671B6C74427812C8A369E2AA5F51809B`, and `get current depth._11`, GUID `D99481FE44867FF76C5940A8B76C40C6`. The log does not name which GUID its warning refers to, so this analysis does not attribute that warning to one arbitrarily.

## Boat: the current graph changes the porting contract

Boat EventGraph has a concrete event-connected chain:

`ReceiveTick F5A3B2F648335B15B3B934AD09842F4C` → `Branch 4122B19A487EE8ED91DAF39618C06527` → `Sequence 9366B51F4347D682AD473AA1CDB63CAC`.

Sequence output `then_0` runs a debug print, then the following chain. `then_1` performs the final angular clamp after that first sequence branch:

| Node GUID | Operation and connected/default data |
|---|---|
| `DEB15F81416F14943AFD40949FD7EB28` | `angspring_cpp` → angular velocity setter below. |
| `36D12B5C4AFA21FF531ADB869A153AB9` | `SetPhysicsAngularVelocityInRadians`, `bAddToCurrent=true` → `spring_cpp`. |
| `485DF02244660A0BA3E0FD835ABED3CA` | `spring_cpp` → linear velocity setter. |
| `1A9FE3044AD938A35B4E9C8815E10673` | `SetPhysicsLinearVelocity`, `bAddToCurrent=true` → another linear setter. |
| `46BF8F764DBEDAF9E403F8B5AC7014D2` | **Overwrite**, `bAddToCurrent=false`. Split NewVel X/Y come from `GetComponentVelocity` `799D441B49E47EF957149995E186FBBC`; Z comes from its Z multiplied by **0.85** at `5FB13B0A41F01C2F34EABE9F943B5CC9`. Thus this damps vertical velocity while retaining X/Y; it is neither another additive spring nor a zero-velocity write. |
| `CB2563BC4BD592ECD803CDA706531773` | `ApplyBoatWaveForces`, linked after that overwrite. Exposed pin defaults include **Strength 1.25, HeaveAcceleration 250, WaveFrequencyHz 0.1**, Seed 1337 and TimeScale 1. These differ from the native helper defaults and must be recorded in a matched fixture. |
| `3F72F7194C2B085EF7951F88E496F7D9` | Sequence `then_1`: **overwrite** angular velocity, `bAddToCurrent=false`, from `ClampVectorSize` `2107D56E47A1DACA5441A9975FF00708`. Min=0; Max is Lerp(1.5,2.5, mapped angular-distance input). This is a tilt-dependent angular-speed clamp in radians/s. |

The branch condition derives from component location Z through `Less_DoubleDouble`, GUID `6D694EB84DEB9DAF2A2808B3530F7DDB`. **Its B pin is unlinked and exports empty default/autogenerated-default strings** (pin ID `46341C974A6A02F9183E0C92B3E150BE`). This manifest does not show a water-level variable connection there. Establish its evaluated intended value before claiming the historical water-level gate has been reproduced.

The unconnected `SetPhysicsLinearVelocity` node `7E59E2424D9DF7375BB499BFAD2A90DA` (default X=1000) is not part of this event chain. Preserve the active sequence's timing: its 0.85 velocity multiplier is applied per executed graph tick, so changing application cadence would change damping.

## Rope/noose: confirmed calls and extra authored root

Potence `ReceiveBeginPlay` GUID `17ED90D34E514CD20E0DDE9FA100EC0B` directly calls **`WeldNooseToRopeEnd`**, EventGraph `_12`, GUID **`83302D5F425638247256148EF02309A8`**. Pins connect to component variables `PhysicsConstraint`, `Noose`, and `SKM_RopeHang`; TerminalBone defaults to `joint27`. Its successor is the `ShrinkRope` call `A47AA1ED4DE5137B5A8A328AE1C5D05C`.

`ShrinkRope` entry GUID `5B501220445E181C056AA8A04FA9CD1B` connects its Exec and Amount to **`UpdatePotenceRopePhysics`**, `_5`, GUID **`AF9A8FF643ADF34BE9B94F87C71BE8C6`**; Target comes from `SKM_RopeHang`. This confirms the native retraction/weld helpers are wired in the exported asset.

`/Game/_mygame/assets/hanging/PHAT_RopeHang.PHAT_RopeHang` contains **29 authored bodies and 28 constraints**, with bones `Root`, `joint`, `joint1`…`joint27`; all 29 shapes are capsules and there are 28 disabled collision pairs. `Root` is authored Kinematic, while `joint` is authored Default. Constraint 0 (`PhysicsConstraintTemplate_107`) joins `joint` to `Root`.

This does not contradict the native helper caching the **28-body controlled chain** (`joint` plus 27 links): [ProphecyPhysicsConstraintBlueprintLibrary.cpp:212](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsConstraintBlueprintLibrary.cpp:212>) explicitly selects `joint`, configures it kinematic, and caches only the 27 segment constraints. It **does** mean a full PHAT importer must account for the additional authored Root/body/constraint and verify their actual state; do not silently truncate the asset to the earlier shorthand. The exporter did not inspect the SCS component class, inherited template or placed overrides, so the current retractable-component type still needs targeted confirmation.

## Agent rigs and authored Chaos settings

| Physics Asset | Proven relation / inventory |
|---|---|
| `/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin` | PhysicsAsset and ShadowPhysicsAsset registry tags of `/Game/_mygame/SKM_UEFN_Mannequin`; this mesh is the native agent/benchmark default at `ProphecyAgent.cpp:1120` and `ProphecyPhysicsBenchmark.cpp:108`. |
| `/Game/_mygame/MetaHumans/BossUEFN/PA_Mine.PA_Mine` | PhysicsAsset registry tag of `/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN`. |

Both candidates have **22 bodies, 21 constraints, 18 capsules, four boxes and 47 disabled collision pairs**. Registry tags report 88 bones on both meshes. A tag/native default is not proof a placed agent has no Physics Asset override.

For each candidate's **default authored profile**:

- All **21** constraints have `bEnableProjection=true`, `bEnableMassConditioning=true`, and `bUseLinearJointSolver=true`; `bEnableShockPropagation` and `bParentDominates` are false.
- **21** have soft swing limits with at least one Limited swing axis; **13** have a soft Limited twist axis. Example constraint index 0, `PhysicsConstraintTemplate_34`, spine_01→pelvis: swing 20°/20°, stiffness 50/damping 20; twist 20°, stiffness 50/damping 50. These are authored soft angular semantics, not just unused boolean flags beside free axes.
- The named **Free profile is not completely free**: 17 constraints have all three angular axes Free; four retain Swing2 and Twist Locked while Swing1 is Free. Preserve the actual selected profile; do not interpret its name as permission to free every axis.
- All 22 bodies have authored `bInertiaConditioning=true`. Asset solver settings show position/velocity/projection iterations 6/1/1, SolverType World and `bUseManifolds=false`; runtime overrides may supersede these.

The rope PHAT has soft Limited swing and twist on all **28** constraints, all 28 enable projection/mass conditioning/linear joint solver, and all 29 bodies have inertia conditioning. Example `PhysicsConstraintTemplate_107`: Swing1 Locked, Swing2 Limited 10°, Twist Limited 10°, soft stiffness 50/damping 5. Twenty-eight rope bodies have authored per-body iteration override enabled; native runtime code also applies its own solver settings.

**Design gate:** authored soft angular limits and Chaos projection/conditioning require a validated Jolt implementation/equivalent **when the selected runtime mode actually uses them**. The manifest alone cannot settle current mode overrides, limit freeing, active profile or effective mass/inertia. It would be incorrect either to discard these settings or to declare every character mode blocked by them without checking the runtime selection.

## Raw engine APIs and newly concrete call sites

No `GetNativePhysicalAnimation` member reference or pin typed as `PhysicalAnimationComponent` was found in the exported Blueprint graphs. Native experimental access remains covered by ledger C13; absence here does not remove that public contract.

Inherited engine setters are genuinely present. Examples below have input Exec links; event reachability/retained use still needs classification:

| Asset / graph | Exact node IDs and implication |
|---|---|
| Agent `begin_f` | `SetCollisionResponseToChannel` `A38A7C1C4CB9934DEED46E92985FA207`, `SetSimulatePhysics` `F84D474A4C4FF10CCFE5BAA1268268AA`, `SetCollisionEnabled` `96ABF4964F9122B8058855ACE1B10488`; `begin_f2` contains additional direct setters. A project backend wrapper alone will not intercept these inherited calls. |
| Agent EventGraph | `SetPhysicsLinearVelocity` `72CA273148B67029DB4FAC95D02339B9`, `SetPhysicsAngularVelocityInRadians` `B16D6376467202F7438DE3A89DC0804F`, `GetPhysicsLinearVelocityAtPoint` `CC7C7ACD4EF4C87618EE8EA1D84693A5`; needs body/readback routing and invocation classification. |
| Function library `set vel and angvel` | Linear setter `54726A1E4875BE15DD555FAFD19B0323`, angular-radians setter `9C151C0B4592E9FDA1123C8563B1BC7E`; audit this library's callers, not only actor graphs. |
| `/Game/_mygame/SandboxCharacter_CMC.SandboxCharacter_CMC` | `Ragdoll_Start`: SetAllBodiesBelowSimulatePhysics `A69EE80143DA7EF8DDA465961EE2C5E8`; `Ragdoll_End`: SetAllBodiesSimulatePhysics `1C01F71F4C03EA47A7D0F5998D3092F0`; `magnetize`: linear/angular setters `91856E5D4BF5474FA1F18E8D2130D0A6` / `E48DFBBD42E0DE0D005089B922D66A60`. The legacy character has retained physics controls beyond boat rider forces. |
| `/Game/_mygame/assets/fireplace/BP_Fireplace.BP_Fireplace`, EventGraph | `SetPhysicsAsset` `6CD2F36846E319424918AF8D65213990` and simulation setters `1C11C0B94A61E886528859B1ADF29C96` / `742B0C074782D7901A9F99AE61DD852E`; concrete additional C25 inventory row, requiring retained-use and target-component classification. |

Across all exported graphs the targeted setter search found 10 SetPhysicsLinearVelocity nodes (nine with input Exec links), five angular-radians setters (five linked), 15 SetSimulatePhysics nodes (11 linked), and one each of SetPhysicsAsset, SetAllBodiesSimulatePhysics and SetAllBodiesBelowSimulatePhysics (all linked). These counts are a routing inventory, **not active-runtime operation counts**.

## Blood/Niagara evidence gained, and the remaining inspection

The current export identifies enabled emitter targets (UE enum CPUSim=0, GPUComputeSim=1):

| System under `/Game/_mygame/` | Enabled emitters |
|---|---|
| `blood2/NS_bloodsplat` | Fountain GPU; Fountain001 CPU |
| `blood2/NS_bloodarc` | Fountain GPU; Fountain001 CPU |
| `blood2/NS_bloodwound` | Fountain001 CPU; Fountain002 CPU; Fountain GPU is disabled |
| `blood/NS_blood2` | Fountain, ParticleSurfacing_1 and SingleLoopingParticle: GPU |
| `blood2/NS_bloodrender` | Zero emitter handles exported; do not infer what any external rendering use does from the name. |

All listed enabled emitters have `localSpace=false`. The separate Fire system has five enabled CPU emitters; HairStrands StableSpringsSystem has an enabled GPU emitter. **Collision modules/method inputs, export interfaces/callback bindings, local-space overrides, scalability and GPU readback settings remain explicitly outside this export.** CPU/GPU identification alone does not close Niagara compatibility.

Decal manager `ReceiveParticleData` EventGraph `_3`, GUID `3CAB16E54063F4AB688CC4B67A27B3CB`, has an Exec successor. In `NewFunction`, `TryPaintFromHit` `_5`, GUID `1349876449570DB375D5E681B54B0214`, and `AddFloorHitToFoliageDecalGrid` `_10`, GUID `B536F57A421B54C367F414A78227FBAD`, have input Exec links; separate debug copies of those calls are unconnected. Full callback-to-hit producer and component/material routing still need a bounded graph/data-interface trace; the old authoring commandlet's intended wiring is not substituted for that inspection.

## Concrete next gates

1. **Effective agent/rope settings:** inspect SCS/inheritable component templates and placed overrides; record selected mesh/PHAT, component class, active mode/profile, per-body filters, gravity, solver overrides, evaluated mass/inertia and reference frames. This closes candidate-versus-active ambiguity and the extra rope Root question.
2. **Retained graph invocation:** determine how the disconnected Sword tick/threshold chains are intended to run, and establish Boat's empty comparison input and per-tick damping baseline. Existing warnings are reported, not silently repaired. Then classify direct setters and CMC/fireplace operations by actual retained use.
3. **Niagara collision/export contracts:** inspect the now-identified enabled CPU/GPU emitters' modules, channels, callback/parameter bindings and payload conditions. Trace decal manager callback inputs through its live connected paint/floor paths.
4. **Solved contact impulse:** no current exported Blueprint consumer establishes this blocker. Keep the native API row open; add a solved-impulse implementation only if a retained consumer/contract actually requires it, with explicit provenance and validation.
5. **World/cook coverage:** this package closure does not inspect world/WorldPartition actor instances, PCG output, landscape holes, source triangles/UVs, dynamic concave counterpart pairs or construction-script results. Those remain separate inventory gates.

Local-only operation is the user's current requirement; inherited replication defaults in exported CDOs do not expand the migration into a networking project. No gameplay, asset, source or configuration changes were made by this analysis. This document is evidence for ledger/plan refinement, not acceptance of any migrated feature.
