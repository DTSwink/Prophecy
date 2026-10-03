# Attack end extension

`Set Attack End Extension` configures one optional extra 30 Hz prediction at the natural end of an attack. It applies to full and half attacks. It is enabled by default.

| Pin | Default | Meaning |
|---|---:|---|
| Enabled | true | False skips the additional inference entirely. |
| Slash Threshold Degrees | 50.688107 | Minimum change in the ghost sword's pointing direction. |
| Hook Threshold Degrees | 50.688107 | Minimum change in the striking forearm's pointing direction. |
| Over Threshold Degrees | 50.688107 | Minimum change in the striking forearm's pointing direction. |

The angle must strictly exceed the threshold. Each attack can receive **at most one** extra frame (1/30 second). A threshold of 180 disables that family. Pikes, jabs, headbutts and kicks are unaffected. Left hooks/overs use the left forearm; right hooks/overs use the right forearm. Slashes use the configured sword hand and grip, including a skeletal socket if present. Sword axial roll alone does not count as a pointing change.

The default is 75% of the measured missing-frame sword turn in the October 1 second slash: 67.584143 degrees × 0.75 = 50.688107 degrees.

The check runs at the existing end boundary, after the configured post-Hit tail and any attack trim. An accepted prediction is committed through the ordinary attack publication path. The existing upper/lower end events and recovery therefore start after that extra frame. Odd 60 Hz trims retain their half-frame timing. Explicit Stop calls stop immediately.

No probe runs during ordinary locomotion or during the earlier attack frames. Accepted predictions are reused unless the input changed before the actual step, or active pelvis inertia needs its real stateful update. A rejected speculative prediction never publishes a pose or changes recurrent attack history; pelvis inertia state is restored after its preview. No additional checkpoint is loaded and no persistent tick or timer is added.

Verification evidence belongs in `Saved/Diagnostics/GhostEnd/`. `sword_direction_continuation.json` records the original measured missing frame; `verify_extension.py` captures the implemented behavior without changing the Blueprint asset.

## Verified October 1

Live Coding loaded the node. In the current two-slash setup, the first candidate turns 39.837864 degrees and is rejected; its ending remains frame 18/tick 187. The second candidate turns 67.584175 degrees and is accepted: frame 19 is published at tick 367, with the end at tick 369. Its final sword direction is 1.059711 degrees from the first swing's finish. Enabled/disabled replays have bit-identical shared attack predictions; disabled keeps both endings at frame 18.

Controlled tests with a zero threshold confirmed one extra frame for each left/right hook and over, no extension for pike/jabL, and preserved half-frame trim timing for slashLU. Invalid negative and greater-than-180 thresholds were rejected. Evidence: `Saved/Diagnostics/GhostEnd/extension_verification.json` and `family_verification.json`.
