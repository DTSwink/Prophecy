# Weapon wheel UI — isolated workstream

## Main-menu scene — October29: horizontal smoke width

Air → Horizontal width now scales the actual native smoke source0.25–8x along
world Y using Grid3D_Gas_SphereSource's Non Uniform Scale input. The old Spread
mostly enlarged empty domain space while its sphere radius capped at240cm.
New smoke_horizontal_width defaults1 to preserve the saved plume; legacy
haze_spread still supplies the original domain/radius baseline. Height, depth,
position, crop and vertical flow stay independent. Domain grows only to fit the
source plus450cm at each end; adaptive maximum-axis resolution preserves old
cell size up to512. Resize is delayed300ms after the last size change; it restarts
the field once, so allow a few seconds for gas to reform. Changes fitting the
existing domain affect emission without clearing the field.

Normal build and native Niagara CPU/GPU preparation pass. Typed source scaling,
source radius, domain bounds, save/reload and existing controls pass. At8x the
source scale is(1,8,1), radius remains227.87cm, domain1000×4545.916×650cm.
1x/4x/8x12s renders inspected;4x visibly spans the upper frame. Evidence under
Saved/SmokeWidth20261029/ and Saved/Captures/smoke-width{1,4,8}.png;
small curated receipts are included in Verification/. User tuning saved with
SaveLive before closing28136: rain4, smoke shift7.4628cm, existing water settings
preserved byte-for-byte against Saved/SmokeWidth20261029/live-saved.json.
User authorizes push of this scene checkpoint. Generated outputs and unrelated
workstreams are excluded. The lab README documents rebuilding from checkout.
Current review PID20344 is open on Air, responding; scene and smoke ready
03:57:58 Warsaw. Horizontal width starts at1x to preserve the current look.

## Main-menu scene — October29: water collision controls

Water tab exposes five live sliders: Push strength, Motion threshold (cm/s),
Contact softness (cm), Damping, Wave relief. Existing background and rain sliders
stay independent. Try calmer contact sets0.6x/5cm/s/4cm/30%, resting contact off,
and clears old waves. Clear existing waves resets only water, including displayed
normals while paused; it retains position and all settings.34 sliders total.
All tuning uses the established automatic recovery/SaveLive workflow.

The old provider remains active even at zero measured bone movement. Frozen
native comparison: always-present contact normal XY energy0.000397816 versus
exact0 with the new gate. Raising only the native speed threshold barely changed
the old footprint. The attempted KeepWaterDepthInsideColliders branch increased
it and is rejected; the final system explicitly retains original false. No engine
modules edited. Its unused experimental duplicate is archived in Saved.
Final gate measures PHAT body transforms whose bounds reach the3.5cm surface,
including angular motion via center and six extent points. It admits the actual
whole-mannequin provider when measured horizontal speed exceeds the slider and
holds80ms after motion to avoid sampling flicker. Resting contact (legacy) bypasses
this gate. Nonmoving shapes are absent as fluid obstacles; vertical-only forcing
still has the stock horizontal-speed limitation. This is a prototype wake driver.

The five slider bindings change actual native module inputs (velocity multiplier,
minimum speed, soft falloff, friction/dissipation) except Wave relief, which adjusts
the existing InteractionStrength material uniform. Damping uses a square curve,
friction0.00025→0.01 and dissipation0.0003→0.05. Zero push blocks new forcing.
Previous1x/1cm/s/4cm/zero-damping defaults retained; gate defaults enabled.
Animated idle at1cm/s gives faint waves; calmer5cm/s gives exact0 over the8s test.
A90cm movement at the same calmer settings still produces0.000135745 normal energy.

Normal build and lab-only Niagara preparation pass. Shared native control/save/
revert/recovery checks and finite GPU normal readbacks pass. Evidence:
Saved/Validation/collision-controls.json, collision-response.json,
weather-controls.json; Saved/Captures/contact-gated-studio.png visually inspected.
SaveLive saved exact live state before closing26304. Resources/scene.json remains
byte-identical to Saved/CollisionControls20261029/live-saved.json. No desktop
input, main-project assets, engine changes or push.
Previous visible review PID28136 reopened on Water; responding and scene/smoke
ready03:38:01 Warsaw. User rain0/background30.597%/wave relief0.8 retained.

