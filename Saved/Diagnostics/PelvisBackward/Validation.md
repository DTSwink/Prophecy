# Pelvis backward-step fix — verified 2026-09-10

The managed NN presentation now retains its greatest interpolation progress within an unchanged policy interval. After a slow frame displays the endpoint, the following fast frame holds that endpoint until the next interval begins. Ordinary interpolation, exact low-FPS display, NN cadence and physics stepping retain their existing behavior.

The manager's existing alpha drives the capsule, the three authored-target readers, and the animation proxy. A small pose-ID/source-time side table shares the value; the proxy resolves it on the game thread and stores it in its existing float slot. Pose-store cleanup removes the entry. Collision rebasing preserves the original interval timestamp. No existing manager, pose snapshot, or animation proxy allocation changes size.

## Verification

- Live Coding compiled and loaded both patches successfully into the existing editor process. No editor restart or game asset save.
- Both `Prophecy.NN.Presentation` automation tests pass: fixed and mixed frame cadence, the recorded hitch sequence, zero-time refresh, exact-pose override, shared readers, same-time re-publication, new intervals, mismatched source fallback, and pose-ID cleanup. The fallback arithmetic checks allow `1e-6` float error under `/fp:fast`.
- A 50-second PIE capture used the actual possessed main agent. After startup, all feedback tolerances were zero, self-collision was disabled, sword was dropped, and movement was constant +X at 180.001920 cm/s facing -Y.
- Eighteen deliberate post-tick sleeps of 35/43/52 ms produced repeated frame hitches. Sampling ran in memory without remote status calls during the capture. Analysis excludes the first five seconds.
- Across **2,658 frames / 45.42 seconds**, there were **zero capsule or target backward movements**, **zero alpha regressions across 1,305 unchanged-pose pairs**, and eight slow-to-fast recoveries within the same pose interval. All eight kept alpha at 1.
- No physical pelvis backward movement exceeded 0.01 cm. The largest small reverse was **0.001639 cm (0.01639 mm)**, versus the original detected **1.88757 cm (18.8757 mm)** jump. This is a measured bound for this capture, not a claim that every physical body movement must always be monotonic.
- Rendered pelvis matched the actual body within `2.03e-12 cm`.

Final state: PIE running with the user's test settings restored; capture callback unregistered, all deliberate sleeps finished. No performance benchmark or separate clean-start build was performed. The fix adds scalar comparison/lookup work but no NN evaluation, physics substep, pose history, or additional update pass.

## Evidence

- `fixed-capture-104959.json`: complete capture, test settings, injected hitch timestamps.
- `fixed-analysis.json`: numerical results and eight recovery pairs.
- `RegressionTests.log`: final two passing tests.
- `LiveCodingBuild.log`, `LiveCodingPatch.log`: build and patch evidence.
- `validate_live.py`, `analyze_fixed.py`: repeatable live fixture and analysis.
- `Diagnosis.md`, `capture-102005.json`: original diagnosis and backward event.
