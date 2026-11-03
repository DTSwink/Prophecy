# Prophecy Sound Studio

Ready on Windows, updated November 3, 2026. Launch **Prophecy Sound Studio** from the desktop.
Native PySide6 app, independent of Unreal, browsers, training and existing labs.
All WAV processing is local; no uploads, model downloads or background services.

The current interface is the user's requested spectrum-first redesign. The older
small waveform / tabbed EQ layout is superseded. A large audio canvas dominates
the centre. **EQ / Volume / Pitch** select its editing view, with exactly five
sliders and five draggable points in each view. EQ is the default. Global pitch
stays beside the canvas and compact effects below. Grain and sequence controls
move into the right sidebar on shorter windows, keeping the canvas usable.
Direct **Granular** and **Crossfade** buttons are in the header, along with one
central status/warning area and the red **Reset all** button. The old footer,
preview-message row, Live Preview badge, Folders/Guide buttons, format selectors
and Multiple takes controls are removed. **Refresh app** is inside the source
panel at the bottom left.

The current theme is **dark silver / gunmetal**: charcoal surroundings, a visibly
lighter neutral-grey spectrum and waveform surface, silver controls and clear
selected states. The bright silver-panel draft was rejected and is superseded.
Frequency colours, purple Play original and red Reset all retain their roles.
Shared control styling is in `studio_theme.py`; both painted envelope views use
the same neutral canvas colours. The user's Refresh app loads this appearance.
Visual checks cover EQ, volume, pitch, Clean controls, granular/crossfade panels
and the details dialog at 1520×970 and 1280×800. Eleven existing UI/integration
checks passed after the theme change; no DSP or playback behavior changed.
Captures: `Saved/Diagnostics/SoundStudio20261103/silver/`.

**Clean** sits in the centre of the sound title bar. It enables the user's selected
**Clear strong** cleanup and reveals an Amount slider, initially **100%**. Click
Clean again to bypass it. Zero percent is unchanged audio; 100% is the complete
cleanup; intermediate values blend the time-aligned original and cleaned sound.
The slider's reset arrow restores 100%. New sounds and Reset all turn Clean off
and restore 100%; Refresh app preserves both its enabled state and amount.

## Workflow

1. Default source: `C:/Users/singerie/Documents/Sounds`. Subfolders are included.
   Choose a different folder, filter names, or drag one WAV into the app.
   Both source and saved-mix lists sort by file creation date, oldest first;
   equal timestamps use the relative filename as a stable tie-breaker.
2. Select a source WAV. The main canvas shows a logarithmic frequency spectrum
   and the actual processed waveform. Frequencies follow a continuous colour map
   from warm bass colours through green, cyan and violet highs. The waveform is
   coloured by local spectral centroid. The dashed spectrum is the original.
   Click/drag a point on the spectrum to choose a band, frequency and gain;
   mouse wheel adjusts its Q width. Double-click resets that band. The white EQ
   response uses the right-hand gain scale; spectral levels use the left scale.
   The **L** handle holds its gain at every frequency to its left; **H** does
   the same to its right. Their curves never climb back toward neutral outside
   the handles. Every band now reaches **CUT** by dragging its point to the bottom
   or its slider fully left; numeric gain also supports CUT. For L/H this zeros
   the outer range; for middle bands 2–4 it places a full cut at the selected
   centre frequency, with attenuation around it controlled by Q. Middle bands
   support the full negative range, removing the old −12 dB limit. Near the
   neutral line, dragging snaps to exactly **0 dB**. Double-click restores neutral.
   Outer Q controls the smooth transition toward the centre, without resonance.