## Main-menu scene — October29: mannequin translation gizmo

Click the mannequin to select it; drag redX/depth, greenY/sideways or blueZ/height
handles. Selection uses the live copied PHAT with QueryOnly collision; movement
updates the actual mesh/colliders, including while paused. UI overlay uses world
projection and continuous subpixel deprojection to avoid depth-axis stepping.
Esc cancels a drag or deselects; empty click deselects; Tab hides controls/gizmo.
Reset position is above Save/Revert on every tab, restoring original position
and heading. R additionally clears water as before. Position is body_offset_x/y/z,
included in Save/Revert/automatic recovery; WASD preserves height. Limits:450cm
horizontal offset, Z-30…400cm. Close-up camera waits until drag ends before following.
Normal build passes. Native shared-handler checks verify actual collider picking,
40cm XYZ drags, scaled geometry, paused lift, cancellation, save/reload, reset and
empty-space deselection. Weather/recovery checks also pass. Evidence:
Saved/Validation/mannequin-gizmo.json, Saved/Captures/mannequin-gizmo.png and
Saved/MannequinGizmo20261029/validation.log. No desktop input or asset preparation.
SaveLive.ps1 preserved user rain0/background30.597% before closing PID30320;
original scene.json remains byte-identical to Saved/MannequinGizmo20261029/live-saved.json.
Previous visible review: PID26304, Ground tab; saved/closed for collision tuning.
Rain remains off and Background ripple remains30.597%.

Latest addition: Ground → Background ripple (`wind_strength`,0–100%, existing16%)
controls ambient normals only; zero retains rain/contact waves.29 sliders total.
User requires automatic preservation, no repeated Save prompts. Run SaveLive.ps1
before authorized rebuilds: exact native settings save via Saved/save-look.request,
acknowledged and disk write checked. Live edits also checkpoint after250ms idle
to scene.json.recovery; startup restores only if its exact saved-file baseline
still matches. Save/Revert synchronize recovery; normal shutdown checkpoints.
Initial implementation-only Live Coding patch installed the save IPC without
native layout changes; current rain-off tuning was saved exactly before closing
PID12136. Subsequent new storage uses a normal build. Backup:
Saved/AmbientRipple20261029/live-saved.json. No desktop input used.
Normal build and native controls pass: ambient zero/live readback, save/reload,
recovery.81 versus saved.37 and explicit Revert. Ground tab visually checked in
Saved/Captures/background-ripple-control.png. Previous review PID30320 opened on
Ground with rain0/background16%; scene/smoke ready01:56:41 Warsaw. SaveLive.ps1
ack/disk-write verification passed. That review was later saved/closed for the gizmo update.

Density now offers four times the old maximum: old80%=new20%, old100%=new25%.
98,532 seeds across four independently jittered layers, with paired surface
impacts. Stored rain_amount remains in original units, now0–4; no saved-look
migration. User explicitly saved before rebuild; scene.json is backed up at
Saved/DenseRain20261029/prior-saved.json. Fine-storm button/preset uses new95%.
The source now emits downward near the center; native density buoyancy
turns the gas upward and vorticity rolls it. Drift controls downward speed and
return acceleration, zero pauses; Rolling motion remains independent. Current
12% drift gives source(0,0,-64)cm/s, density coefficient-.016 and gravity-980Z.
Source is20cm above center, radius~228cm at saved spread, leaving return space.
Height/lower-edge/left-right and all other tuning remain unchanged.
Final normal build and material/Niagara preparation pass (0 preparation errors/
warnings). Native controls pass persistence at raw rain3.27 and both material
readbacks.20%/100% captures have19,718/98,532 active seeds with identical fall
speed, width, length and impact strength. Actual user scene.json is byte-identical
to the saved backup.8s/18s smoke renders show evolving density in frame; typed
bindings confirm downward source and upward density force. No direct GPU velocity
measurement. Receipts: Saved/Validation/dense-rain.json, downward-smoke.json and
weather-controls.json. Current preview: Saved/Captures/dense-roll-studio.png.
Earlier review: PID12136 reopened visibly on Air with saved settings;
SCENE_READY/SMOKE_GAS_READY and responding window verified01:17:13 Warsaw.
It was later saved automatically and closed for the ripple/recovery update.

