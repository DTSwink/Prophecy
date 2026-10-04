# Lab world-velocity handoff correction — October 4

Latest snapshot 7 exactly reproduced from the previous live source: slashR,
variant16, yaw125 degrees, return.26, inertia1, easing.12, spine1,
clavicle.19, upperarm1, lowerarm.61, upper-only anchored. Saved points and axes
match within floating-point roundoff. The full-world-per-local-joint experiment
repeated inherited rotation down the chain. The apparent teleport was a large
velocity jump, not a discontinuous pose at exactly time zero.

The live standalone lab now captures the derivative of the actual authored
sampler (including forearm correction and yaw) immediately before the endpoint.
For every enabled inertial joint:

    local seed = inverse(bone world rotation) * (outgoing world omega - actual parent return omega)
                 - initial local idle-return omega

The parent's actual return omega includes the selected easing and whether its
inertia is disabled. Pelvis return omega is zero in this lab, so spine_01 keeps
the outgoing pelvis contribution. The resulting seeds are cached per settings
profile and used by the existing local FK curve. There is no per-frame world
velocity constraint, new timer, or change to Unreal.

Snapshot 7 measurements at 60 Hz:

| Quantity | Last authored step | Old first return step | Corrected first return step |
| --- | ---: | ---: | ---: |
| Right hand displacement | 7.759 cm | 31.196 cm | 6.444 cm |
| spine_05 rotation | 6.056 deg | 23.624 deg | 6.070 deg |

At the infinitesimal seam, spine_01 incoming164.2996 deg/s becomes164.2995,
spine_05 incoming363.3794 becomes363.3794, and lowerarm_r incoming520.5312
becomes520.5311. Before the correction, spine_05 became1827.2411 deg/s.
Anchored hand linear speed changes465.55→456.79 cm/s, rather than2719.49 cm/s.
Exact point-velocity conservation is not claimed: fixed lengths, existing local
offset interpolation and excluded hand inertia remain. The momentum decay also
remains; this fixes the handoff, not a rigid-body dynamics model.

All320 motions and1280 yaw cases pass. Tests now verify the resulting world
angular velocity, including easing0/.12/1 and disabled parent inertia, rather
than checking only that each local joint received a world-derived seed.
Authored playback, frozen lower body, fixed segment lengths, hand exclusion,
exact idle and positional continuity pass. Existing user settings unchanged.

Evidence: `Saved/Diagnostics/LabSpine20261004/relative-seed-audit.cjs` and JSON.
Previous source retained there as `recovery-before-relative-seed.js`.
