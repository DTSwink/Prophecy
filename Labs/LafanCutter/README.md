# Lafan Cutter

## Loco collection retarget — October 19, 2026

Saved `Documents/Lafan Cutter/datasets/loco_uefn/dataset.json` as a separate
collection from the user's `loco`:12 clips,148,862 frames,41.35minutes at their
original approximately60Hz. Includes5 fall/get-up,4 run,2 walk,1 push/stumble.
Original cuts/manifest and canonical model/PHAT remain unchanged. No training.

Same accepted anatomical mapping, handedness,15-body/34-DOF projection and
foot solver described below. All117,159 requested foot corrections succeeded;
max correction13.29cm. Exact parity against the established locomotion export;
saved FK error<=1.431e-6m/1.126e-6rad and residual added foot penetration
<=0.0000549cm. All12 source/output frame counts, rates and hashes verified.
Current canonical model was independently checked against saved Unreal PHAT.
These are review candidates: poses can exceed PHAT limits and hands may shift
up to27.40cm through rigid-torso/hinge reduction. No hand-contact fitting or
automatic loop creation was requested/performed.

Viewer: **http://127.0.0.1:8875/**. All12 cards, playback/scrubbing, original
blue overlay and last row visually checked. Viewer renders only visible cards
while preserving playback time for offscreen clips. Original crawl gallery8874
kept separate. Server PID/log and buffers: `Saved/LafanLocoViewer`; retarget
reports, PKLs, intermediate BVHs and verification: `Saved/LafanLocoRetarget`.

Commands (existing robotics Python environment):

```powershell
& Saved/Robotics/env/Scripts/python.exe Labs/LafanCutter/retarget_crawls.py --dataset 'C:/Users/singerie/Documents/Lafan Cutter/datasets/loco/dataset.json' --output Saved/LafanLocoRetarget --name loco_uefn
& Saved/Robotics/env/Scripts/python.exe Labs/LafanCutter/verify_retarget.py --dataset 'C:/Users/singerie/Documents/Lafan Cutter/datasets/loco/dataset.json' --output Saved/LafanLocoRetarget
& Saved/Robotics/env/Scripts/python.exe Labs/LafanCutter/gallery.py 'C:/Users/singerie/Documents/Lafan Cutter/datasets/loco_uefn/dataset.json' --output Saved/LafanLocoViewer --port 8875
```

Native Windows BVH curator, following the Stepper NPZ Trimmer's dark interface,
OpenGL skeleton preview, trim handles and source/target workflow. Launch with
the **Lafan Cutter** desktop shortcut. No Unreal, browser server or training job
is required. Uses the existing Stepper Python 3.10 environment (NumPy, SciPy,
Pillow, PyOpenGL, pyopengltk and Tk); does not modify that environment or Trimmer.

## Workflow

1. Select **LAFAN Re-solved** (default, 77 clips) or **LAFAN1 original** (77 clips)
   on the left. Filter by name or choose another LAFAN-compatible BVH folder.
2. Select a motion to preview it. Drag the orange **In/Out** handles to trim;
   drag the highlighted upper band to move the range. The lower lane scrubs
   freely through the source. Numeric In/Out fields and Set In/Out allow precise
   edits. Frame numbers are zero-based and both boundaries are included.
3. Press **Add trim to dataset**. Collect multiple ranges from any source motion.
   Select a collected cut on the right to preview it. Reorder or remove draft cuts.
4. Enter a **Dataset name** and press **Save dataset**. Changing the name saves a
   separate collection. **Open** reloads an existing dataset.json or archived draft.

Space toggles playback, Left/Right step frames, I/O set boundaries, Ctrl+Enter
adds the trim, Ctrl+S saves. Editing text does not trigger playback shortcuts.
Mouse drag orbits, right-drag pans, wheel zooms. Follow pelvis is view-only.
Loop trim previews the selected range; uncheck to play the complete source.

## Files and preservation

User data: `C:/Users/singerie/Documents/Lafan Cutter/`.

- `datasets/<name>/dataset.json`: current dataset manifest.
- `datasets/<name>/revision_.../*.bvh`: actual self-contained motion cuts.
- Each revision has its own `manifest.json`, which can also be reopened.
- `session.json`: automatically recovered current draft and preview range.
- `drafts/`: unsaved selections archived when New/Open replaces the draft.
- `app-identity.json`: the running app's explicit Windows identity and icon handles.