Latest revision replaces the patchy bed with one warped phase field: long curves
and finer strands following the same flow. Saved scale0.75 and independent dark
areas remain. Background water normals are reduced50 times; rain/contact now
dominate. Rain rings last1.05s and expand28cm/s, with directional antialiasing and
shallow refraction so they bend both the reflected lights and submerged pattern.
Rain remains cheap analytical material animation paired to actual3D streaks.
Mannequin disturbances remain actual Epic shallow-water simulation. In the lab
copy, SDFSoftCollisionFalloff30→4cm fixes weak coupling in the3.5cm puddle;
friction0.00025 and velocity dissipation0.0003 reduce wake loss. Stock two substeps
and engine solver retained. Purely vertical contact remains limited by the stock
horizontal-velocity gate. No repeating artificial foot rings were added.

Current isolated project: `Labs/MainMenuSceneLab`. The rejected noise-volume mist
is replaced by Epic NiagaraFluids `Grid3D_Gas_Smoke`, duplicated as
`NS_UpperGasSmoke` with the native Volume Renderer. The GPU gas field rolls and
advects, with zero temperature and art-directed upward density buoyancy. The
engine template stays unchanged.
The stock plume pivot is centered; runtime bounds match the actual grid, and
unused ambient-smoke collision branches are disabled. Mannequin collision still
drives the independent live shallow-water solver.

Air has Density, Bank height, Lower edge, Edge softness, Spread, Drift speed,
Rolling motion, new Left / right and optional Middle mist. Left / right moves
container and source together ±1000cm without resetting the field; current200cm.
Lower edge is a fraction down from the
camera top; smaller keeps more black. Its world-space extinction/emission mask
is independent of bank height. Middle mist0 leaves the center clear. The Cold
smoke / black center button sets density65%, height350cm, lower edge28%, softness6%,
spread1, drift12%, roll65%, shift200cm, mist0. This is a preset, not the current
user look. All43 live user settings, including unsaved edits, were captured via
native F12 report and preserved exactly in scene.json; only new shift200 was
added. Current smoke height394.03cm/spread1.6026/roll27.985%/lower-edge30.075%.
Backups: `Saved/PuddleRevision/prior-live.json` and `prior-saved.json`. Earlier
smoke backup/preset remain available; do not restore them over current tuning.

The studio now has29 sliders across Ground/Rain/Air/Body. Physical rain widths,
depth fading, dense-fine preset, connected ground undulations, UV-attached
clearcoat beads and bounded gravity-tangent runoff are retained. No rain screen
width clamp, no smoke sheets and no old panning-noise volume in the active scene.
Body close-up remains available; runoff does not transport fluid across UV seams.

Normal build-puddle-3 and preparation pass; latest preparation has0 errors/0
warnings. The helper checks actual Niagara CPU/GPU compilation before saving.
Native control bindings, cloud translation, enable/disable and Save/Revert pass.
Current renders: `Saved/Captures/puddle-studio-final.png`, `puddle-rain-final.png`,
`puddle-rain-after.png`, `puddle-contact-final/disabled/after.png`. Exact settings
and controlled raw GPU normal fields are alongside. At3.2167s, moving collision
on produces XY energy0.000369499; disabled gives exactly0. At4.5s, outer250–350cm
energy is3.25times higher, supporting outward propagation after root movement
stops. Rain frames3.2167/3.5167s visibly change ring/reflection shapes.
Receipts: `Saved/Validation/puddle-collision.json`, `puddle-rain-motion.json`,
`weather-controls.json`. Earlier cold-smoke tests retain evidence for evolving
gas,125x224x82 grid at Spread1 and an upper boundary clearing the tested region
to RGB0. `depth-rain-final.png`/`pearling-closeup.png` document retained body/rain
work. No VDB/cache bake yet. These are native renders/shared callback checks,
not desktop mouse-drag tests. Visual fidelity remains an art-review checkpoint.

