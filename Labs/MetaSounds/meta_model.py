"""MetaSounds project model.

Plain, JSON-serialisable dataclasses.  Every object mirrors an Unreal Engine 5
audio asset so a project can be ported mechanically:

    Event        -> MetaSound Source (layers = Wave Players, parameters = Inputs)
    Attenuation  -> Sound Attenuation asset (FSoundAttenuationSettings)
    Zone         -> Audio Gameplay Volume + Soundscape Palette
    Emitter      -> Ambient Sound actor
    Bus          -> Sound Class / Submix;  Duck -> Control Bus Mix

Distances are Unreal units (centimetres); levels are dB; pitch is semitones.
"""
from __future__ import annotations

import copy
import json
import math
import os
import typing
import uuid
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path

SCHEMA_VERSION = 1
SAMPLE_RATE = 48000

BUSES = ('Ambience', 'Foley', 'Combat', 'SFX', 'Voice', 'UI', 'Music')
BUS_PREFIX = {'Ambience': 'AMB', 'Foley': 'FOL', 'Combat': 'CMB', 'SFX': 'SFX',
              'Voice': 'VO', 'UI': 'UI', 'Music': 'MUS'}
BUS_COLORS = {'Ambience': '#5fc9a8', 'Foley': '#e3b26b', 'Combat': '#ef6f6c', 'SFX': '#8fb3ff',
              'Voice': '#d29bf0', 'UI': '#c3cad6', 'Music': '#f2d16b'}
KINDS = ('oneshot', 'loop', 'repeat')
KIND_LABELS = {'oneshot': 'One-shot', 'loop': 'Loop', 'repeat': 'Timed repeat'}
SELECTIONS = ('random', 'shuffle', 'sequence')
SELECTION_LABELS = {'random': 'Random, no repeat', 'shuffle': 'Shuffle', 'sequence': 'In order'}
DISTANCE_MODELS = ('Linear', 'Logarithmic', 'Inverse', 'LogReverse', 'NaturalSound', 'Custom')
SHAPES = ('Sphere', 'Capsule', 'Box', 'Cone')
RULES = ('StopOldest', 'StopFarthestThenOldest', 'StopQuietest', 'PreventNew')
RULE_LABELS = {'StopOldest': 'Stop oldest', 'StopFarthestThenOldest': 'Stop farthest',
               'StopQuietest': 'Stop quietest', 'PreventNew': 'Prevent new'}
FILTERS = ('Off', 'LowPass', 'HighPass', 'BandPass')
GAITS = ('Idle', 'Walk', 'Run', 'Sprint')
EVENT_TARGETS = ('volume', 'pitch', 'cutoff', 'drive')
LAYER_TARGETS = ('gain', 'pitch', 'chance')
TARGET_LABELS = {'volume': 'volume ×', 'pitch': 'pitch st', 'cutoff': 'filter Hz', 'drive': 'drive',
                 'gain': 'gain ×', 'chance': 'chance ×'}

# Reverb presets: decay (RT60, s), pre-delay (ms), HF damping (0..1), early-reflection
# spacing (ms).  Exported as starting values for Unreal Reverb Effect assets.
REVERBS = {
    'None':        None,
    'Small Room':  dict(decay=.45, predelay=4,  damping=.55, early=7),
    'Wood Room':   dict(decay=.85, predelay=7,  damping=.6,  early=9),
    'Stone Hall':  dict(decay=1.9, predelay=16, damping=.3,  early=14),
    'Cave':        dict(decay=3.2, predelay=24, damping=.35, early=19),
    'Cathedral':   dict(decay=4.6, predelay=34, damping=.25, early=26),
    'Courtyard':   dict(decay=1.1, predelay=12, damping=.5,  early=21),
    'Forest':      dict(decay=1.3, predelay=14, damping=.78, early=17),
    'Open Field':  dict(decay=.55, predelay=22, damping=.85, early=30),
    'Canyon':      dict(decay=2.6, predelay=70, damping=.45, early=60),
}

DEFAULT_HOME = Path.home() / 'Documents' / 'Prophecy MetaSounds'


