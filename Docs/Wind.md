# Global wind

Wind bursts (gusts) roll through the forest on top of each plant's own subtle wind animation. The grass shows travelling
waves, the trees lean and their crowns shimmer, leaves are torn off the canopy, and fallen leaves slide, cartwheel and
briefly take off. Everything reads the same burst at the same place and time, so a sound designer can hang wind SFX on
`OnGustStarted` and `GetGustIntensityAt`.

## What a real gust looks like
The look comes from the boundary-layer and plant-mechanics literature, not from a sine wave:
* **A gust is an advected structure, not a global push.** The wind over a canopy is dominated by coherent eddies swept
  downwind faster than the mean wind (Finnigan 2000; Raupach, Finnigan & Brunet 1996). You see a gust *arrive* and
  *pass*, plant after plant.
* **It is broad and patchy.** Near-ground gusts are tens to hundreds of metres across. Inside one, the wind comes in
  irregular patches ("cat's paws") from a few metres to ~20 m. The patches are stretched along the wind and drift with
  it. The amplitude per scale follows the turbulence spectrum (energy ∝ k^-5/3, so amplitude per octave ∝ k^-1/3).
* **A plant leans with the wind, it does not swing left-right.** Its response is a static bend set by the drag
  (∝ U², saturating as it lies over), plus a smaller oscillation about that lean at its own natural frequency: grass
  ~1–3 Hz, a whole tree ~0.2–0.5 Hz, its branches faster, its leaves fastest (de Langre 2008). The travelling "waves"
  over a meadow (honami) are many plants swaying at that frequency in step with the passing eddies (Py, de Langre &
  Moulia 2006).
* **Gusts come in groups and veer.** Bursts arrive in clusters, and each turns a little off the mean direction.
* The games that do this well (Ghost of Tsushima, God of War) drive foliage from a low-resolution, camera-centred
  wind texture that gameplay writes into. This system does the same at the smallest possible scale.