User explicitly authorizes automatic closing/rebuilding/reopening this scene lab
without asking each time. Latest instruction is "without using my computer,
resume": no further desktop input; use files/CLI/offscreen rendering. Prior
review PID23860 and later29744 are closed. October29 user saved before this
automatic rebuild. Subsequent verification used only offscreen renders and
native callbacks; saved tuning preserved. See current review status below.
Preserve saved tuning and unrelated sessions. Never
prepare materials while the lab is open: Windows locks loaded assets. Use a
normal build for retained native layout changes. See journal for current review.
User can launch `Open.ps1 -Visible -Air`. Tab panel, WASD movement, Space demo, P pause,
R body/water reset, F12 capture. Save look retains the last file as .previous;
Revert reloads. No main-project/Blueprint/engine/other-lab edits or cleanup.

### Retained live water implementation

New isolated project: `Labs/MainMenuSceneLab/MainMenuSceneLab.uproject`.
User requested the ground, water and lighting first, with unscripted mannequin
collision and later inexpensive rain. Current reference is copied exactly from
`codex-clipboard-2b655c08-1b69-43d0-9c92-2f686e3b9bab.png` to the lab's
`Resources/reference.png`. Earlier concept galleries remain unchanged.

The initial custom CPU water prototype looked poor and is superseded. Current
solver reuses installed UE5.7 WaterAdvanced/NiagaraFluids `Grid2D_SW_WaterBody`.
Lab-only duplicate `NS_CrimsonShallowWater` lowers the module's collision speed
threshold from30 to1 cm/s; engine assets/solver remain unchanged.512² GPU field,
ten-metre patch,3.5cm surface,negative bottom contour. PhysicsAsset shapes drive
collision, registered explicitly on the Niagara collision data interface after
compilation. RGBA16f output is signed world-normal XYZ plus foam A, not height.

Water combines live normals and layered Epic water textures (background reduced
50times in the current revision). The crimson bed,
metallic mannequin, studio sources and planar reflection are native geometry /
materials. Correct clip-plane setting is `r.AllowGlobalClipPlane=True`; an early
incorrect `r.SupportGlobalClipPlane` setting meant those older streaks were only
direct light specular. A later emissive-body probe confirms real reflected body
and capture-only cards with the far rect lights removed.

Earlier baseline before the current puddle revision: paired native GPU
readbacks at3.2167s with identical10cm unscripted root translation: collision on
XY-normal energy0.000165581; collision off exactly0. No scripted ripple spawning.
Evidence: `Saved/Captures/gentle-contact-on/off.*`, `reflection-confirmed.png` and
`Saved/Validation/verified-water.json`. These test the actual GPU output.

Earlier water-only preview: `Saved/Captures/crimson-water-final.png` with GPU
readback JSON. Depth-limited bed refraction, tapered reflected sources and
filtered reflection glints remain. Current matching is an art-review checkpoint,
not a claim of pixel identity. The UEFN mannequin is still a placeholder; the
decorative main-menu panel is a separate later pass.
The main project, existing UI labs, Blueprint wiring and source animation assets
were not edited. No main editor restart, push or storage cleanup performed.
Full build/run/architecture notes: `Labs/MainMenuSceneLab/README.md`.

## Main menu concepts - October 27, 2026: twenty larger ruby-and-gold refinements

Current review gallery: `Labs/MainMenuConcepts/2026-10-27-ruby-refinements/index.html`.
User selected the ruby-and-gold framed menu and requested 20 more sophisticated
versions, each longer/taller and wider. Exact supplied attachment
`codex-clipboard-896cceb5-e77b-4f25-b8e1-dbd60686d2c7.png` is copied losslessly
to `reference-selected.png`. Keep the enclosing rectangular shape, translucent
ruby/black interior, bright ivory text and vertically stacked actions. This round
refines that selected family rather than exploring unrelated layouts.

