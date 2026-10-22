"""Local, non-destructive WAV processing for Prophecy Sound Studio."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from pedalboard import Pedalboard, Reverb, Compressor, LowShelfFilter, HighShelfFilter, PeakFilter, time_stretch

HERE = Path(__file__).resolve().parent
APP_ID = 'Prophecy.SoundStudio.Desktop.1'
DEFAULT_SOURCE = Path.home() / 'Documents' / 'Sounds'
DEFAULT_TARGET = Path.home() / 'Documents' / 'Sounds Mixed'
DATA_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ProphecySoundStudio'
EQ_FREQUENCIES = (80, 250, 1000, 4000, 12000)


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled('Cancelled. No source files were changed.')


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class Settings:
    start: float = 0.0
    end: float = 0.0  # zero means full source length
    fade_in_ms: float = 5.0
    fade_out_ms: float = 5.0
    pitch: float = 0.0
    speed: float = 1.0
    eq: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)
    eq_frequencies: tuple = EQ_FREQUENCIES
    eq_q: tuple = (.85, .85, .85, .85, .85)
    highpass: float = 0.0
    reverb: float = 0.0
    room: float = 0.35
    polish: float = 0.0
    denoise: float = 0.0
    noise_floor: float = -60.0
    gain_db: float = 0.0
    normalize: bool = False
    normalize_db: float = -3.0
    protect: bool = True
    sample_rate: int = 48000  # zero means source rate
    subtype: str = 'PCM_16'
    channels: str = 'Keep source'
    reverse: bool = False
    formants: bool = False


@dataclass
class Audio:
    path: Path
    samples: np.ndarray  # frames, channels; float32
    rate: int
    subtype: str
    sha256: str

    @property
    def duration(self):
        return len(self.samples) / self.rate


def load_audio(path, cancel=None):
    path = Path(path).resolve()
    if path.suffix.lower() != '.wav':
        raise ValueError('Choose a .wav file.')
    before = path.stat()
    info = sf.info(path)
    if info.channels not in (1, 2):
        raise ValueError('This studio supports mono and stereo WAVs. Split surround files into stems first.')
    if info.frames < 1:
        raise ValueError('This WAV contains no audio samples.')
    if info.samplerate < 8000 or info.samplerate > 192000:
        raise ValueError('Supported source sample rates are 8–192 kHz.')
    if info.frames * info.channels * 4 > 256 * 1024 * 1024:
        raise ValueError('This file exceeds the studio’s 256 MB decoded-audio limit. Split it into smaller clips.')
    check_cancel(cancel)
    samples, rate = sf.read(path, dtype='float32', always_2d=True)
    if not np.isfinite(samples).all():
        raise ValueError('The WAV contains invalid floating-point samples (NaN or infinity).')
    digest = file_hash(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('The source changed while loading. Please select it again.')
    check_cancel(cancel)
    return Audio(path, samples, rate, info.subtype, digest)


def ffmpeg_path():
    config = HERE / 'runtime.json'
    if config.exists():
        candidate = json.loads(config.read_text(encoding='utf-8')).get('ffmpeg')
        if candidate and Path(candidate).is_file():
            return candidate
    candidate = shutil.which('ffmpeg')
    if not candidate:
        raise RuntimeError('FFmpeg is missing. Run install.ps1 to repair the local installation.')
    return candidate


def ffmpeg_filter(samples, rate, filters, cancel=None, output_rate=None):
    check_cancel(cancel)
    with tempfile.TemporaryDirectory(prefix='prophecy-sound-') as work:
        src, dst = Path(work) / 'input.wav', Path(work) / 'output.wav'
        sf.write(src, samples, rate, subtype='FLOAT')
        command = [ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-nostdin',
                   '-i', str(src), '-vn', '-af', ','.join(filters), '-c:a', 'pcm_f32le']
        if output_rate:
            command += ['-ar', str(output_rate)]
        command += ['-y', str(dst)]
        with open(Path(work) / 'error.txt', 'w+b') as errors:
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            started = time.monotonic()
            try:
                while process.poll() is None:
                    check_cancel(cancel)
                    if time.monotonic() - started > 600:
                        raise RuntimeError('Processing exceeded ten minutes. Try a shorter clip.')
                    time.sleep(0.05)
            except BaseException:
                process.kill()
                process.wait()
                raise
            if process.returncode:
                errors.seek(0)
                raise RuntimeError('Audio processing failed:\n' + errors.read().decode('utf-8', 'replace')[-3000:])
        result, result_rate = sf.read(dst, dtype='float32', always_2d=True)
    check_cancel(cancel)
    return result, result_rate


def db(value):
    return 20 * math.log10(max(float(value), 1e-12))


def true_peak(samples):
    """4x polyphase estimate, chunked with overlap to bound working memory."""
    peak = float(np.max(np.abs(samples), initial=0))
    block = 131072
    for start in range(0, len(samples), block):
        a, b = max(0, start - 64), min(len(samples), start + block + 64)
        high = resample_poly(samples[a:b], 4, 1, axis=0)
        valid = high[(start-a)*4:(min(len(samples), start+block)-a)*4]
        peak = max(peak, float(np.max(np.abs(valid), initial=0)))
    return peak


def statistics(samples, rate):
    rms = math.sqrt(float(np.mean(np.square(samples, dtype=np.float64))))
    return {'duration': len(samples) / rate, 'frames': len(samples),
            'sample_rate': rate, 'channels': samples.shape[1],
            'peak_dbfs': db(np.max(np.abs(samples), initial=0)), 'rms_dbfs': db(rms),
            'estimated_true_peak_dbtp': db(true_peak(samples))}


def validate(settings, audio):
    s = settings
    scalars = [s.start, s.end, s.fade_in_ms, s.fade_out_ms, s.pitch, s.speed, *s.eq, *s.eq_frequencies, *s.eq_q,
               s.highpass, s.reverb, s.room, s.polish, s.denoise, s.noise_floor, s.gain_db, s.normalize_db]
    if not all(math.isfinite(float(x)) for x in scalars):
        raise ValueError('All audio controls must be finite numbers.')
    if not (0 <= s.start < (s.end or audio.duration) <= audio.duration + 1e-6):
        raise ValueError('Trim end must be after trim start and inside the source.')
    if not (-12 <= s.pitch <= 12 and .5 <= s.speed <= 2):
        raise ValueError('Pitch must be within ±12 semitones; speed within 50–200%.')
    if len(s.eq) != 5 or any(abs(x) > 12 for x in s.eq):
        raise ValueError('Each of the five EQ bands must be within ±12 dB.')
    if len(s.eq_frequencies) != 5 or any(not 20 <= x <= 20000 for x in s.eq_frequencies):
        raise ValueError('EQ frequencies must be between 20 Hz and 20 kHz.')
    if len(s.eq_q) != 5 or any(not .2 <= x <= 8 for x in s.eq_q):
        raise ValueError('EQ width Q must be between 0.2 and 8.')
    if not (0 <= s.reverb <= .5 and 0 <= s.room <= 1 and 0 <= s.polish <= 1):
        raise ValueError('Invalid reverb or polish amount.')
    if not (0 <= s.denoise <= 12 and -80 <= s.noise_floor <= -20):
        raise ValueError('Invalid noise reduction setting.')
    if not (0 <= s.fade_in_ms <= 10000 and 0 <= s.fade_out_ms <= 10000 and 0 <= s.highpass <= 500):
        raise ValueError('Invalid fade or high-pass setting.')
    if not (-24 <= s.gain_db <= 18 and -24 <= s.normalize_db <= -1):
        raise ValueError('Invalid output level setting.')
    if s.sample_rate not in (0, 44100, 48000, 96000):
        raise ValueError('Unsupported export sample rate.')
    if s.subtype not in ('PCM_16', 'PCM_24', 'FLOAT') or s.channels not in ('Keep source', 'Mono', 'Stereo'):
        raise ValueError('Unsupported WAV format or channel mode.')


def render(audio, settings, cancel=None, progress=lambda text: None):
    validate(settings, audio)
    s = settings
    check_cancel(cancel)
    progress('Trimming and preparing audio…')
    a, b = round(s.start * audio.rate), round((s.end or audio.duration) * audio.rate)
    if b <= a:
        raise ValueError('The trim must contain at least one sample.')
    x = audio.samples[a:b].copy()
    rate = audio.rate
    notes = []
    if s.reverse:
        x = x[::-1].copy()
    if s.channels == 'Mono' and x.shape[1] == 2:
        x = np.mean(x, axis=1, keepdims=True)
        notes.append('Stereo averaged to mono; check phase cancellation by ear.')
    elif s.channels == 'Stereo' and x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    filters = []
    if s.pitch or s.speed != 1:
        progress('Changing pitch / speed with offline Rubber Band R3…')
        # Two-pass offline processing retains the complete clip and exact intended duration.
        x = time_stretch(np.ascontiguousarray(x.T), rate, stretch_factor=s.speed,
                         pitch_shift_in_semitones=s.pitch, high_quality=True,
                         preserve_formants=s.formants).T.copy()
        check_cancel(cancel)
    if s.denoise:
        # afftdn's 3-hop overlap-add window delays audio by 2 hops and does not
        # flush its own tail. Feed silence, then compensate in samples (not ms).
        # This is essential for clicks/impacts and clips shorter than 25 ms.
        hop = rate // 80
        filters += [f'apad=pad_len={3*hop}',
                    f'afftdn=nr={s.denoise}:nf={s.noise_floor}:tn=0:gs=5:nl=min',
                    f'atrim=start_sample={2*hop}:end_sample={2*hop+len(x)}', 'asetpts=PTS-STARTPTS']
        notes.append('Noise reduction is optional; compare transients and quiet tails with the original.')
    if s.highpass:
        filters.append(f'highpass=f={s.highpass}:poles=2')
    for f, gain, q in zip(s.eq_frequencies, s.eq, s.eq_q):
        if gain:
            # Below Nyquist even for low-rate source WAVs.
            freq = min(f, rate * .45)
            filters.append(f'equalizer=f={freq}:t=q:w={q}:g={gain}')
    if filters:
        x, rate = ffmpeg_filter(x, rate, filters, cancel)
    if not len(x):
        raise ValueError('This combination produced no audio. Use a longer trim.')
    if s.polish:
        progress('Applying gentle polish…')
        amount = s.polish
        board = Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=140, gain_db=-.7*amount),
            PeakFilter(cutoff_frequency_hz=320, gain_db=-1.5*amount, q=.8),
            HighShelfFilter(cutoff_frequency_hz=min(6500, rate*.35), gain_db=1.5*amount),
            Compressor(threshold_db=-18, ratio=1+.8*amount, attack_ms=25, release_ms=140),
        ])
        x = board(np.ascontiguousarray(x.T), rate).T.copy()
        notes.append('Polish: gentle low-mid cut, air shelf and slow-attack compression; no AI or automatic loudness boost.')
    check_cancel(cancel)
    # Times are in output milliseconds, independent of speed. Overlap is allowed.
    for fade_ms, at_end in ((s.fade_in_ms, False), (s.fade_out_ms, True)):
        n = min(len(x), round(fade_ms * rate / 1000))
        if n:
            ramp = np.sin(np.linspace(0, math.pi/2, n, dtype=np.float32)) ** 2
            if at_end:
                x[-n:] *= ramp[::-1, None]
            else:
                x[:n] *= ramp[:, None]
    if s.reverb:
        progress('Rendering reverb and its tail…')
        # Freeverb is offline, stereo-linked; append silence to flush internal delay lines.
        tail = int(rate * (2 + 8*s.room))
        padded = np.pad(x, ((0, tail), (0, 0)))
        board = Pedalboard([Reverb(room_size=.15+.7*s.room, damping=.55, wet_level=s.reverb,
                                  dry_level=1-s.reverb, width=1, freeze_mode=0)])
        x = board(np.ascontiguousarray(padded.T), rate).T.copy()
        active = np.flatnonzero(np.max(np.abs(x), axis=1) > 1e-5)
        end = min(len(x), max(len(padded)-tail, (int(active[-1])+int(.04*rate)) if len(active) else 0))
        x = x[:end]
        n = min(len(x), max(2, round(.01*rate)))
        x[-n:] *= np.linspace(1, 0, n, dtype=np.float32)[:, None]
        notes.append('Reverb tail retained after the trimmed clip; fades shape the dry clip before reverb.')
    x *= np.float32(10 ** (s.gain_db / 20))
    final_rate = s.sample_rate or rate
    if final_rate != rate:
        progress('Resampling with high-precision SoX…')
        x, rate = ffmpeg_filter(x, rate, [f'aresample={final_rate}:resampler=soxr:precision=28'], cancel, final_rate)
    if not np.isfinite(x).all():
        raise ValueError('Processing produced invalid samples. No output was saved.')
    peak = float(np.max(np.abs(x), initial=0))
    if s.normalize and peak > 1e-10:
        change = min(10 ** (s.normalize_db / 20) / peak, 10 ** (24/20))
        x *= np.float32(change)
        notes.append(f'Peak normalization applied {db(change):+.2f} dB (boost capped at +24 dB).')
    check_cancel(cancel)
    progress('Checking peaks and preparing WAV…')
    reduction = 0.0
    if s.protect:
        peak = true_peak(x)
        # 0.05 dB margin for dither/quantization and estimator rounding.
        ceiling = 10 ** (-1.05/20)
        if peak > ceiling:
            reduction = db(ceiling / peak)
            x *= np.float32(ceiling / peak)
            notes.append(f'Peak protection applied {reduction:.2f} dB globally to preserve dynamics.')
    if s.subtype != 'FLOAT':
        bits = 16 if s.subtype == 'PCM_16' else 24
        scale = 2 ** (bits-1)
        if np.max(np.abs(x), initial=0) >= 1:
            raise ValueError('The integer WAV would clip. Enable peak protection or reduce gain.')
        # Reproducible TPDF dither: preview and export have exactly the same samples.
        rng = np.random.default_rng(0x50524F50)
        out = x.astype(np.float64)
        out += (rng.random(x.shape) - rng.random(x.shape)) / scale
        out = np.rint(out * scale)
        x = (np.clip(out, -scale, scale-1) / scale).astype(np.float32)
    metrics = statistics(x, rate)
    metrics['protection_gain_db'] = reduction
    metrics['notes'] = notes
    check_cancel(cancel)
    return x, rate, metrics


def output_stem(name):
    name = str(name).strip()
    if name.lower().endswith('.wav'):
        name = name[:-4]
    name = name.rstrip(' .')
    if not name or len(name) > 150 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError('Use a filename of 1–150 characters without / \\ : * ? " < > |.')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *[f'{p}{n}' for p in ('COM', 'LPT') for n in range(1, 10)]}:
        raise ValueError('That filename is reserved by Windows. Choose another name.')
    return name


def save_render(audio, settings, result, target, name, cancel=None):
    """Unique filenames, atomic WAV publication, and a recipe beside each output."""
    stem = output_stem(name)
    target = Path(target).resolve()
    if not target.is_dir():
        raise ValueError('The target folder is unavailable. Choose an existing folder.')
    check_cancel(cancel)
    if not audio.path.exists() or file_hash(audio.path) != audio.sha256:
        raise ValueError('The source file changed or moved after loading. Select it again before generating.')
    x, rate, metrics = result
    temp = target / ('.soundstudio-' + uuid.uuid4().hex + '.tmp')
    destination = None
    try:
        sf.write(temp, x, rate, subtype=settings.subtype, format='WAV')
        check_cancel(cancel)
        for number in range(1, 100000):
            suffix = '' if number == 1 else f'_{number:03d}'
            candidate = target / (stem + suffix + '.wav')
            recipe_path = candidate.with_suffix('.recipe.json')
            if candidate.exists() or recipe_path.exists() or candidate == audio.path:
                continue
            try:
                # Windows rename refuses to overwrite an existing file.
                if os.name == 'nt':
                    os.rename(temp, candidate)
                else:
                    os.link(temp, candidate)
                    temp.unlink()
                destination = candidate
                break
            except FileExistsError:
                continue
        if destination is None:
            raise RuntimeError('Too many files with this name. Choose another name.')
        recipe = {'studio_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'source': str(audio.path), 'source_sha256': audio.sha256,
                  'source_sample_rate': audio.rate, 'source_subtype': audio.subtype,
                  'settings': asdict(settings), 'output': destination.name,
                  'output_sha256': file_hash(destination), 'metrics': metrics}
        try:
            atomic_json(destination.with_suffix('.recipe.json'), recipe)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination
    finally:
        temp.unlink(missing_ok=True)