Saving an existing name creates another revision and atomically replaces only
its current manifest after all files succeed. Previous revisions remain. Sources
are never overwritten. Each clip records source path/hash, inclusive frame range,
source rate and exported-file hash. Saved datasets reopen using their own BVHs,
even when the original downloads are moved. Source modifications after selection
cause saving to fail clearly rather than exporting a different motion silently.

Cuts preserve BVH hierarchy, channel values and original Frame Time. No smoothing,
retargeting, resampling, recentering, heading removal or robotic conversion occurs.
These are curation inputs for the later robotics/AE preparation. Original and
Re-solved skeletons differ; the manifest retains the source for each cut.

Preview follows the authors' translation convention: channels replace the rest
offset on translated axes. This is essential because Re-solved includes full
local positions for every joint; adding offsets again doubles bone lengths.
Original LAFAN likewise supplies complete root positions. Preview is Y-up, cm
converted to metres. Frame Time is honored as stored, including rounding in the
60 Hz export. Skeletons show the actual data, not a substituted mannequin.

## Sources

- Original: `C:/Users/singerie/Downloads/LaFAN1/` (pre-existing files, unchanged).
- Re-solved: `C:/Users/singerie/Downloads/LAFAN-Re-solved/bvh/` (77 BVH files).
- Author's repository: https://github.com/orangeduck/lafan1-resolved
- Author's BVH archive: https://theorangeduck.com/media/uploads/Geno/lafan1-resolved/bvh.zip
- Translation exporter: https://github.com/orangeduck/lafan1-resolved/blob/main/export_bvh.py
- Original data/code: https://github.com/ubisoft/ubisoft-laforge-animation-dataset

Original dataset licensing also applies to Re-solved and curated cuts; see the
source repositories. `download_resolved.py` records download/extraction status,
validates available space and rejects archive paths outside the destination.

## Desktop identity and verification

`install.ps1` creates the desktop shortcut with the scissors/motion icon and
AppUserModelID `Prophecy.LafanCutter.Desktop.1`. The native app sets the same
explicit process identity plus small/large Tk icons. A named mutex prevents
duplicate editing sessions; relaunching raises the existing window.

Run `test_cutter.py` with Stepper's Python. It checks known-coordinate FK (including
full translated-joint channels), real original and Re-solved cuts, exact channel
preservation, endpoints/single frames, named datasets/revisions, independent
reopening, failed-save preservation, source hashes, actual Tk callbacks, slider,
OpenGL pixels, playback and icon identity. GUI tests use a temporary data folder.
Evidence: `Saved/Diagnostics/LafanCutter20261016/`.

## Crawls collection and FBX import — October 17, 2026

Later October17 addition: full `recoveries/crawl_idle.fbx` appended to both
`crawls` and `crawls_uefn`; each now has four clips.48frames/30Hz; source SHA256
`c2c11c9bd05efc4b56792200f8a35b2f3293b6e5afc162d076a004073a5fc674`.
All three previous exported hashes remain unchanged. SDK/BVH position error
<0.000019cm. Imports/revision manifests retain the original FBX and receipts.
The existing gallery/draft was not restarted or overwritten by this import.
Current robotic AE/policy preparation is in `Labs/RoboticCrawlAE` / `Labs/CrawlTraining`.

`Documents/Lafan Cutter/datasets/crawls/dataset.json` now contains the user's
two Re-solved selections (ground1_subject5, inclusive 1503–7586; ground2_subject3,
5245–5376) plus the full `stepper/ue5/slashes/recoveries/crawl.fbx`: 55 frames,
30 Hz, timestamps 0–1.8 seconds. The two existing exported cuts retain their
exact SHA-256 hashes. A new revision was saved; the old revision remains.

`import_fbx.py <source.fbx> <dataset.json>` samples the installed Autodesk SDK at
the source frame rate, preserves global joint positions/orientations, and exports
full local translations plus ZYX rotations to BVH. Zero offsets avoid ambiguous
translated-joint offset conventions. It archives the original FBX and records
provenance and conversion checks under `imports/crawl_4f7f125b46b5/` in this dataset.
No retargeting, smoothing, heading removal, floor correction or training occurs.
The FBX has 89 source joints; a leaf Locator's non-unit display scale is retained
in the source FBX/report but not represented in BVH. Skeletal joint scales are one.
Maximum round-trip error: 0.0000362 cm position, 8.8e-12 rad rotation.

