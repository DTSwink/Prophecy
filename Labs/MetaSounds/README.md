# Prophecy MetaSounds

A standalone game-audio sandbox for designing Prophecy's SFX in a way that ports
to Unreal Engine 5 mechanically. Launch **Prophecy MetaSounds** from the desktop
(or `Launch MetaSounds.cmd`). It runs on Sound Studio's existing Python
environment (PySide6, NumPy, SciPy, soundfile, sounddevice); nothing extra is
installed, and it never touches the Sound Studio folder.

It runs its own real-time engine (`meta_engine.py`, 48 kHz, 1024-sample blocks)
and audio stream, its own project file, and keeps its settings in
`%LOCALAPPDATA%\ProphecyMetaSounds`.

## How it maps to Unreal

Every object matches an Unreal asset; distances are Unreal units (cm), levels dB,
pitch semitones.

| App | Unreal |
| --- | --- |
| Event (layers, parameters, mappings, processing) | MetaSound Source (Wave Players, Inputs, Map Range, DSP nodes) |
| Layer (pool of takes, delay, gain, chance, ± pitch/volume, *when*) | Random Get/Shuffle → Wave Player, Trigger Delay, Random Float |
| Attenuation profile | Sound Attenuation asset (same field names) |
| Max voices + rule | Sound Concurrency |
| Zone (beds, spots, reverb, interior, ground) | Audio Gameplay Volume + Soundscape palette/colours |
| Emitter | Ambient Sound actor |
| Bus, duck | Sound Class/Submix, Control Bus Mix |
| Time of day / weather | Gameplay-tag states |

## Starter project

The first launch creates `Documents\Prophecy MetaSounds\Prophecy.metasounds.json`
with a complete layout:

- footsteps (Dirt, Grass, Stone, Wood, Water), cloth & gear, jump, land
- pads: Punch (1), Kick (2), Sword swing (3), Hit taken (4), Body fall (5)
- beds: wind, forest, village, tavern room tone, night crickets, rain
- spots: birds (day), owl (night), dog barks, crows
- emitters: campfire + crackle, river (capsule), tavern hearth
- zones: Open plains (default), Forest, Village, Tavern (interior)
- ducks: Combat and Voice dip Ambience

Only the WAVs are missing; events without files show ⚠. Drag WAVs from the
**Library** (Sounds, Sounds Mixed, or any folder) onto a layer, or select them and
press **Add to layer**. Double-click a library file to hear it. Edits autosave;
**Project** has Open, Save as and New from template.

## Using it

**Map.** *Move*: click or drag to place the character; right-drag aims the camera.
It is third-person: distance is measured from the character and panning follows
the camera. WASD/arrows walk relative to the camera, Q/E turn it. *Edit*: drag
zones, corners and emitters; double-click an edge to add a corner; Delete removes.
*Draw zone*: click corners, then double-click or Enter. *Place emitter* uses the
selected loop event. *Play at point* fires the selected pad at that spot. Live
voices pulse in their bus colour; grey rings are virtualised (inaudible, still
keeping time). **Project → World map** sets the bounds and an optional top-down
level screenshot.

**Zones** cross-fade using their fade times and edge blend; the higher priority
wins where they overlap and the default zone takes what is left. Beds are 2D
loops. Spots spawn one-shots at random places around the character (distance
range, interval, max alive, chance, optionally inside the zone only); they stay
fixed in the world as you move. Interior zones low-pass and lower outside sounds
while you are inside, and inside sounds while you are outside. Each zone has a
convolution reverb preset; each sound's send comes from its attenuation (farther
= wetter). Beds, spots and emitters can be limited to Time / Weather states.

**Locomotion.** Idle/Walk/Run/Sprint sets the step rate and gain; walking with
WASD while Idle uses Walk. Footsteps receive `Surface` (from the zone under the
character), `Gait`, `Foot` (alternating) and `Speed`; cloth plays per step by
chance. Space jumps; Land follows after the air time.

**Soundboard.** Any event with *Show on soundboard* becomes a pad with an optional
one-key hotkey (not W A S D Q E or Space). One-shots fire; loops toggle. The
sliders beside the pads set that pad's Float parameters. Esc stops pad sounds.

**Inspector.** Events: bus, type (one-shot, loop, timed repeat), 2D/3D,
attenuation, layers, parameters (Float sliders; Enum switches such as Surface),
mappings (a parameter linearly drives event volume/pitch/filter/drive or a
layer's gain/pitch/chance; stack two on one layer to cross-fade light → heavy),
processing (attack/hold/release, biquad filter, waveshaper, delay, limiter), and
max voices with stop oldest/farthest/quietest or prevent new.

**Attenuation.** Sphere, capsule, box or cone; Unreal's distance models
(Linear, Logarithmic, Inverse, LogReverse, NaturalSound, Custom with draggable
points); stereo spread; wrap radius (Non-Spatialized Radius); air absorption;
reverb send — with a live graph.

**Mixer.** Bus faders, mute/solo, meters, master, reverb return, limiter ceiling
and ducks.

**Record** captures everything you hear to `Prophecy MetaSounds\Recordings`.

**Export for Unreal** writes `Unreal Export <date>` containing:

- `Sounds\<Bus>\<Event>\` — your WAVs renamed to convention (`CMB_Punch_Impact_01.wav`)
- `unreal_manifest.json` — every asset with Unreal property and enum names, a
  node-by-node MetaSound graph recipe per event, zones as AGV polygons + Soundscape
  palettes, emitters with locations, locomotion wiring
- `README_UNREAL.md` — import order and convention warnings (non-48 kHz files,
  stereo files in 3D one-shots)

## Limits and next steps

Monitoring is stereo (quad/5.1/7.1 beds are folded down). Not built yet:
occlusion by walls, listener focus, loudness (LUFS) metering, and an Unreal
editor script that creates the assets from the manifest. The app pans capsules
from their nearest point (spline-emitter style), which Unreal needs a spline to
match. Unreal's Soundscape plugin is still marked Beta.

`meta_ui.attach()` can embed this as a second tab of Sound Studio later.

## Tests

`python -m pytest -q test_metasounds.py test_metasounds_ui.py` — engine maths
against Unreal's formulas, layering, randomisation, panning, air absorption,
zones, interiors, spots, locomotion, ducking, reverb, limiter, determinism,
performance, UI flows and the export manifest.
