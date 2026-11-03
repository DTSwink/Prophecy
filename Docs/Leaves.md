# Falling leaves

Leaves let go sparsely from the trees near the player. Each one falls the way its shape and condition make it fall, lands
with simple collision, lies for 7 s, fades out over 2.5 s and is gone. Nothing accumulates. Wind bursts from the global
wind system ([Wind.md](Wind.md)) tear extra leaves off the trees, and push, cartwheel and briefly lift the fallen ones.

## Use it
Nothing to set up. A **Leaf Fall** actor is created automatically in every game world. It looks for the tree meshes,
which default to the PCG hornbeams `/Game/_mygame/pcg/tree1` and `tree2` used by `PCG_Forest` in `mybasic`. Any component
using them works: PCG instances, foliage, or plain actors. It rescans every 5 s, so runtime PCG generation is picked up.
If no tree mesh is found, it idles.

To change the settings, place a **Leaf Fall** actor in the level:

| Setting | Default | |
|---|---|---|
| Tree Meshes | tree1, tree2 | meshes that drop leaves |
| Leaves Per Tree Per Minute | 5 | sparse; Poisson-distributed over the trees in range |
| Active Radius | 45 m | only trees near a player camera |
| Max Leaves | 400 | falling + lying |
| Rest Time / Fade Time | 7 s / 2.5 s | dithered fade, resolved smooth by TSR; the rest clock pauses while a leaf slides |
| Season | 0.65 | 0 = end of summer (mostly green), 1 = late autumn (golden to brown) |
| Fresh / Dry / Damp / Wet Share | 0.25 / 0.45 / 0.18 / 0.12 | condition mix |
| Leaf Length Cm | 6–11 | hornbeam blade |
| Wind | 0 | extra steady air motion (cm/s), added to the global wind |
| Gust Release Boost | 8 | a tree under a burst drops up to 9× more leaves |
| Wind Moves Fallen Leaves | on | bursts slide, cartwheel and lift fallen leaves |
| Ground Wind Factor | 0.18 | wind at a lying leaf, as a share of the wind at 10 m (log profile) |
| Lift Off Ratio | 14 | lift / weight a leaf caught edge-up mid-roll needs to take off |
| Snag Per Metre | 0.6 | how often a moving leaf catches on something and stops |
| Collide With Trees | off | canopy collision would catch leaves in the branches |

**Blueprint / C++:**
* `SpawnLeafAt(Location, Condition, bRandomCondition)` lets one leaf go at a scripted moment.
* `RescanTrees()` rescans the level for trees immediately.
* `GetStats()` returns the counts by flight style and the tick cost.

**Console variables:**
* `leaves.Enable 0` turns falling leaves off.
* `leaves.Auto 0` stops the actor from being created automatically.
* `leaves.RateScale` multiplies the leaf rate.

## How a leaf falls

### Forces
The forces on the blade use the quasi-steady model of a falling plate by Andersen, Pesavento & Wang (2005, *JFM* 541),
relative to the air:
* drag `C_D(α) = C_D0 cos²α + C_D90 sin²α`;
* circulatory lift `C_T sin 2α`;
* rotational circulation `C_R` (lift of a pitching or tumbling blade);
* the added mass of air moving with the blade (Kirchhoff). This gives the swoop at the end of each swing.

A leaf is a finite blade, not the 2D card of the paper:
* lift slope reduced by AR/(AR+2);
* induced drag `C_L²/(π AR e)`;
* more friction drag from the veins and serrated margin.

Terminal speed of a flat leaf broadside is √(2mg/ρAC_D90), about 0.75 m/s for a dry leaf.

### Orientation and regime
The orientation follows the regime the leaf belongs to on the phase diagram of falling plates (Field et al. 1997, *Nature*;
APW 2005). The regime is set by the dimensionless moment of inertia `I* ≈ ρ_s h / 2ρ_f l`, from the leaf's mass per area
and width. Frequency and swing amplitude are scaled from the leaf itself (Strouhal number ~ f·l/U).

| Flight | Who | Motion |
|---|---|---|
| Flutter | light, flat leaves (low I*) | planar zig-zag pendulum: glides one way, swoops up, stalls, glides back (0.7–1.4 Hz, 40–65°); the swing plane drifts slowly (3D zig-zag) |
| Chaotic | flutter / tumble border | flutters, now and then overturns into a few tumbles, then flutters again |
| Tumble | heavier or curled leaves (high I*) | end-over-end about the long axis (1–2 rev/s, faster edge-on), drifting sideways on a slanted path |
| Roll | dry leaf rolled into a tube | spins about its long axis, sheds little lift, drops faster |
| Spiral | twisted / cupped dry leaf | held at a tilt while its glide direction turns: helical descent (Zhong, Chen & Lee 2011 spiral mode) |
| Rock | soaked leaf | heavy and limp: small, quick rocking, almost straight down (~1.3 m/s) |

The thresholds are about 1.3× those of rigid cards. A real leaf is flexible, and its petiole damps the overturn, so it
flutters over a wider range.

With the default shares, the mix is about 27 % flutter, 27 % chaotic, 16 % tumble, 12 % rock, 11 % spiral and 6 % roll.
That is measured: 733 leaves in the test.

### Condition
Condition sets mass, shape and colour.

