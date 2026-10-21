# Zibra VDB effects — performance and spawn controls

## Temperature and scattering colors — October19 installed and verified

Spawn VDB Effect and Light Bomb Fuse append Temperature Color and Scattering Color
as Linear Color pins. Defaults match the plugin: temperature(.99,.13,.011,1),
scattering(1,1,1,1). Finite nonnegative RGB is required; HDR values above1 are allowed.
These are solid colors, independent of the fuse Niagara. They are assigned before
VDB asset assignment/registration, using the plugin's existing color textures and
rendering work. No new shader pass or per-frame color update is introduced.
Non-default bomb colors live in one new non-ticking component until detonation;
default colors allocate no extra component. Existing retained layouts are unchanged.
Optimised tails inherit the already-colored prepared volume through their existing
handoff. Evidence/build and integration checks: Saved/Diagnostics/VDBColors20261019.
Initial five-action Live Coding build failed on an invalid FLinearColor validation
method; corrected to explicit finite-channel checks. Three-action retry passed113.50s,
reload12:00:22UTC, no restart. A_Bomb compiled/saved with all57 existing authored
pins/defaults/links preserved and two matching-default color pins added. Functions
now have12/23 parameters; existing native object layouts unchanged. Normal DLLs are
stale, requiring a minimal normal build before any cold launch.
Five isolated integration cases passed12:03:48UTC: both direct assets, delayed and
instant fuse forwarding, default colors, negative/NaN rejection, non-ticking deferred
storage and Optimised tail handoff. Blue smoke captures inspected. The initial
fixture accidentally selected an existing map VDB during the delayed-bomb check;
corrected by removing only the owned PIE copies of placed VDBs/automatic bombs.
No user map edits. Owned Play ended; callbacks retired and capture references released.
At12:04:46UTC the user had started a new Play with A_Bomb, Niagara and map dirty;
that session and those newer edits were left untouched.
There is no new recurring color work/pass; GPU time was not rebenchmarked for this
parameter-only change. RGB choices can still affect the existing renderer's work.

## Optimised checkbox — October19 installed and verified

`Spawn VDB Effect` and `Light Bomb Fuse` now expose **Optimised**, defaultfalse.
False preserves the previously installed quarter-render/eighth-lighting/step4 path.
True disables projected smoke shadows at spawn and, after the final source frame
has rendered at stable density/transform, reuses its prepared3D textures. Lighting
is fixed during that cached tail; fade still changes absorption and emitted colour.
The animated source phase is not a full-clip cache. Early fades that overlap the
animation remain live until stable, so the checkbox may offer little tail saving
when the effect disappears before it can cache.

The separate optional cache component preallocates a mesh/MID at spawn, waits for
an actual render and a nonblocking render-thread fence, then retires plugin ticking
and preparation. It does not wait synchronously or make periodic refreshes. The
original actor remains alive to own Zibra textures; the cached mesh is another
component on that actor, so normal expiry/early destruction clean up both. Moving
the actor resumes live rendering until its world-to-volume transform can be recached.
The existing playback controller owns authored60-tick timing and zero-density hiding.
No additional component/tick is created when the checkbox is off.

Our material companion is
`/Game/_mygame/animations/VDB/M_ProphecyVDBOptimisedTail`, reproducible with
`Tools/VDB/CreateOptimisedTailMaterial.py` and covered by the existing always-cook
VDB directory. The original plugin material/shader remain unchanged. Captured
shader density is preserved, including Zibra's internal1.5 multiplier; subsequent
fades multiply that captured uniform and cached colour by the authored density ratio.
The earlier Python prototype wrote raw node density and did not preserve that
multiplier, so use installed comparisons for exact appearance/performance claims.

Both pins were appended without altering existing retained native layouts. A new
non-ticking marker carries the bomb option to detonation. Live Coding6 compile
actions passed201.05s and reloaded09:54:56UTC; body-only density correction1 action
passed66.03s and reloaded10:07:26UTC. No restart. Current A_Bomb's56 existing authored
pins/defaults/links are preserved, plus one unchecked bOptimised pin; compiled/saved.
The comparison excludes compiler-generated ReceiveBeginPlay graphs, which get
regenerated on compile. Native10/21-argument functions verified. Normal DLLs remain
stale and require the documented minimal normal build before a future cold launch.
Verification evidence is in Saved/Diagnostics/VDBOptimised20261019.