def new_id(prefix):
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def db_to_gain(db):
    return 0. if db <= -80 else 10 ** (db / 20)


# ---------------------------------------------------------------- events
@dataclass
class Parameter:
    """MetaSound Input.  float -> Float input; enum -> Int32 input with named options."""
    name: str = 'Intensity'
    kind: str = 'float'
    minimum: float = 0.
    maximum: float = 1.
    default: float = .5
    options: list = field(default_factory=list)
    automatic: bool = False   # set by the world (Surface, Gait, Foot, Speed), not by sliders

    def default_value(self):
        if self.kind == 'enum':
            return self.options[0] if self.options else ''
        return self.default


@dataclass
class Binding:
    """Maps a parameter onto a target, linearly between (x0, y0) and (x1, y1), clamped."""
    parameter: str = 'Intensity'
    target: str = 'gain'
    layer: int = -1           # -1 = whole event; otherwise layer index
    x0: float = 0.
    x1: float = 1.
    y0: float = 0.
    y1: float = 1.

    def value(self, x):
        if self.x1 == self.x0:
            t = 1. if x >= self.x1 else 0.
        else:
            t = min(1., max(0., (x - self.x0) / (self.x1 - self.x0)))
        return self.y0 + (self.y1 - self.y0) * t


@dataclass
class Layer:
    """One ingredient of an event: a pool of interchangeable takes (Wave Player + Random Get)."""
    name: str = 'Layer'
    files: list = field(default_factory=list)
    selection: str = 'random'
    delay_ms: float = 0.
    gain_db: float = 0.
    chance: float = 1.
    pitch_st: float = 0.
    pitch_random: float = 1.
    volume_random: float = 1.5
    when: dict = field(default_factory=dict)   # {enum parameter: [allowed options]}


@dataclass
class DSP:
    attack_ms: float = 0.
    hold_ms: float = 0.        # 0 = play to the end
    release_ms: float = 80.
    filter: str = 'Off'
    cutoff: float = 2000.
    q: float = .707
    drive: float = 0.          # 0..1 waveshaper amount
    delay_ms: float = 0.       # 0 = off; otherwise 30..2000
    feedback: float = .3
    delay_mix: float = .25
    limiter: bool = True


@dataclass
class Event:
    id: str = ''
    name: str = 'New event'
    bus: str = 'SFX'
    kind: str = 'oneshot'
    spatial: str = '3D'
    attenuation: str = ''
    volume_db: float = 0.
    pitch_st: float = 0.
    repeat_min: float = 2.
    repeat_max: float = 6.
    random_start: bool = True
    reverb_send: float = 0.    # used for 2D sounds; 3D sends come from attenuation
    layers: list = field(default_factory=list)
    parameters: list = field(default_factory=list)
    bindings: list = field(default_factory=list)
    dsp: DSP = field(default_factory=DSP)
    max_count: int = 8
    rule: str = 'StopOldest'
    pad: bool = False
    hotkey: str = ''

    def parameter(self, name):
        return next((p for p in self.parameters if p.name == name), None)

    def all_files(self):
        return [f for layer in self.layers for f in layer.files]


# ---------------------------------------------------------------- attenuation
@dataclass
class Attenuation:
    id: str = ''
    name: str = 'Attenuation'
    attenuate: bool = True
    shape: str = 'Sphere'
    inner_radius: float = 400.
    box_x: float = 400.
    box_y: float = 400.
    capsule_half_height: float = 600.
    capsule_radius: float = 200.
    cone_angle: float = 30.
    cone_falloff_angle: float = 40.
    falloff: float = 3600.
    model: str = 'Linear'
    db_at_max: float = -60.
    custom_curve: list = field(default_factory=lambda: [[0., 1.], [.25, .55], [.6, .2], [1., 0.]])
    spatialize: bool = True
    stereo_spread: float = 200.
    nonspatial_radius: float = 0.
    air_absorption: bool = True
    air_min: float = 1000.
    air_max: float = 6000.
    lpf_at_min: float = 20000.
    lpf_at_max: float = 4000.
    hpf_at_min: float = 0.
    hpf_at_max: float = 0.
    log_frequency: bool = True
    reverb_send: bool = True
    reverb_min: float = .15
    reverb_max: float = .7
    reverb_dist_min: float = 300.
    reverb_dist_max: float = 4000.

    def max_distance(self):
        inner = {'Sphere': self.inner_radius, 'Cone': self.inner_radius,
                 'Box': max(self.box_x, self.box_y),
                 'Capsule': self.capsule_half_height + self.capsule_radius}[self.shape]
        return inner + self.falloff


