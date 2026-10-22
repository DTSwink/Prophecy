# Prophecy Sound Studio

Ready on Windows, October 22, 2026. Launch **Prophecy Sound Studio** from the desktop.
Native PySide6 app, independent of Unreal, browsers, training and existing labs.
All WAV processing is local; no uploads, model downloads or background services.

## Workflow

1. Default source: `C:/Users/singerie/Documents/Sounds`. Subfolders are included.
   Choose a different folder, filter names, or drag one WAV into the app.
2. Select a source WAV. Drag the waveform IN / OUT handles or use the trim sliders
   and numeric fields. Tabs contain timing, five-band EQ, reverb and polish controls.
   The lateral pitch slider changes pitch independently of speed.
3. Use **Original** and **Preview changes** to compare. Click the waveform to
   audition from that point within the trim. Loop is optional. **Listen** controls
   monitoring volume only. Preview and export share the same rendered samples.
4. Edit **Save as**, then **Generate WAV**. Default target:
   `C:/Users/singerie/Documents/Sounds Mixed`. Both folders have Choose, Refresh
   and Show in Explorer controls. Existing filenames receive `_002`, `_003`, etc.
5. Double-click a target WAV to remix it. Every successfully loaded sound resets
   processing, output format, trim, filename, loop and monitor volume to defaults.
   Folder choices persist. Failed loads leave the existing edit intact.

Double-click an effect slider to reset it; Reset all resets the whole sound.
Ctrl+Enter generates. Space plays/stops when focus is not editing text. Clicking
Original or Preview changes starts that version from the beginning of its trim.

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
| Unreal delivery | [Epic's audio-import documentation](https://dev.epicgames.com/documentation/unreal-engine/importing-audio-files?lang=en-US) documents internal 16-bit conversion and recommends 16-bit import because its 24-bit conversion does not dither. Default delivery is therefore 48 kHz, dithered 16-bit PCM; 24-bit masters and 32-bit float are available. The documentation is the currently served page, not a claim that every engine/platform uses the same final runtime codec. |
| Working precision | Processing is floating point; quantization happens once at final output. Integer export adds TPDF dither. [Audacity's quality guidance](https://manual.audacityteam.org/man/quality_preferences.html) describes dither for reduced-bit-depth conversion. Upsampling does not invent detail missing from the source. |
| Pitch and speed | [Rubber Band integration guidance](https://breakfastquay.com/rubberband/integration.html) recommends offline processing, the Finer engine, linked channels and high-quality pitch mode. Implemented through [Pedalboard time_stretch](https://spotify.github.io/pedalboard/reference/pedalboard.html#pedalboard.time_stretch): two-pass offline R3, stereo together, independent pitch/speed, optional vocal formant preservation. |
| Dynamics and peaks | No automatic loudness boosting or compression by default. Optional peak normalization is explicitly different from perceived-loudness normalization; [Audacity explains that distinction](https://www.audacityteam.org/manual/effects/volume-and-compression/loudness-normalisation/). 4× polyphase estimated true-peak protection lowers the entire clip if necessary, preserving dynamics. The target is −1 dBTP with a 0.05 dB quantization margin. This is an estimate, not a certified BS.1770 meter or a final-game loudness specification. Mix and audition assets in the game as well. |
| Edits and tails | Default 5 ms smooth fades reduce edge discontinuities. Fade times are output milliseconds, after pitch/speed. They shape the dry clip before reverb; a rendered reverb tail is retained and its final edge tapered. Reverb defaults off because the game may add environmental reverb itself. |
| Noise reduction | [Audacity's noise-reduction guidance](https://www.audacityteam.org/manual/effects/noise-removal-and-repair/noise-reduction/) describes steady-noise reduction and the artifacts caused by excessive filtering. The app uses optional [FFmpeg afftdn](https://ffmpeg.org/ffmpeg-filters.html#afftdn), a manual noise-floor estimate, modest 0–12 dB range and smoothing. It defaults off. Its overlap-add latency and tail are explicitly compensated; tests include 1 ms clips. This is not a learned noise-profile or voice-isolation tool. |
| A local “beauty filter” | [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) offers local 48 kHz **speech** enhancement. Applying a speech model to arbitrary impacts, monsters or ambience risks removing wanted material, so no speech model is installed. **Gentle polish** provides a local, optional low-mid reduction, slight air shelf and gentle slow-attack compression. It does not reconstruct missing detail. |
| Resampling | High-precision SoX resampling through FFmpeg (`soxr`, 28-bit precision). Native source rate is kept during effects and converted once if needed. |
| Channels | Keep source mono/stereo by default. Mono conversion is an explicit stereo average and can cancel out-of-phase material. Stereo conversion of mono duplicates the channel; it does not fabricate a stereo recording. Choose spatialization and final game compression settings in Unreal separately. |

Signal path: trim → optional reverse/channel conversion → offline pitch/speed →
optional noise reduction → high-pass/EQ → optional polish → smooth dry fades →
optional reverb with tail → gain → resample → optional peak normalization →
peak protection → optional integer dither/quantization → WAV.

Peak normalization boosts by at most 24 dB, leaves digital silence alone and is off
by default. If protection is disabled and integer export would clip, saving fails
with an actionable message. Floating export can retain out-of-range samples.
Listening volume does not alter exports. Strong pitch shifts and denoising can
still introduce audible artifacts; compare them with the original.

## Installation and identity

Source: `Labs/SoundStudio`. Dedicated Python environment:
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
playback redraw timer stops when playback stops. Closing during work requests
cancellation and waits for the current DSP stage to return before closing safely.

## Verification and limits

Run with the dedicated environment:

```powershell
& Saved/SoundStudio/env/Scripts/python.exe -m pip install pytest
& Saved/SoundStudio/env/Scripts/python.exe -m pytest Labs/SoundStudio/test_studio.py -q
```

26 tests passed during implementation. They cover neutral sample equality,
exact trim, independently measured pitch/speed and duration, fades and reverb
tails, EQ/noise/resampling, short-transient latency, mono/stereo conversion,
16/24/float export, preview/export equality, dither/peak safety, unique filenames,
source hashes, source-change rejection, invalid input, cancellation, and the actual
Qt selection → edit → renamed export → double-click remix → reset workflow.
Playback was exercised on the Windows output device at zero monitor gain; this is
device-path verification, not a claim of subjective listening evaluation.

Visual and identity receipts: `Saved/Diagnostics/SoundStudio20261022/`.
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
