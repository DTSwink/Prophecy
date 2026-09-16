# Agent2 root instability: automatic spacing versus balancing

2026-09-14, exact actor label `BP_ProphecyManualPoseAgent2`, manager handle1. Three 30-second runs, changing only transient runtime settings after5seconds; statistics below use seconds10–30. No saved assets or Blueprint wiring changed.

| Run | Balance activation transitions | Root XY extent | Root speed median / max |
|---|---:|---:|---:|
| Current setup | 142 | 4.80 × 10.47 cm | 11.33 / 28.61 cm/s |
| Balancing disabled | 0 | 0 × 0 cm | 0 / 0 cm/s |
| Input gate temporarily raised to1, continuous balancing | 0 | 1.76 × 0.32 cm | 0.104 / 0.104 cm/s |

Current settings are speed threshold600cm/s, move-input threshold.05, frequency2Hz, damping1, maximum balance speed30cm/s, tolerance1cm. Smoothing is .6/.5/.7. The speed gate cannot explain this oscillation because measured speed stays below29cm/s. Root-to-actual-feet-midpoint distance remains3.85–14.33cm, outside tolerance; this is not repeated crossing of the1cm tolerance boundary.

The saved Blueprint enables balancing at tick130. Its unpossessed-agent branch continuously generates spacing input toward/away from the player using pelvis separation. After tick90 it aims at210cm, with absolute separation error mapped from50–100cm to input0–1. This is an automatically generated movement request, not raw keyboard/gamepad intent. Captured input magnitude ranges .029–.074 around the .05 balance cutoff.

The normal spacing motor reduces separation error until balancing is allowed. The feet-centering spring then moves the root toward a different target, making spacing request movement again. The .05 switch restores the spacing motor, and the cycle repeats. There were142 transitions in20seconds. Continuous balancing removes the switching but lets spacing input rise to .287–.330; raising the cutoff to1 is a diagnostic isolation, NOT an accepted fix because it suppresses requested locomotion.

This establishes a controller interaction rather than a missing future-window spring. Previous mathematical validation of all8 roots did not test this autonomous-spacing handoff. The inactive/active root motor selection is a hard switch; the two goals are not guaranteed to coincide.

Next work must coordinate when automatic spacing relinquishes control to balancing while preserving immediate movement exit. A distinct re-entry threshold or an explicit movement-intent signal is a candidate; neither has been tested here, and hysteresis alone must not be claimed to resolve incompatible goals. Do not alter the user's saved Blueprint or simply increase the exit threshold as a supposed fix.

Capture: `Saved/Diagnostics/CaptureAgent2Balance.py`; evidence `Agent2Balance.json`, `Agent2Balance_disabled.json`, `Agent2Balance_input_one.json` in the same directory. Blueprint read-only graph audit: `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt`. Editor returned to testNN, PIE stopped, no dirty assets.