Verification passed10:09:50UTC with one volume at a time. Off retains expiry240;
ShockwaveExplosion/ Shockwave cache at ticks92/62 and expire240, with correct
shader density, emission ratio and NoCollision. Overlapping fade stays live and
expires120; early zero skips caching, becomes invisible and expires60. Full-density
and half-fade captures inspected. PlaybackTiming automation passed09:58:57UTC.
Instant bomb forwarding off/on passed10:12:10UTC, no fragments or sparks, tiny
isolated physical force; the full interactive bomb suite was not run.

Installed GPU captures at held/fading ticks150/210: off preparation4.712/7.118ms
plus scene translucency1.378/1.169ms; on has no VDB preparation pass and scene
translucency2.331/.820ms. These are sampled pass costs in the diagnostic scene,
not gameplay FPS, and compare the complete checkbox behavior including its
projected-shadow difference. Owned sessions ended, profiling CVar restored,
editor26816 stays open on explosionVFX. Checkbox left off for the user's comparison.

## Deeper performance investigation — October19, findings and controls

This follow-up is an investigation, not another installed quality change. Owned
sequential comparisons use one volume maximum. Inspected installed plugin C++/shaders
and both assets; tested then **restored** a shader experiment. A separate duplicate
material tests retaining the final prepared 3D volume while fading in its raymarch
material. It does not replace the user's material or change the production adapter.
No C++ build/restart, Blueprint edits or user-asset saves. Normal DLLs still require
the previously documented incremental build before a future cold launch.
Five successful comparison runs completed. Temporary cached-tail material deleted
and absence verified09:36:04UTC; original plugin shader restored byte-identical and
recompiled. Editor26816 remains on explosionVFX outside owned Play, profile CVars
and background throttle restored. No experimental runtime change remains installed.

**Startup constraint:** the user accepts a modest hitch at effect startup only.
Periodic expensive refreshes are not acceptable. Whole-sequence precomputation at
spawn has not been measured and must not be promised as a small one-frame hitch.

### Why faint smoke stays expensive, and why the cost returns

The current bomb settings are source120fps, fade start3s, duration1s. The180-frame
clip reaches its last frame at tick90, holds until tick180, then fades through240.
Our installed adapter caches lighting during the hold but **disables that cache at
the fade start**. The visible shape is unchanged, but two GPU passes return:
VolumeDownscale (roughly2.5ms here) and ComputeDirectShadows (roughly1.2ms).
This transition is caused by our fade handling, not by new visible smoke appearing.

Even with lighting reused, Zibra calls ComputeRenderBlocks every rendered frame.
It rebuilds the lit colour texture. DensityScale changes absorption/emission, not
the sparse block list. At1% density the same blocks are prepared and traversed.
Ray traversal can also increase as smoke gets thinner: the shader stops early only
when summed RGB transmittance falls below.001. Fainter smoke reaches that less often.

There is a further trap in the resolution setting: ComputeRenderBlocks evaluates
each source voxel's colour/lighting, THEN averages. Quarter resolution averages64
source samples per output voxel; eighth averages512. It saves output texture space
and ray sampling cost, but does not avoid visiting the source voxels. Eighth was
slower than quarter in the preparation pass in these controlled samples.

### Measured follow-up

Same RTX4060 Laptop8GB, fixed1000x650 SceneCapture2D, one ShockwaveExplosion at
scale.3, final frame179. Each case holds density1/.1/.01 for60ticks each. Current
quarter render/eighth lighting/trilinear/step4 settings with lighting recomputation
represent the installed fade path. Numbers below are **GPU pass times**, not total
frame time. Graphics queue/CSV totals include other scene/UI costs and occasional
large unrelated stalls; do not derive precise FPS or additive savings from them.

At density.01, the repeated unmodified case measured:

| GPU work | ms |
| --- | ---: |
| Density grid downsampling |2.521|
| Lighting/self/received shadows |1.193|
| Colour blocks, including padding |4.465|
| Total VDB preparation |8.181|
| Scene translucency, dominated by this VDB |1.336|

Thus near-invisible smoke still costs about9.5ms in these passes. This does not
include animation decompression, because the final source frame is held. The
earlier30ms figure was the whole capture, not this effect alone.

Temporary shader experiment: use eight stratified colour samples per output voxel,
retaining exact original density-only/HV averaging. Quarter-resolution colour-pass
measurements at densities1/.1/.01: unmodified2.644/4.411/4.465ms versus trial
.650/.892/.957ms. Eighth at density.1:6.393→.310ms. With held-frame lighting reuse,
quarter colour/preparation measured3.481–4.256ms versus.639–.688ms in the trial.
These are pass-level gains; total-frame gains were smaller and noisy.