3. The EQ curve updates immediately as sliders move. Audio rendering starts
   within a 25 ms scheduling window and continues during dragging, including
   gain, normalization and peak protection. A completed intermediate
   preview may play while the newest setting renders, but controls and the EQ
   curve always show your latest edit. Source changes discard obsolete work.
   Playback continues without stopping or resetting the device. One **Play / Pause** button controls playback. Click the purple **Play original** toggle
   to bypass all processing and hear the full source, including its original trim,
   rate and channels. Click it again to hear the current edit. Switching keeps the
   audio stream running and preserves paused/playing state and playback time
   (clamped/wrapped if the other version is shorter). Your settings and exports
   are unchanged by this listening toggle. During playback the spectrum
   measures a short window at the audible position. The waveform starts with a
   two-second window and follows playback at its right edge. Waveform timestamps
   and the trim bar stay on the full source timeline: moving IN/OUT never rebases
   or shrinks the waveform. The trim bar has a red playback line for both original
   and processed audio, with speed/reverse/wrap mapping. Retained samples stay
   bright; excluded sections are greyed out on both waveform and trim strip.
   Click and drag the
   waveform to scrub; holding near either edge scrolls the time window, including
   while paused. The time mapping stays fixed during a drag except for this edge
   scrolling. Mouse wheel over the waveform stretches/compresses the time view
   around the pointer (20 ms to the whole clip); it never changes sound duration,
   pitch or the fixed64x amplitude scale. These gestures work in all three views
   and with original bypass. Playing seeks use the existing device callback;
   paused seeks remain paused. Stop returns to the whole-clip view; loading a new
   sound or Reset all restores the default time window. Preview and export share
   the rendered samples; bypassed
   source-rate changes are resampled only for monitoring on the running device.
4. Edit **Save as**, then **Generate WAV**. Default target:
   `C:/Users/singerie/Documents/Sounds Mixed`. Both folders have Choose, Refresh
   and Show in Explorer controls. Existing filenames receive `_002`, `_003`, etc.
5. Double-click a target WAV to remix it. Every successfully loaded sound resets
   processing, trim, filename, loop and bypass to defaults.
   Folder choices persist. Failed loads leave the existing edit intact.

Drag IN / OUT on the small source strip to trim. They can cross: playback starts
at IN, reaches the source end, wraps to its beginning and finishes at OUT.
OUT can be exactly zero. Equal handles mean one full revolution starting at IN.
For ordinary trims, both outer sections are greyed out. For wrapped trims, the
middle section between OUT and IN is greyed out; equal endpoints retain the whole
source. The red playhead wraps at the source end, then reaches OUT. Trim edits
retain the current source playback position if it is still included; otherwise
playback snaps to the nearest selection boundary without moving the viewport.
Reverb tails hold the source marker at the endpoint. Granular audio is explicitly
shown as selection progress, since scattered grains have no single source position.
Rendered amplitude remains visible at source coordinates; excluded audio remains
visible as a dim source waveform. No fade
or crossfade is silently added at the wrap; the original samples retain their
order, so a discontinuity already present between the source ends can be audible.
The **Trim / extra effects**
dialog contains numeric trims, low cut, noise reduction, room size, reverse,
formant preservation and precise EQ widths. Fade, speed, reverb, polish, compression and gain
sliders remain beneath the audio canvas. Pitch is always at its side.

### Volume and pitch envelopes

Switch between **EQ / Volume / Pitch** above the viewport. Switching views keeps
all three curves active and preserves their settings. Each has five sliders and
five points. Volume ranges from silence to 200%, with **100% neutral**; pitch
ranges from −24 to +24 semitones, with **0 st neutral**. The time fields locate
points as a percentage of the finished clip. Drag a point horizontally for time
and vertically for value; the first and last points stay at the endpoints.
Smooth interpolation avoids overshoot between points.

Use the **↺** button beside each slider, or double-click a slider/point, to reset
its value. EQ reset arrows also restore that band's frequency and Q.
**Reset view** resets only the selected curve, including its point positions.
The red **Reset all** clears all processing, envelope positions, grains/pattern,
trim, output name, loop/bypass options, stored sequence and join settings,
returning to the loaded source and EQ view. Folder locations and source files
are retained. Loading another sound also resets its processing.
Volume and pitch envelopes cover the
whole processed output, including any reverb tail. Pitch automation retains its
duration and stereo relationship using the local Rubber Band Finer R3 engine.
Neutral envelopes bypass processing exactly. The curves update immediately;
audio swaps in when rendering finishes, retaining playing/paused state and time.
Pitch automation and dense grains can need a few seconds; they do not interrupt
the existing playback stream while rendering.

### Clean: the selected Clear strong preset

