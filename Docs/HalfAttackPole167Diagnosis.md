# Half-attack knee pole at tick 167 — September 28, 2026

Current live Blueprint disables leg reconstruction in its Lower Special Ended callback. Diagnosis only: no runtime or Blueprint changes.

The `tick debugging` graph sets reconstruction enabled and configures a one-second recovery at 90 degrees per 60 game ticks. However, EventGraph Lower Special Ended -> Returning To Locomotion branch -> Sequence Then 0 -> Set Kick Locomotion Lower Body Tempering -> Blend Kick Locomotion Lower Body Tempering To Normal -> Set Kick To Locomotion Blend -> **Set Leg Chain Reconstruction, Enabled=false** (`K2Node_CallFunction_243`). The sequence branch has no kick-only condition. Thus a slash's full-to-half release also executes this setter. The following ordinary attack branch does not re-enable it.

Native regional dispatch starts leg recovery before calling the Blueprint event. Disabling reconstruction calls `ProphecyLegRecovery::Cancel`, removing the active recovery and its clock. Enabling reconstruction later alone would not recreate that canceled recovery. The relevant correction would be to prevent this disabling call on the desired recovery path.

Two identical bounded 235-tick owned captures reproduce SlashR starting at 144, full-to-half at 167 and completion at 189. Right target knee pole turns 18.29 and 20.03 degrees at ticks 169 and 170; the right physical knee follows at 17.71 and 20.15 degrees. The future target changes 38.31 degrees across the first returning NN sample. This is present in the animation target, not a separately originating physics disturbance. There is also an earlier right pole change during the full attack at 159–160; that precedes lower recovery and is outside this finding.

Recovery diagnostic switches PoleWindow, PolePresentation, PoleSmoothing and SupportSource all read 1. The opt-in smoothing trace produced no records during the replay, consistent with cancellation before any recovery solve. The earlier trace file is dated September 25 and is not evidence from this capture.

Evidence: `Saved/Diagnostics/Knee202/half165.json`, `half165_trace.json`, their `_nn.jsonl` files, and current `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt`. Capture helper: `Saved/Diagnostics/CaptureHalfPole165.py`. Both owned sessions ended; input and pole tracing were turned off. No build, full suite, asset save, or user Play interruption.
