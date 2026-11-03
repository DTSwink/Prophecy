"""Real-time MetaSounds engine.

Signal flow per 1024-sample block (48 kHz), mirroring Unreal:

  event instance (MetaSound Source)
      layers: Random Get -> Wave Player (pitch/volume randomisation, delay, parameter bindings)
      event DSP: filter -> waveshaper -> delay -> envelope -> limiter
  spatialisation (Sound Attenuation): shape distance, falloff model, cone, air absorption,
      equal-power panning relative to the camera, stereo spread, non-spatialised radius,
      Audio-Gameplay-Volume interior filtering, reverb send by distance
  bus (Sound Class / Submix) fader, mute/solo, ducking (Control Bus Mix)
  zone reverbs (convolution, crossfaded by zone weight) -> master -> limiter

The world (zones, beds, Soundscape-style spot spawners, emitters, locomotion) is
advanced on the audio thread from the sample clock, so timing is block-accurate
and offline renders are deterministic for a given seed.

The UI never touches engine state directly: it queues commands, sets the
listener tuple, and reads the immutable `snapshot` dict.
"""
from __future__ import annotations

import itertools
import logging
import math
import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import lfilter, resample_poly, sosfilt, butter

from meta_model import (SAMPLE_RATE as SR, REVERBS, Attenuation, Event, Layer, Project, db_to_gain,
                        matches, point_in_polygon, zone_targets)

BLOCK = 1024
MAX_INSTANCES = 96
LOG = logging.getLogger('metasounds')
FALLBACK_ATT = Attenuation(id='__fallback__', name='Fallback', attenuate=False, air_absorption=False,
                           reverb_send=False)
_uid = itertools.count(1)


# ====================================================================== clips
class Clip:
    __slots__ = ('path', 'data', 'frames', 'channels', 'source_rate', 'source_channels', 'mtime')

    def __init__(self, path, data, source_rate, source_channels, mtime=0.):
        self.path = path
        self.data = np.ascontiguousarray(data, dtype=np.float32)
        self.frames = len(self.data)
        self.channels = self.data.shape[1]
        self.source_rate = source_rate
        self.source_channels = source_channels
        self.mtime = mtime


def downmix(data):
    """Fold multichannel beds to stereo for monitoring (quad / 5.1 / 7.1 WAV channel order)."""
    channels = data.shape[1]
    if channels <= 2:
        return data
    s = .7071
    if channels == 4:      # FL FR BL BR
        left, right = data[:, 0] + s * data[:, 2], data[:, 1] + s * data[:, 3]
    elif channels >= 6:    # FL FR FC LFE BL BR [SL SR]
        left = data[:, 0] + s * data[:, 2] + s * data[:, 4]
        right = data[:, 1] + s * data[:, 2] + s * data[:, 5]
        if channels >= 8:
            left, right = left + s * data[:, 6], right + s * data[:, 7]
    else:
        left, right = data[:, 0], data[:, 1]
    out = np.stack([left, right], axis=1)
    return out / (1 + s * (channels - 2) / 2)


