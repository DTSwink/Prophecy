# Review of the presentation fix — 2026-09-10

Historical review before the user's timing decision. The user approved continuous interpolation; the implemented correction and passing checks are now in [ContinuousValidation.md](ContinuousValidation.md).

The previous patch fixes the demonstrated within-interval backward alpha change. It does not eliminate the visible movement disturbance: its replacement endpoint hold commands the capsule and physical-animation target to stop after some slow frames.

## Reproduction with the user's saved setup

`capture-105914.json` records 5,359 frames over approximately 90 seconds in a fresh testNN PIE session. No movement, feedback, collision, sword, frame-cap or hitch-injection setter was used. Initial metadata is startup state; movement settles to approximately 180 cm/s along +X. Unlike the earlier agent's controlled validation, this capture retains the saved setup, including its initial weapon and collision state.

After the first five seconds:

| Time | Preceding frame | Current frame | Capsule displacement | Target displacement | Body displacement |
| --- | --- | --- | --- | --- | --- |
| 8.283929 s | 72.077 ms | 16.730 ms | 0 cm | 0 cm | -0.005043 cm |
| 69.392973 s | 69.286 ms | 19.375 ms | 0 cm | 0 cm | +0.000778 cm |

Both events keep alpha at 1 on an unchanged pose interval. At 8.300596 s, the following frame advances the capsule only 0.107193 cm and the target 0.112195 cm, versus about 3 cm at the requested speed. This is an actual stop/slowdown in the commands, not a rendering-only discrepancy.

No world-space capsule or target reversal was found. The largest small pelvis reverse was 0.005043 cm. Body-relative-to-capsule motion also varies during normal gait; that is not equivalent to a world-space backward target. The remaining hitch is therefore established as a pause, not a recurrence of the original 1.89 cm backward event. Full measurements: `capture-105914-analysis.json`; reproducible analysis: `analyze.py`.

## Review and regression scope

Reviewed the manager's retained alpha, pose/source-time table, all three authored readers, animation proxy's game-thread resolution, cleanup and collision-rebase timestamp change. The implementation matches the previously agreed endpoint-hold behavior. The prior report's narrow statement about no backward jumps is supported; it did not establish smooth movement after hitches.

All 84 tests in `Prophecy.Jolt+Prophecy.NN.Presentation` pass with the patch loaded. This includes physical animation, runtime collision/limits, character handoffs, held-sword checks, numerical crash containment and the two presentation tests. Ten recorded warnings are retained in `regressions.json`/`Regressions.log`; this is not a zero-warning or exhaustive gameplay guarantee. No gameplay source or assets were changed during this review. Diagnostic PIE was ended before isolated tests and remains stopped.

## Decision needed for the correction

The instantaneous slow-frame endpoint rule spends the interpolation buffer. If the next fast frame has no new NN sample, moving forward along an existing interpolation segment is impossible: its endpoint has already been displayed. The current patch correctly holds instead of reversing.

Recommended correction: use continuous accumulator interpolation at all frame rates, keeping one consistent presentation delay. This removes the slow-frame jump and subsequent recovery hold, preserves 30 Hz NN and existing physics settings, and adds no inference or pose pass. It changes the old <=30 FPS contract: presentation can remain up to one NN interval (33.3 ms) behind the newest completed pose instead of showing that endpoint immediately. At ordinary interpolated frame rates the existing timing is retained.

Await the user's timing choice before changing that explicitly documented low-FPS behavior. No correction has been claimed complete.