Every generated panel is visibly wider and taller than the supplied reference.
Prompts target roughly 475 x 732 pixels from the reference's roughly 347 x 555;
these are design targets, not measured runtime bounds. More interior spacing,
frame joins, typography, selection treatment and ornament provide the variation.
The approved crimson water, reflections, black void and mannequin remain the
scene reference. No title/logo or additional menu actions.

01-05 Frame: Quiet atelier, Architectural rebate, Jeweller's setting, Floating
inner rail, Stepped classic. 06-10 Typography: Roman inscription, Editorial
ivory, Humanist classic, Bookplate prestige, Ceremonial spacing. 11-15 Material:
Polished ruby, Smoked champagne, Satin garnet, Enamel and gilt, Crystal bevel.
16-20 Detail: Deco fan, Engraved laurel, Long lozenge, Corner compass,
Atelier synthesis. All retain CONTINUE, NEW GAME, LOAD GAME, SETTINGS, QUIT in
that order, with Continue selected.

All 20 generated with built-in imagegen and individually visually reviewed for
size increase, text, enclosure, visible water and unobstructed mannequin.
Twenty unique decoded 1672 x 941 PNGs, 33,481,486 bytes (31.93 MiB); reference
copy hash verified. Exact prompts/source paths are in `manifest.json`, dimensions
and SHA256 in `validation.json`. Gallery links and script syntax checked.
Arrow keys browse; B compares the reference; D enables scrolling 2x inspection.
Selected concepts now have a #concept-NN URL for easier identification.
No live browser interaction used for validation. User selection pending.

These are bitmap concepts with baked translucency, not runtime materials or
working menu controls. Scene preservation is visual, not pixel-identical.
No Unreal/native UI/preset/build/push changes.

Previous enclosed-panel gallery remains intact at
`Labs/MainMenuConcepts/2026-10-27-enclosed-panels/index.html`: 20 typography,
craft, glass and geometry studies (31.97 MiB), original reference and prompts.
The current ruby-and-gold selection supersedes its unrestricted style search.

Previous broad UI gallery remains intact at
`Labs/MainMenuConcepts/2026-10-27-ui-directions/index.html`:20 typography,
layout, material and graphic directions,32.34MiB, with its reference/prompts.
The latest enclosed-panel requirements supersede that round's unrestricted layout.

Previous lighting gallery remains intact at
`Labs/MainMenuConcepts/2026-10-27-reflected-lights/index.html`:20 intensity,
arrangement, source-shape and colour studies,32.87MiB, with its original reference,
prompts and validation. Lighting is now selected via the user's new attachment.
The scene still has no new scenery, celestial ornament, visible light fixtures
or beam above the water.

Previous ground-only review remains intact at
`Labs/MainMenuConcepts/2026-10-27-crimson-fine/index.html`:20 slight colour,
pattern, reflection and water refinements,33.40MiB, with their original selected
reference and exact prompts. Parent review:
`Labs/MainMenuConcepts/2026-10-27-checker-crimson/index.html`; earlier diverse
grounds: `Labs/MainMenuConcepts/2026-10-27-ground-art/index.html`.
Preserve all selected references; original rippled red was chosen over the
prior smoothed lacquer replacement.

## Current checkpoint — October 24, 2026

**Accepted checkpoint:** user approved and saved the pause menu, then requested
this UI work pushed. Latest saved unselected opacity is0.8032181263, selected
whiteness0 and right extension200. Both isolated UI labs, their assets/fonts/
presets, the font study and pause concept galleries are included in this push.
Build/cache/capture folders and other chats' work are excluded. User cancelled
the separate disaster-recovery audit; do not perform or claim that audit here.

