# Upper-body idle initialization

Agents now initialize their upper recurrent state from frame0 of the authored neutral `M_Neutral_Stand_Idle_Loop` in `training/slashes2/walk_run_sword_prep/authored_pruned_npz/walk_omni`. Previously startup used the identity/rest-offset FK base, which is a feature baseline rather than a valid authored idle and could place one arm up and the other down.

`Tools/NN/ExportProphecyUpperIdleSeed.py` generates `Private/ProphecyUpperIdleSeed.h`:90 floats containing ten local core rotations and the hand positions/hand rotations/elbow frames relative to the source pelvis. The source SHA256 and frame are recorded in the generated header. Its export checks both hand positions round trip to the authored world pose. No checkpoint or ONNX file changes.

Startup transforms this seed through each previous/current lower pelvis into the upper model's heading coordinates. Both initial published upper frames use the current idle seed, matching the already identical initial published lower frames. The saved physical-feedback seed also uses idle. The neutral upper FK feature base remains unchanged, so the first inference still receives the expected feature representation. Lower seeds, root placement and per-step inference behavior are unchanged. Reset-to-initial checkpoints naturally capture this new initial pose.

The data is compiled in and only used during initialization: no animation loading, warm-up rollout, new tick or per-frame lookup is added. Minimal runtime smoke: first presentation before the first30Hz policy update, then through0.15s; all three current-scene agents, finite poses and both hands below their shoulders. Evidence: Saved/Diagnostics/UpperIdleStartup.json.