Read-only gallery: **http://127.0.0.1:8874/**. `gallery.py <dataset.json>` generates
the complete collection's position buffers into `Saved/LafanCrawlViewer`, then
serves `gallery.html` and existing LAFAN Three.js dependencies on localhost.
All three clips have independent playback/scrubbing, shared speed/play/restart,
orbit/zoom, fullscreen and optional helper joints. Narrow panels stack cards;
wide windows show all three side by side. Camera following changes only the view.
The server reads a dataset snapshot at launch; relaunch to display later saves.
Server PID/logs are in `Saved/LafanCrawlViewer`.

The already-running Cutter draft was deliberately left intact. Use **Open** on
the updated `crawls/dataset.json` before saving again from that old editing session.

## LAFAN to current locomotion rig — October 17

User requested the same retarget as current locomotion training for the two
LAFAN clips. Output: `Documents/Lafan Cutter/datasets/crawls_uefn/dataset.json`.
It contains two retargeted UEFN BVHs plus the byte-identical FBX-derived crawl.
The original `crawls` dataset remains unchanged. The gallery on8874 now shows this
new collection with an optional blue, uniformly scaled LAFAN source overlay.

`retarget_crawls.py` uses `Saved/Robotics/env/Scripts/python.exe`. First it maps
LAFAN joint directions/axial orientation to the actual UEFN reference skeleton,
including the established Stepper world/local handedness conversion. Directly
copying named rotations or using only a proper world-axis rotation is incorrect.
The four source spine orientations map to five target spines (Spine1 shared by
spine_02/03). Fingers omitted by the physics model retain UEFN rest locals.
Root translation scales uniformly by the target/source leg-length ratio,
1.04495068 and1.04494966 respectively; target bone lengths stay fixed.

Then the same current15-body/34-DOF locomotion projection is applied, including
the restored wrists and the unchanged `RetargetFootLift.py`. It preserves root,
projects elbows/knees onto the actual hinges, and removes only added foot-box
penetration. No hand-contact fitting, joint-limit clamp, PHAT change or trainer
change. The UEFN skeleton preview is reconstructed from the physical anchors,
as in the existing locomotion skin preview. The third clip stays its original
full UEFN skeleton; it has NOT been reduced into a robotic training export here.

Numerical exports and reports: `Saved/LafanCrawlRetarget/`. Two `.pkl` motions
contain40 columns (6root+34joint), original approximately60Hz timing, and CLAMP
semantics; paired NPZs retain before/after poses. Original sources, current
model/limits and locomotion preparation files remain unchanged. No training starts.

`verify_retarget.py` reproduces the accepted `M_Neutral_Run_Loop_B.pkl` exactly
(zero channel difference), verifies both saved crawl exports/FK to<1e-6m and
<1e-6rad, dataset/source hashes, and remaining added foot penetration<.00004cm.
All4536 requested foot corrections succeeded; maximum lifts4.893cm/1.944cm.
The final viewer was checked with all three clips, playback and source overlay.

These are review candidates. The current rigid torso/hinge reduction moves hands
relative to the full mapped UEFN pose by up to26.82cm/19.43cm in the two clips;
it does not preserve hand contacts. Some frames exceed current locomotion PHAT
limits; per-joint counts are in each report. Limits were not expanded. Forearm
axial rotation is also lost through hinge projection, although wrist world
orientation is retained to<.0001degree. The source overlay makes the resulting
differences visible; do not label these as contact-fitted or training-ready.

## October19 expanded loco collection

Current loco_uefn has474clips: twelve long retargets with the first420frames
removed, plus462 native omni/transitions. Viewer8875 filters/pages six at a time.
Old revisions retained. Conversion, exact trim/source verification, AE recipe and
material hinge-projection limitations are documented in ../RoboticMotionAE/README.md.

## Corrected MSE selection — October19

The474-clip expansion is superseded at user request. Current loco_uefn contains
64clips:12 existing trimmed retargets plus52 exact full-body MSE references
(48omni,2idle,2get-ups) from the stopped Physical Loco (2) deployment. Native
NPZ/transition imports excluded. Viewer8875 reflects this selection. See
../RoboticMotionAE/README.md for provenance and fresh AE training.
