# Right physical hand gap around128 — September29

Current physical rollout reproduced the gap: hand-to-presented-target distance3.556cm at128,3.928cm at129. The displayed raw NN target and authored physical target agree at these samples. Shoulder/elbow position errors at128 are0.395/0.553cm; forearm angular error is7.017°, hand angular error26.103°.

There is a confirmed target/physical length mismatch. At128 the authored elbow-to-hand length is23.79085cm; physical length22.44354cm. The target's locomotion forearm clamp allows rest22.349cm±2cm, while the physical wrist joint remains near its fixed rest offset. Physical hand in forearm-local coordinates is approximately(-22.4435,-0.0428,-0.0052)cm; target is(-23.7908,0,0)cm. The forearm angle error adds a transverse component to the wrist gap. This establishes the geometry of the discrepancy, but not the complete underlying cause of that angular tracking error.

Drive profiles remain L1/A1 and joint damping0 for upperarm_r/lowerarm_r/hand_r through entry139. Feedback tolerances change from1cm/23° to1000/1000 at attack entry, but these are feedback settings, not stronger physical drives. Gap already declines before entry (3.203 at136,2.225 at138), then1.943 at139,0.939 at141,0.608 at142. Target forearm length moves toward physical rest (24.349 at138,23.476 at141,23.102 at142), and forearm orientation error drops2.90°→0.63°→0.44°. The recorded catch-up spans several ticks; it is not an observed single-tick teleport or drive-strength increase.

Controlled changes affected only owned diagnostic PIE instances, starting95:

- Disable right-arm self-collision:128 gap3.556cm, effectively unchanged. Body self-contact is not responsible for this gap.
- Disable joint-limit prediction:128 gap3.55565cm, unchanged.
- Clamp locomotion forearm leeway to0:128 gap3.042cm;138 gap0.818cm versus2.225. It removes the length mismatch but does not remove the angular tracking error; it is not a complete fix.
- Disable right-hand angular drive:128 gap5.577cm, worse. This is diagnostic evidence, not a proposed setting.

Five completed165-frame owned captures ended; traces disabled. Attempted read-only PHAT constraint-property inspection is unsupported in the Python wrapper. A sword-collision ablation was prepared but did not start because user Play was active; that session was left untouched. Sword/external-contact versus other solver contributions to the remaining angular error have not been isolated. No gameplay code/Blueprint/assets changed, no build or full suite.

Evidence: `Saved/Diagnostics/Knee202/right_hand128.json` and suffixes `_no_arm_self`, `_zero_forearm_leeway`, `_no_hand_angular`, `_no_limit_prediction`, with corresponding NN traces. Script: `Saved/Diagnostics/CaptureRightHand128.py`.
