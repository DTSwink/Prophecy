# Repeated-kick knee diagnosis — 2026-09-20

The restored runtime is unchanged. This investigation separates endpoint geometry,
pole selection and recurrent feedback; it is not a claim that the knee is fixed.

## Reproduction and attribution

Fresh capture `Saved/Diagnostics/ThighOutward-20260920-170452` ran 600 frames of
the user's unchanged scene. It reproduced the restored baseline's first three
recovery peaks: 15.92, 28.01 and 36.83 degrees sideways. Future and presented
poses agree; the actor is kinematic. Only diagnostic-owned PIE was ended.

`Saved/Diagnostics/KneeMechanismAudit.py` independently evaluates the restored
solver from recorded previous state, accepted endpoint and controls. Across
180 recovery policy samples, its knee positions match the actual output within
0.000023 cm. These are 30 Hz policy samples; their angular steps must not be
confused with interpolated 60 Hz presentation steps.

At the third-kick peak (3.516666s):

| Same accepted hip/ankle/foot | Knee sideways offset |
| --- | ---: |
| Previous hinge transported to the new endpoint, before guidance | 16.76 cm |
| Published knee after guidance | 23.38 cm |
| Same guide applied fully | 29.39 cm |

The synthetic upright frame is minimally swung onto the ankle direction. That
operation does **not** enforce a knee in the foot-forward vertical plane. The
sole-side-derived heading also differs from the actual horizontal toe heading
by 19.60 degrees here, but changing heading alone still leaves 22.95 cm sideways
offset at full guidance. Neither increasing the guide strength nor changing only
the heading is a complete fix.

## Endpoints and the inward radius

This skeleton's left thigh/calf lengths are 39.0062 / 42.5633 cm. The requested
`1.2 * abs(thigh - calf)` bound is 4.2685 cm. It permits approximately 176.68
degrees of flexion (zero = straight), so it is a near-total-fold guard, not an
anatomical knee-angle limit.

The third-kick peak has hip-to-ankle distance 11.6921 cm, about 164.29 degrees
of flexion. The ankle is only 0.196 cm below the hip. The inward bound is inactive;
the smallest distance across the 180 recovery samples is 9.2073 cm.

For fixed endpoints, the knee must lie on a circle:

`upper = axis * along + pole * radius`

`along = (thigh² - calf² + distance²) / (2 * distance)`

Here the calf is longer than the thigh. Below distance 17.0338 cm, `along` is
negative: the knee must project opposite the hip-to-ankle direction. This does
not by itself prove an invalid pose, but explains why almost folded endpoints
are especially difficult to reconcile with a forward knee.

For the actual third-kick endpoint and horizontal toe heading, the two exact
zero-sideways knee solutions are 7.80 cm and 9.48 cm **behind the hip** in that
heading; one is 38.22 cm above the hip, the other 37.84 cm below it. Thus these
endpoints cannot simultaneously produce a knee with zero sideways offset and
a positive forward thigh projection. A pole-only repair cannot guarantee both.
This is a precise statement about this pose and those constraints, not a claim
that every visible sideways knee is mathematically unavoidable.

`KneeFixedEndpointExperiment.py` starts from one of those zero-sideways solutions
and freezes all endpoint/foot inputs. Repeated application of current guidance
moves the knee sideways by 15.48 cm on the first solve, approaching 29.39 cm.
Both segment lengths stay exact. This isolates the guide's attraction toward
an outward pose without any NN updates. The initial synthetic pose demonstrates
geometry, not a certified anatomically acceptable pose.

## Cause of the rejected snapping change

`KneeSnapAudit.py` reproduces the rejected NN-hint/plane solver against capture
`ThighOutward-20260920-165427`, within 0.000038 cm across its recovery samples.
Its conditional reflection activated when the ankle crossed below hip height.

At 4.4500 → 4.4833s:

- ankle-axis Z crossed +0.08954 → -0.09869;
- raw NN thigh direction changed 8.68 degrees; toe heading changed 1.02 degrees;
- the reflected guidance changed 168.59 degrees;
- the published thigh jumped 108.08 degrees in one policy step.

The hint's projected length was about 30 cm, not near zero. This snap was a
discontinuous sign decision, not numerical noise near a tiny pole. Smoothing
only low-confidence hints would not fix this example. That code remains reverted.

## Why repeated kicks differ and why Dodge is not an identical case

`ApplyOutputBatch` feeds the reconstructed lower state into `NextState`, then
swaps it into the recurrent NN input. New full attacks encode the published
current/previous poses. Consequently, recovery modifications influence later
attacks. This is intentional pose/state agreement, not evidence of a state-copy
bug; removing feedback would hide a mismatch rather than solve it. It means a
frozen-input solver experiment does not prove closed-loop rollout quality.

Training's `ParryAndDodge/dodge_leg_feedback.py::solve` takes the current decoded
baseline's complete hinge, adjusts pelvis/ankle, then transports that hinge. It
passes identical source/target foot rotations for Dodge's position modification.
Tempering modifies foot rotation too and currently uses the previous published
hinge plus synthetic guidance. Therefore the successful Dodge transport is not
evidence that this additional guidance is correct.

## Consequence for a replacement

Endpoint acceptance and knee orientation must be solved together. Reject the
inward configurations that make the desired knee impossible, preserve a complete
oriented hinge continuously, and avoid rules that switch sides at hip height.
Do not silently enlarge the user-requested radius, enable outer reach clamping,
or add smoothing to hide a discontinuity. Any replacement needs a defined inward
anatomical constraint and validation of forward bend, sideways deviation, joint
lengths and per-step motion across repeated kicks together. No replacement has
been installed by this investigation.
