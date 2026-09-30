# Right foot at tick 131 — September 29

Reproduced with the user's current setup: physical-start enabled, full slashL starts at129, both feet initially use locomotion authoring. At131 the right foot releases **locomotion to attack**, while the left remains locomotion-authored. First attack prediction is at131 (Frame starts at1 before inference).

The physical-start implementation incorrectly reused the physical initialization sample as the preceding visible interpolation endpoint. The model was correctly initialized from physical pose/velocity, but the already-published locomotion interval continued through130. First attack publication then interpolated from the physical position sampled at129 instead of the published endpoint reached at130: a15.465cm mismatch. This caused the apparent pause and forward catch-up, even though the predicted next foot target itself was continuous.

Fix: keep the attack model and ghost seeded from physical pose/velocity, while initializing the visible-history cache from the existing published NN endpoint. No new sampling, per-tick work or inference. Full/half ownership rules and foot release settings unchanged.

Two completed155-frame captures, identical through130:

| Right foot | Before | After |
|---|---:|---:|
| Previous endpoint mismatch at131 |15.465cm|0cm|
| Physical forward travel130→131 |0.758cm|9.152cm|
| Physical forward travel131→132 |21.455cm|13.610cm|
| Physical COM forward velocity at131 |98.42cm/s|607.87cm/s|
| Physical COM forward velocity at132 |1211.50cm/s|732.79cm/s|

Future target at131 is exactly unchanged, confirming this fixes presentation history rather than modifying the checkpoint prediction. This does not impose constant velocity: the subsequent attack still decelerates the foot.

Live Coding loaded13:13:00UTC. Replay completed and owned PIE ended; no full suite, Blueprint edits or saves. Evidence: `Saved/Diagnostics/Knee202/foot131_before.json`, `foot131.json`, corresponding NN traces, and `Saved/Diagnostics/AnalyzeFoot131.py`.
