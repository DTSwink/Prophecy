# Lower physical feedback alignment

The existing physical feedback tolerance nodes keep their units and selection rules. Zero tolerance passes the physical deviation; a positive tolerance removes that much deviation. This change corrects **Jolt lower-body** feedback. Upper feedback and the legacy Chaos sampling path are unchanged.

Previously, the lower NN's recurrent pose was compared directly with a physical sample expressed relative to the displayed root. The NN recurrence had already advanced/rebased to the next root; the physical mesh followed the interpolated publication. Even a perfect follower therefore appeared to deviate. The isolated investigation and recorded rollouts are in `Saved/Diagnostics/LegFeedbackIsolation/README.md`.

The corrected sequence is:

1. At the shared physics completion boundary, before animation callbacks can publish another target, capture the authored lower target used for that step. The capture covers only pelvis, both thighs, feet and toes. Helpers without their own PHAT body inherit the same local transforms used to compose the physical skeleton.
2. Pair the captured target with the completed physical skeleton by binding and completed-pose revision. A newly bound/recreated rig waits for its first matching capture; it never falls back to the old mismatched lower sample.
3. Express both in the current recurrent root frame. Compute actual-minus-authored translation, authored-to-actual rotation and relative toe-angle deviation.
4. Apply these deviations to the current lower recurrent pose, then run the existing tolerance and previous/current history commit. A perfect match copies the current state exactly, preserving the existing unchanged-state path.

Rotation uses a quaternion-equivalent composition, not Euler subtraction. Tolerances still operate on the shortest rotation. Transform roundoff below one micrometre / quaternion component epsilon 1e-6 is treated as numerical identity, not a configurable gameplay tolerance.

The capture also evaluates a partially completed authored trajectory when explicit physics steps are shorter than that trajectory. Normal automatic stepping captures its endpoint. Capture state is removed with the Jolt binding, including reset/re-admission.

No new tick, physics step, NN evaluation, Blueprint node or per-frame UObject search is added. Kinematic agents skip the feedback path. Storage is separate from retained character/manager allocations so Live Coding does not change their native layouts. Capture arrays and prepared-batch arrays retain capacity. Upper/Chaos behavior is deliberately preserved.

Focused native regression: `Prophecy.NN.PhysicalFeedback.LowerTargetAlignment` checks exact preservation under a different presented root/pose, real 5 cm translation and 20-degree rotation deviations, 2 cm / 5-degree tolerance results, toe deviation, and serial/prepared equivalence. The existing 100-agent pure-state prepared/parallel oracle remains in the same automation group. These are isolated data tests, not gameplay tests.

Installation and actual test outcomes are recorded in `ProjectJournal.md` after the build completes. No Blueprint or map edits are needed to use the corrected existing nodes.

Development-only comparison switch: `Prophecy.NNLowerFeedbackAlignment 0` selects the original absolute physical lower sample in both serial and prepared feedback. `1` restores the corrected path and is the default. Use fresh PIE sessions when comparing so recurrent history starts identically. This does not change any Blueprint tolerance or upper-body setting. The switch is compiled out of Shipping.