# ---------------------------------------------------------------- world
@dataclass
class Bed:
    event: str = ''
    gain_db: float = 0.
    when: dict = field(default_factory=dict)  # {state: [values]}


@dataclass
class Spot:
    """Soundscape colour: one-shots spawned around the listener at random places."""
    event: str = ''
    gain_db: float = 0.
    interval_min: float = 3.
    interval_max: float = 10.
    distance_min: float = 600.
    distance_max: float = 3000.
    max_active: int = 3
    chance: float = 1.
    inside_only: bool = True
    when: dict = field(default_factory=dict)


@dataclass
class Zone:
    id: str = ''
    name: str = 'Zone'
    color: str = '#5fc9a8'
    points: list = field(default_factory=list)
    is_default: bool = False
    priority: int = 0
    edge_blend: float = 300.
    fade_in: float = 1.5
    fade_out: float = 2.
    surface: str = ''
    reverb: str = 'None'
    reverb_wet_db: float = -6.
    interior: bool = False
    outside_lpf: float = 1200.
    outside_db: float = -8.
    inside_lpf: float = 900.
    inside_db: float = -12.
    beds: list = field(default_factory=list)
    spots: list = field(default_factory=list)


@dataclass
class Emitter:
    id: str = ''
    name: str = 'Emitter'
    event: str = ''
    x: float = 0.
    y: float = 0.
    z: float = 0.
    yaw: float = 0.
    gain_db: float = 0.
    attenuation: str = ''     # '' = use the event's attenuation
    when: dict = field(default_factory=dict)


@dataclass
class Bus:
    name: str = 'SFX'
    volume_db: float = 0.
    mute: bool = False
    solo: bool = False


@dataclass
class Duck:
    source: str = 'Combat'
    target: str = 'Ambience'
    amount_db: float = -4.
    attack_ms: float = 15.
    hold_ms: float = 250.
    release_ms: float = 700.


@dataclass
class Locomotion:
    footstep_event: str = ''
    cloth_event: str = ''
    cloth_chance: float = .7
    start_event: str = ''
    stop_event: str = ''
    jump_event: str = ''
    land_event: str = ''
    air_time_ms: float = 550.
    default_surface: str = 'Dirt'
    cadence: dict = field(default_factory=lambda: {'Walk': 1.85, 'Run': 2.7, 'Sprint': 3.3})
    gain_db: dict = field(default_factory=lambda: {'Walk': -4., 'Run': 0., 'Sprint': 2.})
    speed: dict = field(default_factory=lambda: {'Walk': 170., 'Run': 420., 'Sprint': 650.})


@dataclass
class WorldMap:
    min_x: float = -6000.
    min_y: float = -6000.
    max_x: float = 6000.
    max_y: float = 6000.
    image: str = ''
    start_x: float = 0.
    start_y: float = 0.


@dataclass
class Project:
    version: int = SCHEMA_VERSION
    name: str = 'Prophecy'
    events: list = field(default_factory=list)
    attenuations: list = field(default_factory=list)
    zones: list = field(default_factory=list)
    emitters: list = field(default_factory=list)
    buses: list = field(default_factory=lambda: [Bus(name) for name in BUSES])
    ducks: list = field(default_factory=list)
    locomotion: Locomotion = field(default_factory=Locomotion)
    world: WorldMap = field(default_factory=WorldMap)
    states: dict = field(default_factory=lambda: {'TimeOfDay': ['Dawn', 'Day', 'Dusk', 'Night'],
                                                  'Weather': ['Clear', 'Rain', 'Storm']})
    state_values: dict = field(default_factory=lambda: {'TimeOfDay': 'Day', 'Weather': 'Clear'})
    master_db: float = 0.
    reverb_return_db: float = 0.
    limiter_ceiling_db: float = -1.

    # lookups ------------------------------------------------------------
    def event(self, event_id):
        return next((e for e in self.events if e.id == event_id), None)

    def attenuation(self, att_id):
        return next((a for a in self.attenuations if a.id == att_id), None)

    def zone(self, zone_id):
        return next((z for z in self.zones if z.id == zone_id), None)

    def emitter(self, emitter_id):
        return next((e for e in self.emitters if e.id == emitter_id), None)

    def bus(self, name):
        return next((b for b in self.buses if b.name == name), None)

    def referenced_files(self):
        return sorted({f for e in self.events for f in e.all_files()})

    def clone(self):
        return copy.deepcopy(self)


