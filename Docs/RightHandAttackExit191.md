# Right-hand attack-exit motion — September 29

Diagnosis only; gameplay code and Blueprint settings were not changed. Six bounded 235-tick owned replays on the current unsaved `testNN` setup finished, with tracing disabled and PIE ended after each. No build or full suite.

The current SlashR begins at tick 144, is half mode by tick 171 in the NN trace, and exits at tick 191. Tick 180 is still attack-owned: the right target moves about 20.10 cm per world tick at 179–180, and the physical hand follows. Locomotion hand/core tempering does not control that portion of the attack.

At actual exit, three controls remain relevant even when the configured hand/core follow values start at zero:

- Upper Special Ended -> Set Locomotion FK Core Tempering (`K2Node_CallFunction_224`, zero) -> Blend FK Core To Normal (`222`, hold 0, duration 0.5 s) -> Set Locomotion Hand Tempering (`203`, all zero) -> Blend Hand Tempering To Normal (`204`, hold 0, duration 0.5 s). Zero is the initial value, not a maintained freeze.
- The same chain then enables **Set Attack Arm Return To Neutral** (`157`): hold 0, blend 1 s, speed 400. This procedural return runs after hand tempering and continues to move the hand even with both follow settings held at zero. The audit's first return sample has dt/elapsed/path step zero; subsequent samples advance the route. The configured 400 is distance-scaled once to approximately 142.06 for this attack, as documented by that node.
- Startup **Set Attack Upper Body Inertia** (`tick debugging / K2Node_CallFunction_162`) is enabled: response 0.82 s, hold 0, blend 0.08 s, momentum 0.69. Inertia is applied after core tempering. Separately, locomotion forearm clamp is enabled with 2 cm leeway (`tick debugging / 215`). The first exit target's forearm length changes from 26.7551 to 24.3492 cm; with the locomotion clamps disabled it is 26.5227 cm instead. The visible target already contains the disturbance; it does not originate solely in physics.

Measurements use future right-hand position relative to spine_05, to remove whole-character movement:

| Temporary owned-replay configuration | First exit change, ticks 190→192 | Change 198→200 |
| --- | ---: | ---: |
| Current setup | 3.2753 cm | 3.6685 cm |
| Hold hand/core tempering at zero | 3.2753 cm | 2.6728 cm |
| Hold zero and cancel arm return | 3.2753 cm | effectively 0 |
| Disable locomotion arm clamps only | 2.1841 cm | 3.6365 cm |
| Hold zero; disable return, upper inertia and arm clamps | 0.6385 cm | effectively 0 |

Overrides run from tick 190 in the diagnostic callback. The upper-end event can therefore enable arm return during the first exit evaluation; the diagnostic cancels it after that evaluation. The first return audit shows no path advancement on that evaluation. These experiments isolate the ongoing return and most of the initial disturbance, but do not establish the exact source of the remaining 0.6385 cm first-sample difference. There are small attack-to-locomotion spine-offset changes (largest about 0.52 cm at spine_02) in the captured geometry; a separate handoff investigation would be needed before attributing all residual motion to those offsets. No claim of a complete handoff fix.

Evidence: `Saved/Diagnostics/Knee202/hand180*.json`, associated `_nn.jsonl` captures, `hand180_comparison.json`, current `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt`, and `SlashReturnAudit` entries at 22:51:16 UTC September 28 in the editor log. Helpers: `CaptureHand180.py`, `CaptureHand180Ablation.py`, `CaptureHand180Audit.py`, `CompareHand180.py`, `Hand180ExitGeometry.py`.
