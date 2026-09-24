# Left foot hover at ticks 260–270

Read-only current-scene diagnosis, 2026-09-24. No production code, Blueprint, or settings saved/changed. Owned diagnostic Play sessions ended; NN input trace disabled and callbacks unregistered.

The NN requests downward ankle motion through tick267: e.g. policy tick259 delta Z -3.8048cm, tick261 -3.0484cm, tick265 -1.5567cm. These raw poses penetrate the foot/toe support geometry. Normal floor correction raises the ankle, retaining the NN foot/toe rotations. It does not make the sole flat. No lower-body tempering is active; Walk weight1.

After that correction, the locomotion calf clamp in DecodePose pulls the ankle toward the knee to enforce rest calf length. With current knee/thigh orientation the required calf is too long. This lifts the already-ground-corrected foot; no subsequent floor planting undoes the upward shift. Offline replay of this existing clamp against captured published state matches the actual authored world endpoint to displayed precision (about 0.00001cm):

| Policy tick | Excess calf length cm | Clamp vertical lift cm | World ankle Z after clamp cm |
|---|---:|---:|---:|
|259|1.70542|1.47198|12.62388|
|261|1.95184|1.64561|13.61454|
|263|2.31849|1.85802|14.66320|
|265|1.66754|1.26721|15.02576|
|267|0.42339|0.30356|15.95845|
|269|0.04484|0.02886|18.10103|

These are ankle-joint heights, not sole clearances. The hovering introduced by the clamp is its vertical lift. Near the interval end the NN begins raising the foot (tick269 delta +1.3864cm), so not all later upward motion is the clamp.

At tick266 a second identical replay reads the target before/after disabling knee-pop smoothing on the same already-published pose, then ends diagnostic Play immediately. Foot change exactly zero; preceding captured endpoint positions identical to baseline. The rolled-back entry foot inertia is absent. Physical mesh follows authored foot within roughly 0.01cm here. Thus this is not a physical following lag or evidence against the accepted knee reconstruction. Pin strength only governs horizontal foot holding/roll correction, not a promise to keep Z at ground; it is1 through tick261 and later falls due to backward bound.

Evidence: Saved/Diagnostics/Hover260.json, Hover260-nn.jsonl, Hover260KneeCheck.json and corresponding capture/analyze scripts. AnalyzeHoverClamp.py gives the causal arithmetic without changing the rollout. Ground geometry analysis uses exact box minima, which differ about0.2cm from the production smoothed-side contact approximation; this does not affect the calf-clamp match.

A potential correction must reconcile knee position with the grounded ankle (or permit the extra length), rather than clamp the ankle upward. No solver/leg-chain changes made in this investigation.
