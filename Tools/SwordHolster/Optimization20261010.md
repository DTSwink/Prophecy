# D/S optimization — October 10, 2026

The spine/clavicle search is about11× faster, head look-in about6.3×, ordinary FK return about4×, and initial pose planning7.3–7.7×. The complete procedural cycle is2.5–2.6× faster. Agents remain synchronized; update frequency, search steps, targets, velocity controls and authored timing were not reduced.

## Paired native measurements

Seven alternating-order old/new trials after warmup,100 independent agents in the same process. Medians across each idle/walk × drawing/sheathing case. Microbenchmarks below are one call per agent; the complete-cycle row is mean time per active tick. These are procedural calculations, not full game-frame times.

| Work | Before, ms for100 | After, ms for100 | Speedup |
| --- | ---: | ---: | ---: |
| Spine/clavicle refit |5.733–6.915|0.506–0.632|10.9–11.4×|
| Head look-in |0.836–1.051|0.132–0.165|6.3–6.4×|
| Head look-out |0.163–0.197|0.048–0.057|3.4–3.5×|
| Ordinary FK return |0.769–0.924|0.183–0.238|3.9–4.3×|
| Initial body fit |9.847–12.130|0.865–1.084|11.2–11.6×|
| Reach-duration calculation |7.405–9.101|1.298–1.636|5.6–5.8×|
| **Complete initial pose planning** |**17.661–22.290**|**2.430–2.891**|**7.3–7.7×**|
| **Complete procedural cycle, mean/tick** |**1.458–1.826**|**0.577–0.700**|**2.5–2.6×**|
| Complete cycle, median peak/tick |7.223–9.130|1.976–2.460|3.6–3.7×|

Ranges describe the four cases; calculate ratios within the same case, not between unrelated range endpoints. Absolute times differ from the earlier audit because machine load and the measurement process differ. The comparisons above run both implementations side by side. No cross-agent result sharing, staggering or reduced tick cadence is used. The10× gain is real for the search, not a claim about the whole system.

## Work removed

1. Body fitting evaluates shoulder position directly. It no longer builds seven bone transforms or allocates a pose buffer for every candidate.
2. Fixed spine-link vectors, shoulder offset and rotation axes are prepared once per search. Candidates reuse the current twist or clavicle swing when that component did not change.
3. Distance is evaluated in clavicle coordinates, avoiding repeated conversions of each candidate back to world coordinates. Search order, steps, limits and improvement threshold remain the same. Zero angle limits and candidates clamped to the current answer need no evaluation. Nonstandard hierarchies retain the generic calculation.
4. Head aiming evaluates only the neck/head chain. It no longer copies the full pose for each of eight iterations. It stops when its fixed point converges; look-out bypasses the unused entrance-position calculation.
5. Head alpha1 avoids an unnecessary interpolation. Angular-cap sine/cosine values are cached, and capped rotation reuses the known cap angle. One-third neck rotation uses a bounded cubic solution, with the original normalized-linear behavior retained near zero.
6. FK return prepares fixed quaternion/offset interpolation arcs, inertia axes and child indices once on entry. Unchanging offsets and rotations bypass work, while captured segment lengths are retained as the live NN moves.
7. Local FK return writes directly to the result. It avoids unused world-inertia arrays, an intermediate pose and repeated per-bone group calculations. Scaled parents retain the generic transform path; world inertia, spring return and twist removal remain supported.
8. The body pose is not constructed when FK return will replace it in the same tick. Early curve completion retains the prior behavior until the return clock starts.
9. Bounded short-arc trigonometry avoids general range reduction. Its measured maximum component error against the engine functions is5.56e-16 over20,001 samples; arbitrary larger inertia rotations retain the general function.
10. Initial planning reuses fixed interpolation arcs across all96 wrist samples and evaluates only the wrist transforms needed for speed limits. Joint-local angular speed has its exact maximum at the centre interval of the existing quintic sampling grid, so288 repeated joint-angle checks become three. Wrist displacement and wrist rotation still use all96 intervals. Scaled initial transforms are preserved.

## Correctness and scope

Eight isolated native tests passed, including existing lab parity, physical-feedback isolation and authored clocks. Added comparisons against the frozen pre-optimization implementation cover640 body-search cases,15,048 head ticks with moving targets and varied alpha/speed/exponents,800 duration cases including small arcs/scaled transforms,48 full lifecycle cases across local/world, ordinary/spring, inertia/twist controls and moving bases, plus scaled-parent return. Head and authored completion decisions had zero mismatches.

Maximum old/new differences: body-fit parameters0; head0.000002415degrees; full pose0.00001107degrees and0.000001096cm; duration0.000000000577seconds. The one-third quaternion comparison over20,001 samples had maximum squared component error1.43e-31. These are numerical comparisons, not a new motion design. Lab settings, NN input, collision, physical motors and reachability policy were unchanged. The existing15% reach limitation in some poses is not addressed by this optimization.

The100-agent measurements exclude NN reads/inference, pose-cache publication/consumers, physics, rendering and equipment operations. Initial planning excludes skeleton discovery and full runtime admission. Stage measurements are for the saved ordinary-return profile; alternative return modes are verified for correctness, not claimed to have the same speedup.

Normal build: `Saved/Diagnostics/SwordOptimization20261010/build-final.txt` (67.34s). Full local evidence and earlier optimization passes are preserved in that directory. `Optimization20261010.json` is the compact receipt. Runtime changes are confined to `ProphecySwordHolsterPose.cpp`; the legacy implementation is retained only in development tests. Reproduce with `Tools/SwordHolster/RunParity.ps1`, then `Tools/SwordHolster/SummarizeOptimization.py`.

## Actual Unreal verification

- Saved15% Sim cycle passed: sheathe reach/slide-end/complete68/99/161; draw191/222/284. These match the previous implementation exactly. Maximum return hand tracking error0.20725cm for S and1.29271cm for D.257 right-arm collision-suppression checks passed, unrelated contacts stayed unchanged, and duplicate calls did not add joints.
- Existing reachable25% kinematic fixture passed: S72/99/161 and D191/218/280, then switching back to Sim and restoring holster simulation passed at340.25% was a temporary PIE-only value, not saved; the current15% geometry limitation remains unchanged.
- Full Blueprint graph and all four map/agent/sword/profile hashes are unchanged. Reflection inspection reports status3, native_properties0, pin_types0. Editor PID17896 remains open on TestNN, outside Play, with no dirty packages. One editor shutdown/reopen was required for the changed private retained cache layout; no Live Coding was used for that change.
