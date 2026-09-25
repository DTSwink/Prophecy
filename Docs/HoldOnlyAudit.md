# Hold-only timing audit, 2026-09-25

Contract: a positive hold remains meaningful when the subsequent blend/fade is
zero. Hold for the configured game ticks, then switch immediately at the end.
Both durations zero, an explicit disable or a Normal source creates no active
recovery work. One authored second is60 unpaused ticks; policy consumers see
the transition at their next publication, as before.

| Feature | Result |
| --- | --- |
| Regular attack/special pelvis and leg checkpoint recovery | Fixed in preceding change; positive hold no longer disabled by zero blend. |
| Kick checkpoint recovery, kicking/non-kicking roles | Same corrected regional implementation, no separate remaining bug. |
| Optional Walk recovery foot rotations | Uses the same corrected regional hold/blend lifetime. |
| Hand Walk/Run checkpoint recovery | Same bug found and fixed in this audit: activation checked only blend duration. Sampling already supported hold-only. |
| Feet/pelvis tempering, regular and kick profiles | Already correct; shared and separate return timelines preserve positive hold. |
| Hand tempering to normal | Already correct, both hands retire independently. |
| FK core tempering to normal | Already correct; hold-only and delayed-consumption boundary covered by lifecycle test. |
| Kick self-balancing exception | Already correct; uses hold+fade activation and handles end before division by fade. |
| Attack arm return to neutral | Already correct; uses hold+blend activation and branches around zero blend. |
| Upper-body inertia | Already correct; uses hold+blend lifetime; response-time validity remains a separate requirement. |

The public hold parameters and their consumers were enumerated across the project
and ProphecyJolt source. Magnetisation/tolerance/damping/clamp snapshot blends,
angular-limit restoration, calf joint-leeway return, camera fade and independent
leg-pole recovery have no configurable hold; their zero-duration bypass/immediate
behavior is intentional and unchanged. Physical constraints holding bodies are
unrelated to this timing contract.

Production change is limited to hand checkpoint recovery activation and its
tooltip. No inference/state/timer remains after hold expiry. Normal source still
bypasses regardless of hold; positive blends, reset, special admission and separate
left/right timing retain their existing behavior. No Blueprint values changed.

Checks add hold-only coverage for hand source selection/independent retirement,
hand tempering, arm return-to-idle and upper-body inertia at30/60/120FPS, together
with existing lower/core tempering, kick balance, regional/kick recovery and
60-tick timing tests. Live Coding build succeeded in144.06s and loaded16:21:16UTC.
All15 targeted native tests passed16:21:43UTC, including the newly added cases.
User closed Play before tests; no editor restart, asset save or Blueprint edits.
No rollout retuning or unrelated solver changes. Include this live patch in the
next authorized normal editor build. Test runner: `Saved/Diagnostics/VerifyHoldAudit.py`.