# ---------------------------------------------------------------- (de)serialisation
_HINTS = {}


def _hints(cls):
    if cls not in _HINTS:
        _HINTS[cls] = typing.get_type_hints(cls)
    return _HINTS[cls]


# Element types of list fields that hold dataclasses.
_LISTS = {(Event, 'layers'): Layer, (Event, 'parameters'): Parameter, (Event, 'bindings'): Binding,
          (Zone, 'beds'): Bed, (Zone, 'spots'): Spot, (Project, 'events'): Event,
          (Project, 'attenuations'): Attenuation, (Project, 'zones'): Zone,
          (Project, 'emitters'): Emitter, (Project, 'buses'): Bus, (Project, 'ducks'): Duck}


def _load(cls, data):
    """Build a dataclass from a dict; unknown keys are ignored, missing keys keep defaults."""
    if not isinstance(data, dict):
        return cls()
    hints = _hints(cls)
    values = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        raw = data[f.name]
        kind = hints[f.name]
        element = _LISTS.get((cls, f.name))
        if element is not None:
            values[f.name] = [_load(element, item) for item in raw or []]
        elif is_dataclass(kind):
            values[f.name] = _load(kind, raw)
        elif kind is float:
            values[f.name] = float(raw)
        elif kind is int:
            values[f.name] = int(raw)
        elif kind is bool:
            values[f.name] = bool(raw)
        else:
            values[f.name] = copy.deepcopy(raw)
    return cls(**values)


def project_from_dict(data):
    project = _load(Project, data)
    present = {b.name for b in project.buses}
    project.buses += [Bus(name) for name in BUSES if name not in present]
    return project


def project_to_dict(project):
    return asdict(project)


def save_project(project, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(project_to_dict(project), indent=1), encoding='utf-8')
    os.replace(temporary, path)


def load_project(path):
    return project_from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


# ---------------------------------------------------------------- helpers
def matches(when, values):
    """True when every listed key's value is among the allowed options (empty = always)."""
    for key, allowed in (when or {}).items():
        if allowed and values.get(key) not in allowed:
            return False
    return True