Smoke shape/shading looks close in inspected fixed views. The fire capture gains
visible fine grain; animated shimmer and other views/assets are **not validated**.
This is an opt-in quality candidate, not a production-ready identical replacement.
Original shader restored byte-for-byte and RecompileShaders Changed completed;
the final comparison was run using the restored shader, confirming the expensive
pass returned. No experimental shader remains installed.

### Successful prepared 3D tail prototype

Once the source animation has ended, retain its existing density/colour/index 3D
textures and bounding-box mesh. Stop Zibra preparation and render the same volume
through a separate material instance. Fade absorption with DensityScale and scale
the integrated colour by the same fraction (source colour prepared at density1).
This preserves volume sampling and depth; it is not a camera-facing image. It
freezes self/received lighting from the prepared frame, so thin smoke can remain
darker than it would with freshly recomputed self-shadowing.

The original plugin shader was in use for this test. One final source frame179,
same camera/scale/resolutions as above; density1 held for60ticks, then linear fade
to.01 over60ticks. **Projected shadows disabled in every compared case**; do not
claim this benchmark preserves the production actor's projected shadows.

| Matching phase | Current-style preparation + scene translucency | Cached 3D tail |
| --- | ---: | ---: |
| Half density |8.152 +1.280ms|No preparation passes;1.006ms translucency|
| Density.0833 |7.971 +1.255ms|No preparation passes;1.410ms translucency|
| Density.01 |7.504 +1.206ms|No preparation passes;1.300ms translucency|

These are measured GPU scopes in this setup, not whole-game frame times. There
are no periodic refresh passes after the handoff. This proves the held/fading
tail path, **not the animated fire phase**, full-clip caching or a production
implementation. The prototype retains its hidden, tick-disabled original actor
to own the textures; destroying it releases the resources despite MID references.
Resource ownership, handoff synchronization, zero-density cleanup, projected
shadows and both assets need production handling before installation.

The retained textures in this case are150³ RGB(R11G11B10),150³ density(R8),50³
max-density(R16F),109×85×103 block indices(R32_UINT), and a4-texel transform.
Their combined raw payload is about19.97MiB for this frame, excluding working
buffers/alignment. The prototype reuses existing textures; it allocates no full
sequence cache. Extrapolating this one frame to90/180 unique frames would be
roughly1.75/3.51GiB, **not a measured cache size**. Actual frame occupancy varies.
A full animated cache needs a separate memory budget, compression/streaming design
and measured startup/upload cost.

Follow-up09:34:39UTC repeated all three cases through native SetDensityScale,
avoiding editor property notifications, and moved the camera90degrees around the
volume. Captured views confirm depth/parallax and continued fading. Cached-tail
preparation remained absent; translucency at half/.0833/.01 density was
1.332/1.333/1.205ms. Live preparation was9.482/6.261/8.004ms, plus
1.467/1.038/1.208ms translucency. Static-lighting-only preparation remained
4.364/3.416/3.807ms (colour blocks).

This also resolved a diagnostic trap: set_editor_property(DensityScale) during a
continuous fade invalidated lighting even with static illumination enabled. Native
SetDensityScale did not. The production adapter writes the native property directly;
its explicit disabling of static lighting during fading remains the reason those
passes return there. Do not use the editor-property static-lighting fade case as a
prediction of the native setter's cache behavior. CSV window summaries are diagnostic
only; GPU scope captures are the evidence used for the pass-cost claims above.

### Existing knobs: where they live and what they actually do

Select a Zibra actor's **MaterialComponent**, then use Details > Volume. These are
native plugin properties, not new pins on Light Bomb Fuse. Our spawn adapter currently
sets render resolution/lighting resolution/main step at spawn and owns density and
lighting-reuse timing. Editing a separately placed VDB actor does not change bombs.
Persistent bomb tuning would need a performance profile forwarded before asset
assignment; do not imply the complete list below is already on our spawn node.

