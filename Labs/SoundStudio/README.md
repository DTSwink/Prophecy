# Prophecy Sound Studio

Ready on Windows, updated October 24, 2026. Launch **Prophecy Sound Studio** from the desktop.
Native PySide6 app, independent of Unreal, browsers, training and existing labs.
All WAV processing is local; no uploads, model downloads or background services.

The current interface is the user's requested spectrum-first redesign. The older
small waveform / tabbed EQ layout is superseded. A large audio canvas dominates
the centre; the five coloured EQ sliders remain above it, with pitch beside it
and compact effects below. Folders can be hidden for additional canvas width.

## Workflow

1. Default source: `C:/Users/singerie/Documents/Sounds`. Subfolders are included.
   Choose a different folder, filter names, or drag one WAV into the app.
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
   gain, format, normalization and peak protection. A completed intermediate
   preview may play while the newest setting renders, but controls and the EQ
   curve always show your latest edit. Source changes discard obsolete work.
   Playback continues without stopping or resetting the device. One **Play / Pause** button controls playback. Tick **Play original**
   to bypass all processing and hear the full source, including its original trim,
   rate and channels. Untick to hear the current edit again. Switching keeps the
   audio stream running and preserves paused/playing state and playback time
   (clamped/wrapped if the other version is shorter). Your settings and exports
   are unchanged by this listening checkbox. During playback the spectrum
   measures a short window at the audible position, and the waveform scrolls
   through a two-second window. Stop returns to the whole-clip view. Click the
   waveform to seek. Preview and export share the rendered samples; format-rate
   changes are resampled only for monitoring on the already-running device.
4. Edit **Save as**, then **Generate WAV**. Default target:
   `C:/Users/singerie/Documents/Sounds Mixed`. Both folders have Choose, Refresh
   and Show in Explorer controls. Existing filenames receive `_002`, `_003`, etc.
5. Double-click a target WAV to remix it. Every successfully loaded sound resets
   processing, output format, trim, filename, loop and monitor volume to defaults.
   Folder choices persist. Failed loads leave the existing edit intact.

Drag IN / OUT on the small source strip to trim. The **Trim / extra effects**
dialog contains numeric trims, low cut, noise reduction, room size, reverse,
formant preservation and precise EQ widths. Fade, speed, reverb, polish, compression and gain
sliders remain beneath the audio canvas. Pitch is always at its side.

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
no reverb, polish, compression, denoise, normalization or peak protection. Source sample rate
and uncompressed PCM/float format are retained, with no added dither when the
samples are unchanged. Compressed WAV encodings export as float. An explicit
16-bit export is still available for Unreal. Peak protection can be enabled when
needed; it reduces the entire clip only above the estimated −1 dBTP ceiling.
Unsafe integer settings display the unclipped signal and block export; ongoing
playback keeps the last valid buffer until the settings are corrected.

**Loop is on by default. Space pauses/resumes; Left/Right seek by 0.25 seconds.**
These keys take precedence everywhere in the studio, including text fields,
sliders, lists and the details dialog. To put spaces into a filename, paste the
name. Seek preserves paused/playing state. The single Play button starts, pauses
or resumes the version selected by Play original. Stop returns to the start.
Changing a setting while paused updates the buffer and retains the position.
Double-click an effect slider to reset it; Reset resets the whole sound.
Ctrl+Enter generates a WAV.

