# Omni locomotion recordings

## Equipment variants — October 16

Separate candidate dataset: `Saved/MimicKitUEFN/equipment/dataset.json` and
`motions.yaml`: **54 clips**, 27 unarmed and 27 drawn. Each set has 14 run,
12 walk and one idle. The unarmed copies are byte-identical to the accepted
references. The drawn set was recorded from the Unreal NN with an actually
equipped sword, matching locomotion checkpoints and zero gaze, after two
seconds of settling. Moving captures are three seconds; idle is ten seconds.
Existing original idle is authored; drawn idle is an NN continuation with
zero movement input. Its small measured root motion was retained, not frozen.

Drawn retarget review: **http://127.0.0.1:8842/omni.html?set=drawn**.
The existing default viewer and original references are unchanged. The drawn
set uses the same best-loop selection, 15-body/34-DoF retarget and independent
foot-lift correction. No seam blending or joint-limit clamping was added.
All moving cuts pass the existing loop screening. Capture evidence and helper
scripts are in `Saved/Diagnostics/OmniDrawn20261016/`.

Reproduction: `Tools/Locomotion/RecordOmni.py` supports `--drawn`,
`--include-idle`, `--accepted-only` and a separate `--output`; then
`Tools/Locomotion/PrepareDrawnOmni.py` prepares the duplicate dataset and preview.
Recording requires its own temporary Play sessions; preserve the user's session
and restore the original map. No Unreal assets were saved during capture.

The user's later saved wrist limits were imported without regenerating motion.
The user subsequently authorized fitting all54 clips plus5% angular room:
current audit is `equipment/limit-verification.json`; exact changes and backup
are documented in `Docs/MimicKitUEFNBodyMatching.md`. Dataset entries contain
`sword_drawn`, but no policy
equipment input or active training configuration was silently changed. These
variants must not be mixed into training without explicit equipment conditioning.



Local viewer: **http://127.0.0.1:8841/**. Current gallery: **26 clips (12 walk / 14 run)**. Launch with the project Python:

`Labs/OmniLocomotionViewer/server.py`.



This is a separate read-only recording viewer. It does not alter the D/S lab,

training replayer, checkpoints or Unreal assets. Six recordings play together;

select a clip or Expand to inspect one. The time slider updates immediately,

arrow buttons step one 60 Hz frame, and playback supports 0.25x/0.5x/1x.

Drag to orbit, right-drag to pan and wheel to zoom. Cameras are shared.

The view follows horizontal root translation; vertical gait movement remains.

Loop capture repeats the entire three seconds and may jump at its boundary;

these captures have not been fitted into seamless loops.



## Recording procedure



`Tools/Locomotion/PrepareOmni.py` discovers the 30 real AnimSequences in Unreal

(14 Walk / 16 Run, including the offset and strafe variants) and measures each

clip's root velocity. Root rotation in all these source clips is identity.

The skeleton faces +Y in its local frame; the capsule's +X is not substituted.



`Tools/Locomotion/RecordOmni.py` owns temporary Play sessions only. It refuses

an existing user Play session and never saves assets. Each clip starts in a

fresh session with the user's current manager/models. It switches the recorded

agent to Kinematic, hides temporary equipment, disables that temporary actor's

Blueprint tick to prevent scene D/S/reset/input fixtures, and removes other PIE

agents. The normal native manager continues running. No native build/restart.



The existing full-body NN animation layer with zero blending plays 0.2 seconds

to populate both recurrent history frames from that clip. It is stopped with

zero blend-out. Only after the layer has actually retired do we count **120

game ticks of NN continuation**, then **180 further ticks** are recorded, including

both endpoints (**181 samples / exactly 3 authored seconds at 60 Hz**). No source

animation layer, replay interpolation, motion cleanup or fitting is inserted

into the recorded continuation. Normal NN presentation interpolation remains.



Movement direction comes from clip root displacement transformed into the

mesh carrier. Facing is held at the initial skeleton-forward direction.

Run/Walk input selects the matching lower checkpoint; checkpoint blend times

are zero and speed-based checkpoint overrides are disabled in the temporary

agent only. The current scene's automatic Run override otherwise selected Run

for walking clips; this was caught before accepting any Walk recording.

The selected checkpoint weights are checked at every captured tick.



