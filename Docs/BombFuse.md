# Bomb fuse and prepared fragmentation

October19 startup correction installed in the interactive editor, on explosionVFX.

## Grid3D rendering override — October20

User wants existing scalability settings preserved while keeping the fuse visible.
`Config/DefaultEngine.ini` now sets `r.HeterogeneousVolumes=1` in
`[ConsoleVariables]`. UE5.7 loads this section in Shipping too, at
SetBySystemSettingsIni priority, above SetByScalability. Only this switch is
overridden; other scalability values are unchanged.
Applies on the next editor/game startup and future packages. No live console
change, build, restart or runtime/Shipping test performed, per user request.

## Optimised VDB checkbox — October19

**VDB colors added October19:** Light Bomb Fuse and Spawn VDB Effect expose
Temperature Color(default .99,.13,.011) and Scattering Color(default white).
Values apply once to the spawned VDB; fuse Niagara is unaffected. Custom colors
are stored until detonation in one non-ticking component, with no extra component
for default colors. No added per-frame color update or render pass. HDR RGB allowed;
negative/nonfinite values rejected. Three-action corrected Live Coding build
passed113.50s/reloaded12:00:22UTC without restart; existing retained layouts unchanged.
A_Bomb compiled/saved:57 existing pins preserved plus2 color pins. Direct/custom/
default/delayed/instant/Optimised forwarding verified12:03:48UTC. Normal DLLs stale.
See Saved/Diagnostics/VDBColors20261019 and Docs/ZibraExplosionFade.md.

Light Bomb Fuse exposes **Optimised** (defaultfalse), forwarded to Spawn VDB Effect.
On disables projected VDB shadows and reuses the completed3D volume for a cheap tail
with fixed lighting; off preserves the previous rendering. This is a VDB choice,
independent of physical force, fragments and fuse sparks. See
[VDB performance and controls](ZibraExplosionFade.md) for the cache conditions.
The existing A_Bomb node was preserved/refreshed/compiled/saved with56 authored pins
unchanged and one unchecked checkbox. Added optional components preserve existing
retained layouts; loaded through minimal Live Coding, no restart. Normal DLLs are
stale until the next required normal build. Evidence Saved/Diagnostics/VDBOptimised20261019.
Both direct VDB assets passed cache/fade/lifetime checks; instant-bomb forwarding
off/on passed10:12:10UTC with no fragments/emitter and one isolated effect at a time.

## Static fuse and upright Niagara — October19 installed and verified

The flame's red debug box is **User Parameters > Draw Bounds** (`User.DrawBounds`)
in NewNiagaraSystem1. October19 11:03UTC inspection confirmed it remains enabled.
Automatic toggle was not applied: the parameter store is protected in Python,
editor SET is disabled, and the desktop helper failed to initialize twice.
Full exported asset remained identical; only our no-change dirty marker was saved,
leaving the user's dirty A_Bomb untouched. No build/restart. Compact receipt:
`Saved/Diagnostics/NiagaraDebugGrid20261019/receipt.json`.

User retired the entire fuse-physics experiment. Runtime now uses only original
static geometry: the intact bomb remains visible until ignition/hide, then a
matching static shell plus the470 original fuse triangles preserve its shape.
UV1 burn distance still clips the fuse progressively. No bones, AnimDynamics,
rigidity/stiffness control, startup component or animation ticking remain on bombs.
The shared holster strap implementation is restored and remains supported.

Light Bomb Fuse retains its existing burn/cap/explosion/fragment controls and
optional Fuse Sparks. Spark Rotation Offset is removed: the emitter tracks the
burn cut with identity world rotation and absolute rotation/scale, keeping grid
Z upright as the bomb rotates. Null Fuse Sparks still means no emitter. Current
A_Bomb now uses /Game/_mygame/bomb/NewNiagaraSystem1; its stiffness
node is bypassed without changing the remaining authored exec path or tuning.

This changes retained component layout and removes a reflected class/function;
normal build/restart was required. Assets backed up, editor closed cleanly.
Initial11-action build compiled runtime but failed on editor helper pointer type;
corrected4-action retry passed59.17s. Editor26816 reopened explosionVFX, base DLLs
current. No interactive explosion/VDB regression:
focused StaticFuse test uses a non-activating Niagara component in isolated
-nullrhi, checking180 rotating/moving samples, clipping, material and hide.
StaticFuse passed05:41:54UTC; test process exited. A_Bomb compiled/saved,63->56 pins
with only requested changes. Orphaned transaction-buffer node subobjects in text
exports were excluded using active graph membership. All470 fuse triangles match
original positions/normals/tangents/UV0; UV1 burn coordinates are protected from
lightmap generation. Skeletal mesh/skeleton deleted after referencer checks and
six obsolete tools removed. Niagara saved bytes unchanged; agent reflection healthy.
The two retired physics diagnostic directories were moved to Windows Recycle Bin
in the user's October19 cleanup, along with superseded asset backups, graph dumps
and logs. Compact verification receipts/scripts remain in
Saved/Diagnostics/BombStaticFuse20261019. Exact recycled paths are recorded in
Saved/Diagnostics/ExplosionClutterCleanup20261019.json.

