# Walk pinning tolerance

The raw-value Walk pinning limit was removed on2026-09-24 at the user's request. There is no setter/getter, stored threshold or implicit threshold2 veto. Ordinary selection, tolerance, temporal smoothing, geometric bounds/transfer and the reach guard remain.

**Set Walk Pinning Tolerance** takes Agent, Tolerance (default 0), and Tolerance Fallback (default 0). Configure once or change at runtime. **Get Walk Pinning Tolerance** reads the per-agent settings. No Blueprint Tick wiring is needed.

The accepted Walk contract uses raw logits: two negative outputs pin both feet; otherwise the smaller raw output wins (equivalently, the larger decoded pinning probability). An exact tie selects the left foot. Tolerance zero preserves this selection.

With positive Tolerance, the exception triggers only when **both raw outputs are strictly positive** and `abs(left - right) <= Tolerance`. Tolerance is measured in raw NN output units, not cm or a probability percentage.

- Tolerance Fallback **0**: both weights become zero.
- Tolerance Fallback **1**: use the decoded soft weights `1 / (1 + exp(raw * PinScale))` instead of hard 0/1 selection.
- Intermediate fallback values scale those soft weights. Direct unbounded logits are not passed as projection weights.

Outside that condition, ordinary hard Walk selection remains. Tolerance does not change negative/mixed signs. Run, attack/frozen-stage pinning, and near-ground thresholds are unchanged; the Walk branch already bypasses Run's near-ground forcing. During a Walk/Run policy blend, only the Walk policy's correction uses this option. Existing pinning debug output reports the resulting decoded/effective weights.

Invalid negative/nonfinite tolerance or fallback outside 0..1 is rejected without changing configuration. Zero tolerance removes stored settings. Weak-agent storage and world-cleanup removal avoid retaining destroyed PIE agents. The default path has an empty-map check; soft exponentials run only when the exception is active and fallback is nonzero. No extra update loop, inference or actor/component layout change.

Validation is limited to one small rule/boundary regression plus a short PIE setter check; gameplay tuning is left to the user.