**Underline and hover controls:** R panel includes **Underline left crop**
with range0–0.05 (up to5% of line length),20× finer than its original full-length
range, displayed to four decimals. Saved as `underline_left_crop`, default0.
Right star stays fixed; line start and line glow shorten together.
**Text-to-line spacing** (0–30, default16) persists as `underline_gap`.
**Selection color…** is the live color picker. Save settings retains all.
**Selected text whiteness** blends selected label RGB from original(.96,.95,.93)
at0 to pure white at1, default0 (`selected_text_whiteness`). **Unselected text
opacity** controls the other labels' opacity0-1, default.90
(`unselected_text_opacity`); selected opacity remains1. Both persist via Save.
Controls now follow creation order top-to-bottom. Original controls first,
then hairline, line gap, crop, top/bottom padding, right extension, whiteness,
opacity. User explicitly requires new controls appended at bottom before Save,
not inserted among earlier controls. Fonts, underline, colliders and saved
user tuning untouched by this addition.
User reauthorized ONLY right-collider extension after the morning rollback.
Restored **Hover right extension** (0-200, default0, `hover_padding_right`),
with zero using the longest label's common horizontal span for all rows.
Fixed visual underline length is intentional and unchanged; do not make it
label-relative. Rendering source and saved JSON hashes unchanged by this task.
Earlier fixed hairline advances and separate top/bottom padding are retained.
Unpadded bottom is the underline;
upper edge mirrors around glyph center. **Hover top padding** and **Hover bottom
padding** independently extend those edges (0–20, defaults0); saved as
`hover_padding_top`/`hover_padding_bottom`. Old `hover_padding` initializes both
if separate values are absent. Overlap still resolves to the glyph center,
not the asymmetrically padded rectangle center. Cached, no recurring tick.
October24: fixed hairline-driven letter spacing. Drawing and hit bounds now
advance characters using fixed Medium (optical10) metrics at the selected text
size, plus user tracking. Optical strength changes glyph contours only; no
accumulated letter-position drift. Current Medium appearance preserved.
Four-action build18.55s;351/351 input/bounds checks pass, including independent
padding. Native optical0/Medium/1 comparisons change4152/4864 menu pixels and
zero outside menu in that earlier comparison. Latest opacity/control-order
build passed12.31s (four actions; prior partial edit build22.77s also passed).
351/351 input checks passed, fresh native checkpoint captured. Owned pause
lab14944 open; saved settings preserved, including right extension200. No
main-game integration. Painter tint now intentionally differs from the old
collider-only source hash; underline remains fixed and unchanged.

**Approved font correction now loaded:** user approved the isolated optical-size
study and requested it as an option. **R → Menu hairline strength** replaces the
rejected translucent outline. It selects19 authored Bodoni Moda optical sizes
24→6 at constant weight400 (0original,1strong); initial B Medium is size10.
Actual single-fill glyphs, no outline, no faux bold. PAUSED/footer/decorations
are unchanged. Designer optical adjustments affect curves; advances now stay fixed;
do not claim every heavy contour is mathematically identical.
Save settings persists `menu_hairline_strength`; all13 earlier layout/tuning
values preserved, backed up in `Resources/pre-optical-user-preset.json`.
The study remains at `Labs/PauseMenuLab/FontStudies/Hairlines/index.html`.
Static fonts total~1.1MB, reproducible with Resources/Fonts/build_optical.py.
Four-action incremental build passed21.67s;21/21 input checks passed.
VerifyOptical.py:6304/7184 changed menu pixels for medium/strong and ZERO
changed outside menu. Actual native review inspected; no embossed coloring.
Review instance25084 left open. Only owned pause lab restarted; wheel4296
and main project untouched. No production hookup yet.

