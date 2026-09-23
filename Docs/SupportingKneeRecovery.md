# Supporting knee recovery, 2026-09-23

The subsequent [supporting-foot height diagnosis](SupportingFootRecovery.md)
refines the source-follow weight described below. The captures here establish
knee orientation stability only; they did not check the early vertical reversal.

The current repeated kickL setup reproduced a large supporting-knee sweep and
additional knee jumps in kinematic playback. Over five complete returns, the
right knee's transported swivel spanned265.57degrees, with a65.88degree single
frame step. The thigh rotated30.86degrees in one frame.159 of366 locomotion
samples had the knee behind the foot's forward direction. These are measured
angles, not a claim that the captured knee completed an exact360degree turn.

The prior calf-tip check validated length/scale only and did not establish knee
orientation stability. Turning off the new length return did not remove the
sweep (258.01degrees), although some jumps were smaller. Turning off only the
existing grounded NN hinge guidance reduced the sweep to64.26degrees. Neither
ablation is retained: disabling guidance can restore the planted-thigh hitch.

## Cause and correction

The untempered NN foot and the displayed tempered foot have different headings.
At the first handoff the NN requested about67degrees of foot yaw while the
displayed foot followed about7degrees. The knee consumed the NN's turned frame
against the held foot, allowing its bend to drift behind that foot. Independently
interpolating source hip/ankle positions and thigh rotation also fails to preserve
a coherent intermediate hinge.

During existing active grounded tempering, align a copy of the NN leg source to
the displayed foot's horizontal heading. Rotate its ankle and thigh together
around its own hip; preserve its internal lengths and stance. Solve previous and
NN source hinges at the same final ankle before blending their bend directions
on that solution circle. Remaining thigh interpolation is twist about the shared
upper direction. Near-straight/antipodal guidance fades toward the prior hinge.
When foot heading is unobservable, fade source influence rather than partially
rotating yaw, avoiding a discontinuity at the +/-180degree heading wrap.

The guidance handover bound, knee-plane rule, floor/pin projection,15cm inner
reach, unclamped outer reach, calf return curve and interpolation remain in
place. This is shared geometry, with no kick-side/family gate, new timer, reflected
node or Blueprint change. Raised/frozen feet retain prior-hinge behavior; normal
modifier-free locomotion does not invoke this reconstruction.

## Evidence

`Saved/Diagnostics/CalfAnkleConnection-knee-regression.json` is the unchanged
current setup. Isolation captures use suffixes `knee-no-length-return` and
`knee-source-off`. `RecoveryKneeGeometry-knee-trace-baseline.jsonl` records source
and connected policy geometry. The direct mesh analyzer includes evaluated bone
rotation and scale; episode comparisons exclude initial spawn.

Candidate comparison: aligning intact hinges removes all159 backward samples
and reduces supporting-knee single-frame swivel65.88→7.83degrees. A blanket
guidance slowdown was rejected at this stage to preserve the earlier grounded
support response. The follow-up correction applies authored FeetRotation once to
both hinge and stance guidance, preserving the stance weight. Candidate-only modes and geometry tracing were removed
from production source after comparison.

Eight controlled episodes (three kickR, two kickL, two overL, one overR) preserve
the previously working kickR/overL behavior within small numerical differences
and reduce kickL supporting-knee swivel. These episodes disable only the owned
Play instance's actor Tick to replace its automatic attack trigger; they do not
change or save the Blueprint. The unchanged-scene capture is the primary evidence.

The kicking foot itself uses translation following0.7 in this setup and can move
about12cm in the first return frame. Its resulting rapid knee flexion also exists
with the new calf-length return disabled. This change does not silently slow that
user-authored foot trajectory. Do not claim every visible fast knee motion is
eliminated, or extrapolate kinematic captures to arbitrary dynamic collisions.

Final Live Coding build succeeded in30.28s. All23 focused tests passed at
19:43:22UTC, including a new recorded-fixture test: changing the NN source leg's
heading while retaining its internal stance leaves the displayed knee unchanged;
pelvis, ankle, rotation and returning calf length are preserved. A near-vertical
source-heading sign crossing remains continuous. Existing planted-hitch/stance,
raised-source, reach, pinning, pelvis-inertia and recovery tests pass unchanged.

Final unchanged-scene capture `CalfAnkleConnection-knee-final.json` has five
complete recovery windows: backward supporting-knee samples159→0 of366,
maximum supporting swivel step65.8816→7.8272degrees, maximum knee-to-foot angle
48.905degrees instead of reaching180. Maximum thigh steps45.4259→25.8963degrees
on the kicking side and30.8631→19.7643degrees on the supporting side. These thigh
angles include endpoint-driven swing and thigh twist, not just knee swivel.
Calf scale is constant through each return; first-tick tip-gap change stays below
0.00244cm and all final gaps below0.000001cm. Assertions in
`VerifyRecoveryKneeFinal.py` passed; results in `RecoveryKnee-final-verification.json`.
Owned diagnostic Play ended. No graph/asset saves or restart; this change is live
in the current editor and should enter the next authorized normal Editor build.
