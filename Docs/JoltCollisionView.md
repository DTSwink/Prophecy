# Live Jolt collision overlay

During Play, console commands:

```text
showflag.collision 0
Prophecy.Jolt.ShowCollision 1
```

The first hides Unreal's separate PHAT/Chaos collision overlay. The second draws the **live Jolt** dynamic and kinematic shapes. `Prophecy.Jolt.ShowCollision 2` additionally draws static Jolt geometry; `Prophecy.Jolt.ShowCollision 0` turns it off. Cyan=dynamic, yellow=kinematic, gray=static. This is a separate console overlay, not a change to Unreal's ShowFlag implementation.

Uses each admitted native body's current collision shape and COM transform. Collects transformed leaf shapes before extracting triangles, handling compound/scaled shapes and the retained-COM wrapper used by foot front trimming. Draws triangle edges, including surface triangulation diagonals. Curved shapes use Jolt's triangle approximation. Does not draw Chaos-only objects or alter collision response, PHAT assets, body shapes or simulation. Removed/welded-away native bodies are omitted; their actual carrier geometry is drawn.

Off by default. Only while enabled does a world post-actor-tick callback enumerate and draw bodies; switching off the last world removes the callback. World cleanup removes its entry and retires unused delegates. Non-Shipping only. Each body has its own2048-triangle drawing limit, so complex objects cannot hide later skeletons. Very complex individual bodies may be partially drawn; total debug cost scales with the number of admitted bodies.

The original shared20000-triangle limit was exhausted by the scene's rope bodies before reaching the agents (confirmed12:05UTC, final rope joint27 consumed the remaining56 triangles). Replaced with per-body limits; no collision or gameplay change. Explicit `Prophecy.Jolt.ContactExperiment collisionstats all` draws one frame and logs each included native body's component, bone, motion and triangle count for diagnosis.

Correction Live Coding build succeeded16.47s, loaded12:06:17UTC. Owned current-scene test12:06:45UTC enumerated and submitted geometry for all66 PhysicalMesh bodies across3 agents, including6 foot boxes; no body exhausted its2048-triangle allowance. Owned Play ended; no Blueprint/settings edits. Latest budget correction is live-loaded and should be included in the next authorized normal build.

## Validation2026-09-26

The initial test exposed a Jolt assertion: `GetTrianglesStart` cannot be called on an `OffsetCenterOfMassShape` directly. That diagnostic closed the editor. Corrected by collecting transformed leaves, as required by Jolt's local API contract. No gameplay trim change was made.

Saved pose Blueprint timestamp13:50:10 local was newer than the autosave13:41:37; both backed up in `Saved/Diagnostics/JoltCollisionViewRecovery/`. Reopened the saved project without substituting the older autosave.

Normal Development editor build succeeded22 actions/70.36s, consolidating the preceding Live Coding changes. Separate-process test with `/Engine/Maps/Entry` and NullRHI passed `Prophecy.Jolt.RigWorld.FootColliderFrontTrim` at11:57:13UTC: drawn live box geometry has heel−9cm and toe9cm after6cm trim, then toe15cm after restoration, alongside existing native ray/contact-geometry/COM/velocity/atomicity checks. UnarmedRotation regression passed in the same process. Log `Saved/Diagnostics/JoltCollisionViewRecovery/Headless.log`.

Editor reopened on `/Game/testNN`, process14576; remote Python responsive11:58UTC, new hand-constraint node reflected. No Blueprint wiring changes or explicit asset save.

Owned four-second scene check passed11:58:53UTC, toggling moving-only→all→off→moving-only and then ending Play with drawing enabled to exercise world cleanup. Native scene shapes rendered through the callback without assertions; no user session was interrupted. Evidence `Saved/Diagnostics/JoltCollisionView.json`. Overlay is off again after world cleanup.