def read_clip(path):
    path = str(path)
    data, rate = sf.read(path, dtype='float32', always_2d=True)
    source_channels = data.shape[1]
    data = downmix(data)
    if rate != SR:
        divisor = math.gcd(int(rate), SR)
        data = resample_poly(data, SR // divisor, int(rate) // divisor, axis=0).astype(np.float32)
    if len(data) < 2:
        data = np.zeros((2, data.shape[1]), np.float32)
    return Clip(path, data, rate, source_channels, os.path.getmtime(path))


class ClipCache:
    """Background WAV loading; the audio thread only ever reads finished clips."""

    def __init__(self):
        self.clips = {}
        self.missing = set()
        self.pending = set()
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(2, thread_name_prefix='metasound-load')
        self._info = {}

    def get(self, path):
        return self.clips.get(path)

    def state(self, path):
        if path in self.clips:
            return 'ready'
        if path in self.pending:
            return 'loading'
        return 'missing' if path in self.missing else 'unknown'

    def request(self, paths, blocking=False):
        for path in paths:
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                with self.lock:
                    self.missing.add(path)
                    self.clips.pop(path, None)
                continue
            with self.lock:
                clip = self.clips.get(path)
                if (clip is not None and clip.mtime == mtime) or path in self.pending:
                    continue
                self.pending.add(path)
            if blocking:
                self._load(path)
            else:
                self.pool.submit(self._load, path)

    def _load(self, path):
        try:
            clip = read_clip(path)
            with self.lock:
                self.clips[path] = clip
                self.missing.discard(path)
        except Exception as error:   # unreadable or vanished file
            LOG.warning('Could not load %s: %s', path, error)
            with self.lock:
                self.missing.add(path)
        finally:
            with self.lock:
                self.pending.discard(path)

    def wait(self, timeout=30.):
        deadline = time.monotonic() + timeout
        while self.pending and time.monotonic() < deadline:
            time.sleep(.005)
        return not self.pending

    def retain(self, keep):
        with self.lock:
            for path in list(self.clips):
                if path not in keep:
                    del self.clips[path]

    def info(self, path):
        """(sample rate, channels) from the header, or None when the file is unreadable."""
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        cached = self._info.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            header = sf.info(str(path))
            result = (int(header.samplerate), int(header.channels))
        except Exception:
            result = None
        self._info[path] = (mtime, result)
        return result


# ====================================================================== maths
def falloff_gain(att, distance):
    """Unreal distance models evaluated on distance outside the inner shape."""
    if distance <= 0:
        return 1.
    span = att.falloff
    if span <= 0 or distance >= span:
        return 0.
    t = distance / span
    model = att.model
    if model == 'Linear':
        g = 1 - t
    elif model == 'Logarithmic':
        g = .5 * -math.log(t)
    elif model == 'Inverse':
        g = .02 / t
    elif model == 'LogReverse':
        g = 1 + .5 * math.log(1 - t)
    elif model == 'NaturalSound':
        g = 10 ** (att.db_at_max * t / 20)
    else:
        g = curve_value(att.custom_curve, t)
    return min(1., max(0., g))


def curve_value(points, t):
    points = sorted(points)
    if not points:
        return 1 - t
    if t <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if t <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (t - x0) / (x1 - x0)
    return points[-1][1]


def shape_distance(att, sx, sy, yaw_deg, lx, ly):
    """(distance outside the shape, cone factor, point to pan from)."""
    dx, dy = lx - sx, ly - sy
    shape = att.shape
    if shape == 'Sphere':
        return max(0., math.hypot(dx, dy) - att.inner_radius), 1., (sx, sy)
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    local_x, local_y = dx * c + dy * s, -dx * s + dy * c
    if shape == 'Box':
        ox, oy = max(0., abs(local_x) - att.box_x), max(0., abs(local_y) - att.box_y)
        return math.hypot(ox, oy), 1., (sx, sy)
    if shape == 'Capsule':
        h = att.capsule_half_height
        along = min(h, max(-h, local_x))
        distance = math.hypot(local_x - along, local_y) - att.capsule_radius
        return max(0., distance), 1., (sx + along * c, sy + along * s)
    # Cone, pointing along yaw
    d = math.hypot(dx, dy)
    angle = math.degrees(math.acos(max(-1., min(1., local_x / d)))) if d > 1e-6 else 0.
    if angle <= att.cone_angle:
        cone = 1.
    else:
        cone = max(0., 1 - (angle - att.cone_angle) / max(att.cone_falloff_angle, 1e-6))
    return max(0., d - att.inner_radius), cone, (sx, sy)


def air_filters(att, distance):
    low, high = att.air_min, att.air_max
    t = 0. if distance <= low else 1. if distance >= high or high <= low else (distance - low) / (high - low)

    def interpolate(a, b):
        if att.log_frequency and a > 0 and b > 0:
            return math.exp(math.log(a) + (math.log(b) - math.log(a)) * t)
        return a + (b - a) * t
    return interpolate(att.lpf_at_min, att.lpf_at_max), interpolate(att.hpf_at_min, att.hpf_at_max)


def reverb_send_level(att, distance):
    if not att.reverb_send:
        return 0.
    span = att.reverb_dist_max - att.reverb_dist_min
    t = 0. if distance <= att.reverb_dist_min else 1. if span <= 0 or distance >= att.reverb_dist_max \
        else (distance - att.reverb_dist_min) / span
    return att.reverb_min + (att.reverb_max - att.reverb_min) * t


def equal_power(pan):
    theta = (max(-1., min(1., pan)) + 1) * math.pi / 4
    return math.cos(theta), math.sin(theta)


def pan_value(px, py, lx, ly, right, nonspatial_radius):
    vx, vy = px - lx, py - ly
    d = math.hypot(vx, vy)
    if d < 1e-6:
        return 0.
    pan = (vx * right[0] + vy * right[1]) / d
    if nonspatial_radius > 0 and d < nonspatial_radius:
        pan *= d / nonspatial_radius
    return pan


def biquad(kind, cutoff, q):
    cutoff = min(max(cutoff, 20.), SR * .45)
    q = max(q, .1)
    w0 = 2 * math.pi * cutoff / SR
    alpha, cw = math.sin(w0) / (2 * q), math.cos(w0)
    if kind == 'LowPass':
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
    elif kind == 'HighPass':
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    else:
        b = [alpha, 0., -alpha]
    a0 = 1 + alpha
    return np.array([[b[0] / a0, b[1] / a0, b[2] / a0, 1., -2 * cw / a0, (1 - alpha) / a0]])


def one_pole(x, cutoff, zi, highpass=False):
    """First-order low/high-pass with persistent state; bypasses cleanly at the extremes."""
    if highpass:
        if cutoff <= 20:
            a = math.exp(-2 * math.pi * 20 / SR)
            zi[:] = a * x[-1]
            return x
        a = math.exp(-2 * math.pi * min(cutoff, SR * .45) / SR)
        low, zi[:] = lfilter([1 - a], [1, -a], x, axis=0, zi=zi)
        return x - low
    if cutoff >= 19500:
        a = math.exp(-2 * math.pi * 19500 / SR)
        zi[:] = a * x[-1]
        return x
    a = math.exp(-2 * math.pi * max(cutoff, 20.) / SR)
    y, zi[:] = lfilter([1 - a], [1, -a], x, axis=0, zi=zi)
    return y


def limit_block(buf, previous, ceiling, release_s=.25):
    """Block peak limiter: instant attack (32-sample ramp), smooth release."""
    peak = float(np.max(np.abs(buf))) if len(buf) else 0.
    target = min(1., ceiling / peak) if peak > 0 else 1.
    if target < previous:
        new = target
    else:
        coefficient = 1 - math.exp(-len(buf) / (release_s * SR))
        new = previous + (min(1., target) - previous) * coefficient
        new = min(new, target)
    if new == previous == 1.:
        return buf, 1.
    ramp = np.full(len(buf), new, np.float32)
    k = min(32, len(buf))
    ramp[:k] = np.linspace(previous, new, k, dtype=np.float32)
    return buf * ramp[:, None], new


# ====================================================================== reverb
def make_impulse(preset, seed=11):
    spec = REVERBS.get(preset)
    if not spec:
        return None
    rng = np.random.default_rng(seed)
    pre = int(spec['predelay'] / 1000 * SR)
    decay = spec['decay']
    length = int(decay * 1.15 * SR)
    t = np.arange(length) / SR
    noise = rng.standard_normal((length, 2)).astype(np.float32)
    damping = spec['damping']
    bands = (('lowpass', 400, decay * 1.15), ('bandpass', (400, 3500), decay),
             ('highpass', 3500, decay * max(.12, 1 - damping)))
    tail = np.zeros_like(noise)
    for kind, cutoff, rt in bands:
        sos = butter(2, cutoff, kind, fs=SR, output='sos')
        tail += sosfilt(sos, noise, axis=0) * (10 ** (-3 * t / rt))[:, None]
    spacing = spec['early'] / 1000
    tail *= np.clip(t / (spacing * 2.5 + 1e-3), 0, 1)[:, None] ** 1.5
    early = np.zeros_like(tail)
    for k in range(1, 10):
        index = int(k * spacing * (1 + rng.uniform(-.3, .3)) * SR)
        if index < length:
            early[index, rng.integers(2)] += rng.choice((-1., 1.)) * .8 * (.72 ** k)
    ir = tail / np.sqrt(np.sum(tail ** 2) / 2) + early * .35
    ir = sosfilt(butter(1, 16000 * (1 - .55 * damping), 'lowpass', fs=SR, output='sos'), ir, axis=0)
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return np.concatenate([np.zeros((pre, 2), np.float32), ir.astype(np.float32)])


class Convolver:
    """Uniformly partitioned overlap-save convolution: mono in, stereo out."""

    def __init__(self, ir, block=BLOCK):
        self.B = block
        self.P = max(1, math.ceil(len(ir) / block))
        padded = np.zeros((self.P * block, 2), np.float32)
        padded[:len(ir)] = ir
        self.H = np.fft.rfft(padded.reshape(self.P, block, 2), n=2 * block, axis=1).astype(np.complex64)
        self.fdl = np.zeros((self.P, block + 1), np.complex64)
        self.head = 0
        self.previous = np.zeros(block, np.float32)
        self.idle = 0

    def reset(self):
        self.fdl.fill(0)
        self.previous.fill(0)

    def process(self, x):
        spectrum = np.fft.rfft(np.concatenate([self.previous, x]))
        self.previous = np.array(x, np.float32)
        self.head = (self.head - 1) % self.P
        self.fdl[self.head] = spectrum
        order = (self.head + np.arange(self.P)) % self.P
        y = np.einsum('pk,pkc->kc', self.fdl[order], self.H)
        return np.fft.irfft(y, n=2 * self.B, axis=0)[self.B:].astype(np.float32)


# ====================================================================== voices
class Picker:
    """Random Get (no repeats) / Shuffle / sequential choice of a take from a pool."""

    def __init__(self):
        self.last = None
        self.deck = []
        self.size = 0
        self.index = 0

    def pick(self, n, mode, rng):
        if n != self.size:
            self.size, self.deck, self.last, self.index = n, [], None, 0
        if n <= 1:
            self.last = 0
            return 0
        if mode == 'sequence':
            choice = self.index % n
            self.index += 1
        elif mode == 'shuffle':
            if not self.deck:
                self.deck = [int(i) for i in rng.permutation(n)]
                if self.deck[0] == self.last:
                    self.deck[0], self.deck[-1] = self.deck[-1], self.deck[0]
            choice = self.deck.pop(0)
        elif self.last is None:
            choice = int(rng.integers(n))
        else:
            choice = int(rng.integers(n - 1))
            if choice >= self.last:
                choice += 1
        self.last = choice
        return choice


class Voice:
    __slots__ = ('clip', 'pos', 'rate', 'gain', 'layer', 'delay', 'loop', 'done', 'previous', 'file')

    def __init__(self, clip, rate, gain, layer, delay, loop, pos=0., file=''):
        self.clip, self.rate, self.gain, self.layer = clip, rate, gain, layer
        self.delay, self.loop, self.pos, self.file = delay, loop, pos, file
        self.done = False
        self.previous = None

    def read(self, n, rate):
        clip = self.clip
        frames = clip.frames
        if self.loop:
            index = np.mod(self.pos + rate * np.arange(n), frames)
            self.pos = (self.pos + rate * n) % frames
        else:
            limit = frames - 1
            if self.pos >= limit:
                self.done = True
                return None
            count = min(n, max(1, math.ceil((limit - self.pos) / rate)))
            index = self.pos + rate * np.arange(count)
            self.pos += rate * count
            if self.pos >= limit:
                self.done = True
        i0 = index.astype(np.int64)
        fraction = (index - i0).astype(np.float32)[:, None]
        i1 = i0 + 1
        i1[i1 >= frames] = 0 if self.loop else frames - 1
        data = clip.data
        return data[i0] + (data[i1] - data[i0]) * fraction

    def skip(self, n, rate):
        """Advance without rendering (virtualised)."""
        if self.delay:
            if self.delay >= n:
                self.delay -= n
                return
            n -= self.delay
            self.delay = 0
        self.pos += rate * n
        if self.loop:
            self.pos %= self.clip.frames
        elif self.pos >= self.clip.frames - 1:
            self.done = True


MONO_2D = np.array([[.7071, .7071], [0., 0.]], np.float32)
STEREO_2D = np.array([[1., 0.], [0., 1.]], np.float32)


class Instance:
    """One playing event: a MetaSound Source instance."""

    def __init__(self, engine, event, params, position, owner, gain=1., attenuation=''):
        self.uid = next(_uid)
        self.event = event
        self.event_id = event.id
        self.params = params
        self.position = position          # (x, y, yaw degrees) or None
        self.owner = owner
        self.owner_gain = gain
        self.zone_link = None             # spot one-shots follow their zone's weight
        self.base_gain = gain
        self.attenuation = attenuation
        self.voices = []
        self.age = 0
        self.stopping = False
        self.release_left = self.release_total = 0
        self.done = False
        self.stereo = False
        self.level = 0.
        self.distance = 0.
        self.virtual = False
        self.silent_blocks = 0
        self.inside = None
        self.pending_layers = []
        self.repeat_timer = 0
        self.sos = self.sos_key = self.zi = None
        self.ring = None
        self.ring_pos = 0
        self.tail = 0
        self.limit = 1.
        self.matrix = None
        self.lp_zi = np.zeros((1, 2))
        self.hp_zi = np.zeros((1, 2))
        if event.kind == 'repeat':
            self.repeat_timer = int(engine.rng.uniform(0, max(event.repeat_min, .05)) * SR)
        else:
            self.hit(engine)

    # -------------------------------------------------------------- parameters
    def bound(self, target, layer=-1):
        values = [b.value(float(self.params.get(b.parameter, 0.) or 0.)) for b in self.event.bindings
                  if b.target == target and b.layer == layer and isinstance(self.params.get(b.parameter), (int, float))]
        return values

    def layer_gain(self, index):
        g = 1.
        for value in self.bound('gain', index):
            g *= max(0., value)
        return g

    def layer_pitch(self, index):
        return sum(self.bound('pitch', index))

    def hit(self, engine):
        event = self.event
        for index, layer in enumerate(event.layers):
            if not matches(layer.when, self.params):
                continue
            chance = layer.chance
            for value in self.bound('chance', index):
                chance *= max(0., value)
            if chance < 1 and engine.rng.random() >= chance:
                continue
            if not self.add_voice(engine, index, layer) and event.kind == 'loop':
                self.pending_layers.append(index)

    def add_voice(self, engine, index, layer):
        if not layer.files:
            return True
        choice = engine.picker(self.event_id, index).pick(len(layer.files), layer.selection, engine.rng)
        path = layer.files[choice]
        clip = engine.clips.get(path)
        if clip is None:
            engine.note_unavailable(path)
            return False
        rng = engine.rng
        pitch = layer.pitch_st + (rng.uniform(-layer.pitch_random, layer.pitch_random) if layer.pitch_random else 0.)
        volume = layer.gain_db + (rng.uniform(-layer.volume_random, layer.volume_random) if layer.volume_random else 0.)
        loop = self.event.kind == 'loop'
        start = rng.uniform(0, clip.frames - 1) if loop and self.event.random_start else 0.
        voice = Voice(clip, 2 ** (pitch / 12), db_to_gain(volume), index, int(layer.delay_ms * SR / 1000),
                      loop, start, path)
        self.voices.append(voice)
        if clip.channels == 2:
            self.stereo = True
        return True

    def stop(self, fade=None):
        if self.stopping:
            return
        self.stopping = True
        seconds = self.event.dsp.release_ms / 1000 if fade is None else fade
        self.release_total = self.release_left = max(64, int(seconds * SR))

    # -------------------------------------------------------------- render
    def render(self, engine, n):
        event = self.event
        if event.kind == 'repeat' and not self.stopping:
            self.repeat_timer -= n
            if self.repeat_timer <= 0:
                self.hit(engine)
                low, high = sorted((max(.05, event.repeat_min), max(.05, event.repeat_max)))
                self.repeat_timer += max(n, int(engine.rng.uniform(low, high) * SR))
        if self.pending_layers and engine.sample_clock % (BLOCK * 8) == 0:
            waiting, self.pending_layers = self.pending_layers, []
            for index in waiting:
                if index < len(event.layers) and not self.add_voice(engine, index, event.layers[index]):
                    self.pending_layers.append(index)

        matrix, lowpass, highpass, send, gain = engine.spatial(self)
        envelope_gain = db_to_gain(event.volume_db) * self.owner_gain * gain
        for value in self.bound('volume'):
            envelope_gain *= max(0., value)
        matrix = matrix * envelope_gain
        previous = self.matrix if self.matrix is not None else matrix
        self.age += n

        audible = bool(np.any(matrix > 1e-5) or np.any(previous > 1e-5))
        if not audible and not self.ring_active():
            self.virtual = True
            pitch = event.pitch_st + sum(self.bound('pitch'))
            for voice in self.voices:
                if voice.layer < len(event.layers):
                    voice.skip(n, voice.rate * 2 ** ((pitch + self.layer_pitch(voice.layer)) / 12))
                else:
                    voice.done = True
            self.voices = [v for v in self.voices if not v.done]
            self.matrix = matrix
            self.level = 0.
            if self.stopping:
                self.release_left -= n
            self.finish_check(n)
            return None
        self.virtual = False

        buf = np.zeros((n, 2), np.float32)
        pitch = event.pitch_st + sum(self.bound('pitch'))
        for voice in self.voices:
            if voice.done:
                continue
            if voice.layer >= len(event.layers):
                voice.done = True
                continue
            start = 0
            if voice.delay:
                if voice.delay >= n:
                    voice.delay -= n
                    continue
                start, voice.delay = voice.delay, 0
            rate = voice.rate * 2 ** ((pitch + self.layer_pitch(voice.layer)) / 12)
            data = voice.read(n - start, rate)
            if data is None:
                continue
            target = voice.gain * self.layer_gain(voice.layer)
            begin = target if voice.previous is None else voice.previous
            voice.previous = target
            m = len(data)
            ramp = np.linspace(begin, target, m, dtype=np.float32)[:, None] if begin != target else target
            buf[start:start + m] += data * ramp
        self.voices = [v for v in self.voices if not v.done]

        buf = self.dsp(buf, n)
        if lowpass is not None:
            buf = one_pole(buf, lowpass, self.lp_zi)
        if highpass is not None and highpass > 20:
            buf = one_pole(buf, highpass, self.hp_zi, highpass=True)
        elif highpass is not None:
            self.hp_zi[:] = math.exp(-2 * math.pi * 20 / SR) * buf[-1]

        ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        rows = previous + (matrix - previous)[None, :, :] * ramp[:, :, None]  # (n, in, out)
        out = buf[:, 0:1] * rows[:, 0, :] + buf[:, 1:2] * rows[:, 1, :]
        self.matrix = matrix
        self.level = float(np.sqrt(np.mean(out * out)))
        self.finish_check(n)
        mono_send = (out[:, 0] + out[:, 1]) * (.5 * send) if send > 0 else None
        return out, mono_send, self.level

    def ring_active(self):
        return self.ring is not None and self.tail > 0

    def dsp(self, buf, n):
        d = self.event.dsp
        cutoff = d.cutoff
        for value in self.bound('cutoff'):
            cutoff = value
        drive = d.drive
        for value in self.bound('drive'):
            drive = value
        if d.filter in ('LowPass', 'HighPass', 'BandPass'):
            key = (d.filter, round(cutoff, 1), round(d.q, 3))
            if key != self.sos_key:
                self.sos, self.sos_key = biquad(d.filter, cutoff, d.q), key
                if self.zi is None:
                    self.zi = np.zeros((1, 2, 2))
            buf, self.zi = sosfilt(self.sos, buf, axis=0, zi=self.zi)
            buf = buf.astype(np.float32)
        if drive > 0:
            k = 1 + 14 * min(1., drive)
            buf = np.tanh(buf * k) / math.tanh(k) * (10 ** (-10 * min(1., drive) / 20))
        if d.delay_ms >= 30:
            size = int(2.1 * SR) + BLOCK
            if self.ring is None:
                self.ring = np.zeros((size, 2), np.float32)
            delay = min(int(d.delay_ms * SR / 1000), size - n)
            read = (self.ring_pos - delay + np.arange(n)) % size
            write = (self.ring_pos + np.arange(n)) % size
            delayed = self.ring[read]
            self.ring[write] = buf + delayed * min(.95, max(0., d.feedback))
            self.ring_pos = (self.ring_pos + n) % size
            buf = buf + delayed * d.delay_mix
            if self.voices:   # echoes ring until roughly -60 dB
                feedback = min(.95, max(.01, d.feedback))
                echoes = min(40, max(1, math.ceil(math.log(1e-3) / math.log(feedback))))
                self.tail = delay * (echoes + 1)
            else:
                self.tail = max(0, self.tail - n)
        envelope = None
        a = int(d.attack_ms * SR / 1000)
        t = self.age - n + np.arange(n)
        if a > 0 and t[0] < a:
            envelope = np.clip(t / a, 0, 1).astype(np.float32)
        if d.hold_ms > 0 and self.event.kind == 'oneshot':
            release_start = a + int(d.hold_ms * SR / 1000)
            length = max(1, int(d.release_ms * SR / 1000))
            if t[-1] >= release_start:
                cut = np.clip(1 - (t - release_start) / length, 0, 1).astype(np.float32)
                envelope = cut if envelope is None else envelope * cut
                if t[-1] >= release_start + length:
                    self.done = True
        if self.stopping:
            left = self.release_left
            fade = np.clip((left - np.arange(n)) / self.release_total, 0, 1).astype(np.float32)
            envelope = fade if envelope is None else envelope * fade
            self.release_left -= n
        if envelope is not None:
            buf = buf * envelope[:, None]
        if d.limiter:
            buf, self.limit = limit_block(buf, self.limit, .98, .15)
        return buf

    def finish_check(self, n):
        if self.stopping and self.release_left <= 0:
            self.done = True
        elif self.event.kind == 'oneshot' and not self.voices and not self.ring_active():
            self.done = True


# ====================================================================== engine
class Engine:
    def __init__(self, project=None, seed=None):
        self.clips = ClipCache()
        self.rng = np.random.default_rng(seed)
        self.project = project.clone() if project else Project()
        self.revision = 0
        self.instances = []
        self.commands = deque()
        self.pickers = {}
        self.listener = (0., 0., 0.)        # x, y (cm), camera yaw (radians, map space)
        self.gait = 'Idle'
        self.moving = False
        self.zone_weights = {}
        self.cond_weights = {}
        self.owned = {}                     # ('bed'|'emitter', ...) -> Instance
        self.spot_timers = {}
        self.reverbs = {}
        self.reverb_previous = {}
        self.duck_state = {}
        self.bus_previous = {}
        self.master_previous = 1.
        self.limit_gain = 1.
        self.sample_clock = 0
        self.step_timer = 0.
        self.foot = 0
        self.previous_gait = 'Idle'
        self.land_timer = None
        self.surface = ''
        self.unavailable = deque(maxlen=12)
        self.recording = None
        self.stream = None
        self.error = ''
        self.cpu = 0.
        self.fifo = np.zeros((0, 2), np.float32)
        self.lock = threading.RLock()
        self.interior_zones = []
        self.snapshot = {}
        self._apply_project(self.project)

    # -------------------------------------------------------------- UI-thread API
    def _queue(self, fn, droppable=False):
        self.commands.append((time.monotonic(), droppable, fn))

    def set_project(self, project, blocking=False):
        project = project.clone()
        self.clips.request(project.referenced_files(), blocking=blocking)
        self._queue(lambda: self._apply_project(project))

    def set_listener(self, x, y, yaw):
        self.listener = (float(x), float(y), float(yaw))

    def set_gait(self, gait):
        self.gait = gait

    def set_moving(self, moving):
        self.moving = bool(moving)

    def set_states(self, values):
        values = dict(values)
        self._queue(lambda: self.project.state_values.update(values))

    def trigger(self, event_id, params=None, position=None, gain_db=0.):
        """Play an event: position None = at the character (3D) or 2D."""
        params = dict(params or {})
        self._queue(lambda: self._trigger(event_id, params, position, db_to_gain(gain_db), ('pad',)), True)

    def toggle_loop(self, event_id, params=None):
        params = dict(params or {})
        self._queue(lambda: self._toggle_loop(event_id, params), True)

    def stop_event(self, event_id):
        self._queue(lambda: [i.stop() for i in self.instances if i.event_id == event_id and i.owner[0] == 'pad'])

    def jump(self):
        self._queue(self._jump, True)

    def preview(self, path, gain_db=-3.):
        self.clips.request([path])
        event = Event(id='__preview__', name='Preview', bus='UI', kind='oneshot', spatial='2D',
                      layers=[Layer('Preview', [path], pitch_random=0, volume_random=0)], max_count=1)
        event.dsp.limiter = False

        def start(attempt=0):
            if self.clips.get(path) is None and self.clips.state(path) == 'loading' and attempt < 200:
                self._queue(lambda: start(attempt + 1))
                return
            for instance in self.instances:
                if instance.event_id == '__preview__':
                    instance.stop(.03)
            self._spawn(event, {}, None, ('preview',), db_to_gain(gain_db))
        self._queue(start)

    def stop_preview(self):
        self._queue(lambda: [i.stop(.05) for i in self.instances if i.event_id == '__preview__'])

    def stop_all(self):
        self._queue(lambda: [i.stop(.1) for i in self.instances if i.owner[0] in ('pad', 'preview')])

    def start_recording(self):
        with self.lock:
            self.recording = []

    def stop_recording(self):
        with self.lock:
            blocks, self.recording = self.recording, None
        if not blocks:
            return np.zeros((0, 2), np.float32)
        return np.concatenate(blocks)

    # -------------------------------------------------------------- output
    def start_output(self):
        if self.stream is not None:
            return
        import sounddevice as sd
        cutoff = time.monotonic() - .05
        self.commands = deque(c for c in self.commands if not (c[1] and c[0] < cutoff))
        self.fifo = np.zeros((0, 2), np.float32)
        self.stream = sd.OutputStream(samplerate=SR, channels=2, dtype='float32', blocksize=BLOCK,
                                      latency='low', callback=self._callback)
        self.stream.start()

    def stop_output(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:
                LOG.exception('Closing MetaSounds output failed')

    @property
    def running(self):
        return self.stream is not None

    def _callback(self, outdata, frames, timing, status):
        try:
            outdata[:] = self.pull(frames)
        except Exception as error:
            LOG.exception('MetaSounds render failed')
            self.error = str(error)
            outdata.fill(0)

    def pull(self, frames):
        with self.lock:
            while len(self.fifo) < frames:
                self.fifo = np.concatenate([self.fifo, self.render_block()])
            out, self.fifo = self.fifo[:frames], self.fifo[frames:]
        return out

    def render_seconds(self, seconds):
        blocks = max(1, int(math.ceil(seconds * SR / BLOCK)))
        with self.lock:
            return np.concatenate([self.render_block() for _ in range(blocks)])

    # -------------------------------------------------------------- audio thread
    def _drain(self):
        now = time.monotonic()
        for _ in range(len(self.commands)):   # commands queued while draining wait a block
            stamp, droppable, fn = self.commands.popleft()
            if droppable and now - stamp > .4 and self.stream is not None:
                continue
            try:
                fn()
            except Exception:
                LOG.exception('MetaSounds command failed')

    def _apply_project(self, project):
        self.project = project
        self.revision += 1
        self.interior_zones = [z for z in project.zones if z.interior and len(z.points) >= 3]
        for instance in self.instances:
            event = project.event(instance.event_id)
            if instance.event_id == '__preview__':
                continue
            if event is None:
                instance.stop(.1)
                continue
            if instance.event.kind != 'oneshot' and _signature(event) != _signature(instance.event):
                instance.stop(.15)          # owned loops respawn with the new definition
            instance.event = event
            instance.inside = None

    def picker(self, event_id, layer):
        key = (event_id, layer)
        if key not in self.pickers:
            self.pickers[key] = Picker()
        return self.pickers[key]

    def note_unavailable(self, path):
        if self.clips.state(path) != 'loading' and path not in self.unavailable:
            self.unavailable.append(path)

    def _params(self, event, given):
        values = {p.name: p.default_value() for p in event.parameters}
        values.update(given)
        return values

    def _spawn(self, event, params, position, owner, gain=1., attenuation='', respect_limits=True):
        if event is None or not event.layers:
            return None
        if respect_limits:
            active = [i for i in self.instances if i.event_id == event.id and not i.stopping]
            if len(active) >= max(1, event.max_count):
                if event.rule == 'PreventNew' or owner[0] == 'emitter':
                    return None
                if event.rule == 'StopQuietest':
                    victim = min(active, key=lambda i: i.level)
                elif event.rule == 'StopFarthestThenOldest':
                    victim = max(active, key=lambda i: (i.distance, i.age))
                else:
                    victim = max(active, key=lambda i: i.age)
                victim.stop(.03)
            live = [i for i in self.instances if not i.stopping]
            if len(live) >= MAX_INSTANCES:
                victims = [i for i in live if i.event.kind == 'oneshot'] or live
                min(victims, key=lambda i: i.level).stop(.03)
        instance = Instance(self, event, self._params(event, params), position, owner, gain, attenuation)
        if event.kind == 'oneshot' and not instance.voices and event.kind != 'repeat':
            return None
        self.instances.append(instance)
        return instance

    def _trigger(self, event_id, params, position, gain, owner):
        event = self.project.event(event_id)
        if event is None:
            return None
        if position is None and event.spatial == '3D':
            x, y, _ = self.listener
            position = (x, y, 0.)
        return self._spawn(event, params, position, owner, gain)

    def _toggle_loop(self, event_id, params):
        running = [i for i in self.instances if i.event_id == event_id and i.owner[0] == 'pad' and not i.stopping]
        if running:
            for instance in running:
                instance.stop()
        else:
            self._trigger(event_id, params, None, 1., ('pad',))

    def _jump(self):
        loco = self.project.locomotion
        surface = self.surface or loco.default_surface
        self._trigger(loco.jump_event, {'Surface': surface}, None, 1., ('loco',))
        self.land_timer = loco.air_time_ms / 1000

    def _cond(self, key, when, dt, fade=2.):
        target = 1. if matches(when, self.project.state_values) else 0.
        current = self.cond_weights.get(key)
        if current is None:
            current = target
        elif target > current:
            current = min(target, current + dt / fade)
        else:
            current = max(target, current - dt / fade)
        self.cond_weights[key] = current
        return current

    def _update_world(self, n):
        p = self.project
        dt = n / SR
        x, y, _ = self.listener
        targets = zone_targets(p, x, y)
        for zone in p.zones:
            target = targets.get(zone.id, 0.)
            current = self.zone_weights.get(zone.id)
            if current is None:
                current = target
            elif target > current:
                current = min(target, current + dt / max(zone.fade_in, 1e-3))
            else:
                current = max(target, current - dt / max(zone.fade_out, 1e-3))
            self.zone_weights[zone.id] = current
        best = 0.
        self.surface = p.locomotion.default_surface
        for zone in p.zones:
            if zone.surface and targets.get(zone.id, 0) > best:
                best, self.surface = targets[zone.id], zone.surface

        live = set()
        for zone in p.zones:
            weight = self.zone_weights.get(zone.id, 0.)
            for index, bed in enumerate(zone.beds):
                key = ('bed', zone.id, index)
                live.add(key)
                event = p.event(bed.event)
                gain = weight * self._cond(key, bed.when, dt) * db_to_gain(bed.gain_db)
                self._own(key, event, gain, None, '', dt)
        for emitter in p.emitters:
            key = ('emitter', emitter.id)
            live.add(key)
            event = p.event(emitter.event)
            gain = self._cond(key, emitter.when, dt) * db_to_gain(emitter.gain_db)
            self._own(key, event, gain, (emitter.x, emitter.y, emitter.yaw), emitter.attenuation, dt)
        for key in [k for k in self.owned if k not in live]:
            self.owned.pop(key).stop(.3)

        for zone in p.zones:
            weight = self.zone_weights.get(zone.id, 0.)
            for index, spot in enumerate(zone.spots):
                key = ('spot', zone.id, index)
                event = p.event(spot.event)
                if event is None:
                    continue
                if key not in self.spot_timers:
                    self.spot_timers[key] = self.rng.uniform(0, max(spot.interval_min, .1))
                if weight < .05 or not matches(spot.when, p.state_values):
                    continue
                self.spot_timers[key] -= dt
                if self.spot_timers[key] > 0:
                    continue
                low, high = sorted((max(.1, spot.interval_min), max(.1, spot.interval_max)))
                self.spot_timers[key] = self.rng.uniform(low, high)
                alive = sum(1 for i in self.instances if i.owner == key and not i.done)
                if alive >= spot.max_active or self.rng.random() >= spot.chance:
                    continue
                position = self._spot_position(zone, spot, x, y)
                if position is None:
                    continue
                instance = self._spawn(event, {}, position, key, weight * db_to_gain(spot.gain_db))
                if instance is not None:
                    instance.zone_link = zone.id
                    instance.base_gain = db_to_gain(spot.gain_db)
        for instance in self.instances:
            if instance.zone_link is not None:
                instance.owner_gain = instance.base_gain * self.zone_weights.get(instance.zone_link, 0.)

        self._locomotion(dt)

    def _own(self, key, event, gain, position, attenuation, dt):
        instance = self.owned.get(key)
        if instance is not None and (instance.done or instance.stopping or event is None
                                     or instance.event_id != event.id):
            if not instance.stopping:
                instance.stop(.3)
            self.owned.pop(key)
            instance = None
        if event is None or event.kind == 'oneshot':
            return
        if gain > 1e-4:
            if instance is None:
                instance = self._spawn(event, {}, position if event.spatial == '3D' else None, key, gain,
                                       attenuation, respect_limits=key[0] != 'bed')
                if instance is None:
                    return
                self.owned[key] = instance
            instance.owner_gain = gain
            instance.position = position if event.spatial == '3D' else None
            instance.attenuation = attenuation
            instance.silent_blocks = 0
        elif instance is not None:
            instance.owner_gain = 0.
            instance.silent_blocks += 1
            if instance.silent_blocks * dt > 1.:
                instance.stop(.05)
                self.owned.pop(key)

    def _spot_position(self, zone, spot, x, y):
        low, high = sorted((max(0., spot.distance_min), max(1., spot.distance_max)))
        for _ in range(12):
            angle = self.rng.uniform(0, 2 * math.pi)
            distance = math.sqrt(self.rng.uniform(low * low, high * high))
            px, py = x + math.cos(angle) * distance, y + math.sin(angle) * distance
            if not spot.inside_only or zone.is_default or point_in_polygon(px, py, zone.points):
                return (px, py, 0.)
        return None

    def _locomotion(self, dt):
        loco = self.project.locomotion
        gait = self.gait
        if gait == 'Idle' and self.moving:
            gait = 'Walk'
        if gait != self.previous_gait:
            if self.previous_gait == 'Idle':
                self._trigger(loco.start_event, {'Surface': self.surface}, None, 1., ('loco',))
                self.step_timer = .12
            elif gait == 'Idle':
                self._trigger(loco.stop_event, {'Surface': self.surface}, None, 1., ('loco',))
            self.previous_gait = gait
        if gait != 'Idle':
            self.step_timer -= dt
            if self.step_timer <= 0:
                cadence = max(.3, float(loco.cadence.get(gait, 2.)))
                self.step_timer += (1 / cadence) * self.rng.uniform(.97, 1.03)
                speed = {'Walk': .35, 'Run': .7, 'Sprint': 1.}.get(gait, .5)
                params = {'Surface': self.surface, 'Gait': gait, 'Foot': ('Left', 'Right')[self.foot], 'Speed': speed}
                gain = db_to_gain(float(loco.gain_db.get(gait, 0.)))
                self._trigger(loco.footstep_event, params, None, gain, ('loco',))
                if loco.cloth_event and self.rng.random() < loco.cloth_chance:
                    self._trigger(loco.cloth_event, params, None, gain, ('loco',))
                self.foot ^= 1
        if self.land_timer is not None:
            self.land_timer -= dt
            if self.land_timer <= 0:
                self.land_timer = None
                self._trigger(loco.land_event, {'Surface': self.surface}, None, 1., ('loco',))

    def spatial(self, instance):
        event = instance.event
        if event.spatial != '3D' or instance.position is None:
            instance.distance = 0.
            return (STEREO_2D if instance.stereo else MONO_2D), None, None, event.reverb_send, 1.
        p = self.project
        att = p.attenuation(instance.attenuation) or p.attenuation(event.attenuation) or FALLBACK_ATT
        sx, sy, yaw = instance.position
        lx, ly, camera = self.listener
        distance, cone, (px, py) = shape_distance(att, sx, sy, yaw, lx, ly)
        instance.distance = distance
        gain = falloff_gain(att, distance) * cone if att.attenuate else 1.
        extra_db, lowpass = self._interior(instance, sx, sy)
        highpass = 0.
        if att.air_absorption:
            air_low, highpass = air_filters(att, distance)
            lowpass = min(lowpass, air_low)
        if att.spatialize:
            right = (-math.sin(camera), math.cos(camera))
            if instance.stereo:
                half = att.stereo_spread / 2
                rows = []
                for side in (-1, 1):
                    pan = pan_value(px + side * half * right[0], py + side * half * right[1], lx, ly, right,
                                    att.nonspatial_radius)
                    left, rgt = equal_power(pan)
                    rows.append((left * .7071, rgt * .7071))
                matrix = np.array(rows, np.float32)
            else:
                left, rgt = equal_power(pan_value(px, py, lx, ly, right, att.nonspatial_radius))
                matrix = np.array([[left, rgt], [0., 0.]], np.float32)
        else:
            matrix = STEREO_2D if instance.stereo else MONO_2D
        send = reverb_send_level(att, distance)
        return matrix, lowpass, highpass, send, gain * db_to_gain(extra_db)

    def _interior(self, instance, sx, sy):
        if not self.interior_zones:
            return 0., 20000.
        if instance.inside is None or instance.inside[0] != self.revision or instance.owner[0] == 'pad':
            instance.inside = (self.revision, {z.id: point_in_polygon(sx, sy, z.points) for z in self.interior_zones})
        db, lowpass = 0., 20000.
        for zone in self.interior_zones:
            weight = self.zone_weights.get(zone.id, 0.)
            inside = instance.inside[1].get(zone.id)
            amount = (1 - weight) if inside else weight
            if amount <= 1e-3:
                continue
            zone_db, zone_lpf = (zone.inside_db, zone.inside_lpf) if inside else (zone.outside_db, zone.outside_lpf)
            db += zone_db * amount
            lowpass = min(lowpass, math.exp(math.log(20000) + (math.log(max(zone_lpf, 20.)) - math.log(20000)) * amount))
        return db, lowpass

    def _reverb_weights(self):
        weights = {}
        for zone in self.project.zones:
            weight = self.zone_weights.get(zone.id, 0.)
            if zone.reverb in REVERBS and REVERBS[zone.reverb] and weight > 0:
                weights[zone.reverb] = weights.get(zone.reverb, 0.) + weight * db_to_gain(zone.reverb_wet_db)
        return weights

    def _ducks(self, active, n):
        dt = n / SR
        result = {}
        for index, duck in enumerate(self.project.ducks):
            state = self.duck_state.setdefault(index, [0., 0.])
            if duck.source in active:
                state[1] = duck.hold_ms / 1000
                target = duck.amount_db
            elif state[1] > 0:
                state[1] -= dt
                target = duck.amount_db
            else:
                target = 0.
            depth = abs(duck.amount_db) or 1.
            if target < state[0]:
                state[0] = max(target, state[0] - depth * dt / max(duck.attack_ms / 1000, 1e-3))
            else:
                state[0] = min(target, state[0] + depth * dt / max(duck.release_ms / 1000, 1e-3))
            result[duck.target] = result.get(duck.target, 0.) + state[0]
        return result

    def render_block(self):
        started = time.perf_counter()
        self._drain()
        n = BLOCK
        p = self.project
        self._update_world(n)
        names = [b.name for b in p.buses]
        buses = {name: np.zeros((n, 2), np.float32) for name in names}
        sends = {name: np.zeros(n, np.float32) for name in names}
        active = set()
        for instance in self.instances:
            result = instance.render(self, n)
            if result is None:
                continue
            out, send, level = result
            bus = instance.event.bus if instance.event.bus in buses else names[0]
            buses[bus] += out
            if send is not None:
                sends[bus] += send
            if level > 3e-4:
                active.add(bus)
        self.instances = [i for i in self.instances if not i.done]

        duck = self._ducks(active, n)
        solo = any(b.solo for b in p.buses)
        master = np.zeros((n, 2), np.float32)
        reverb_in = np.zeros(n, np.float32)
        peaks = {}
        ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        for bus in p.buses:
            gain = 0. if bus.mute or (solo and not bus.solo) else db_to_gain(bus.volume_db + duck.get(bus.name, 0.))
            previous = self.bus_previous.get(bus.name, gain)
            self.bus_previous[bus.name] = gain
            mixed = buses[bus.name] * (previous + (gain - previous) * ramp)
            master += mixed
            reverb_in += sends[bus.name] * gain
            peaks[bus.name] = float(np.max(np.abs(mixed)))

        weights = self._reverb_weights()
        returned = db_to_gain(p.reverb_return_db)
        for name in set(weights) | {k for k, v in self.reverbs.items() if v.idle > 0}:
            weight = weights.get(name, 0.)
            convolver = self.reverbs.get(name)
            if convolver is None:
                if weight <= 0:
                    continue
                convolver = self.reverbs[name] = Convolver(make_impulse(name))
            previous = self.reverb_previous.get(name, 0.)
            self.reverb_previous[name] = weight
            if weight > 0 or previous > 0:
                convolver.idle = convolver.P + 2
            else:
                convolver.idle -= 1
                if convolver.idle <= 0:
                    convolver.reset()
                    continue
            feed = reverb_in * np.linspace(previous, weight, n, dtype=np.float32)
            master += convolver.process(feed) * returned
        peaks['Reverb'] = 0.

        target = db_to_gain(p.master_db)
        master *= np.linspace(self.master_previous, target, n, dtype=np.float32)[:, None]
        self.master_previous = target
        master, self.limit_gain = limit_block(master, self.limit_gain, db_to_gain(p.limiter_ceiling_db))
        np.clip(master, -1., 1., out=master)
        if self.recording is not None:
            self.recording.append(master.copy())
        self.sample_clock += n
        elapsed = time.perf_counter() - started
        self.cpu = .9 * self.cpu + .1 * (elapsed / (n / SR))
        self._publish(peaks, float(np.max(np.abs(master))))
        return master

    def _publish(self, peaks, master_peak):
        voices = []
        for instance in self.instances:
            if instance.position is not None and instance.event.spatial == '3D':
                voices.append((instance.position[0], instance.position[1], instance.level, instance.event.bus,
                               instance.virtual, instance.event.name, instance.owner[0]))
        self.snapshot = {
            'time': self.sample_clock / SR,
            'zones': dict(self.zone_weights),
            'voices': voices,
            'count': len(self.instances),
            'audible': sum(1 for i in self.instances if not i.virtual),
            'cpu': self.cpu,
            'peaks': peaks,
            'master': master_peak,
            'reduction_db': 20 * math.log10(max(self.limit_gain, 1e-6)),
            'surface': self.surface,
            'gait': self.previous_gait,
            'unavailable': list(self.unavailable),
            'recording': None if self.recording is None else len(self.recording) * BLOCK / SR,
            'pads': {i.event_id for i in self.instances if i.owner[0] == 'pad' and i.event.kind != 'oneshot'
                     and not i.stopping},
        }

    def shutdown(self):
        self.stop_output()
        self.clips.pool.shutdown(wait=False, cancel_futures=True)


def _signature(event):
    return (event.kind, event.spatial, tuple((tuple(l.files), l.selection) for l in event.layers))
