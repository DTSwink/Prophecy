# Kick foot floor penetration, September 22

Numerically confirmed in the saved testNN kickL loop after the kicking/non-kicking
profile update. Diagnostic runs started from stopped Play, preserved scene/Blueprint
settings, and ended only their own Play sessions. No gameplay code or asset changed.

The first 600-frame capture (`Saved/Diagnostics/ThighOutward-20260922-224649`)
records the right support foot/toe crossing the floor during an active kick in
kinematic mode. At frame470 the measured toe point reaches -0.834cm; the actual
Floor mesh top is -0.5cm (local top0, component Z-0.5). This is a bone point, not
a claimed full rendered-mesh penetration depth. NN presented/future and visible
mesh agree closely. Tempering itself is bypassed during active attacks.

The second 600-frame capture (`ThighOutward-20260922-224904`) includes117 Slash
steps with raw decoded output before presentation. Existing Blueprint config has
Set Kick Foot Joint Leeway=5cm, return1s. `ApplyKickExtension` in
`ProphecyNNPoseTypes.cpp` clamps axial displacement relative to the authored calf
end to `[0, Leeway]`, projects out sideways displacement, and translates the toe
with the foot. Consequently it also extends any NN calf shorter than its authored
length, regardless of the prior floor correction. There is no subsequent floor
test in this operation.

Offline replay of that exact function, using the captured calf orientation,
authored foot reference offset and raw Slash foot target, reproduces the published
foot position to at most0.000029cm over all captured attack steps. The unchanged
knee position agrees with the raw output too. Example: right support leg at0.85s,
kickL policy frame11 requests -4.52399cm extension (compression). Its raw ankle
Z11.29710 becomes7.31649, a3.98061cm downward correction. This identifies the
post-NN length correction, rather than inferring a cause from the screenshot.

This finding does not establish that the latest role mapping introduced the issue.
The offending function predates that change. Different recovery poses can expose
shorter source calves on later kicks. No claim that the NN itself requests floor
penetration, or that physics contact resolution is failing.

A correction must reconcile floor clearance with the permitted calf length and
preserve the accepted knee/recovery behavior. Simply lifting the final foot can
violate the joint/axis constraint; allowing compression changes the physical
leeway contract too. Neither behavior was changed during this diagnosis.

Evidence: `clamp-replay.json` in the second capture and
`Saved/Diagnostics/ReplayKickFootClamp.py`; tracing variables restored after capture.