Recovered from the chat **Clean latest Bandicam audio**
(`01a1942d-495c-7842-9427-adc5faf0ee25`) and its retained processing scripts in
`C:/Users/singerie/Documents/Bandicam/Audio Cleanup 2026-10-31/`.
The user chose `08_Clear_strong.wav`: Antinode Clear, ambience **−24 dB**, voice
reverb **−12 dB**, voice **0 dB**, Eco off, default linked/mono processing.
This uses that installed VST3 processor, not the separate FFmpeg noise-reduction
effect. Clean targets voice noise and room reverb; audition it carefully on other
game sounds and nonverbal textures.

As in the comparison, input is temporarily levelled to −3 dBFS for Clear, and the
result is matched over source-active 10 ms blocks with a −1.5 dBFS matching ceiling.
The temporary input gain is then undone: the studio does **not** add the old
comparison's +18.58 dB listening boost. The existing final mono/48 kHz/16-bit
conversion, chosen effects and peak safety remain in place.

Clear processes the complete source before trims, reverse, grains and other
effects. A full-strength result is cached within the existing 128 MiB limit;
changing Amount, trim or EQ reuses it while cached. Playback continues during
processing. Turning Clean off or using Reset all cancels an unfinished pass.
The plugin runs in a hidden isolated child process so cancellation and plugin
failures cannot take down the studio. Missing/failed plugin errors appear in the
top bar; there is no silent substitution with another cleaner.