Input amplitude matches source speed where possible within the normal native

directional limit. The RR-offset run clip is authored at 350 cm/s while the

native cap is 345 cm/s: it remains full input at 345, not an invented speed boost.

Both speeds are kept in metadata and the viewer's speed tooltip. Existing

runtime pose/root modifiers are retained: this is the presented Unreal NN

output, not an isolated raw-ONNX rollout or a Jolt/Chaos simulation.



## Evidence and reproduction



- `Saved/Diagnostics/OmniRecord20261015/clips.json`: source paths, durations,

  root velocities and rotations.

- One `M_Neutral_*.json` per capture: full bone transforms, root carrier,

  actual input, target/measured mover velocity, interpolation alpha, checkpoint

  weights and actual runtime contract paths. Original precision retained.

- `validation.json`: sample counts, speed errors, raw hashes and contracts.

- `Labs/OmniLocomotionViewer/data.json`: compact display copy (6 decimal places),

  generated by `Tools/Locomotion/BuildOmniViewer.py`; no temporal smoothing.



Use `Tools/RunUnrealRemote.py Tools/Locomotion/PrepareOmni.py`, then the same

runner with `Tools/Locomotion/RecordOmni.py`. `--filter` selects asset substrings;

`--skip-existing` skips completed capture files. Build viewer data after capture.

Timeout/error cleanup ends only owned Play and restores the previous FPS cap.

The renderer and quaternion math are reused read-only from SwordHolsterLab.



All 30 validated and loaded. Receipt: `Saved/Diagnostics/OmniRecord20261015/receipt.json`. Editor remains outside Play with its original dirty PoseAgent and FPS cap60. No asset saves, builds or restarts.



## Viewer axis correction — October15



Fixed missing local-Y sign conversion in the Omni viewer adapter. Shared D/S renderer expects X,-Y,Z after the world Y/Z swap; Omni originally supplied X,Y,Z, putting facial features behind the recorded head and reversing directional surface accents. Adapter now matches SwordHolsterLab.displayAxes exactly. Run BL recorded head forward remains within4.69–7.76degrees of skeleton forward in yaw; recording data unchanged. Verified corrected Run BL face/feet orientation in the live viewer. Shared renderer, D/S, Unreal and training untouched.


## Best full-stride cuts - October15

User requested showing the best cut for every motion, reserving seamless fitting for later and flagging only poor cuts. SelectOmniLoops.py finds the first prominent recurrence of the same named feet (18..96tick lag search), avoiding half-stride foot exchanges and later multi-cycle minima. Exhaustive integer start/end search within88..112% of that stride; edges retain two frames for velocity estimates. Score compares body-origin positions after root-horizontal translation removal, world rotations, translational/angular velocities, foot position, pelvis height and kinematic support proxies. Adjacent phases contribute40% to avoid an accidental one-frame match. Support is a low-height/low-vertical-speed proxy, not physics contact. Fixed review thresholds and full metrics are in the script/report; no learned quality guarantee.

All30 cuts pass screening. Durations35..39ticks running,53..61ticks walking. Worst selected seams across all clips: body RMS position0.968cm, RMS rotation1.749deg, max single-bone rotation3.879deg, foot displacement2.316cm, pelvis height0.299cm, velocity RMS22.83cm/s, angular velocity RMS37.45deg/s, zero endpoint support-proxy mismatches. These are tolerable unblended cuts for review, not seamless certification.

Saved exact indices/durations/root displacement/metrics in Saved/Diagnostics/OmniRecord20261015/loop-cuts.json; BuildOmniViewer embeds metadata without trimming or altering original frame arrays. Original captures/hashes validated. Viewer defaults Best cuts ON; card shows ticks/duration, tooltip seam metrics, orange warning only if a threshold fails. No smoothing, retiming, snapping, fitted endpoints or data replacement. Independent natural-speed grid loops; individual expansion and original-capture toggle retained. No Unreal/training/D/S changes.

## Lateral duplicate removal - October15

User accepted the cuts and removed Run LL, Run RR, Walk LL and Walk RR from the gallery. BuildOmniViewer excludes those four exact IDs on rebuild; offset variants remain. Original30 raw recordings and cut metadata are retained;26 clips are displayed,12walk/14run. No motion or cut changes.