| Details section / control | Current spawned effect | Performance effect / tradeoff |
| --- | --- | --- |
| Render / Volume Resolution |1/4; options1,1/2,1/4,1/8|Lower output memory/detail. Current averaging still visits all source voxels;1/8 was not faster overall here.|
| Illumination / Illumination Resolution |1/8; same four options|Smaller lighting grid/shadow dispatch. Already at the lowest exposed resolution. Density downsampling still reads full source.|
| Render / Ray Marching Filtering |Trilinear; alternative None|None skips padding pass and reduces texture memory; introduces voxel/block edges. No reliable major total win in this scene.|
| Illumination / Main Step Size |4; range.1–8|Larger skips ray samples.8 reduced the ray pass modestly, leaving expensive preparation intact. Can miss detail.|
| Illumination / Max Main Steps |256;32–1024|Caps **block traversal iterations** in this implementation, not simply total voxel samples. Low values can cut off deep portions of the volume.|
| Illumination / Use Static Illumination |On while held/stable; off during fade|Reuses lighting until source-frame change. Large held-frame saving, but changing density/light/occluders can leave stale shadows. Colour preparation still runs.|
| Decompression / Allow Skip Decompression |On|Skips unchanged source frames. Turning it off adds work; it does not improve average performance.|
| Shadows / Enable Directional, Point, Spot, Rect Light Shadows |All on|Independent self-shadow toggles per light type. Disabling skips density raycasts for those lights; smoke loses internal depth.|
| Shadows / Self Shadow Step Size |1.5; range.1–8|Larger reduces self-shadow sampling; can cause light leaks/banding.|
| Shadows / Max Self Shadow Steps |128;8–1024|Lower cap reduces worst-case shadow traversal; may truncate shadows.|
| Shadows / Received Shadows / four light-type toggles |All on|Controls scene objects casting shadows into smoke. Separate from smoke self-shadowing.|
| Shadows / Received Shadows / Smooth Received Shadows |On|Off changes seven VSM samples to one per lit voxel/light. Removes smoothing; still receives shadows.|
| Shadows / Projected Shadows / Enable Projected Shadows |On|Turns smoke's shadows on the scene off; removes its light-function participation. Separate from internal/received shadows.|
| Shadows / Projected Shadows / Enable For All Lights; Light List |All lights; empty manual list|Restrict projected shadows to selected lights instead of every relevant light.|
| Shadows / Projected Shadow Step Size; Max Projected Shadow Steps |4 and128; ranges.1–8,8–1024|Larger steps/lower cap reduce projected-shadow raymarch cost; shadows may lose detail or truncate.|
| Illumination / Ambient / Ambient Lighting Mode |Sky Atmosphere; Constant/Disabled alternatives|Disabled skips ambient/AO branch; changes smoke lighting substantially. Constant still runs AO.|
| Illumination / Ambient / AO Steps Count |2;1–16, six directions|1 halves AO density samples. Only a portion of the lighting pass.|
| Illumination / Ambient / AO Intensity; AO Radius |1 and.04|Appearance controls. **AO Intensity0 does not bypass AO sampling** in the shader.|
| Illumination / Ambient / Ambient Light Intensity |1|Zero disables ambient branch in the proxy. Equivalent performance caveat to disabling ambient: smoke becomes differently lit.|
| Illumination / Directional, Point, Spot, Rect Light Brightness |All1|Zero excludes contribution/calculation for that light type; intermediate values mainly change appearance.|
| Illumination / Lighting Channels |Default channel|Restrict which lights affect this volume. Helps when many lights overlap it.|
| Render / Culling / Allow Frustum Culling |On|Normal culling can skip colour/lighting for out-of-view volumes; decompression may remain for projected shadows.|
| Render / Culling / Full Frustum Culling |Off|Also skips out-of-view preparation/decompression. Reflections/offscreen shadow contribution can disappear.|
| Render / Culling / Max Draw Distance |0 = unlimited|Distance cull; threshold uses camera-to-bounds distance. Reflection participants bypass normal distance culling unless full culling is enabled.|
| Render / Culling / ZibraVDB Bounds Scale |1|Controls culling bounds, not voxel resolution. Too small causes popping/clipping.|
| ReflectionManagerComponent / Reflective Meshes |Empty|Nonempty enables extra reflected-volume preparation. Keep empty if unnecessary.|
| ReflectionManager / Reflections Resolution |1/4|Lower resolution reduces extra reflection texture/cost when reflections are active.|
| ReflectionManager / Max GDF Raymarch Steps; Max Volume Raymarch Steps; Min Volume Raymarch Distance |64;64;.01|Reflection-only traversal controls; no benefit while Reflective Meshes is empty.|
| Playback / Visible |On until zero/finish|Actually removes all effect rendering when false. Animate=false merely holds a frame and does not remove rendering cost.|
| Spawn node / Framerate |Bomb120|Changes animation speed/lifetime. Lowering it is not a timing-preserving optimization. A separate update cadence would hold sampled frames while preserving timeline speed.|
| Spawn node / Density Fade Start, Duration, Target |Bomb3,1,0|Control visible lifetime; low positive density is not a performance cutoff. Current adapter hides only at exactly zero.|

