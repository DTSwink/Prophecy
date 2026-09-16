# Root angular impulse

`Add Root Angular Impulse` uses the angular half of `Add Root Impulse`. World Z is yaw; X/Y are ignored by the upright ground mover. With Velocity Change enabled Z is rad/s; otherwise angular impulse is divided by the capsule's yaw inertia. Force/torque nodes integrate through the same impulse path.

An angular impulse now changes both momentum and the stored facing target. The target is the predicted stopping heading under the mover's existing angular braking, summed using the same discrete integration as the future-root window. The present root is not teleported. The future window and actual mover share this calculation; the impulse brakes to its new heading instead of returning to the previous one. Repeated impulses recalculate the stopping heading from combined momentum.

`Stop Locomotion Input` clears move and facing vectors; a zero facing vector retains the stored target, including the new impulse target. If a nonzero facing vector was stored, the impulse updates it too. A subsequent explicit facing command can steer toward another heading. `Get Locomotion Target` exposes the changed target immediately. With Turn Scale zero there is no braking and the existing coasting behavior remains.

Large finite impulses saturate resulting angular speed just below 180 degrees per NN step instead of returning false. This avoids aliasing in the root window's orientation representation. At 30 Hz this is approximately 94.22 rad/s. Stopping headings retain whole revolutions internally so a strong impulse does not reverse direction at the +/-180-degree boundary.

Focused check: `Tools/NN/TestProphecyRootMomentum.cpp` covers signed impulses, saturation, no return rotation, repeated impulses, turn strengths 0.25/0.5/1, future-window versus actual-step equality, zero-strength coasting, and unchanged no-impulse stepping. Gameplay testing is left to the user. No saved Blueprint or scene edits are required.

Installed through successful Live Coding on September 15 without an editor restart. Build/test evidence: Saved/Diagnostics/RootAngularStoppingBuild.log and RootAngularStoppingTests.txt. Include source changes in the next planned normal build.

Combined linear/angular impulse follow-up (September 15, user accepted): travel-direction smoothing previously retained its history in root-local space, causing linear momentum to curve as the root spun. External linear impulses now seed the cache with combined world velocity and transport that direction history between root frames until ordinary movement, balancing, or rest takes over. Distance and orientation smoothing retain their settings; ordinary locomotion retains its original local smoothing. The user confirmed the installed result with "it works perfect"; no additional gameplay testing followed that acceptance.
