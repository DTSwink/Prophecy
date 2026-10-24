# Weapon wheel UI — isolated workstream

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