Other appearance controls found: DensityScale; ScatteringColor/gradient/mode;
AbsorptionColor; TemperatureScale/color/gradient/mode; FlameScale/color/gradient/mode;
ShadowIntensity; ProjectedShadowsIntensity; emission-mask enable/flame/temperature
toggles, center, width, intensity, ramp; sphere-mask enable, position, radius,
falloff; depth-fade enable, distance, opacity. These do not shrink the source sparse
block list or automatically switch off rendering. Both assets lack an independent
flames channel, so FlameScale is not a useful control for these clips. Translucency
sort priority/offset and first-person mode are ordering/presentation controls, not
the performance bottleneck. The Heterogeneous Volume switch and its Step Factor,
Shadow Step Factor, Shadow Bias Factor, Lighting Downsample Factor, Cast Shadows
and Emissive Light Source controls belong to the alternate renderer; no HV migration
was tested or installed.

Asset-side controls: compression Quality0–1, per-channel quality and active channels
when importing **OpenVDB**. Both downloaded assets are precompressed ZibraVDB with
empty OpenVDB source paths, so this is not currently a live recompression knob.
Obtaining/downsampling the original source before compression would reduce source
voxel work, unlike changing the render-volume resolution alone. Compression/channel
changes need an actual reimport and quality validation, not just a runtime scalar.

### Changes worth implementing next, in order

1. Offer **Cache Final Volume** for held/fading tails, based on the tested 3D
   prototype above. This is the largest demonstrated tail saving, but fixes the
   lighting during the fade and needs explicit projected-shadow handling. Prepare
   the rendering objects at spawn and reuse the already-prepared final frame;
   do not schedule periodic rebuilds or promise zero handoff cost without measuring.
2. Cache the **unscaled density grid** independently of lighting. Its shader has
   no DensityScale input; same source frame/channel/resolution can reuse it during
   a fade while still recalculating correct lighting. Current wasted pass is around
   2.5ms here. Must invalidate on source/resource/channel/resolution change. This
   saving is inferred from code/pass cost, not yet an implemented benchmark.
3. Cache prepared colour blocks when all their inputs are unchanged. Existing
   lighting reuse alone does not do this. Must handle density, colours/curves,
   emission/masks, texture allocation, source frame and illumination invalidation.
4. Expose a bounded colour-sampling quality setting (full / sampled). The temporary
   eight-sample result proves substantial headroom, but fire grain/temporal aliasing
   require validation. Do not silently replace the full-quality path.
5. Expose a user-controlled low-density render cutoff (0 disables it), optionally
   with a short final fade, to stop paying for near-invisible tails. A positive
   density threshold is an approximation, not a screen-space visibility proof.
6. User subsequently clarified that only a modest **startup** hitch is acceptable;
   recurring refresh hitches are not. Do not use a low update cadence as the remedy.
   Prefer work prepared once and reused, or an offline-baked bounded3D cache.
   Precomputing an entire animated sequence at explosion time has unmeasured startup
   latency and memory cost and must not be presented as a small guaranteed hitch.

These are proposed production controls/renderer changes, **not installed nodes**.
The exact density-grid cache is the first improvement that preserves dynamic
lighting. The final-volume prototype demonstrates larger savings with fixed lighting.
Our previous quarter/eighth/step4 adapter remains installed unchanged.

Evidence: Saved/Diagnostics/VDBPerformance20261019/DeepBenchmark.py,
ShaderExperiment.py, ShaderTrialBenchmark.py, ShaderRestoredBenchmark.py,
AnalyzeDeep.py, CreateCachedTailMaterial.py, CachedTailBenchmark.py,
CachedTailNativeBenchmark.py and corresponding JSON receipts/profiles; raw CSVs in
Saved/Profiling/CSV/VDBDeepBenchmark.csv, VDBShaderTrial.csv, VDBShaderRestored.csv,
VDBCachedTail.csv and VDBCachedTailNative.csv. Cached-tail density windows differ
from the earlier stepped-density run: the middle window is a fade, not density.1.
Shader receipt records originalSHA256
e4979b2b0a086d128f08ecb786d6d1460438a334580065e0b988d1e09d32efe9 and active=false.
Kept only selected smoke/fire/near-invisible views; no videos or large full-clip cache.
Installed-source audit: ZibraVDBMaterialRendering.cpp (preparation/cache conditions),
ZibraVDBComputeRenderBlocks.usf (full-voxel averaging), ZibraVDBVolumeDownscale.usf
(density grid independent of DensityScale), ZibraVDBShadows.usf (AO/shadow loops),
ZibraVDBBBoxRaymarch.ush (transmittance early exit). Vendor overview, checked against
installed source: https://www.zibra.ai/blog-posts/zibravdb-performance-and-quality-optimization.