User selected **10 — Silent Type** from the first pause-menu set. Ten close
variations are ready in `Labs/PauseMenuConcepts/2026-10-23/silent-type-variations/`
(about19MiB), with numbered gallery and exact prompts in `manifest.json`.
They preserve the left menu, oversized serif title, forest scene and violet
selection while varying typography, spacing, blur and selection ornaments.
User chose **02 — Fine Underline**. Native checkpoint01 is now available in
`Labs/PauseMenuLab`, a separate UE5.7 project. See its README for controls
and modular source. Final4-action build passed16.62s; actual1672×941 render
reviewed and21/21 handler checks passed (three hover scales, keyboard wrap,
resume/Escape and tuning close). Review instance11072 left open.
Title uses Antic Didone, menu Bodoni Moda; OFL licenses included. The background
is a clean imagegen extraction; UI itself is live Slate with separate blur,
gradient, typography, underline, star and glow. R opens tuning, F5 reloads,
F12 snapshots, P hides hints. Save persists `Resources/pause.json`.
Approximately43MiB including build outputs; no large PCH. Wheel4296 and
its settings remain untouched. One isolated font-loading assertion was fixed
by using LazyLoad for file-backed composite fonts; final launch passed.
User approved checkpoint01; its subsequent outline trial was rejected and
replaced by the approved optical-size control described above.

User accepted the latest wheel controls and moved to pause-menu exploration.
Twenty numbered, separate concepts generated with built-in imagegen are in
`Labs/PauseMenuConcepts/2026-10-23/` (about42MiB). `index.html` is the review
gallery; `manifest.json` stores all exact prompts, references and original paths.
English labels, translucent forest gameplay backdrops, white celestial linework
and violet selection tie the concepts to the wheel. Await user selection before
pause-menu implementation. Main game and wheel source unchanged by this artwork.
Requested Blueprint push was checked: no saved Blueprint changes, no ignored
custom Blueprint candidates; fetch/push confirmed branch already current at
16d490e0. The modified TestNN map and unrelated work were not staged.

The user approved the constellation layout with **local shadows** and requested
incremental, modular implementation, isolated from the main game. **All UI and
communication must be in English** (explicit correction on October 22).

The independent UE 5.7 project is `Labs/WeaponWheelLab/WeaponWheelLab.uproject`.
It runs its own native Slate viewport over the original forest screenshot. No
Prophecy maps, Blueprint wiring, physics, main C++ modules or plugins were edited.
No managed Git worktree or full content copy is needed for this small project.

Checkpoint 03 adds eight distinct orbit profiles: different tilts, gaps and inner
curves replace repeated dashed rings. Stars and pearls are evaluated on their
carrying curves, including the concentric connecting arcs. All eight weapon
centers still share one radius. Neutral white engraved icons and antialiased
ornaments remain; the selected crescent and star now have localized soft glow.
The name backing is a continuously fading Gaussian veil without a flat oval
center. Whole-wheel size, selection glow and a native live color picker are
available in Settings. No inventory or
production gameplay hookup yet. Stop for the next visual rating before extending
scope or moving it into the main project.

October 23: replaced the shared Ornament brightness slider with **Center
brightness**, **Circle line brightness** and **Connecting line brightness**.
Each is independent, ranges 0–1 and persists with Save settings. Center owns the
name, two stars, diamonds and horizontal strokes; circles own their orbit lines,
stars/pearls/pinpoints and bomb spark; connectors own their arcs/stars/pearls.
Selection color/glow, weapon drawings and dark backings retain separate controls.
Center starts at 1; circles/connectors inherit the user's saved 0.3777549863.
Legacy `ornament_opacity` remains only a fallback for old presets.

**Center font size** changes only the label (12–36, whole steps, default22).
**Center decoration size** scales all surrounding stars, diamonds and lateral
lines together about the wheel center (0–1.5, default1; zero hides them).
The two sliders are fully independent: the decoration layout measures the
original 22-point label, so changing text size cannot move or resize decorations.
Their scale controls positions, line lengths/thicknesses and symbol dimensions.
The name backing remains separate. `center_font_size` and
`center_decoration_size` persist with Save settings.
The latest pre-font user preset is preserved in
`Resources/pre-font-size-user-preset.json`; only the two new size fields were added.

