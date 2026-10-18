# ShockwaveExplosion loop investigation — October18

## Spawn node — October18, installed and verified

User requested spawning either downloaded asset, uniform scale, source framerate,
density fade start, target density and duration; clarified play once and disappear.
`Spawn VDB Effect` is in Prophecy/VFX. Pins: Effect (Shockwave / Shockwave Explosion),
Location, Scale1, Framerate30, Density Fade Start3, Target Density0, Density Fade
Duration1; Rotation is advanced, and Spawned VDB returns the actor.

Density is1 until the delay, then interpolates linearly to the target; duration0
snaps. Nonnegative targets above1 are allowed. Timing uses60 unpaused game ticks
per authored second, including framerate progression (30 means half a source frame
per tick). No hitch catch-up or time-dilation acceleration. Both controls stay in
phase. The one-shot lifetime is the longer of the clip and the complete fade.
The final source frame is held if the fade extends past the clip; there is no wrap.
Afterward the actor and its playback controller are destroyed. Only density changes.
The node rejects editor-world calls, invalid/nonfinite inputs and unavailable assets.

Shockwave has120 frames/density only; ShockwaveExplosion180/density+temperature.
The exact two asset paths are selected by enum and their existing folder is added
to DirectoriesToAlwaysCook. Plugin code and existing actor/Blueprint tuning are
unchanged. Adapter binds validated reflected plugin properties once per spawn;
no per-tick reflection search or world scan. This avoids a broad dependency/SDK
define change to the game module because Zibra's material class is not exported.

Files: ProphecyVDBLibrary.h/.cpp, ProphecyVDBPlaybackComponent.h, ProphecyVDBTiming.h.
Native retained state required one normal restart. Current explosionVFX was backed
up, saved, and closed cleanly; no other dirty content existed. Seven-action normal
build passed (173.93s). A final implementation-only correction assigns the exact
target at/after the fade endpoint, avoiding endpoint arithmetic rounding. Loaded
through layout-safe Live Coding patch_0:2 compile actions/125.32s; patch link and
reload completed. The subsequent33-action normal bomb build incorporated this
endpoint correction into the base DLL. Current build/reload status is recorded
in [BombFuse](BombFuse.md): its later editor-only baker patch still requires a
minimal normal build before the next cold launch. No further editor closure now.

Final verification after that patch:
- `Prophecy.VDB.PlaybackTiming` passes (13:28:30UTC).
- Both owned Play cases pass166 sampled frames: Shockwave at60fps, density1→.25
  after.25s over.5s, destroyed at tick120; ShockwaveExplosion at600fps, density1→.2
  after.4s over.4s, holds source frame179 and destroys at tick48. Tests also check
  location, uniform scale, disabled native looping, one controller and invalid inputs.
- Editor5800 remains open on `/Game/explosionVFX`, outside Play; no dirty maps/content.
  Existing agent BP inspection: native_properties0, pin_types0, status3,
  wiring_preserved1. No repair or Blueprint wiring edits were needed.

Verification caveats: an owned headless process failed before tests because the
saved Fab tab attempted to open a disabled browser (`FFabBrowser::OpenTab` assertion).
It exited; verification used the normal interactive editor instead. Live Coding
reload emitted handled RigVM data-race ensures during CDO reference replacement;
the editor remained responsive, reload finished, then timing/Play/BP checks passed.
Do not describe that reload as warning-free or the failed headless run as a pass.

Evidence: `Saved/Diagnostics/ZibraFade/` contains normal build log, runtime-verification.json,
final-status.json, source verification scripts and the map preservation receipt/backup.
`verification-log.txt` retains compact timing/reload evidence; the live agent inspection
is `Saved/Diagnostics/LiveAgentTypes-Inspect.txt`. No packaged-build test was performed.
The separate explosion-impact event work stays paused.

## Earlier investigation

Historical state before the spawn-node work above: user paused the isolated explosion impact-event task to inspect the downloaded
ZibraVDB effect in `/Game/explosionVFX`. Interactive editor7604 is open on that map,
outside Play. Actor `ShockwaveExplosion` is native `ZibraVDBActor_3` using
`/Game/_mygame/animations/VDB/ShockwaveExplosion` and stock `ZibraVDBBBoxRender`.

Verified live settings:180 frames,30fps, Animate/Visible true, StartFrame0;
DensityScale/FlameScale/TemperatureScale all1. Channels are density and temperature;
FlamesChannel=None. Native playback uses Fmod(CurrentFrame+Framerate*DeltaTime,
FrameCount), always wrapping; there is no automatic temporal fade or loop toggle.
Installed source: Engine/Plugins/Marketplace/Pluginfoc9dbc05f9b82V5/Source/
ZibraVDBRuntime/Private/ZibraVDBPlaybackComponent.cpp.

Temporarily paused preview at final frame179 and took an editor-render screenshot:
`Saved/Diagnostics/ZibraFade/last-frame.png`. Smoke and its cast shadow remain
clearly visible. The source clip's nonempty ending plus unconditional wrap explains
the cut; no evidence of a shortened playback range. Playback and original frame
were automatically restored (capture-result.json); a second inspection confirms
Animate=true and unchanged controls. No settings or assets saved, no build/restart.
The temporary property scrub marked explosionVFX dirty; it was clean beforehand.
Leave dirty state intact rather than clearing possible concurrent user edits.

Minimal proposed fix, not implemented: fade the existing DensityScale and
TemperatureScale to zero over a short final portion (e.g. last30 source frames),
then restore authored scales at loop start or hide/stop after a single explosion.
FlameScale alone does nothing for this asset. DensityScale feeds both smoke and
shadow shaders. No VDB reimport or simulation rebuild is needed for this approach.
Depth Fade in the component is spatial intersection fading, not end-of-clip fading.

The impact-event task remains paused. Its isolated ProjectJournal.md records the
completed12-action build and5 passing tests, plus the pending rebuild/test of the
extra PHAT event and Blueprint-pin checks. Nothing has been installed into the
main project's native code/DLLs or Blueprint wiring.
