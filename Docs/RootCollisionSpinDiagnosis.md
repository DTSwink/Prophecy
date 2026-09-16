# Fixed-heading root spin after a collision — 2026-09-16

Follow-up: the user subsequently requested the fix. Production steering now distinguishes an impulse-owned stopping target from explicit facing input. `SetLocomotionInput` relinquishes impulse ownership whenever it supplies a nonzero facing vector, even if that vector is unchanged. While angular momentum is active, an explicit heading is re-anchored to its nearest equivalent every policy step. An impulse with no subsequent steering retains its original unwrapped stopping target. No Blueprint edits or new nodes are needed.

The unchanged testNN scene reproduces the problem. `mmmove debug` runs for the possessed pawn from `tick debugging`, requesting world movement and facing `(0,1,0)` every tick. Its keyboard counterpart derives direction from the camera.

In `BuildInputBatch`, the angular-impulse path only reselects the nearest equivalent target angle when the requested facing differs from the existing target **modulo one revolution**. Once a fixed input has chosen an angle such as zero, that guard retains zero even if momentum subsequently carries the current angle past a full turn. The momentum-aware yaw motor uses an unwrapped target-minus-current error, so it unwinds those revolutions. A changing camera heading passes the guard again and reselects a nearby equivalent angle, hiding the problem.

Recorded player trajectory in the unmodified scene:

- Initial heading unchanged until the collision, approximately 1.4 seconds.
- Approximately -747 degrees accumulated rotation by 2.72 seconds.
- It then reverses and returns through both revolutions to the original numerical angle by about 5.7 seconds.
- Peak measured angular speed about 1,284 degrees/s. This large impact genuinely carries momentum; the unwanted part is the subsequent full-turn unwinding.

The implemented solution distinguishes explicit steering from the impulse-selected stopping target. A fresh explicit facing command selects `current yaw + shortest angular difference(current yaw, requested heading)` even when the requested vector is unchanged. The impulse's unwrapped stopping target remains intact when no new steering command is supplied. Damping and impulse strength are unchanged; a sufficiently large impact can still physically rotate the character through complete turns. The fix removes the erroneous full-turn unwinding afterward.

An isolated test runs the actual native mover with the same initial impulse under three target-selection policies:

| Input / selection | Reverse travel | Final unwrapped heading |
| --- | ---: | ---: |
| Current guard, fixed heading | 680.73 degrees | 0 degrees |
| Current guard, tiny changing heading | 48.46 degrees | 720.006 degrees |
| Always choose nearest equivalent explicit heading | 48.32 degrees | 720 degrees |

Zero and 720 degrees are the same orientation. The last two settle without unwinding complete turns. The test does not change Unreal or the NN.

Evidence: `Saved/Diagnostics/RootCollisionSpin.json` (actual scene), `SwordThigh/BlueprintGraph.txt` (read-only dump of loaded graphs), and `TestRootFacingTurns.cpp` / `BuildRootFacingTurns.cmd` (isolated native comparison).

## Installed fix and scene verification

Installed via Live Coding on 2026-09-16 without restarting. Fresh optional `ProphecyRootFacing` ownership storage avoids modifying retained native layouts. No normal-frame work is added outside the existing impulse-facing branch; explicit input has a cheap empty-set guard. Ownership is cleared on explicit facing, settling, and agent teardown.

The unchanged scene's initial peak angular speed remained 1283.798 degrees/s. Reverse travel dropped from 757.750 degrees to 126.667 degrees, and the root settled at -720 degrees instead of unwinding to zero. See `Saved/Diagnostics/RootFacingFixComparison.json` and `RootCollisionSpinFixed.json`. The remaining partial-turn correction follows the same motor and impact strength; this fix does not suppress genuine initial angular momentum.

The separate free-impulse check compares the untouched zero-facing path against a nonzero facing supplied once before the impulse, without further commands. Both settle at the predicted 894.27693-degree displacement, within 0.00012 degrees. Both exhibit the same small approximately 5-degree endpoint correction in this UE setup; this was not introduced or removed by the steering fix. The comparison checks matching endpoint/correction and zero final angular velocity, not an unsupported claim of perfectly monotonic presentation. Report: `Saved/Diagnostics/RootFreeImpulseAfterFacingFix.json`.
