# hookR return comparison and profile import

## Comparison before the new profile

The October 8 current scene repeated full hookR at absolute 59–83, 119–143 and 179–203. The live lab selected variant 8. Both had the accepted algorithm SHA256 `7245f85fd9b2e13b351e1aed246ec8ec4b58634516978034565224d822487b0a` and matching profile: duration .25, easing .87, inertia 1, world inertia, hold .05, decay .8, spine-angle addition .29 seconds per 90 degrees. Runtime confirmed NN alpha hold 1 / trim 0.

The outgoing motion was different: first Unreal upperarm_r world angular speed 1292.02 degrees/second, versus lab variant 8's 619.83. Repeats measured 1255.77/1255.06. Effective return durations were .2985/.2992 seconds in Unreal, versus .3063 in the lab. Feeding Unreal's entry pose and velocity into the unmodified lab sampler, with the lower body frozen, produced a 114.57 cm spine-relative hand path, versus 84.88 cm for variant 8. These are different entry poses as well as velocities; do not attribute the entire difference to speed alone.

The lab freezes the lower body throughout recovery and its current view additionally anchors spine_01. Unreal returns its pelvis to locomotion. An isolated diagnostic VM of the lab sampler was supplied the observed lower pose and the native moving-pelvis baseline blend. Across all three returns, non-hand upper positions matched native future endpoints within .000416 cm. Applying the observed wrist-to-elbow length from the existing forearm stretch return reduced hand discrepancy to .000433 cm maximum. Before accounting for that length return the largest hand discrepancy was 1.596 cm. This verifies the authored return computation; it does not establish that the physical body exactly follows it. The physical right hand differed from its presented target by up to 24.69 cm in the first recovery, so physical tracking can additionally affect the visible result.

No motion fix was made. Evidence and reproducible offline comparison: `Saved/Diagnostics/HookRLabCompare20261008/compare.cjs`, `lab-vs-unreal.json`, `current.json`, and `current-audit.log`. Owned capture ended and audit CVars restored. Final graph comparison noticed user edits during the investigation; no graph was restored or overwritten.

## Requested new profile

User subsequently changed hookR in the live lab and requested import. Only the hookR row in `ProphecyFKReturnData.h` changes: base duration .25 → .28 seconds, easing .87 → 0, main inertia 1 → .7. Bone weights, world inertia, inertia timing, angle addition and every other attack/idle datum remain byte-identical. This does not edit Blueprint NN hold/trim pins.

Import snapshot and byte-scope checks: `Saved/Diagnostics/HookRProfile20261008/`.