| Condition | Mass per area | Shape | Colour |
|---|---|---|---|
| Fresh | 50–75 g/m² | flat, slight V-fold and pleats | green to early yellow |
| Dry | 35–55 g/m² | wavy, cupped, rolled or twisted | gold to orange to brown |
| Damp | ×1.7–2.3 | flat or wavy, limper | mid-autumn |
| Wet | ×2.8–3.2 | limp, drooping | darker and glossier |

Hornbeam's own leaf mass per area is about 50–75 g/m², and a soaked leaf carries 2–3× its weight in water.

### Collision
A line trace along each frame's motion, against static, dynamic, physics and pawn objects (the trees are ignored by default):
* **Ground** (slope < 57°): the leaf lands either side up, settling onto the surface in 0.2 s.
* **Walls, trunks and characters:** it bounces off and keeps falling.

A leaf that never lands fades after 40 s.

## Look
The leaves are the trees' own scanned leaves: 8 real hornbeam leaves cut from `T_Hornbeam_01_Foliage_CA/_NT`. The
falling ones therefore match the canopy exactly.

`M_Leaf` is a two-sided foliage material, so leaves glow when back-lit. It does senescence per leaf:
* Chlorophyll goes from the margin and tip first.
* Green lingers along the veins.
* Green turns to yellow, gold and orange, then brown with necrotic spots.

Wet leaves are darker, deeper in colour and glossy (roughness 0.62 → 0.2).

There are 6 blade meshes (Flat, Wavy, Cupped, Rolled, Twisted, Wet; 352 triangles each), one instanced mesh per shape.
Per-instance data: senescence, wetness, atlas cell, fade, hue variation and spots.

**Assets:** `/Game/Prophecy/Ambient/Leaves/` (meshes, `M_Leaf`, `MI_Leaf_Hornbeam`, textures). To regenerate them:
`UnrealEditor-Cmd <uproject> -ExecutePythonScript=Exports/Leaves/setup_leaves.py -LeafSetupQuit -unattended -nullrhi`.

## In the wind
The leaves read the global wind (`AGlobalWind::GetWindAt`) every step, so they follow the same bursts the grass and the
trees show.
* **In the air**, the wind follows the log profile of a surface layer, `ln(1 + h/z0) / ln(1 + 10 m/z0)` with
  z0 = 0.1 m (clamped 0.2–1.1). A leaf near the ground feels less of the burst than one in the canopy.
* **Release**: a tree is picked for the next leaf with weight `1 + GustReleaseBoost × burst intensity`. A burst through the
  canopy visibly strips it.
* **On the ground** (the physics is simple, but the behaviour is varied):
  * **Wind at the leaf** is `GroundWindFactor` (0.18) × the wind at 10 m. That is the log profile ln(z/z0)/ln(10 m/z0)
    for a leaf lying 2–5 cm above litter.
  * **Drag** acts on what sticks up into the flow. A flat leaf offers almost nothing, because the wind skims over it. A
    curled or cupped leaf catches it, as does one already tipped on edge.
  * **Friction:** static friction (×1.35 plus any snag) is higher than sliding friction. Each leaf has its own grip
    (0.8–2.2, for litter interlock and roughness), and wet leaves hold about 3× more. A leaf needs a real surge to start,
    keeps going while the gust patch holds, and stops when it fades.
  * **Snags:** a moving leaf catches on something about every 1.7 m (`SnagPerMetre` 0.6). It then holds there,
    harder, until a stronger gust frees it.
  * **Rolling:** curled leaves roll over their edge. Flat ones skid and now and then flip over.
  * **Take-off needs an angle of attack.** Only a leaf caught edge-up into the wind mid-roll, in a strong surge, lifts
    off. The lift is ½ρU²A·1.2 sin 2α, and it has to exceed `LiftOffRatio` (14) × the leaf's weight. The leaf then
    rests at least 3 s on the ground before it can lift again. It blends back into the flight model over 0.4 s, and
    also goes airborne if it slides off an edge.
  * In the test, one strong burst over about 370 lying leaves set a few dozen sliding at a time and lifted about 100
    over its whole passage (many of them more than once).

## Cost
* 0.1 ms per frame at the in-game rate.
* 0.23 ms with 400 leaves at once (154 falling + 245 lying).
* Physics substeps at 120 Hz; only moving instances are sent to the renderer.

## Tests
`-BirdTest=leaves` (a hornbeam grove in low autumn sun) or `-BirdTest=leavesmap` on `/Game/mybasic`.

Each test:
* films a wide shot, one leaf of each flight style followed by the camera, and slow motion;
* times one leaf from landing to removal (7 s + 2.5 s);
* runs a 400-leaf load window.

The results are written as `LEAFTEST` / `BIRDTEST` lines to `Saved/BirdTest/<run>/`.

## References
* Raupach, Finnigan & Brunet 1996; Finnigan 2000 — see [Wind.md](Wind.md) for the wind side.
* Andersen, Pesavento & Wang 2005, *Unsteady aerodynamics of fluttering and tumbling plates*, JFM 541.
* Field, Klaus, Moore & Nori 1997, *Chaotic dynamics of falling disks*, Nature 388.
* Zhong, Chen & Lee 2011/2013, *Experimental investigation of freely falling thin disks* (zig-zag → spiral), JFM.
* Wejchert & Haumann 1991, *Animation aerodynamics*, SIGGRAPH (the classic falling-leaf animation).
