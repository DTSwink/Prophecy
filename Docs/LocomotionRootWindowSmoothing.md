# Future root-window smoothing

**Set Locomotion Root Window Smoothing** is a Blueprint function-library node with an **Agent** input and three factors, each in 0..1:

- **Distance:** distance of each future sample from the present root.
- **Direction:** travel heading relative to root0's orientation.
- **Orientation:** the sample's facing rotation relative to root0 (yaw).

All default to **1**, preserving the original forecast. **0** retains the previously filtered value; intermediate factors move that fraction toward the newly predicted value at each 30 Hz NN step. Angle channels take the shortest arc. These are smoothing factors, not durations. **Get Locomotion Root Window Smoothing** returns the configuration.

Root0 remains the anchor while constructing each window; it is not moved by the smoothing operation itself. The mover then advances to the **filtered root1**. Retained future local transforms follow root0's translation and orientation. Thus all-zero factors from an idle, collapsed window keep the agent idle even when movement/turn intent changes. If enabled while moving, zero retains the previous local step instead. A zero-length displacement retains the previous travel direction.

The setter seeds local history from the last window already sent to the NN when available. Before the first window exists, history starts collapsed onto root0. Setting all factors to 1 discards smoothing history and restores the original movement path. Invalid/nonfinite/out-of-range factors are rejected atomically.

Movement, reported actual velocity, angular history, travelled distance, and ordinary/authored-layer pose rebasing all consume the same filtered first step. The existing intent/acceleration model still generates candidate windows, but smoothing now also determines the movement committed from that prediction. **Get Locomotion Root Window** and future-window drawing expose the filtered NN inputs. Existing input-range clamping still applies.

State is allocated only for opted-in agents. No extra inference, Tick, timers or model copies are introduced. Default operation only checks for active smoothing state; polar/angle filtering runs on the eight future samples for enabled agents. This is a separate function library to avoid changing the live ProphecyAgent class layout when installing it through Live Coding.

The original forecast-only implementation was incorrect for the user's intended behavior: it held the window while advancing the actual mover through an unfiltered step. Its earlier moving-root test (`RootWindowSmoothing.json`) therefore does not validate the corrected movement semantics. The follow-up idle and root1-advancement regressions cover the corrected behavior. New-class Python wrappers were not regenerated live; fixtures invoke registered UFunctions through `call_method`. A normal build remains due when the editor is next closed, to incorporate the live patches into the base DLL before a fresh editor session or packaging.

Corrected validation (2026-09-13): same saved testNN setup, four seconds, all-zero interval: before fix 743.230619 cm root displacement and up to 500 cm/s; after fix 0 cm displacement and 0 cm/s (`RootIdleBefore.json`, `RootIdleAfter.json`). Controlled fixture verifies 0 cm idle drift, 0 degree idle yaw drift despite move/turn input, movement resuming with .3/.4/.5 factors, root0 advancing to the previous filtered root1 within 0.000027 cm, and restoring normal motion with all-one factors (`RootWindowMovement.json`). Corrective Live Coding patch installed successfully without editor restart or Blueprint asset edits.
