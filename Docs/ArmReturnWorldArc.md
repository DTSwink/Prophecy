# Right-hand return arc diagnosis — 2026-09-26

This records the pre-fix diagnosis. The subsequently authorized [split reference correction](ArmReturnReference.md) now uses pelvis position with current root rotation; the same-prefix first return improves28.91→3.84cm world deviation.

Diagnosis only; no mechanics, Blueprint, settings or build changes. Attached to the user's running Play session without restarting or stopping it. Recorded 360 ticks, then removed the capture callback and disabled SlashReturn.Audit.

Fresh capture: `Saved/Diagnostics/ArmReach/detect_world_arc.json` and `.log`. Analysis: `Saved/Diagnostics/MeasureWorldArc.py`; results: `detect_world_arc_metrics.json`.

Four pike recovery intervals show the right hand bending substantially away from the straight segment joining its first and last presented world positions:

| Recovery ticks | World maximum deviation (cm) | Pelvis-relative maximum deviation (cm) | Pelvis rotation from start (degrees) |
| --- | ---: | ---: | ---: |
| 6777–6839 | 29.54 | 4.30 | 68.91 |
| 6869–6929 | 28.37 | 1.92 | 63.78 |
| 6957–7019 | 30.15 | 4.04 | 67.26 |
| 7045–7109 | 27.53 | 7.47 | 68.52 |

All four world deviations peak 13 ticks after recovery begins. Future authored targets also curve (25.11–27.40cm), so this exists before physical following and presentation interpolation.

Removing pelvis translation and rotation analytically makes these paths much straighter. This is a coordinate decomposition, not a rerun with the pelvis frozen: it does not prove that every remaining component is harmless. It does strongly identify the moving body reference as the dominant geometric contribution to the observed arc.

The current pelvis-reference implementation explicitly recalculates `Reference = Offset * Pelvis` every application, stores procedural wrist position relative to that reference, then converts `LocalTarget * Frame` back to world space. Switching from upper torso to pelvis therefore preserves the same moving-reference mechanism. A straighter local route still swings around as the pelvis turns. Actual-shoulder attachment and the moving NN destination can contribute additional curvature; no claim that the residual is zero. The graph audit command was rejected during Play, so this turn did not independently reread current runtime configuration through that command.

The previous report's 'straighter' result did not solve the requested world-space straightness. A subsequent fix must decouple the progressing wrist's world trajectory from rotation of its reference, while retaining shoulder reach and body/blade clearance. Do not remove those safeguards or promise that all poses admit a perfectly straight path.