**Refresh app** at the bottom left restarts with the latest local code. It keeps
current folder choices, WAV, processing settings, output name, loop/bypass settings and
window layout. Playback stops for the restart; press Space to listen again.
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
| Unreal delivery | [Epic's audio-import documentation](https://dev.epicgames.com/documentation/unreal-engine/importing-audio-files?lang=en-US) documents internal 16-bit conversion and recommends 16-bit import because its 24-bit conversion does not dither. 48 kHz and dithered 16-bit PCM are available as explicit export choices; defaults preserve the source rate and format. The documentation is the currently served page, not a claim that every engine/platform uses the same final runtime codec. |
| Working precision | Processing is floating point; quantization happens once at final output. Processed integer export adds TPDF dither; a neutral same-format copy does not add noise. [Audacity's quality guidance](https://manual.audacityteam.org/man/quality_preferences.html) describes dither for reduced-bit-depth conversion. Upsampling does not invent detail missing from the source. |
| Pitch and speed | [Rubber Band integration guidance](https://breakfastquay.com/rubberband/integration.html) recommends offline processing, the Finer engine, linked channels and high-quality pitch mode. Implemented through [Pedalboard time_stretch](https://spotify.github.io/pedalboard/reference/pedalboard.html#pedalboard.time_stretch): two-pass offline R3, stereo together, independent pitch/speed, optional vocal formant preservation. |
| Dynamics and peaks | No automatic loudness boosting or compression by default. Optional peak normalization is explicitly different from perceived-loudness normalization; [Audacity explains that distinction](https://www.audacityteam.org/manual/effects/volume-and-compression/loudness-normalisation/). 4× polyphase estimated true-peak protection lowers the entire clip if necessary, preserving dynamics. The target is −1 dBTP with a 0.05 dB quantization margin. This is an estimate, not a certified BS.1770 meter or a final-game loudness specification. Mix and audition assets in the game as well. |
| Edits and tails | Optional smooth fades reduce edge discontinuities; both default to zero at the user’s request. Fade times are output milliseconds, after pitch/speed. They shape the dry clip before reverb; a rendered reverb tail is retained and its final edge tapered. Reverb defaults off because the game may add environmental reverb itself. |
| Noise reduction | [Audacity's noise-reduction guidance](https://www.audacityteam.org/manual/effects/noise-removal-and-repair/noise-reduction/) describes steady-noise reduction and the artifacts caused by excessive filtering. The app uses optional [FFmpeg afftdn](https://ffmpeg.org/ffmpeg-filters.html#afftdn), a manual noise-floor estimate, modest 0–12 dB range and smoothing. It defaults off. Its overlap-add latency and tail are explicitly compensated; tests include 1 ms clips. This is not a learned noise-profile or voice-isolation tool. |
| A local “beauty filter” | [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) offers local 48 kHz **speech** enhancement. Applying a speech model to arbitrary impacts, monsters or ambience risks removing wanted material, so no speech model is installed. **Gentle polish** provides a local, optional low-mid reduction, slight air shelf and gentle slow-attack compression. It does not reconstruct missing detail. |
| Resampling | High-precision SoX resampling through FFmpeg (`soxr`, 28-bit precision). Native source rate is kept during effects and converted once if needed. |
| Channels | Keep source mono/stereo by default. Mono conversion is an explicit stereo average and can cancel out-of-phase material. Stereo conversion of mono duplicates the channel; it does not fabricate a stereo recording. Choose spatialization and final game compression settings in Unreal separately. |

Signal path: trim → optional reverse/channel conversion → offline pitch/speed →
optional noise reduction → high-pass/EQ → optional polish → smooth dry fades →
optional reverb with tail → optional compression → gain → resample → optional peak normalization →
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
by default. If protection is disabled and integer export would clip, saving fails
with an actionable message. Floating export can retain out-of-range samples.
Listening volume does not alter exports. Strong pitch shifts and denoising can
still introduce audible artifacts; compare them with the original.

## Installation and identity

Source: `Labs/SoundStudio`. `studio_layout.py` builds the compact native UI;
`visual_audio.py` calculates measured audio views and the matching EQ response.
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
mutation; source identity changes invalidate the cache. Compression edits reuse
the wet cache and run before output gain. Preview and export still
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
existing system FFmpeg path in ignored `runtime.json`, renders the SVG icon into
multi-resolution ICO and creates the desktop shortcut. Internet is needed for a
fresh dependency installation; normal operation is offline.

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
& Saved/SoundStudio/env/Scripts/python.exe -m pytest Labs/SoundStudio/test_studio.py -q
```

51 tests passed after adding live compression. They cover neutral sample equality,
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

Supports mono/stereo WAVs at 8–192 kHz, up to 256 MB of decoded float32 samples.
Very short cuts may be too short for a meaningful pitch transform; processing
reports an error if Rubber Band produces no audio. Large folder scans run locally
and may take time; Refresh picks up external file additions. Recipes are metadata,
not reloadable project sessions. This is a single-clip studio, not a multitrack DAW.

Dependencies keep their respective upstream licenses. Runtime wheels and FFmpeg
are installed locally, not vendored into the repository. The source and small
SVG/ICO assets are the maintainable deliverable; generated audio and test receipts
are outside the tracked application source.