## How it is built
**`AGlobalWind`** (C++, one per world, created automatically):
* A mean wind (`DirectionYaw` or the level's wind direction, `MeanSpeed` 3 m/s, `Turbulence`).
* Up to 6 live **bursts**, each an analytic shape travelling at `max(3, 1.4 U + 0.35 × strength)` m/s:
  * **Along the path**, the rise is quick (exp(−(s/0.15L)²)) and the decay long (exp(−(s/L)²)).
  * **Across the path**, the edges are broad and flat-topped (exp(−(n/W)⁴)), and the front is bowed.
  * The envelope fades in over the first 12 % of its life and out over the last 45 %.
* Spawning:
  * Bursts spawn 25–80 m upwind of the camera at `GustsPerMinute` (4).
  * Each has a strength of 5–12 m/s, a length of 40–110 m, a half-width of 45–120 m and a life of 10–20 s, and veers by up
    to ±18°.
  * There is a 35 % chance of a follow-up gust.
* **Gust patches** (`GustPatches`): three octaves of value noise, stretched 2:1 along the wind and drifting downwind at
  1.4 U + 3 m/s, scale the burst from 0.3× to 1.5× and turn it by up to ±14°. The material uses the same noise, the same
  constants and the engine clock, so leaves, SFX and grass agree.
* Every tick it fills **`MPC_GlobalWind`**: field origin and time, mean wind, the 6 bursts, and last frame's origin and
  mean.
* **Only while a burst is alive** it draws the smooth burst field into **`RT_WindField`** (128 × 128 RGBA16F over 256 m
  around the camera). Before that, it copies last frame's field into `RT_WindFieldPrev`.
* Gameplay queries:
  * `GetWindAt(P)` returns mean wind + bursts with their patches, in cm/s.
  * `GetGustAt(P)` returns the bursts only.
  * `GetGustIntensityAt(P)` returns 0..1, for SFX volume. It rises and falls with the patches.
  * `TriggerGust(Strength, YawOffset, UpwindM)` starts a burst on cue.
  * `OnGustStarted` fires when a burst starts.

**`MF_WindBurst`** (material function, added on top of a material's own WPO):
* **When calm:** one uniform branch on the MPC. No texture fetch and no cost.
* **In a burst,** with one texture fetch plus the patch noise:
  * **Lean** in the (wandering) wind direction. The bend angle is θmax·(1 − e^(−(U/U0)²)), where U0 runs from 4 m/s
    (grass) to 20 m/s (trunk) and θmax from 0.8 to 0.06 rad with `Stiffness`.
  * The plant bends from the root (∝ height fraction²), keeps its length, and never folds over.
  * **Sway** of ±25 % about that lean at `Freq`, with its phase travelling downwind.
  * **Crown** (`Branch`): outer branches move more than the trunk, about 5 % of the tree height at full lean, each
    crown patch with its own phase.
  * **Leaf flutter** (`Flutter` cm, ~6 Hz) along the normal, with the phase varying smoothly over the crown.
* Every term that moves fast uses the engine's Time node, and the slow field part goes through a *PreviousFrameSwitch*
  (`RT_WindFieldPrev`, `WindOriginPrev`, `WindMeanPrev`). TSR therefore gets correct motion vectors and does not smear
  the foliage.
* Nothing in it has a frequency that varies in space. Neighbouring vertices can never drift out of phase and tear a
  leaf.

**The forest overlay** (`Exports/Wind/wind_overlay.py`):
* The three foliage masters the PCG forest uses are duplicated, and their WPO becomes *original + MF_WindBurst*. The
  originals and their own wind are untouched.
  * `MA_Foliage_Trees` (PVE hornbeam; material attributes, Nanite) → `Masters/MA_Foliage_Trees_Wind4`
  * `M_MS_Foliage` (Megascans grass, sorrel, pratia) → `Masters/M_MS_Foliage_Wind4`
  * `M_MS_Billboard` (their far LOD) → `Masters/M_MS_Billboard_Wind4`
* The forest's material instances are reparented onto the duplicates and given per-plant values:

| Instance | Height | Stiffness | Flutter | Branch | Freq |
|---|---|---|---|---|---|
| Hornbeam bark / foliage | 1500 | 0.92 | 0 / 4 | 1 | 0.3 Hz |
| Wild grass | 38 | 0.12 | 0.8 | 0 | 1.6 Hz |
| Thatching grass | 60 | 0.18 | 1.0 | 0 | 1.2 Hz |
| Violet wood sorrel | 20 | 0.35 | 0.8 | 0 | 2.2 Hz |
| Matted pratia | 8 | 0.55 | 0.4 | 0 | 2.8 Hz |

* Max WPO displacement is set to 300 cm (trees) and 60 cm (grass) so that Nanite and shadow bounds stay right.
* The duplicates are flagged *Used with Nanite* and *Used with Instanced Static Meshes*. A packaged or standalone game
  cannot add a missing usage at run time and draws the default material instead.
* **Motion vectors:** the burst is evaluated twice behind a *PreviousFrameSwitch*.
  * The current frame reads `RT_WindField` / `WindOrigin` / `WindMean`.
  * The previous frame reads `RT_WindFieldPrev` / `WindOriginPrev` / `WindMeanPrev`. `M_WindFieldCopy` copies last
    frame's field into `RT_WindFieldPrev` just before the new one is drawn.
  * Without this, TSR gets no velocity for the gust motion and smears leaves across the sky.
* The duplicates are versioned. A rebuild makes the next version, moves the instances onto it, and retires the old one.
* **To undo:** run `Exports/Wind/wind_overlay_revert.py` in the editor. It reads `Saved/WindTest/overlay_revert.json`
  and puts every instance back on its original master.
* **For another plant material**, add `MF_WindBurst` to its WPO, or reparent its instance onto one of the `_Wind`
  masters.

**Leaves:** see [Leaves.md](Leaves.md), section *In the wind*.

## Settings
Place a **Global Wind** actor to change the defaults. Console variables:
* `wind.Enable 0` turns the bursts off.
* `wind.Auto 0` stops the actor from being created automatically.
* `wind.GustRateScale` multiplies the gust rate.

## Cost
Measured in `-BirdTest=wind` (Entry map, 6 hornbeams, a meadow of 15 172 Megascans grass instances, ~300 leaves):

| | Calm | During a burst |
|---|---|---|
| Wind actor tick (game thread) | 0.008–0.011 ms | 0.07–0.10 ms (includes the two 128² field draws) |
| Field render targets | none drawn | 2 draws of 128 × 128 per frame |
| Foliage vertex shader | +1 branch, early out | trees 293 → 593 instructions in the compiled shader (current and previous-frame paths; one runs per pass) |
| Foliage pixel shader | unchanged | unchanged (+1 on billboards) |
| Leaves, incl. sliding on the ground | 0.2–0.3 ms | 0.3–0.6 ms (~170 leaves sliding) |

The vertex-shader cost only applies while a burst exists. The first branch skips the whole function otherwise, and
there is no texture fetch.

## Test
`-BirdTest=wind` sets up a meadow of the forest's own grass around a hornbeam grove, with a carpet of fallen leaves.
It films:
1. bursts rolling across the meadow, from the side and from down in the grass;
2. a burst over the leaf carpet;
3. a burst through the canopy (leaf release, calm vs gust);
4. a slow-motion close-up of leaves sliding and lifting off.

The results are written as `wind ...` lines to `Saved/BirdTest/wind_v5/game.log`.

## References
* Finnigan, J. 2000. *Turbulence in plant canopies.* Annual Review of Fluid Mechanics 32: 519–571.
* Raupach, M. R., Finnigan, J. J. & Brunet, Y. 1996. *Coherent eddies and turbulence in vegetation canopies: the
  mixing-layer analogy.* Boundary-Layer Meteorology 78: 351–382.
* de Langre, E. 2008. *Effects of wind on plants.* Annual Review of Fluid Mechanics 40: 141–168.
* Py, C., de Langre, E. & Moulia, B. 2006. *A frequency lock-in mechanism in the interaction between wind and crop
  canopies.* Journal of Fluid Mechanics 568: 425–449 (honami).
* Gardiner, B. 1994. *Wind and wind forces in a plantation spruce forest.* Boundary-Layer Meteorology 67 (gusts
  sweeping through tree crowns).
* Rockenbeck, B. (Sucker Punch) 2021. *Blowing from the West: Simulating Wind in Ghost of Tsushima.* GDC.
* Renard, R. (Santa Monica Studio) 2019. *Wind Simulation in God of War.* GDC.
