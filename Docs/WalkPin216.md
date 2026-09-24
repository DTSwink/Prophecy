# Left Walk pin at tick216 — current setup, September24

Read-only diagnostic replay completed ticks180–230 on the current unsaved-editor
Blueprint; no settings, graph, code or asset modifications. Own PIE ended and
NN trace disabled. Captures use an isolated Python namespace and unregister on exit.

At215/216: raw NN logits left0.856031/right0.880445; hard gate left1/right0;
effective left0.941601/right0. Current checkpoint weights Walk1/Run0, no attack.
The sample timestamp is3.583333s (tick215), so216 retains the previous30Hz policy
step's applied pin rather than publishing a new one.

Connected Blueprint configuration in `tick debugging`: pin smoothing enabled,
PinInFrames3/PinOutFrames0; backward bound20–50cm, heading root7; transfer1.15.
Circle-bound and reach-guard nodes inspected in this graph are disconnected.
Raw limit/tolerance path remains wired (tolerance0). Node defaults alone must not
be mistaken for enabled calls; the export includes disconnected alternatives.

The hard gate selected right through213/214, then switched left at215. `SmoothPins`
sets a new target without instantly advancing its current value. The incoming
left pin therefore starts its three-tick ramp. `TransferBackwardPins` takes the
maximum of that smoothed value and the opposite geometric release times1.15.
This supplies the measured0.941601 floor, not an upper limit on a full pin.
At217/218 the own ramp is2/3 and transfer yields0.879474. At219 the hard winner
switches right again, clearing the left ramp immediately (out duration0).
There is no Run blend reducing these values. The left foot lies inside its own
full-strength backward region around216; raw/reach vetoes would zero the value,
not produce this partial weight.

Evidence: `Saved/Diagnostics/Pin216.json`, `Pin216-nn.jsonl`,
`CapturePin216.py` / `RunCapturePin216.py`, `AnalyzePin216.py` and the current
`Saved/BP_ProphecyManualPoseAgent.t3d` export summarized by
`InspectPin216Blueprint.py`. World geometry inspected after a policy evaluation
must not be substituted for that evaluation's held-foot/input-root geometry.
The diagnosis uses observed gate/smoothing/transfer sequence and actual applied
pin samples; no new native instrumentation or compilation was necessary.
