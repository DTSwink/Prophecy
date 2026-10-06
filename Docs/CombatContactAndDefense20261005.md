# Blocked sword and defense parity — October 5, 2026

**Superseded for sword contact:** the user reported that the proposed motor did not resolve the observed jiggle and requested removal. The contact motor, activation tracking, 64-iteration override and its dedicated test were removed; the original Jolt hand servo is restored. Measurements below describe the rejected experiment, not the current implementation. The separate defense exit fix remains.

## Blocked attached sword

The saved debug1=false scene reproduces an alternating right-hand angular velocity of roughly +/-10 rad/s once the blade meets the victim. Removing the victim removes the oscillation. The authored hand target is almost stationary; its orientation error is about 22 degrees, not a quaternion hemisphere crossing. The sword is welded collision/inertia on the physical hand, not an independently simulated sword body.

The former motor overwrote hand velocity toward the target before each solve. Contact and wrist constraints then opposed that velocity. At this lever arm and mass distribution the two operations formed an alternating limit cycle. More solver iterations alone made it worse. Restitution was already zero; changing contact slop, wrist damping, COM displacement or collision substeps did not solve it.

The welded hand now has a dormant six-axis position motor. A real positive contact impulse enables that motor, so the drive, wrist and contact solve together. Free motion retains the existing velocity driver. The motor uses 60 Hz critically damped springs and 64 velocity iterations only on its active island, with a 50 ms contact grace period. It preserves configured channel strengths, follow weights and gravity compensation. Unwelding/destruction removes the constraint. No new Blueprint setting is required. The contact flag does not manufacture gameplay Hit events.

Measured over ticks 200–400 in the original scene:

| Experiment | Peak hand angular speed (rad/s) |
| --- | ---: |
| Original velocity motor | 10.2143 |
| Original motor, 128 velocity/position iterations | 12.804 |
| Original motor, four collision substeps | 20.894 |
| Coupled motor, 32 velocity iterations | 2.4069 |
| Coupled motor, 64 velocity iterations | 0.1398 |
| Automatic contact activation | 0.1301 |
| Automatic version with preserved gravity compensation | 0.0810 |

Removing the blocking victim lets the hand resume reaching its target. This change does not soften magnetization values or alter NN output. The extra island iterations have a cost while weapons are in contact; this is not a claim of free global solver work or a many-agent benchmark.

## Dodge and Parry

The saved Blueprint's debug1=true branch actually forces **Kinematic every tick**. Debug2=false selects Dodge; debug2=true selects Parry. Physical tests used both scripted attacks with debug1=false and the existing reversible `Prophecy.Editor.PreviewFixedArmMode Physical` command for the exact Blueprint sequence. That preview was restored afterwards. No saved simulation-mode pin was changed.

Two independent comparisons were used:

1. Reconstruct cases from the latest saved replayers, including their exact first two poses, roots, fixed target, attacker samples and per-case skeleton geometry. Re-evaluate them using the installed saved checkpoints, then run those same tensors through Unreal's real NNE models and full recurrent native decoders. Dodge rows 0/2/5 and Parry rows 0/14/15 cover slashL, slashR and slashRD, walking/running and the Parry weapon input. Maximum errors across complete traces were 4.03e-5 for Dodge and 4.71e-6 for Parry across mixed input/state/rotation channels. These are numerical comparisons, not visual estimates.
2. Feed 39 actual live Dodge states and inputs back through the original Python trainer. Maximum pose-position error was 4.33e-7 metres and rotation-element error 1.08e-6. This independently verifies the live decoding path.

The replayer files are 50 Dodge steps and 25 Parry steps newer than the installed durable checkpoints. Their pixels cannot be asserted identical to older weights. The comparison regenerates the oracle using the installed weights. Using a different row's skeleton also produces centimetre-scale errors despite identical NN outputs; the fixture must include geometry. Parry's event means defense activation, whereas Dodge's event is the attacker Hit latch.

The first live slashL target was constant, with zero variation. Its learned root correction was only (0.170, 0.206) cm horizontally. Each next-step private root matched the preceding output exactly: neither capsule correction nor self-balancing discarded that learned movement.

### Actual exit defect

When an attacker emitted Hit, the normal locomotion batches had already skipped the defender. The defense exit then republished the *old* upper pose pair with a new timestamp. Interpolation went backwards for one game tick, forwards again, then resumed normal locomotion. This is visible in both defenses; it is not learned motion.

For the first slashL Dodge, tick213 spine velocity was (-2.43, 3.28, -2.08) rad/s; tick214 incorrectly became its exact opposite, and tick215 replayed the original direction. Parry did the same at tick212, reversing approximately (-0.23, -4.54, -9.17) rad/s.

Known Dodge deadlines now release ownership before the locomotion batches, so the real next locomotion sample exists on the exit frame. Parry learns the deadline later in the step; it fills only the skipped upper locomotion lane once. Other agents are not stepped twice. Active defense inference, checkpoint inputs and the configured Hit deadlines remain unchanged. Ordinary NN recovery may still turn back toward idle; this fix removes the spurious backwards/forwards replay, not that intended ownership change.

## Evidence and reproduction

Diagnostics are under `Saved/Diagnostics/CombatParity20261005/`. `physics_capture.py` records the original scene; `live_defense_capture.py` records owned transient Play sessions. Reproducible fixture builders are `Tools/NN/BuildCombatDodgeWitness.py` and `Tools/NN/BuildCombatParryWitness.py`, run from this project root using Stepper's Python. They require the pinned local replayers, checkpoints and training packs referenced in the scripts. `compare_live_training.py` in the diagnostic folder evaluates captured inputs through the original trainer. Native replay tests are `Prophecy.NN.Defense.CombatDodgeParity20261005` and `CombatParryParity20261005`; `Prophecy.Jolt.Servo.ContactDriveLifecycle` guards inactive free-motion equality, independent channel disable and teardown.

Final verification: normal Editor build succeeded; **42/42** native tests passed, including defense, servo, FK return, camera and attack-feedback checks. Both independent physical stress runs completed 1,200 ticks with finite body states and seven completed attack families; the exact Blueprint sequence also completed 300 ticks each in physical Dodge and Parry. Final blocked-hand peak was **0.080973 rad/s**, a **99.2%** reduction versus the original 10.2143 rad/s. `comparison.png` plots the blocked hand and both exit reversals. Free-motion transforms with a dormant contact drive are identical bit for bit in the native regression.

All editor restarts save dirty assets first and build the normal DLL before opening TestNN. No persistent launcher was added.

Final saved state: TestNN open outside Play, debug1=true and debug2=false. All eight simulation-mode pins match the original graph, all three editor actor positions are unchanged, and no content/map packages remain dirty. `final_verify.json` records this check.
