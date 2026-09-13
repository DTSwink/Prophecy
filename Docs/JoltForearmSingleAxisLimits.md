# Forearm single-axis limits — 2026-09-12

The current testNN setup's calls used Limited 1 degree for the selected axis and Limited 180 degrees for the other axes. The old Jolt converter rejected 180 because of its generic near-free threshold guard. Angular updates are atomic, so this rejected the entire joint update. Live inspection confirmed both lowerarm_r-to-upperarm_r joints remained Free on all three angular axes. The Blueprint did not consume Return Value/Out Error, so the rejection was not visible in gameplay.

The converter now recognizes exact endpoints: Limited 180 becomes a native free axis, and Limited 0 becomes a native fixed axis. The requested UE profile is retained. Interior limits still use the existing supported interval 0.5 through 179.5 degrees; nonzero near-locked/near-free values outside that interval remain rejected rather than silently rounded. Other invalid requests remain atomic.

No constraint frames, axis mapping, magnetisation, damping or player-only speculative policy were changed. This adds work only when converting an authored/runtime limit, with no new per-frame work. The PHAT mapping remains Twist=X, Swing2=Y, Swing1=Z in the joint reference frames, not world axes. A rotation visibly carried by an ancestor is separate from rotation at the forearm's own joint.

Regression coverage exercises each of the three axes independently with a 0- or 1-degree limit and both other axes at Limited 180. The native solver must correct a 35-degree violation on the selected axis while retaining an independent 70-degree rotation on an unrestricted axis. Actual character tests also exercise the lowerarm_r and lowerarm_l Blueprint entry points with Limited 180/180/1.

Evidence and build/test records: `Saved/Diagnostics/ForearmAxis/`. `before.json` records the live all-Free forearm profiles and the rejected Python node invocation (`None`, Unreal Python's failed bool/out-parameter convention).

After the fix, the live Blueprint's Limited 1/1/180 request was present on both forearms, and an explicit single-axis Limited 1/180/180 request succeeded (`after-live.json`). The user's saved graph currently leaves Twist at 180; restricting twist alone requires Twist Locked or Limited 1 and the other axes Free or Limited 180. No Blueprint wiring was changed.

Normal Editor build succeeded. All seven selected tests passed, including SingleAxisWithFullRangeEndpoints and the existing native/player-policy/Blueprint runtime regressions. There were no test errors and one existing disconnected A_Sword compiler warning (`result.json`, `Automation.log`). The user saved the current Blueprint before the restart. Unreal was left open on testNN, outside PIE, with no dirty packages.
