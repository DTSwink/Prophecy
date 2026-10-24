# Pause Workshop — checkpoint 01

Independent Unreal 5.7 project, native Slate menu matching approved
**02 — Fine Underline**. The Prophecy editor and weapon-wheel lab are not loaded
or modified. Gameplay integration awaits visual approval.

Run `Open.ps1`. Hover or ↑/↓ selects; Enter/click activates.
Resume hides the menu, blur and backing; Esc reopens it. Inventory, Journal
and Quit to Menu currently report their selection without running gameplay.
Settings opens the visual tuning panel.

- **R** toggles tuning; **P** hides the workshop hints.
- **F12** snapshots the window to `Saved/Captures/latest.png`.
- **F5** reloads `Resources/pause.json`; **Save settings** persists tuning there.
- Independent controls: whole UI size, title size, menu size/tracking/spacing,
  backdrop width/darkness, blur, underline length, selection glow and color.
- **Selected text whiteness** blends only the selected label from its original
  warm off-white (0) to pure white (1), default0; saves as
  `selected_text_whiteness`. Unselected text remains at90% opacity and the
  selected label at100%. No changes to title, underline, fonts or colliders.
- **Unselected text opacity** controls that non-selected opacity from0–1,
  default0.90; saved as `unselected_text_opacity`. Selected text stays opaque.
- Tuning controls are ordered by creation time, oldest at top and newest at
  bottom. Append future controls immediately before Save settings; do not
  insert them among older controls. Whiteness and opacity are currently last.
- **Text-to-line spacing** moves the underline, star and glow together below the
  selected text (0–30 design pixels, default16). It follows menu text size and
  persists as `underline_gap`. **Selection color…** opens the existing live
  color picker; Save settings keeps the chosen color and spacing.
- **Underline left crop** trims from the left (0–0.05, up to5% of the line),
  keeping the right star fixed. The line glow shortens with it; star glow stays.
  This range makes adjustment20× finer; displayed to four decimals.
  Save settings persists `underline_left_crop`, default0.
- Hover and click share the longest label's horizontal span. **Hover right
  extension** adds0–200 design pixels to that shared right edge (default0,
  saved as `hover_padding_right`). This changes only mouse hit areas; underline
  and all artwork remain unchanged. The unpadded lower boundary is the
  underline; the upper boundary mirrors it around the text's vertical center.
  **Hover top padding** and **Hover bottom padding** extend each edge separately
  (0–20 design pixels, default0). Save uses `hover_padding_top` and
  `hover_padding_bottom`; legacy `hover_padding` loads into both as a fallback.
  Padding does not move the artwork or change the opposite edge.
  If expanded areas overlap, the closest text center wins. Bounds follow font,
  text size, spacing and overall scale; cached on tuning changes, with no new
  recurring tick or glyph measurements on mouse movement.

**Menu hairline strength** (0–1) uses Bodoni Moda's authored optical-size axis:
0 is the original optical size24; 1 is the strongest size6, in19 steps.
Default is the study's B Medium (optical size10). Weight remains400; the actual
glyphs are drawn once in a single color. The rejected outline effect is removed.
Only the five menu entries change; PAUSED, Esc hint and decorations stay intact.
Letter advances are locked to the approved Medium font for every strength,
so hairline adjustment no longer changes letter positions. Optical variants
still change the glyph contours. Tracking remains an independent control.
Save settings persists `menu_hairline_strength`; existing layout values remain.
The19 small font files are baked by `Resources/Fonts/build_optical.py`, with no
runtime font generation. The isolated comparison remains in FontStudies/Hairlines.

The concept's number/title is an art-board label, intentionally omitted from
the functional menu. The selected underline is a fixed, adjustable length,
independent of label width; its star follows its endpoint.

## Modules

All implementation is under `Source/PauseMenuLab/Private/`.

| File | Responsibility |
| --- | --- |
| PauseModel.h | Menu data, hit regions, clamped JSON tuning |
| PausePainter.h | Independent type, feathered shade, line, star and local glow |
| SPauseMenu.h | Native input, live blur, tuning and cached painting |
| PauseMenuLab.cpp | Isolated host, snapshot and explicitly requested verification |

The background plate is imagegen's text/UI removal from the selected reference.
It is a review backdrop, not the runtime menu. Prompt and origin are in
`Resources/provenance.json`; unmodified reference retained separately.
Production will draw the same UI over gameplay rather than this still.
Title is Antic Didone; menu is Bodoni Moda at optical size6–24/weight400. Both fonts
are supplied under their included SIL OFL licenses, from Google Fonts.
The retained variable Bodoni source allows future optical/weight variants.

The UI is antialiased native font/line rendering, with explicit coverage on the
star. Glow is two small alpha quads, not a world bloom pass. The dark gradient
is a 512×2 reusable mask; star halo is 128×128. Paint is invalidated by interaction
or tuning; there is no custom recurring UI tick. Blur still costs GPU time while
visible. No production performance/shipping/controller validation is claimed.

## Build / review

`Build.ps1` compiles only this separate module; no shared multi-GB PCH.
Close only this lab before rebuilding; preserve the main game and wheel lab.
`Open.ps1 -Capture` runs an owned review instance, verifies hover at65%,100%,115%
plus key wrap, resume/Escape and tuning close, captures checkpoint01, then exits.
Add `-StayOpen` to leave it available after capture. No desktop automation.

The design canvas is1672×941 and scales to fit the window with DPI awareness.
Current checkpoint is intended for visual feedback before further pages,
transition animation, input routing or gameplay pause are implemented.

