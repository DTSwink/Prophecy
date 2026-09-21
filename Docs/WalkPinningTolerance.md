# Walk pinning tolerance

**Set Walk Pinning Limit** takes Agent and Limit (default **2**), in signed raw
NN output units. **Get Walk Pinning Limit** returns the current per-agent limit.
Every agent starts at2, even before calling the setter. After normal Walk winner
selection and any tolerance fallback, each foot whose raw output is **strictly
greater** than the limit gets weight0. Equality remains eligible. There is no
winner re-selection or transfer: if the selected foot is vetoed, the other foot
can stay unpinned too. For example, raw2.5/3 with limit2 produces0/0, not0/1.

The veto applies to soft fallback weights as well as hard pins. Run and the
attack-specific/frozen-stage pinning paths are unchanged; during Walk/Run blending
only the Walk contribution is limited. Debug decoded/effective Walk weights
include this veto; Raw Network Output remains the original NN value. Finite
negative limits are allowed because raw outputs are signed. Nonfinite inputs
are rejected. Setting2 removes the sparse override without altering tolerance.
There is no tick, timer, extra inference, or persistent pose data; default Walk
processing adds two scalar comparisons and an empty-map check. Weak-agent entries
are released on world cleanup.

**Set Walk Pinning Tolerance** takes Agent, Tolerance (default 0), and Tolerance Fallback (default 0). Configure once or change at runtime. **Get Walk Pinning Tolerance** reads the per-agent settings. No Blueprint Tick wiring is needed.

The accepted Walk contract uses raw logits: two negative outputs pin both feet; otherwise the smaller raw output wins (equivalently, the larger decoded pinning probability). An exact tie selects the left foot. Tolerance zero preserves this selection, subject to the subsequent raw-value limit above.

With positive Tolerance, the exception triggers only when **both raw outputs are strictly positive** and `abs(left - right) <= Tolerance`. Tolerance is measured in raw NN output units, not cm or a probability percentage.

- Tolerance Fallback **0**: both weights become zero.
- Tolerance Fallback **1**: use the decoded soft weights `1 / (1 + exp(raw * PinScale))` instead of hard 0/1 selection.
- Intermediate fallback values scale those soft weights. Direct unbounded logits are not passed as projection weights.

Outside that condition, ordinary hard Walk selection remains, subject to the separate limit. Tolerance does not change negative/mixed signs. Run, attack/frozen-stage pinning, and near-ground thresholds are unchanged; the Walk branch already bypasses Run's near-ground forcing. During a Walk/Run policy blend, only the Walk policy's correction uses this option. Existing pinning debug output reports the resulting decoded/effective weights.

Invalid negative/nonfinite tolerance or fallback outside 0..1 is rejected without changing configuration. Zero tolerance removes stored settings. Weak-agent storage and world-cleanup removal avoid retaining destroyed PIE agents. The default path has an empty-map check; soft exponentials run only when the exception is active and fallback is nonzero. No extra update loop, inference or actor/component layout change.

Validation is limited to one small rule/boundary regression plus a short PIE setter check; gameplay tuning is left to the user.
