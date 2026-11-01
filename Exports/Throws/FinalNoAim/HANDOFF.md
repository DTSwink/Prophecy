# Final throws

November 1, 2026. Use **BigThrow_Final_NoAim.fbx** and
**SmallThrow_Final_NoAim.fbx** in this folder: both 100%, Aim at target OFF,
saved hand/forearm edits baked, complete original 89-bone UEFN skeleton.

For a JS lab, **clips.json** contains the same final 26 controlled bones:
60 fps, Y-up meters, world `[px,py,pz,qx,qy,qz,qw]`, plus parent-local transforms.
Big: F0–130, armed F25. Small: F0–68, armed F18. Both release at F34.

**Do not reapply the old hand/forearm edits or source pose shaping.** Keep
weapon grip/scale and physical launch values from **manifest.json**; launch
velocity already includes saved amplitude/direction, with shaft-axis spin.
Use `Labs/ThrowLab/data/objects.json` for matching geometry/binds. Physical
speed multipliers are not baked into animation timing. Add any new aim once.

Small at100% has no rotation edits and therefore matches its source motion;
partial-charge shaping remains procedural. FBX round-trip checks passed for
every frame/bone; **verification.json** records errors/hashes. Source FBXs,
live lab state and Unreal assets were not changed.
