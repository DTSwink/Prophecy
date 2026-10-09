# Half-attack ghost lean at absolute tick 195

## Shared-target fix

The user requested both models see the same target. The inverse-mount correction
now runs once **before lower inference**, using the current ghost pelvis/spine
pose. Lower and upper histories and target heights use that shared frame; the
old separate upper remapping and lower preservation copy are removed. The red
marker now represents the target of both models. No additional inference or
allocation; no reflected node or retained model layout changed. Full attacks and
compensation-disabled/zero-clamp calls retain the original path.

In the same scene at absolute195, pelvis-to-nearest-foot horizontal separation
falls from 26.899 to 7.360 cm and ghost pelvis height rises from 69.452 to 92.692 cm.
Both models use the same target, 31.888 cm horizontally from the resulting ghost
pelvis. It is still 30 cm from the real pelvis after the clamp. Ghost pelvis and
feet positions are deliberately different; this is a change to prediction inputs,
not merely drawing. Ghost pelvis Y is392.288 versus477.086 before, and feet Y are
394.600/450.942 versus428.924/453.012. This is not a claim of full physical balance.

Replay through220 completed, with all6375 captured pre-attack bone positions
exactly matching the original. Attack starts170, Arms178, Hits196, last active207
in both runs. Evidence `Saved/Diagnostics/GhostSharedTarget20261008/`.

The native test compares both models' actual input arrays and all437 output values
against an ordinary full-model invocation with the compensated target explicitly
provided. This checks shared target semantics independently of the displayed
marker. All six focused native tests pass. Across four checkpoint families, both
single/distributed compensation modes match the explicit-target oracle exactly.
Clamp-only oracle conversion differs by at most1.193e-7 in lower input,5.961e-7
in upper input and2.139e-6 across the output; bounded float tolerances cover this
separate cm-to-metres expression. Disabled/full paths remain bit-identical. The
clamp fixture was corrected to use a radius beyond its existing target distance
(100cm had not actually activated the clamp).

Loaded through Live Coding21:11:21UTC, no object changes; normal DLL rebuild is
required before a future cold launch. Three incremental compiles each rebuilt
only the manager unity unit; the last two corrected tests only. Owned Play ended,
trace restored-1/0, graph byte-identical, preexisting dirty BP left unsaved. No
Blueprint/map edits or restart.

## Original diagnosis (superseded by the fix above)

Investigation only, October 8. Replayed the current TestNN Blueprint without changing settings; captured absolute ticks 85–220 and accepted native slash predictions. Player half slashL is at accepted attack frame 13 at absolute tick 195.

The ghost visualization combines two different target frames. Its pelvis and legs are the attack lower model's output, pursuing the original requested world point in the fixed attack anchor. Its red target marker is the accepted **upper** compensated target, inverse-mapped from the real locomotion pelvis and subject to the 30 cm minimum horizontal reach. The lower inference runs before that upper-only correction and never receives it.

At absolute 195 (centimetres, horizontal distances unless stated):

| Measurement | Value |
| --- | ---: |
| Ghost pelvis to displayed upper target | 28.956 |
| Ghost pelvis to lower model's accepted target | 185.189 |
| Separation of those two targets, 3D | 157.336 |
| Real pelvis to effective upper target | 30.000 |
| Ghost pelvis to feet midpoint | 36.561 |
| Ghost pelvis to nearest foot | 26.899 |
| Ghost pelvis height | 69.452 |

The lower target distance grows from 107.746 cm at tick 172 to 185.189 cm at 195, whereas the displayed upper target distance shrinks from 90.736 to 28.956 cm. Real locomotion carries the real pelvis forward while the ghost retains its separate attack trajectory. The lower prediction is therefore not a response to the nearby marker shown in the image. The target split is proven by accepted input data and the code paths; no counterfactual lower-target intervention was run, so its exact contribution to the lean has not been isolated from the rest of the recurrent attack trajectory.

Relevant code: `ProphecyNNSlashRuntime.inl` builds the original lower input, caches upper reach targets and substitutes that cache in `ReadAgentAttackGhost`; `ProphecySlashNative.inl` performs lower inference before remapping the upper held target; `ProphecyGhostAttackLibrary.cpp` applies the same visualization offset to all bones and the returned upper target. This is not an offset applied only to the marker. The split predates the latest defense delay/root-perception changes and was explicitly retained by the half-reach fix.

Next useful experiment, if a behavior change is requested: compare a consistent lower ghost target against the existing split while preserving the established upper reach correction. Do not assume simply feeding the already upper-compensated point into lower inference is equivalent: that point uses the predicted ghost pelvis and the inverse upper mount.

Evidence: `Saved/Diagnostics/GhostLean20261008/{capture.json,trace.jsonl,analyze.py,measurements.json,verified.json}`. Native accepted frame 13 is reused at tick 195; the gameplay Requested getter has already advanced, so measurements use the actual accepted lower input. All owned Play ended, trace cvars restored to -1/0, Blueprint graph byte-identical before/after, preexisting dirty Blueprint preserved without saving. No production code, motion settings, assets or build changed.