def point_in_polygon(x, y, points):
    inside = False
    n = len(points)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def distance_to_edges(x, y, points):
    best = math.inf
    n = len(points)
    for i in range(n):
        ax, ay = points[i]
        bx, by = points[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0. if length == 0 else max(0., min(1., ((x - ax) * dx + (y - ay) * dy) / length))
        best = min(best, math.hypot(x - (ax + t * dx), y - (ay + t * dy)))
    return best


def zone_presence(zone, x, y):
    """0..1 presence of a listener at (x, y), ramping up over edge_blend inside the polygon."""
    if zone.is_default or not point_in_polygon(x, y, zone.points):
        return 0.
    if zone.edge_blend <= 0:
        return 1.
    return min(1., distance_to_edges(x, y, zone.points) / zone.edge_blend)


def zone_targets(project, x, y):
    """Priority-stacked target weights; the default zone receives whatever is left."""
    targets = {}
    remaining = 1.
    for zone in sorted((z for z in project.zones if not z.is_default), key=lambda z: -z.priority):
        weight = zone_presence(zone, x, y) * remaining
        targets[zone.id] = weight
        remaining -= weight
    for zone in project.zones:
        if zone.is_default:
            targets[zone.id] = remaining
            remaining = 0.
    return targets


def surface_at(project, x, y):
    best, surface = 0., project.locomotion.default_surface
    for zone_id, weight in zone_targets(project, x, y).items():
        zone = project.zone(zone_id)
        if zone.surface and weight > best:
            best, surface = weight, zone.surface
    return surface


def problems(project, info=None):
    """Asset-convention warnings: {event id: [messages]}.  info(path) -> (rate, channels) or None."""
    found = {}
    for event in project.events:
        notes = []
        if not event.layers or not event.all_files():
            notes.append('No sound files yet')
        for layer in event.layers:
            for path in layer.files:
                meta = info(path) if info else None
                if info and meta is None:
                    notes.append(f'Missing: {Path(path).name}')
                    continue
                if meta:
                    rate, channels = meta
                    if rate != SAMPLE_RATE:
                        notes.append(f'{Path(path).name}: {rate} Hz (48 kHz recommended)')
                    if event.spatial == '3D' and event.kind == 'oneshot' and channels > 1:
                        notes.append(f'{Path(path).name}: stereo in a 3D one-shot (mono recommended)')
        if event.spatial == '3D' and not project.attenuation(event.attenuation):
            notes.append('3D without an attenuation profile')
        if notes:
            found[event.id] = notes
    return found


# ---------------------------------------------------------------- starter project
def _att(name, **kw):
    return Attenuation(id=new_id('att'), name=name, **kw)


def _event(name, bus, kind='oneshot', spatial='3D', attenuation='', layers=(), **kw):
    return Event(id=new_id('evt'), name=name, bus=bus, kind=kind, spatial=spatial,
                 attenuation=attenuation, layers=list(layers), **kw)


def starter_project():
    """A ready-made layout: every event, zone and emitter exists; only the WAVs are missing."""
    p = Project()
    near = _att('Footsteps & body', inner_radius=150, falloff=2200, model='NaturalSound', db_at_max=-40,
                nonspatial_radius=150, reverb_dist_min=100, reverb_dist_max=2000)
    combat = _att('Combat', inner_radius=300, falloff=3500, model='NaturalSound', db_at_max=-45,
                  nonspatial_radius=200)
    prop = _att('Small prop', inner_radius=150, falloff=1800, model='Logarithmic', reverb_dist_max=1800)
    large = _att('Large source', shape='Capsule', capsule_half_height=1800, capsule_radius=250,
                 falloff=4500, model='NaturalSound', db_at_max=-40, nonspatial_radius=500, stereo_spread=600)
    distant = _att('Distant one-shot', inner_radius=600, falloff=9000, model='NaturalSound', db_at_max=-35,
                   air_min=800, air_max=7000, lpf_at_max=2500, reverb_min=.35, reverb_max=.9,
                   reverb_dist_max=8000)
    p.attenuations = [near, combat, prop, large, distant]

    surfaces = ['Dirt', 'Grass', 'Stone', 'Wood', 'Water']
    footsteps = _event('Footsteps', 'Foley', attenuation=near.id, max_count=4, layers=[
        Layer(name=s, pitch_random=1., volume_random=2., when={'Surface': [s]}) for s in surfaces],
        parameters=[Parameter('Surface', 'enum', options=surfaces, automatic=True),
                    Parameter('Gait', 'enum', options=['Walk', 'Run', 'Sprint'], automatic=True),
                    Parameter('Foot', 'enum', options=['Left', 'Right'], automatic=True),
                    Parameter('Speed', 'float', 0, 1, .4, automatic=True)])
    footsteps.bindings = [Binding('Speed', 'volume', -1, 0, 1, .8, 1.15)]
    footsteps.dsp.limiter = True
    cloth = _event('Cloth & gear', 'Foley', attenuation=near.id, max_count=3,
                   layers=[Layer('Cloth', volume_random=3.), Layer('Gear', chance=.5, gain_db=-4)])
    jump = _event('Jump', 'Foley', attenuation=near.id, max_count=2,
                  layers=[Layer('Push-off'), Layer('Effort', chance=.5, gain_db=-3)])
    land = _event('Land', 'Foley', attenuation=near.id, max_count=2,
                  parameters=[Parameter('Surface', 'enum', options=surfaces, automatic=True)],
                  layers=[Layer(s, when={'Surface': [s]}) for s in surfaces] + [Layer('Body', gain_db=-3)])

    punch = _event('Punch', 'Combat', attenuation=combat.id, pad=True, hotkey='1', max_count=6, layers=[
        Layer('Whoosh', delay_ms=0, gain_db=-6),
        Layer('Impact', delay_ms=60),
        Layer('Body thud', delay_ms=60, gain_db=-3),
        Layer('Cloth', delay_ms=10, gain_db=-10),
        Layer('Grunt', delay_ms=80, gain_db=-4, chance=.4)],
        parameters=[Parameter('Intensity', 'float', 0, 1, .6)])
    punch.bindings = [Binding('Intensity', 'gain', 2, 0, 1, .15, 1.),
                      Binding('Intensity', 'pitch', 1, 0, 1, 1.5, -1.5),
                      Binding('Intensity', 'chance', 4, 0, 1, .3, 1.6)]
    kick = _event('Kick', 'Combat', attenuation=combat.id, pad=True, hotkey='2', max_count=6, layers=[
        Layer('Whoosh', gain_db=-5), Layer('Impact', delay_ms=90), Layer('Body thud', delay_ms=90, gain_db=-2),
        Layer('Grunt', delay_ms=100, chance=.4, gain_db=-4)],
        parameters=[Parameter('Intensity', 'float', 0, 1, .6)])
    kick.bindings = [Binding('Intensity', 'gain', 2, 0, 1, .2, 1.)]
    sword = _event('Sword swing', 'Combat', attenuation=combat.id, pad=True, hotkey='3', max_count=6, layers=[
        Layer('Swing'), Layer('Metal ring', delay_ms=20, gain_db=-8, chance=.6), Layer('Cloth', gain_db=-10)],
        parameters=[Parameter('Intensity', 'float', 0, 1, .5)])
    sword.bindings = [Binding('Intensity', 'pitch', 0, 0, 1, 1., -1.)]
    hit = _event('Hit taken', 'Combat', attenuation=combat.id, pad=True, hotkey='4', max_count=4, layers=[
        Layer('Impact'), Layer('Pain grunt', delay_ms=40, gain_db=-2, chance=.8)])
    fall = _event('Body fall', 'Foley', attenuation=near.id, pad=True, hotkey='5', max_count=3, layers=[
        Layer('Body'), Layer('Gear rattle', delay_ms=50, gain_db=-6, chance=.7)])

    wind = _event('Wind bed', 'Ambience', 'loop', '2D', layers=[Layer('Wind', pitch_random=0, volume_random=0)])
    wind.dsp.attack_ms = 1500
    forest_bed = _event('Forest bed', 'Ambience', 'loop', '2D', layers=[Layer('Forest', pitch_random=0, volume_random=0)])
    village_bed = _event('Village bed', 'Ambience', 'loop', '2D', layers=[Layer('Village', pitch_random=0, volume_random=0)])
    tavern_bed = _event('Tavern room tone', 'Ambience', 'loop', '2D', layers=[
        Layer('Room tone', pitch_random=0, volume_random=0), Layer('Murmur', gain_db=-6, pitch_random=0, volume_random=0)])
    crickets = _event('Night crickets', 'Ambience', 'loop', '2D', layers=[Layer('Crickets', pitch_random=0, volume_random=0)])
    rain = _event('Rain bed', 'Ambience', 'loop', '2D', layers=[Layer('Rain', pitch_random=0, volume_random=0)])
    birds = _event('Birds', 'Ambience', attenuation=distant.id, max_count=4, layers=[Layer('Bird call', pitch_random=2., volume_random=4.)])
    owl = _event('Owl', 'Ambience', attenuation=distant.id, max_count=2, layers=[Layer('Owl', pitch_random=.5)])
    dog = _event('Dog bark', 'Ambience', attenuation=distant.id, max_count=2, layers=[Layer('Bark', pitch_random=1.)])
    crow = _event('Crow', 'Ambience', attenuation=distant.id, max_count=2, layers=[Layer('Crow', pitch_random=1.)])
    fire = _event('Campfire', 'Ambience', 'loop', attenuation=prop.id, layers=[
        Layer('Fire loop', pitch_random=0, volume_random=0)])
    crackle = _event('Fire crackle', 'Ambience', 'repeat', attenuation=prop.id, repeat_min=.4, repeat_max=2.5,
                     layers=[Layer('Crackle', pitch_random=2., volume_random=4.)])
    river = _event('River', 'Ambience', 'loop', attenuation=large.id, layers=[Layer('Water', pitch_random=0, volume_random=0)])
    hearth = _event('Tavern hearth', 'Ambience', 'loop', attenuation=prop.id, layers=[Layer('Hearth', pitch_random=0, volume_random=0)])
    p.events = [footsteps, cloth, jump, land, punch, kick, sword, hit, fall,
                wind, forest_bed, village_bed, tavern_bed, crickets, rain, birds, owl, dog, crow,
                fire, crackle, river, hearth]
    p.locomotion = Locomotion(footstep_event=footsteps.id, cloth_event=cloth.id, jump_event=jump.id,
                              land_event=land.id, default_surface='Grass')

    night, day = {'TimeOfDay': ['Night']}, {'TimeOfDay': ['Dawn', 'Day', 'Dusk']}
    rainy = {'Weather': ['Rain', 'Storm']}
    plains = Zone(id=new_id('zone'), name='Open plains', color='#8fb3ff', is_default=True, surface='Grass',
                  reverb='Open Field', reverb_wet_db=-10,
                  beds=[Bed(wind.id, -4), Bed(crickets.id, -8, night), Bed(rain.id, -3, rainy)],
                  spots=[Spot(crow.id, -6, 8, 20, 1500, 5000, 1, inside_only=False, when=day)])
    forest = Zone(id=new_id('zone'), name='Forest', color='#5fc9a8', priority=1, surface='Dirt',
                  points=[[-5600, -5400], [-600, -5600], [-200, -1800], [-1600, -400], [-5600, -800]],
                  edge_blend=600, reverb='Forest', reverb_wet_db=-6,
                  beds=[Bed(forest_bed.id, 0), Bed(wind.id, -12), Bed(crickets.id, -4, night), Bed(rain.id, -5, rainy)],
                  spots=[Spot(birds.id, -2, 1.5, 6, 500, 3500, 3, when=day),
                         Spot(owl.id, -4, 6, 18, 1200, 4000, 1, when=night)])
    village = Zone(id=new_id('zone'), name='Village', color='#e3b26b', priority=1, surface='Stone',
                   points=[[800, 600], [5400, 400], [5600, 5200], [1000, 5400]],
                   edge_blend=500, reverb='Courtyard', reverb_wet_db=-8,
                   beds=[Bed(village_bed.id, 0), Bed(wind.id, -14), Bed(rain.id, -4, rainy)],
                   spots=[Spot(dog.id, -4, 6, 16, 1000, 4500, 1)])
    tavern = Zone(id=new_id('zone'), name='Tavern (interior)', color='#d29bf0', priority=10, surface='Wood',
                  points=[[3700, 3700], [5100, 3700], [5100, 4800], [3700, 4800]], edge_blend=60,
                  fade_in=.6, fade_out=.8, reverb='Wood Room', reverb_wet_db=-5, interior=True,
                  beds=[Bed(tavern_bed.id, 0)])
    p.zones = [plains, forest, village, tavern]
    p.emitters = [
        Emitter(id=new_id('emt'), name='Campfire', event=fire.id, x=-2200, y=-2600),
        Emitter(id=new_id('emt'), name='Campfire crackle', event=crackle.id, x=-2140, y=-2540, gain_db=-2),
        Emitter(id=new_id('emt'), name='River', event=river.id, x=-1400, y=2600, yaw=-20),
        Emitter(id=new_id('emt'), name='Tavern hearth', event=hearth.id, x=4800, y=4000),
    ]
    p.ducks = [Duck('Combat', 'Ambience', -4, 15, 250, 700), Duck('Voice', 'Ambience', -6, 40, 200, 900)]
    return p