## Gameplay performance — October19 installed

User requires true 3D and prioritizes low cost. `Spawn VDB Effect`, including calls
from `Light Bomb Fuse`, now selects quarter-resolution render volume, eighth-resolution
illumination and main ray step4 before assigning the asset (avoids first allocating
the default full-resolution rendering textures). Trilinear filtering, existing
ray-step cap, lights and shadows remain. Source files, animation rate, transforms,
density controls and one-shot lifetime remain unchanged. Fine smoke detail is softer.

Zibra already caches unchanged-frame decompression. The adapter now enables its
current-frame illumination reuse while density is stable. Source-frame changes
invalidate that cache automatically. Reuse is disabled throughout a fade, including
its exact endpoint, and for a zero-duration density snap; re-enabled the next tick.
This avoids stale shadowing during fades on a held final frame. Lighting changes
from moving lights/occluders can remain frozen while the same source frame is held
at constant density: this is the deliberate caching tradeoff. No whole-clip prelit
cache is stored; render-block preparation and volume ray marching still run.

When density reaches exactly zero, the two supported density/density+temperature
clips have no independent flame emission. Hide the actor AND set plugin playback
Visible=false to stop volume/decompression/projected-shadow work, while preserving
the original actor lifetime. No independent-flame asset is supported by this enum.
Property searches happen only on spawn/fade boundaries, no retained layout changes.
The plugin's rendered bbox and HV components explicitly use NoCollision; physical
blast/debris remain separate and unchanged. No engine/plugin edits.

Controlled comparison: RTX4060 Laptop8GB, one ShockwaveExplosion, scale.3, fixed
1000x650 SceneCapture2D, source120fps / fade start3 / duration1 / target0 (current
A_Bomb node values). PIE bomb copies removed before ignition; only one VDB at a time.
Matching GPU Profile graphics queue times in ms:

| Phase | Stock | Optimized | Stock repeat |
| --- | ---: | ---: | ---: |
| Source moving |47.74|33.96|47.36|
| Last frame held |41.41|22.25|41.58|
| Density fading |40.09|28.84|43.14|

These include the capture's scene/UI overhead, not an in-game FPS promise. CSV
means confirm a smaller moving-phase improvement (33.56→30.11ms), a large held-phase
improvement (40.70→24.89ms), and fading38.14→30.77ms. Resident GPU-memory samples
3514.7→2939.9MiB including scene; empty scene2677.8MiB. Earlier background viewport
pilots / incorrect capture orientation are invalid and were discarded. Earlier
30fps moving-only benchmark did not establish a large overall gain; do not reuse
its stage improvement as an FPS claim.

Implementation: only ProphecyVDBLibrary.cpp. First one-action Live Coding build
passed61.15s; follow-up moves quality before asset allocation and disables native
visibility for invisible tails, one action83.47s, reload08:33:08UTC. No object changes
detected, no restart, no Blueprint reflection/wiring/content saves. Normal DLLs
remain stale and require minimal normal build before any cold launch.

Verification: PlaybackTiming native test passes08:33:59UTC, including lighting
reuse/fade endpoint/snap cases. Owned runtime verification passes four cases with
both actual clips; current bomb expires at240, early-zero remains alive but stops
rendering, instant nonzero and snap cases retain timing. Native spawn quality and
every sampled source frame/density/reuse/visibility checked. Installed captures at
ticks140/210/238 visually confirm stable smoke, half fade, and near disappearance.
Editor26816 remains open explosionVFX, owned Play ended. Evidence/scripts and small
before/after captures: Saved/Diagnostics/VDBPerformance20261019; raw final CSV:
Saved/Profiling/CSV/VDBCacheBenchmark.csv. No packaged build or many-bomb stress test.

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