October 22 validation passed: incremental native build; 45/45 checks across 100%, 65% and
106.10% sizes using actual scaled canvas geometry, all eight hover sectors,
center dead zone, keyboard wraparound and wheel/settings visibility. Independent
rendered comparisons changed 232,644 pixels (weapon backing), 58,926 (arcs),
55,271 (name) and 15,221 (selection glow). The native color picker opened and
rendered; changing the color through its shared callback changed 12,719 pixels.
All temporary test values were restored without saving. Picker mouse dragging
and Cancel were not separately automated. Native DPI awareness remains verified
on the 125% display. Clean capture:
`Labs/WeaponWheelLab/Saved/Captures/checkpoint-03.png` (1024×949 physical pixels).
Small-size, settings and picker captures are beside it. The review window was
left open then (PID3248). These are handler/render checks, not production gameplay
or controller integration tests.

## Open and change

Run `Labs/WeaponWheelLab/Open.ps1`. Mouse hover or arrow keys select weapons;
Tab toggles the wheel and blur. R opens **Settings**, P hides the review footer,
F12 saves a screenshot. Settings can be saved to `Resources/wheel.json` and
reloaded with F5. That JSON is the persistent, agent-readable tuning state.
The independent darkness controls are **Weapon circle darkness** (`shadow`),
**Connecting arc darkness** (`arc_shadow`), and **Name backdrop darkness**
(`label_shadow`). Always read `Resources/wheel.json` for current user tuning.
At the font-size change, latest tuning included blur3.979, radius332.918,
icon size134.184, overall size0.982, center/circle/connector brightness
0.998/0.881/0.385, revised purple and DAGGER selected. Every existing field was
preserved. `Resources/checkpoint-03-user-preset.json` retains the earlier
pre-brightness preset; do not restore it over later user tuning.

**Overall UI size** scales icons, geometry, text, shadows and hit testing around
the wheel center. Its upper limit keeps the current radius inside the canvas.
**Selection color…** opens Unreal's picker with RGB/HSV and hex controls, live
preview and Cancel restoration. **Selection glow** changes halo intensity
independently of the crisp strokes. Save settings persists all three; moving
controls alone does not overwrite the preset.

Layer ownership and build instructions are in the [lab README](../Labs/WeaponWheelLab/README.md).
Only the weapon atlas was image-generated. The background is the user's original
screenshot. The approved concept remains an unchanged reference, including its
original baked text. Runtime icons, soft shadow quads, orbit geometry, label and
selection are independent, not a single baked wheel image. Weapon shadows use a
16 KB radial alpha texture; the name has a separate 256×128 Gaussian veil. Local
selection glow uses a 256×256 crescent and a 128×128 star spot, generated once.
No scene bloom pass is enabled. The connecting shadow has a separate 1 MB curved
mask which excludes weapon interiors and rebuilds only on radius changes.
The replacement monochrome atlas is filtered at load into an 11-level trilinear
mip chain using alpha-weighted linear-space filtering. Source art stays unchanged
by this runtime sampling. Geometry is cached after invalidation, with no new
per-frame UI tick. The prompt and asset provenance are retained in
`Resources/provenance.json`.

For native changes close only the isolated lab, build its one module with
`Build.ps1`, then reopen. The main editor must remain untouched. The existing
remote Python helper selects its first discovered editor, so do not use it
blindly when more than one editor is running. This lab does not need it.

## Build/storage notes

Shared UnrealEd PCHs are disabled for this one-file module. The initial generated
2.49 GB PCH/object pair was sent to the Recycle Bin; it will not be recreated by
the current configuration. The whole lab, including current binaries and small
build metadata and retained review captures, is approximately 48 MiB.
Builds use the existing dynamic-memory worker scheduler. The latest incremental
compile/link was four actions in 14.14 seconds for the independent text/decoration
sizes; review window4296 reopened. Existing preset fields compared unchanged.
Only the standalone lab was
restarted for these native changes; no main-editor restart was performed.

The user's disk was nearly full during early launches. Zen DDC returned HTTP 507
and could not retain shader results, causing repeated compilation. The user freed
space before resumption (about 23.9 GB then available). Do not diagnose those long
startups as wheel rendering cost. Production GPU performance is not measured yet.

Georgia is read from Windows for this local checkpoint; no font is redistributed.
Select a redistributable typeface before packaging the UI.