The retired rigidity trial's251-sample check passed after correcting its test
oracle to normalized quaternion interpolation, but user rejected its behavior.
Do not restore it. The earlier interactive full explosion test caused GPU-memory
exhaustion; do not repeat that test in the user's editor.

## Crash/reopen and Niagara recovery — October19

Normal15-action build84.41s after GPUMessage::FSystem::PollMessages crash brought
all prior bomb features into base DLLs. Editor12676 opened explosionVFX normally;
user dismissed recovery dialog. FuseCap/setup/native agent checks passed.
NewNiagaraSystem1 had no saved package/autosave. Recovered the full October18
19:23 text snapshot (Saved/Diagnostics/NiagaraPulse.txt) using editor-only
Prophecy.Editor.RecoverNiagaraText, remapping session type indices from current
Grid3D_MovingGridFire template. Native valid=1/ready=1/emitters=1, saved6,167,842
bytes at /Game/_mygame/bomb/NewNiagaraSystem1 and opened it; user confirmed.
Later RenderScale/pivot/visual tuning was not reapplied; user is recovering it.
Keep original text snapshot and Saved/Diagnostics/NiagaraRecovery20261019 receipt
and type map. Recovery helper required one-action Live Coding110s; normal base
DLLs predate this helper. No unrelated asset save during recovery.

## Fuse Cap — October19 installed and verified

Light Bomb Fuse now has Fuse Cap (default0, clamped0–1). It is the fraction of
fuse remaining at detonation:0 burns to the end,.25 burns75%,.5 burns half,
1 detonates synchronously even with zero burn speed. Instant Explosion still
overrides the cap. Burn speed, visible clipping and spark tracking retain their
full-length clock; only the detonation deadline is shortened, rounded up to an
authored60Hz tick. Existing calls/defaults retain their previous behavior.

An optional non-ticking UProphecyBombFuseCapComponent stores the deadline for
partial caps. Existing retained component layouts are unchanged; cap0 adds no
component and cap1 uses the existing instant path. Minimal Live Coding3 actions
passed237.58s, reload complete03:54:40UTC. Editor6904 remained open; no restart.
Normal base DLLs still require minimal build before any cold launch.

Current A_Bomb was preserved, refreshed, compiled and saved;54 authored existing
pins/defaults/links preserved, one FuseCap pin added at0. The old archived Bomb
Library CDO reference was repaired by package refresh. Initial strict comparison
flagged only that expected CDO change; verified with its exact normalization
before saving. Other assets/maps were not saved. Native21-argument reflection
and existing agent reflection are healthy. FuseAndDetonation passes03:56:48UTC,
covering0/.25/.5/1 deadlines, unchanged visible burn speed, immediate cap1 with
zero speed, optional sparks, VDB and physical force. EOS heartbeat warnings only;
no test errors. Evidence Saved/Diagnostics/BombFuseCap20261019.

## Niagara scaled flame clipping — October19 diagnosis

NewNiagaraSystem1 uses Render Scale0.2, WorldSpaceSize50,50,300 and Local Pivot
Z0.12. The red debug box and scaled simulation have different center offsets
(36 versus7.2cm); actual volume top is37.2cm above the actor. Flame was reaching
that finite simulation boundary. Temporary component bounds enlargement did not
recover it. Doubling only WorldSpaceSizeZ to600 recovered the missing flame top;
restored300 afterward because this was an inspection of the user's tuning.
No asset/map save, build or restart. Fixed bounds, BoundsScale, cube visibility
and diagnostic camera changes also restored. Keep Render Scale0.2 and increase
WorldSpaceSizeZ for headroom; fixed ResolutionMaxAxis means coarser cells in a
taller domain. Evidence: Saved/Diagnostics/NiagaraClip20261019.txt and two PNGs.

## Static shell material preservation

SM_BombShell copies original mesh-description vertex attributes and original
MikkTSpace build settings, excluding only the470 fuse triangles. It preserves
2152 shell triangles and original rendered normals/tangents/UV0. Its effective
material follows the original bomb component while burning. This static shell is
retained by the static-fuse implementation above; the old skeletal/startup setup
is removed. Reproduce shell with Tools/BombFuse/PrepareStaticShell.py, fuse with
Tools/BombFuse/PrepareStaticFuse.py. Original imported mesh/collider untouched.

