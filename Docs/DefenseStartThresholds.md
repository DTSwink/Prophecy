# Parry / Dodge start delays (supersedes Hit thresholds)

**Set Parry Start Delays** and **Set Dodge Start Delays** configure independent integer delays on the defending agent. Pins cover headbutt, hookL/R, jabL/R, kickL/R, overL/R, pike, slashL/LD/LU/R/RD/RU. Synthetic spear remains excluded; pike is the sword thrust.

- Every pin defaults to **0**: start at Armed, as before. Positive values count unpaused game ticks from the attacker's first accepted Armed output; 60 ticks are one authored second regardless of FPS or global time dilation.
- Delayed requests activate on the first normal defense NN step at or after the deadline. At the existing 30 Hz policy cadence, an odd delay can wait one additional game tick. There is no extra inference or off-cadence prediction.
- The delay is measured from Armed, not from the request. Requests made after the deadline may start immediately. Calling a setter changes pending/future starts but does not interrupt active defense.
- Continue using Start NN Parry / Start NN Dodge to request defense. Waiting preserves fresh two-pose history and does not take locomotion ownership.
- Negative values reject the entire setter. Existing post-Hit deadlines, attack-end cancellation, manual Stop and maximum-duration exits remain; a delay that misses the attack's usable defense window will not extend it.

The previous raw-Hit cache and per-prediction writes are removed. One manager tick counter advances with the existing game-tick budget, and each attack stamps its first Armed tick once. Start/wait checks subtract these integers. New attacks reset their stamp. Default profiles need no profile entry; no extra timers, tick delegates, per-agent countdown loop, bone reads or inference.

The native function names SetParryStartHitThresholds / SetDodgeStartHitThresholds remain only to preserve saved Blueprint function references. Their displayed names and pins are now tick delays. The one-shot editor command Prophecy.Editor.UpgradeDefenseTickDelays resets old fractional constants to zero (there is no meaningful score-to-time conversion), preserves execution/Agent links, and refreshes the root-velocity option. It is never run automatically at startup.

Tests: Prophecy.NN.Defense.StartTickDelays and Prophecy.Agent.TimeDilation.GameTickBudget.