The previous installation was the **Clear trial**. Its licensing is unchanged:
[Antinode states that unactivated trials add noise every 60 seconds](https://antinodeaudio.com/clear-download).
The app does not activate, purchase, suppress trial noise or reset the plugin
between audio chunks. One continuous pass covers the full source, including any
trial behavior. Activate the plugin normally for unrestricted exports.

### Granular synthesis

The top **Granular** button enables the effect and reveals its controls. Clicking
it while its controls are visible disables it. If Crossfade covers an active
grain panel, clicking Granular reopens it; a second click disables it.
It is off by default. **New pattern** changes the random seed; the same settings
and seed recreate the same grain pattern in preview and export.

| Control | Meaning |
| --- | --- |
| Size, 10–250 ms | Grain duration: short for fine texture, longer for recognizable fragments. |
| Density, 1–12× | Number of overlapping grains; higher values make a fuller cloud and take more work. |
| Position, 0–100% | Starting position in the trimmed source; the scan wraps. |
| Scatter, 0–100% | Random source-position spread around that scan. |
| Freeze position | Hold the scan at Position while Scatter can still explore around it. |
| Pitch spread, 0–12 st | Random up/down pitch range per grain. |
| Reverse chance, 0–100% | Probability that an individual grain plays backwards. |
| Length, 25–400% | Output duration relative to the trimmed source. |

Grains use Hann windows, overlap normalization, linked source channels and
band-limited interpolation. The default scan uses an 8× polyphase lookup;
upward pitch shifts use a rate-dependent sinc filter to reduce aliasing. These
choices improve continuity but cannot make every grain size/pitch combination
transparent. The controls are for texture design. Output is bounded to 256 MiB
and 60,000 grains per render. Volume envelopes, EQ and the other effects remain
available for shaping the result.

### Stitch clips and crossfade

Click **Crossfade** in the header. **Add source / Add mix** inserts the selected
WAV, or opens a file chooser when its browser is hidden. **Add current edit** adds
a snapshot of the sound you were editing, including its effects. Select a
sequence item, use the arrows to reorder it, or Remove it. Each item after the
first has an incoming crossfade, adjustable from zero to 10,000 ms.

**Equal gain** keeps identical overlapping material at its original level.
**Equal power** better maintains energy for unrelated clips, but correlated
material can rise in level. Automatic overload protection prevents clipping.
Effective overlap is capped at half of each neighbour, preserving short middle
clips and preventing three-way overlaps. Markers show the resulting joins on an
untrimmed sequence. The first clip sets the working sample rate; other clips are
resampled locally, and mono clips are duplicated if the sequence needs stereo.

The combined sequence becomes one editable sound: EQ, envelopes, grains and
normal export controls apply to it. Sequence edits rebuild without stopping
playback. Clicking **Crossfade** again while its panel is visible restores the
single-sound edit; switching again keeps the sequence. If grains cover the panel,
the first click reopens it. Up to 32 clips are supported within the memory limit.
Sequence generation checks every constituent source hash and records the clip
settings and joins in its recipe. Refresh app preserves the sequence and edit.

### Repeated generation and renaming

Generate repeatedly from one loaded sound after changing its settings; the
loaded source stays in place and filenames are numbered to prevent overwrites.
Each Generate click saves one clip, without stopping ongoing playback. Change
settings or click New pattern to create another variation, then Generate again.
Repeated clicks with unchanged settings make identical copies with unique names.
The previous automatic batch/variation controls are removed at the user's request.

**Rename selected** works in both source and mix browsers. It renames the WAV and
its accompanying recipe without changing the audio samples, rejects collisions,
and updates loaded/sequence references. Generation itself never renames sources.

**Compression** runs from **Off** (0%) to 100%. Dragging updates the sound and
waveform during playback, without stopping, seeking or waiting for release.
It reduces loud/quiet differences with a shared stereo gain envelope. The threshold
follows the clip's peak, so quiet assets respond too. No automatic makeup gain is
added; use Gain to adjust the final level. Off bypasses the compressor entirely,
preserving the original samples. New sounds and Reset restore Off; app refresh
retains the current amount. Play original bypasses compression along with the
other effects. Saved WAVs and recipes include the chosen amount.

The view is fixed at **64×**, and playback volume is **100%**. The View and Listen
controls and all hover popups are removed. Waveforms exceeding the magnified
view are visually cropped; this does not imply clipping in the audio itself.

Defaults are neutral: zero fades, flat EQ, unchanged pitch/speed/channels,
flat neutral volume/pitch envelopes, and granular synthesis off.
No reverb, polish, compression, denoise or normalization is enabled by default.
The studio now always prepares **48 kHz, mono, 16-bit PCM WAV**, with high-precision
resampling and TPDF dither at final quantization. These fixed output choices
supersede the old source-format default. Stereo is averaged to mono; compare the
original when phase cancellation matters. There is no universal "AAA" format;
this profile targets direct Unreal import using Epic's recommended bit depth.

Automatic overload protection is always enabled in the studio. When the
estimated true peak reaches full scale, it lowers the whole clip to approximately
−1 dBTP, preserving its dynamics. The header reports the reduction. Below full
scale it leaves level alone. **Protect peaks** remains an optional stricter
−1 dBTP ceiling even for signals that have not reached full scale. The old
integer-clipping popup and blocked preview are gone: both playback and export
use the protected samples. Other errors appear in the header, without a modal
warning popup. Source files are never processed in place.

**Loop is on by default. Space pauses/resumes; Left/Right seek by 0.25 seconds.**
These keys take precedence everywhere in the studio, including text fields,
sliders, lists and the details dialog. To put spaces into a filename, paste the
name. Seek preserves paused/playing state. The single Play button starts, pauses
or resumes the version selected by Play original. Stop returns to the start.
Changing a setting while paused updates the buffer and retains the position.
Every effect slider has a reset arrow; double-click also resets it.
Ctrl+Enter generates a WAV.

**Refresh app** at the bottom left restarts with the latest local code. It keeps
current folder choices, WAV, processing settings, envelope view, grain pattern,
sequence, output name, loop/bypass settings and window layout.
Playback stops for the restart; press Space to listen again.
Pending work is cancelled and drained before the single-instance lock is released
and a fresh interpreter starts. Normal launches and selecting another sound still
use fresh defaults; the refresh snapshot is consumed only by that restart.

Files are never overwritten. A `.recipe.json` records settings, UTC creation time,
source and output SHA-256, export format and measured levels beside each WAV.
The recipe is a provenance record; selecting a saved WAV deliberately starts fresh
instead of reapplying its previous processing. Source changes after loading are
detected before saving. WAV publication is atomic, with collision-safe naming.

## Audio decisions and research

The following sources were consulted before implementation and during verification.
Defaults are deliberately modest, suitable for editing game assets without forcing
everything to the same loudness. These are design choices, not a claim that one
preset improves every recording.

| Topic | Research and implementation |
| --- | --- |
| Unreal delivery | [Epic's audio-import documentation](https://dev.epicgames.com/documentation/unreal-engine/importing-audio-files?lang=en-US), checked November 3, documents internal 16-bit conversion and recommends 16-bit import because its 24-bit conversion does not dither. The studio fixes output at 48 kHz mono, dithered 16-bit PCM. The page describes import, not every platform's final runtime codec. |
| Working precision | Processing is floating point; quantization happens once at final output. Processed integer export adds TPDF dither; a neutral same-format copy does not add noise. [Audacity's quality guidance](https://manual.audacityteam.org/man/quality_preferences.html) describes dither for reduced-bit-depth conversion. Upsampling does not invent detail missing from the source. |
| Pitch and speed | [Rubber Band integration guidance](https://breakfastquay.com/rubberband/integration.html) recommends offline processing, the Finer engine, linked channels and high-quality pitch mode. Implemented through [Pedalboard time_stretch](https://spotify.github.io/pedalboard/reference/pedalboard.html#pedalboard.time_stretch): two-pass offline R3, stereo together, independent pitch/speed, optional vocal formant preservation. |
| Pitch automation | The official [Rubber Band R3 CLI](https://github.com/breakfastquay/rubberband/blob/default/main/main.cpp) supports sample-position pitch maps. The studio supplies a smoothed map every 256 input frames, linked stereo and optional formant preservation, with silence padding and exact duration cropping. Neutral automation bypasses it. |
| Granular synthesis | [Csound's partikkel reference](https://csound.com/docs/manual/partikkel.html) describes grain envelopes, duration/density, source positions, pitch and channel distribution. The studio implements its own seeded Hann overlap-add engine with these controls, gain normalization and band-limited sampling. It does not embed Csound. |
| Crossfades | [Audacity's crossfade guidance](https://manual.audacityteam.org/man/crossfade_tracks.html) explains equal-gain and equal-power curves and their level differences. Both are available; equal gain is the conservative default, with overlap bounded by the adjacent clip lengths. |
| Dynamics and peaks | No automatic loudness boosting or compression by default. Optional peak normalization is explicitly different from perceived-loudness normalization; [Audacity explains that distinction](https://www.audacityteam.org/manual/effects/volume-and-compression/loudness-normalisation/). 4× polyphase estimated true-peak protection lowers the entire clip if necessary, preserving dynamics. The target is −1 dBTP with a 0.05 dB quantization margin. This is an estimate, not a certified BS.1770 meter or a final-game loudness specification. Mix and audition assets in the game as well. |
| Edits and tails | Optional smooth fades reduce edge discontinuities; both default to zero at the user’s request. Fade times are output milliseconds, after pitch/speed. They shape the dry clip before reverb; a rendered reverb tail is retained and its final edge tapered. Reverb defaults off because the game may add environmental reverb itself. |
| Noise reduction | [Audacity's noise-reduction guidance](https://www.audacityteam.org/manual/effects/noise-removal-and-repair/noise-reduction/) describes steady-noise reduction and the artifacts caused by excessive filtering. The app uses optional [FFmpeg afftdn](https://ffmpeg.org/ffmpeg-filters.html#afftdn), a manual noise-floor estimate, modest 0–12 dB range and smoothing. It defaults off. Its overlap-add latency and tail are explicitly compensated; tests include 1 ms clips. This is not a learned noise-profile or voice-isolation tool. |
| A local “beauty filter” | [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) offers local 48 kHz **speech** enhancement. Applying a speech model to arbitrary impacts, monsters or ambience risks removing wanted material, so no speech model is installed. **Gentle polish** provides a local, optional low-mid reduction, slight air shelf and gentle slow-attack compression. It does not reconstruct missing detail. |
| Resampling | High-precision SoX resampling through FFmpeg (`soxr`, 28-bit precision). Native source rate is kept during effects and converted once if needed. |
| Channels | Mono output is fixed at the user's request. Stereo sources are averaged and can cancel out-of-phase material; Play original retains the untouched source for comparison. Choose spatialization and final game compression settings in Unreal separately. |

Signal path: optional cached Clear strong cleanup/blend → wrapped trim → optional reverse/channel conversion → optional granular synthesis → offline pitch/speed →
optional noise reduction → high-pass/EQ → optional polish → smooth dry fades →
optional reverb with tail → optional pitch envelope → optional compression →
volume envelope → gain → resample → optional peak normalization →
peak protection → optional integer dither/quantization → WAV.

The compression control uses the existing local
[Pedalboard compressor](https://spotify.github.io/pedalboard/reference/pedalboard.html#pedalboard.Compressor)
on a mono detector formed from the maximum absolute channel level, applying its
gain reduction equally to both channels. Amount maps the threshold from 0 to
30 dB below the clip peak and ratio from 1:1 to 8:1, with 10 ms attack and
120 ms release. These are studio design choices. Only the detector is normalized;
the audio receives downward gain only. Compression follows the cached wet effects,
so moving its slider reuses existing pitch, EQ, polish and reverb processing.

Peak normalization boosts by at most 24 dB, leaves digital silence alone and is off
by default. Studio output automatically reduces overloads. The reusable engine
still supports source/float/stereo formats and explicit rejection of unsafe
integer exports for callers that do not enable automatic protection.
Listening volume does not alter exports. Strong pitch shifts and denoising can
still introduce audible artifacts; compare them with the original.

## Installation and identity

Source: `Labs/SoundStudio`. `studio_layout.py` builds the compact native UI;
`visual_audio.py` calculates measured audio views and the matching EQ response.
`creative_tools.py` manages envelope controls, grains, renaming and
sequences; `envelope_display.py` draws the five-point automation views.
`creative_audio.py` contains their audio processing and file operations.
`clean_audio.py` hosts the exact Clear preset in an isolated process, restores
input level and supports the cached dry/clean blend. Pedalboard compensates the
plugin's reported latency; half a second of trailing silence flushes clip endings.
Unsupported Clear rates are converted locally to 48 kHz and back before blending,
retaining the source frame count.
Outer ranges use a shared smooth frequency mask and padded, channel-wise
[SciPy real FFT processing](https://docs.scipy.org/doc/scipy/reference/generated/scipy.fft.rfft.html).
The response is zero-phase, preserves duration/sample alignment and uses two
seconds of silence on each side to avoid joining the clip boundaries. Like other
zero-phase filters it can introduce pre-ringing on sharp transients. CUT sets
stopband mask coefficients to exactly zero; finite-clip/window leakage and
integer-export dither can still produce a residual spectrum noise floor.
The middle three bands and low cut now run in-process through
[SciPy second-order sections](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html),
using the same RBJ coefficients with float64 filter state. Tests compare against
FFmpeg’s explicit float64 reference. No temporary WAVs or FFmpeg startup are
needed for EQ; FFmpeg remains in use for denoise and SoX resampling.
Middle-band CUT uses notch zeros at the selected centre and keeps the deepest
finite bell's poles, avoiding a sudden width change on the last slider step.
Both graph and audio share these coefficients; the graph samples exact band
centres so deep cuts are visible. This extends the bell/notch forms in the
[W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/).

A worker-owned 128 MiB cache reuses unchanged pitch/speed/denoise preparation and
wet audio before final gain/output processing. Cached arrays are copied before
mutation; source identity changes invalidate the cache. Pitch automation has an
additional cache stage, so volume/compression edits reuse the completed pitch
curve. Compression and volume automation run before output gain. Preview and export still
use the same DSP and final samples. Rubber Band stays in its high-quality offline
mode: a new pitch/speed value or a long file can still require a substantial render.
Audio is published before whole-file visualization analysis finishes. Spectrum
analysis uses batched FFTs with half-window overlap, and waveform envelopes use
vectorized reductions. The playback stream requests the device’s low-latency mode.

Measured on the 6.08-second fireplace WAV: repeated EQ changes with pitch already
set fell from roughly 1.3–1.4 seconds of audio processing to 76–80 ms. The tested
slider-to-audible updates were about 0.19–0.29 seconds including UI/device latency,
with pitch and reverb combinations. Curve settings changed in 0.3 ms; screen
painting follows the Qt event loop. The actual device buffer was 91 ms and reported
no underruns during the benchmark. These are local measurements, not latency
promises for other devices or clip lengths. Receipts: `performance-before.json`,
`performance-after.json`, and `performance-ui.json` in the diagnostics directory.
October 24 compression check on the same WAV: slider-to-device updates took
0.21–0.28 seconds, including with pitch/reverb already enabled; no underruns.
The audio path was exercised at zero monitor gain. Layouts at 1280 and 1520 pixels
were inspected. Receipts: `Saved/Diagnostics/SoundStudio20261024/compression-*`.
Dedicated Python environment:
`Saved/SoundStudio/env`; other Python environments are not modified.

Run `Labs/SoundStudio/install.ps1` to repair/install. It uses the existing Stepper
Python 3.10 to create a separate venv, installs pinned requirements, records the
existing system FFmpeg path in ignored `runtime.json`, installs the official
Rubber Band 4.0 Windows CLI privately under `Saved/SoundStudio/tools`, renders the SVG icon into
multi-resolution ICO and creates the desktop shortcut. Internet is needed for a
fresh dependency installation; normal operation is offline.

`install_audio_tools.py` also installs/repairs just the private pitch-map CLI,
without changing the desktop shortcut. Its official archive is pinned by SHA-256;
the extracted release retains its upstream license. `runtime.json` records its
`rubberband` executable path alongside `ffmpeg`. No global PATH changes are made.

Clean uses the existing `%CommonProgramFiles%/VST3/Clear.vst3` installation.
An optional `clear_plugin` path in `runtime.json` overrides that location.
Clear is a separate proprietary dependency with its own activation; the studio
installer does not download, activate or bundle it. All other editing works
without Clear installed.

The desktop shortcut and running process share AppUserModelID
`Prophecy.SoundStudio.Desktop.1`; Qt sets both small and large window icons.
This follows [Microsoft's AppUserModelID guidance](https://learn.microsoft.com/en-us/windows/win32/shell/appids).
A per-user lock prevents duplicate studio instances; a second launch raises the
existing window. No persistent taskbar helper is used.

User preferences, logs and the current window/identity receipt are in
`%LOCALAPPDATA%/ProphecySoundStudio`. Only the source/target folder selections are
persisted. Editing settings are intentionally not restored across sounds/sessions.

The app has no web server, listener, cloud dependency or runtime telemetry. The
playback redraw timer stops when playback pauses or stops. Closing during work requests
cancellation and waits for the current DSP stage to return before closing safely.

## Verification and limits

Run with the dedicated environment:

```powershell
& Saved/SoundStudio/env/Scripts/python.exe -m pip install pytest
& Saved/SoundStudio/env/Scripts/python.exe -m pytest Labs/SoundStudio -q
```

**84 tests passed on November 3, 2026 (200.63 seconds).** The original 51 checks cover neutral sample equality in the engine,
exact trim, independently measured pitch/speed and duration, fades and reverb
tails, EQ/noise/resampling, short-transient latency, mono/stereo conversion,
16/24/float export, preview/export equality, dither/peak safety, unique filenames,
source hashes, source-change rejection, invalid input, cancellation, and the actual
Qt selection → edit → renamed export → double-click remix → reset workflow,
mouse-targeted EQ agreement with the actual filter, automatic normalization and
peak-protection displays, final latest-edit ordering during rapid edits, sample-exact
neutral defaults, local FFT/waveform movement, tooltip suppression, keyboard focus
priority, pause/seek/loop, continuous stream identity during EQ/rate/channel edits,
monotonic outer cuts, measured stopband/passband gain, true-zero combined cuts,
mouse access to CUT and exact neutral, refresh restoration with pending processing,
and single-button playback with original bypass, retained edits and uninterrupted
switching while playing or paused. New checks verify EQ against a float64 reference,
cached/uncached sample equality, pitch reuse and invalidation, bounded cache memory,
and delivered audio updates while a slider remains held down. Middle-band checks
measure −24 dB, deepest finite gain and CUT against the graph and rendered tones,
check the smooth last step, and drag all five sliders/graph handles to CUT and
back to neutral. Compression checks cover reduced dynamic range, quiet-asset response,
linked stereo, silence/short clips, exact Off bypass, cached/fresh equality, export
samples/recipe, input validation, updates during dragging, waveform changes, paused
position retention, original bypass, refresh persistence and reset on another sound.
The creative-feature checks add exact wrapped trims including zero/equal handles,
neutral and zero volume automation, measured pitch-map frequency/duration and
short clips, seeded grains and alias suppression, both crossfade laws, mixed-rate
sequences, complete source provenance, collision-safe rename, repeated/manual
generation, five sliders per envelope view, graph/reset synchronization,
playback continuity and refresh restoration of envelopes/grains/sequences.
The simplification checks cover all reset arrows, complete workspace reset,
overload playback/export equality, fixed mono/48 kHz/16-bit output, repeated
generation without stopping playback, header-only messages and direct mode buttons.
The visual regression covers the fixed 64× source trim strip:
loud source peaks are clipped to that strip and cannot paint over the spectrum
or other controls. The pixel comparison accounts for Windows display scaling.
The running production app is left for the user's Refresh app button.
A separate real-process refresh smoke check confirmed a new PID, consumed session,
responsive window, matching taskbar identity and no startup errors.
Playback was exercised on the Windows output device at zero monitor gain; this is
device-path verification, not a claim of subjective listening evaluation.

Visual and identity receipts: `Saved/Diagnostics/SoundStudio20261022/`.
`redesign-fireplace*.png` and `redesign-verification.json` cover the user's actual
fireplace WAV: automatic normalization increased measured peak from 0.029602 to
0.469635, while its source SHA-256 stayed identical. The default +24 dB boost cap
explains why this very quiet source does not reach the requested −3 dBFS target.
The 1 ms through 100 ms denoise tests preserve the position of the last transient
to within one source sample. Pitch-only tests retain exact clip frame counts;
speed tests remain within one sample of intended duration.

November 3 captures and measurements: `Saved/Diagnostics/SoundStudio20261103/`.
EQ, volume, pitch, grains, stitching and batch layouts were inspected at 1520×970
and 1280×800. On a wrapped 4.08-second portion of the fireplace WAV, default grain
rendering improved from about 6.1 seconds to 0.8–1.3 seconds after the polyphase
lookup optimization. A pitch-envelope render including UI work took about 3.2
seconds under concurrent load. These are local observations, not real-time
latency guarantees. Playback continues on its previous buffer while those
expensive edits render. The original WAV's SHA-256 remained unchanged.

The later simplified interface is captured in the `simplified/` subdirectory:
all five envelope knobs, reset arrows, direct mode buttons, header warnings and
compact layouts. The standard canvas grew from 519 to 572 pixels high at
1520×970 after removing the footer/message rows. Playback and repeated generation
of an overloaded edit were verified on a muted Windows device; output was mono,
48 kHz, PCM16 and sample-identical to its protected preview. The source hash
remained unchanged.

Clean receipts: `Saved/Diagnostics/SoundStudio20261103/clean/`. Reprocessing the
selected Bandicam source matched the chosen Clear strong reference (after undoing
its listening boost) with correlation **0.999999982**, zero measured sample lag
and RMS error **1.08e−6**. The initial 12.77-second stereo cleanup took about
33–34 seconds including plugin startup on this machine; a cached 50% amount
change took 1.06 seconds in the real UI test. Both retained the playback stream.
Tests additionally cover exact zero/Off bypass, blend endpoints,
source-cache reuse across trims/EQ, reset/refresh, cancelled/missing processing,
continuous playback and preview/export equality. Original comparison files were
read only.

Supports mono/stereo WAVs at 8–192 kHz, up to 256 MB of decoded float32 samples.
Very short cuts may be too short for a meaningful pitch transform; processing
reports an error if Rubber Band produces no audio. Large folder scans run locally
and may take time; Refresh picks up external file additions. Recipes are metadata,
not reloadable project sessions. Stitch mode assembles an ordered sequence into
one editable sound; it is not a multitrack mixing DAW.

Dependencies keep their respective upstream licenses. Runtime wheels and FFmpeg
are installed locally, not vendored into the repository. The source and small
SVG/ICO assets are the maintainable deliverable; generated audio and test receipts
are outside the tracked application source.