## Fragment fade — installed and verified, no restart

Light Bomb Fuse adds Fragment Fade Duration, default1 authored second. Fragments
retain their original material until the final fade window of Fragment Lifetime,
then opacity interpolates1→0. Duration0 retains abrupt expiry; duration longer than
lifetime is clamped to the whole lifetime. Lifetime/cleanup timing is unchanged.
One new non-ticking optional component holds settings and the shared MID, preserving
the existing bomb/controller native layouts for Live Coding. The existing cleanup
tick performs one opacity write per explosion, not20 per-fragment ticks. Physics
continues through fading; expiry destroys all pieces and the cleanup owner.

Real translucent companion M_BombFragmentFade/MI_BombFragmentFade is derived from
the imported glTF material family without changing original assets. At detonation,
current bomb textures/scalars/vectors (including dynamic overrides) copy into one
shared MID. The current Bomb and PressureBomb share the prepared static shader
configuration. Arbitrary alternative shader families/static permutations are not
automatically recompiled: translucent materials may supply FragmentOpacity directly;
otherwise the runtime warns and preserves their original appearance/expiry. It does
not silently replace a different material with the bomb shader. Fully opaque versus
translucent rendering can differ during fading, especially shadows/sorting.

Minimal Live Coding5 compile actions passed452.06s; reflection reload completed
16:07:27UTC (one new fade class, changed library,19 unchanged classes). No existing
native component/Agent/world layout changes. Existing unrelated Niagara deprecation,
duplicate-test and .voltbl diagnostics occurred; reload and verification succeeded.
The user briefly started Play during compilation, then explicitly stopped it before
reload. Native20-argument call verified; current A_Bomb package pins refreshed by
reloading only its clean preserved package. Blueprint compiles, saved bytes match
the preservation receipt, agent reflection status3/native_properties0/pin_types0.
No wiring edits or unrelated saves. Original materials unchanged; two derived assets
saved in the already cooked BombGenerated directory. All nine effective static
switches match Bomb and PressureBomb; live scalar/vector/texture values copy at detonation.

Prophecy.Bomb.FuseAndDetonation passes16:07:51UTC including shared material/no extra
tick, half opacity, exact zero endpoint, physical fragments and cleanup, plus existing
fuse/VDB/force/toggle cases. Owned rendered Play check passed239 samples with current
PressureBomb: lifetime4s/fade2s stays solid through tick120, fades121–239, destroys240.
Solid/half screenshots inspected: actual transparency and retained green material.
Fragments were deliberately spread/frozen for this visual comparison only; production
physics remains unchanged. No claim of arbitrary shader/static-permutation support.

Editor6904 remains on explosionVFX/outside Play. User dirty explosionVFX and newly
authored NewNiagaraSystem left untouched. Base DLLs need minimal normal build before
the next cold launch, including this fade and preceding fragment-toggle/impact patches.
Evidence Saved/Diagnostics/BombFragmentFade; preparation CreateFragmentFadeMaterial.py
and owned visual check VerifyFragmentFade.py under Tools/BombFuse.

Fragment toggle follow-up: Light Bomb Fuse adds Spawn Fragments, defaulttrue.
False skips loading the20 prepared meshes and spawning debris/cleanup controller;
the VDB and physical blast still execute for timed and instant detonation.
The existing Fragments array carries the choice (empty means no debris), so this
adds no retained native storage and can load via Live Coding without restart.
Live Coding3 actions passed286.30s; patch_0 and reflection reload completed
15:22:44UTC. Native test passes15:23:03UTC for enabled/default20 fragments and
disabled timed/instant paths, including VDB and actual physical force. No cleanup
controller is created for an empty fragment list. Native19-argument call accepted;
Python wrapper doc remains stale after Live Coding, so use reflected call_method.
Existing A_Bomb needed its old pin list refreshed: reloaded only its clean,
freshly preserved package, then compiled successfully15:25:12UTC and reopened its
asset tab. No editor restart or manual wiring edits. User map/PressureBomb dirty
state preserved. Handled RigVM/MTAccessDetector ensures and .voltbl diagnostics
occurred during reload; subsequent verification passed. Minimal normal build
required before next cold launch because base DLL predates this checkbox.
Evidence: Saved/Diagnostics/BombFragmentsToggle (preservation, native-reflection,
build-summary, verification-log and final-status). Editor6904 remains open.

## Retired fuse simulation

The October18–19 five-body cosmetic fuse and normalized rigidity experiment were
removed at user request, including build/import/probe scripts and skeletal assets.
Burn timing, permanent hide, instant explosion, optional Niagara,
material inheritance, physical blast and fragment behavior remain supported.
