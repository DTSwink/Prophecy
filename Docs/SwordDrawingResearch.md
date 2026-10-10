# Pelvis-side sword draw — research and proposed first experiment

October10, 2026. Research/proposal only; no sword implementation, asset, socket,
collision or Blueprint changes made. User wants a holster on the side of the
pelvis first and concise implementation ideas before proceeding.

Epic documents three useful building blocks: [skeletal sockets and Keep World
attachment](https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-sockets-in-unreal-engine?application_version=5.7),
[animation-timed events](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-notifies-in-unreal-engine?application_version=5.7),
and [two-bone IK targeting a socket](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprint-two-bone-ik-in-unreal-engine?application_version=5.7).
[Motion Warping](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-warping-in-unreal-engine?application_version=5.7)
primarily adjusts root motion to targets; a holster carried by this character's
own pelvis suggests local hand correction as the first experiment instead.

Proposed project-specific approach (engineering recommendation, not a claim that
Epic provides a ready-made unsheathing system):

1. Attach a rigid holster/scabbard to a tunable socket or offset on PhysicalMesh's
   pelvis. Give it a mouth frame, extraction axis and sword grip target. Start
   with a stationary draw to establish reach and blade clearance.
2. Sample an authored draw clip through the existing manual NN animation path.
   Blend the right hand to the real handle with small IK correction; optionally
   place the left hand on the scabbard. Three timeline events: Grip, Blade Clear,
   Return to NN. Our manual sequence sampler has no observed notify dispatch,
   so use explicit playback-time crossings or deliberately add notify dispatch;
   don't assume standard AnimGraph Notifies fire automatically. Use the existing
   60-unpaused-tick timing contract.
3. At Grip, match hand/sword transforms, then transfer the same sword from pelvis
   carrier to hand through the sword controller. Preserve world pose and staged
   Jolt ownership. During extraction, keep the blade on the sheath axis until its
   tip clears; an unconstrained hand animation can cut sideways through a sheath.
   Start with authored motion plus correction, not a physical scabbard simulator.
4. At Blade Clear, release the extraction restriction and enable ordinary sword
   contacts/combat. Scope any draw-time owner/scabbard collision exclusions to this
   transition and restore them on finish/cancel. Blend upper body back to the NN;
   retain locomotion lower body once the stationary test is approved.

Current integration facts: `ProphecySwordComponent` binds to `SwordHandSocket`
and `SwordGripTransform`, with managed Jolt weld/fixed-joint admission and drop
momentum handling. Generic reparenting alone won't transfer that native ownership.
See [existing sword contract](AgentSwordBlueprint.md). The manager's NN sword
input, physical-profile equipment selection and defense geometry currently infer
Drawn from `IsValid(GetHeldSword())`. Add explicit holstered/drawing/drawn/sheathing
state before keeping a persistent holstered sword; audit these consumers together.
Keep sword ownership distinct from being ready in the hand.

First motion review should be Grip alignment and blade clearance. Ask the user to
watch that transition instead of inferring smoothness from still images. The
existing active-get-up physics work is complete and verified separately in
`Tools/Recovery/GetUpPhysics20261010.json`.
