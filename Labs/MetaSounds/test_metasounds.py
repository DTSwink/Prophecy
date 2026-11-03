"""MetaSounds engine, model and export tests (offline: no audio device needed)."""
import json
import math

import numpy as np
import pytest
import soundfile as sf

import meta_engine as me
from meta_model import (Attenuation, Binding, Bed, DSP, Duck, Emitter, Event, Layer, Parameter, Project,
                        Spot, Zone, load_project, save_project, starter_project, zone_targets, problems)

SR = 48000


def tone(path, freq, seconds=.25, channels=1, amp=.5, rate=SR):
    t = np.arange(int(seconds * rate)) / rate
    data = amp * np.sin(2 * np.pi * freq * t)
    fade = np.minimum(1, np.minimum(t, t[::-1]) / .004)
    data = (data * fade)[:, None].repeat(channels, 1)
    sf.write(str(path), data, rate, subtype='PCM_24')
    return str(path)


def noise(path, seconds=2., channels=1, amp=.3, seed=0):
    rng = np.random.default_rng(seed)
    sf.write(str(path), amp * rng.uniform(-1, 1, (int(seconds * SR), channels)), SR, subtype='FLOAT')
    return str(path)


@pytest.fixture
def sounds(tmp_path):
    return {
        'a': tone(tmp_path / 'a.wav', 300), 'b': tone(tmp_path / 'b.wav', 700),
        'c': tone(tmp_path / 'c.wav', 1500), 'd': tone(tmp_path / 'd.wav', 3000),
        'long': tone(tmp_path / 'long.wav', 500, 3.), 'noise': noise(tmp_path / 'noise.wav'),
        'stereo': noise(tmp_path / 'stereo.wav', channels=2, seed=1),
        'r44': tone(tmp_path / 'r44.wav', 440, .3, rate=44100),
        'burst': noise(tmp_path / 'burst.wav', .3, seed=4),
    }


def engine_for(project, seed=3):
    engine = me.Engine(project, seed=seed)
    engine.clips.request(project.referenced_files(), blocking=True)
    return engine


def energy_at(signal, freq, rate=SR):
    mono = signal.mean(axis=1) if signal.ndim == 2 else signal
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    bins = np.fft.rfftfreq(len(mono), 1 / rate)
    band = (bins > freq * .9) & (bins < freq * 1.1)
    return float(spectrum[band].max())


def onsets(signal, threshold=.05, window=480):
    frames = len(signal) // window
    level = np.abs(signal[:frames * window]).max(axis=1).reshape(frames, window).max(axis=1) > threshold
    return int(np.sum(level[1:] & ~level[:-1]) + level[0])


def simple(files, **kw):
    att = Attenuation(id='att', inner_radius=100, falloff=2000, air_absorption=False, reverb_send=False)
    layers = kw.pop('layers', None) or [Layer('L', files, pitch_random=0, volume_random=0)]
    event = Event(id='ev', name='Test', bus=kw.pop('bus', 'SFX'), attenuation='att', layers=layers, **kw)
    event.dsp.limiter = False
    project = Project(events=[event], attenuations=[att])
    return project, event, att


# ------------------------------------------------------------------ maths
def test_distance_models_match_unreal_formulas():
    att = Attenuation(falloff=1000)
    expected = {'Linear': lambda t: 1 - t, 'Logarithmic': lambda t: min(1, .5 * -math.log(t)),
                'Inverse': lambda t: min(1, .02 / t), 'LogReverse': lambda t: max(0, 1 + .5 * math.log(1 - t)),
                'NaturalSound': lambda t: 10 ** (-60 * t / 20)}
    for model, fn in expected.items():
        att.model = model
        for t in (.05, .3, .7, .95):
            assert me.falloff_gain(att, t * 1000) == pytest.approx(fn(t), abs=1e-9)
        assert me.falloff_gain(att, 0) == 1 and me.falloff_gain(att, 1000) == 0
    att.model = 'Custom'
    att.custom_curve = [[0, 1], [.5, .2], [1, 0]]
    assert me.falloff_gain(att, 250) == pytest.approx(.6)


def test_shapes_measure_distance_outside_inner_volume():
    att = Attenuation(inner_radius=100)
    assert me.shape_distance(att, 0, 0, 0, 300, 0)[0] == pytest.approx(200)
    att.shape, att.box_x, att.box_y = 'Box', 100, 50
    assert me.shape_distance(att, 0, 0, 0, 150, 0)[0] == pytest.approx(50)
    assert me.shape_distance(att, 0, 0, 90, 150, 0)[0] == pytest.approx(100)  # rotated box
    att.shape, att.capsule_half_height, att.capsule_radius = 'Capsule', 1000, 100
    distance, _, nearest = me.shape_distance(att, 0, 0, 0, 800, 400)
    assert distance == pytest.approx(300) and nearest == pytest.approx((800, 0))
    att.shape, att.cone_angle, att.cone_falloff_angle = 'Cone', 30, 30
    assert me.shape_distance(att, 0, 0, 0, 500, 0)[1] == 1
    assert me.shape_distance(att, 0, 0, 0, 0, 500)[1] == 0          # 90 degrees off-axis
    assert 0 < me.shape_distance(att, 0, 0, 0, 500, 400)[1] < 1


def test_air_absorption_and_reverb_send_interpolate():
    att = Attenuation(air_min=1000, air_max=5000, lpf_at_min=20000, lpf_at_max=2000, log_frequency=True,
                      reverb_min=.1, reverb_max=.9, reverb_dist_min=0, reverb_dist_max=1000)
    assert me.air_filters(att, 0)[0] == pytest.approx(20000) and me.air_filters(att, 9000)[0] == pytest.approx(2000)
    assert me.air_filters(att, 3000)[0] == pytest.approx(math.sqrt(20000 * 2000))
    assert me.reverb_send_level(att, 500) == pytest.approx(.5)


def test_pickers_never_repeat_and_shuffle_covers_pool():
    rng = np.random.default_rng(0)
    picker = me.Picker()
    picks = [picker.pick(4, 'random', rng) for _ in range(300)]
    assert all(a != b for a, b in zip(picks, picks[1:])) and set(picks) == {0, 1, 2, 3}
    picker = me.Picker()
    picks = [picker.pick(5, 'shuffle', rng) for _ in range(20)]
    for start in range(0, 20, 5):
        assert sorted(picks[start:start + 5]) == [0, 1, 2, 3, 4]
    assert all(a != b for a, b in zip(picks, picks[1:]))
    picker = me.Picker()
    assert [picker.pick(3, 'sequence', rng) for _ in range(5)] == [0, 1, 2, 0, 1]


# ------------------------------------------------------------------ events
def test_layers_play_with_their_delays_chances_and_conditions(sounds):
    layers = [Layer('Whoosh', [sounds['a']], pitch_random=0, volume_random=0),
              Layer('Impact', [sounds['b']], delay_ms=100, pitch_random=0, volume_random=0),
              Layer('Never', [sounds['c']], chance=0, pitch_random=0, volume_random=0),
              Layer('Stone', [sounds['d']], when={'Surface': ['Stone']}, pitch_random=0, volume_random=0)]
    project, event, _ = simple([], layers=layers, spatial='2D',
                               parameters=[Parameter('Surface', 'enum', options=['Grass', 'Stone'])])
    engine = engine_for(project)
    engine.trigger('ev')
    out = engine.render_seconds(.5)
    first = out[:int(.09 * SR)]
    assert energy_at(first, 300) > 10 * energy_at(first, 700)
    impact = out[int(.1 * SR):int(.3 * SR)]
    assert energy_at(impact, 700) > 10 * energy_at(first, 700)
    assert energy_at(out, 1500) < energy_at(out, 300) / 50
    assert energy_at(out, 3000) < energy_at(out, 300) / 50
    engine.trigger('ev', {'Surface': 'Stone'})
    assert energy_at(engine.render_seconds(.3), 3000) > energy_at(out, 3000) * 20


def test_parameter_bindings_scale_layers(sounds):
    layers = [Layer('Thud', [sounds['a']], pitch_random=0, volume_random=0)]
    project, event, _ = simple([], layers=layers, spatial='2D', parameters=[Parameter('Intensity')])
    event.bindings = [Binding('Intensity', 'gain', 0, 0, 1, 0., 1.)]
    engine = engine_for(project)
    levels = []
    for value in (.25, 1.):
        engine.trigger('ev', {'Intensity': value})
        levels.append(np.abs(engine.render_seconds(.3)).max())
    assert levels[1] / levels[0] == pytest.approx(4, rel=.05)
    event.bindings = [Binding('Intensity', 'pitch', -1, 0, 1, 0., 12.)]
    engine = engine_for(project)
    engine.trigger('ev', {'Intensity': 1.})
    out = engine.render_seconds(.2)
    assert energy_at(out, 600) > 10 * energy_at(out, 300)   # one octave up


def test_randomisation_varies_pitch_and_volume(sounds):
    layers = [Layer('L', [sounds['a']], pitch_random=3, volume_random=6)]
    project, _, _ = simple([], layers=layers, spatial='2D')
    engine = engine_for(project)
    peaks = []
    for _ in range(8):
        engine.trigger('ev')
        peaks.append(np.abs(engine.render_seconds(.4)).max())
    assert max(peaks) / min(peaks) > 1.3


def test_resampled_and_stereo_files_are_supported(sounds):
    project, _, _ = simple([sounds['r44']], spatial='2D')
    engine = engine_for(project)
    engine.trigger('ev')
    out = engine.render_seconds(.4)
    assert energy_at(out, 440) > 10 * energy_at(out, 600)
    project, _, _ = simple([sounds['stereo']], spatial='2D', kind='loop')
    engine = engine_for(project)
    engine.toggle_loop('ev')
    out = engine.render_seconds(.5)[4096:]
    assert np.corrcoef(out[:, 0], out[:, 1])[0, 1] < .5         # channels kept apart


def test_dsp_filter_drive_delay_and_envelope(sounds):
    project, event, _ = simple([sounds['noise']], spatial='2D')
    event.dsp = DSP(filter='LowPass', cutoff=500, limiter=False)
    engine = engine_for(project)
    engine.trigger('ev')
    filtered = engine.render_seconds(.5)
    event.dsp = DSP(limiter=False)
    engine = engine_for(project)
    engine.trigger('ev')
    plain = engine.render_seconds(.5)
    assert energy_at(filtered, 6000) < energy_at(plain, 6000) / 8

    project, event, _ = simple([sounds['a']], spatial='2D')
    event.dsp = DSP(delay_ms=400, feedback=.4, delay_mix=.5, limiter=False)
    engine = engine_for(project)
    engine.trigger('ev')
    out = engine.render_seconds(1.)
    echo = out[int(.42 * SR):int(.6 * SR)]
    assert np.abs(echo).max() > .15
    event.dsp = DSP(attack_ms=200, limiter=False)
    engine = engine_for(project)
    engine.trigger('ev')
    out = engine.render_seconds(.25)
    assert np.abs(out[:480]).max() < .1 * np.abs(out[9600:11000]).max()


def test_concurrency_rules_limit_instances(sounds):
    project, event, _ = simple([sounds['long']], spatial='2D', max_count=2, rule='StopOldest')
    engine = engine_for(project)
    for _ in range(5):
        engine.trigger('ev')
        engine.render_seconds(.03)
    assert sum(1 for i in engine.instances if not i.stopping) == 2
    event.rule = 'PreventNew'
    engine = engine_for(project)
    for _ in range(5):
        engine.trigger('ev')
        engine.render_seconds(.03)
    assert len(engine.instances) == 2 and all(not i.stopping for i in engine.instances)


# ------------------------------------------------------------------ spatial
def test_panning_follows_camera_and_distance(sounds):
    project, event, att = simple([sounds['a']], spatial='3D')
    engine = engine_for(project)
    engine.set_listener(0, 0, 0)                 # camera facing +X; +Y is to the right
    engine.trigger('ev', position=(0, 600, 0))
    out = engine.render_seconds(.3)
    assert np.abs(out[:, 1]).max() > 5 * np.abs(out[:, 0]).max()
    engine.set_listener(0, 0, math.pi)           # turn around: now on the left
    engine.trigger('ev', position=(0, 600, 0))
    out = engine.render_seconds(.3)
    assert np.abs(out[:, 0]).max() > 5 * np.abs(out[:, 1]).max()
    engine.set_listener(0, 0, 0)
    engine.trigger('ev', position=(1100, 0, 0))   # half-way through the falloff
    half = np.abs(engine.render_seconds(.3)).max()
    engine.trigger('ev', position=(50, 0, 0))
    near = np.abs(engine.render_seconds(.3)).max()
    assert half / near == pytest.approx(.5, rel=.05)
    engine.trigger('ev', position=(5000, 0, 0))
    assert np.abs(engine.render_seconds(.3)).max() == 0


def test_air_absorption_darkens_distant_sounds(sounds):
    project, event, att = simple([sounds['burst']], spatial='3D')
    att.air_absorption, att.air_min, att.air_max, att.lpf_at_max = True, 0, 1500, 800
    att.attenuate = False
    engine = engine_for(project)
    engine.trigger('ev', position=(50, 0, 0))
    near = engine.render_seconds(.4)
    engine.trigger('ev', position=(1600, 0, 0))
    far = engine.render_seconds(.4)
    ratio = lambda x: energy_at(x, 8000) / energy_at(x, 300)
    assert ratio(far) < ratio(near) / 6


def test_virtualised_loops_keep_time_without_rendering(sounds):
    project, event, _ = simple([sounds['long']], spatial='3D', kind='loop')
    project.emitters = [Emitter(id='em', event='ev', x=100000, y=0)]
    engine = engine_for(project)
    engine.render_seconds(.5)
    instance = engine.owned[('emitter', 'em')]
    assert instance.virtual and instance.voices[0].pos > 0
    engine.set_listener(100000, 0, 0)
    assert np.abs(engine.render_seconds(.3)).max() > .1


# ------------------------------------------------------------------ world
def square(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def world(sounds):
    project = Project()
    bed_a = Event(id='bed_a', name='Plains', bus='Ambience', kind='loop', spatial='2D',
                  layers=[Layer('L', [sounds['long']], pitch_random=0, volume_random=0)])
    bed_b = Event(id='bed_b', name='Hall', bus='Ambience', kind='loop', spatial='2D',
                  layers=[Layer('L', [sounds['noise']], pitch_random=0, volume_random=0)])
    project.events = [bed_a, bed_b]
    project.zones = [Zone(id='plains', name='Plains', is_default=True, beds=[Bed('bed_a')], fade_in=.5, fade_out=.5),
                     Zone(id='hall', name='Hall', points=square(0, 0, 1000, 1000), edge_blend=0, fade_in=.5,
                          fade_out=.5, priority=1, beds=[Bed('bed_b')], surface='Stone', reverb='Stone Hall')]
    return project


def test_zone_weights_crossfade_beds_with_fade_times(sounds):
    project = world(sounds)
    engine = engine_for(project)
    engine.set_listener(-500, -500, 0)
    out = engine.render_seconds(.5)
    assert energy_at(out, 500) > 0 and engine.snapshot['zones'] == {'plains': 1., 'hall': 0.}
    engine.set_listener(500, 500, 0)
    engine.render_seconds(.25)
    assert .3 < engine.snapshot['zones']['hall'] < .7
    engine.render_seconds(.5)
    assert engine.snapshot['zones'] == {'plains': 0., 'hall': 1.}
    assert engine.surface == 'Stone'
    engine.render_seconds(1.2)
    assert not any(i.event_id == 'bed_a' for i in engine.instances)   # silent beds released


def test_priority_and_edge_blend_targets():
    project = Project(zones=[Zone(id='d', is_default=True),
                             Zone(id='outer', points=square(0, 0, 1000, 1000), edge_blend=200, priority=1),
                             Zone(id='inner', points=square(400, 400, 600, 600), edge_blend=0, priority=5)])
    assert zone_targets(project, 500, 500) == {'inner': 1., 'outer': 0., 'd': 0.}
    assert zone_targets(project, 100, 500) == pytest.approx({'inner': 0., 'outer': .5, 'd': .5})


def test_states_switch_beds(sounds):
    project = world(sounds)
    project.zones[0].beds[0].when = {'TimeOfDay': ['Night']}
    engine = engine_for(project)
    engine.set_listener(-500, -500, 0)
    assert np.abs(engine.render_seconds(.3)).max() == 0
    engine.set_states({'TimeOfDay': 'Night'})
    engine.render_seconds(2.2)
    assert np.abs(engine.render_seconds(.3)).max() > .1


def test_interior_zone_muffles_outside_emitters(sounds):
    project = world(sounds)
    project.zones[1].beds = []
    project.zones[1].interior = True
    project.zones[1].outside_db, project.zones[1].outside_lpf = -12, 600
    project.zones[0].beds = []
    fire = Event(id='fire', name='Fire', bus='Ambience', kind='loop', spatial='3D', attenuation='att',
                 layers=[Layer('L', [sounds['noise']], pitch_random=0, volume_random=0)])
    project.events.append(fire)
    project.attenuations = [Attenuation(id='att', inner_radius=2000, falloff=2000, air_absorption=False,
                                        reverb_send=False)]
    project.emitters = [Emitter(id='em', event='fire', x=1500, y=500)]
    project.zones[1].reverb = 'None'
    engine = engine_for(project)
    engine.set_listener(1100, 500, 0)
    outside = engine.render_seconds(1.)[SR // 2:]
    engine.set_listener(900, 500, 0)
    engine.render_seconds(1.)
    inside = engine.render_seconds(.5)
    assert np.sqrt(np.mean(inside ** 2)) < np.sqrt(np.mean(outside ** 2)) * .3
    assert energy_at(inside, 6000) < energy_at(outside, 6000) / 20


def test_spot_spawner_respects_distance_zone_and_limits(sounds):
    project = Project()
    project.events = [Event(id='bird', name='Bird', bus='Ambience', attenuation='att',
                            layers=[Layer('L', [sounds['long']])], max_count=10)]
    project.attenuations = [Attenuation(id='att', falloff=10000)]
    zone = Zone(id='forest', name='Forest', points=square(-3000, -3000, 0, 3000), edge_blend=0,
                spots=[Spot('bird', 0, .2, .3, 500, 1500, 3, inside_only=True)])
    project.zones = [zone]
    engine = engine_for(project)
    engine.set_listener(-100, 0, 0)
    engine.render_seconds(3.)
    spots = [i for i in engine.instances if i.owner[0] == 'spot']
    assert len(spots) == 3
    for instance in spots:
        x, y, _ = instance.position
        assert 500 <= math.hypot(x + 100, y) <= 1500 and x <= 0


def test_locomotion_cadence_and_surface(sounds):
    project = world(sounds)
    for zone in project.zones:
        zone.beds = []
        zone.reverb = 'None'
    steps = Event(id='steps', name='Steps', bus='Foley', attenuation='', spatial='2D', max_count=8,
                  parameters=[Parameter('Surface', 'enum', options=['Grass', 'Stone'])],
                  layers=[Layer('Grass', [sounds['a']], when={'Surface': ['Grass']}),
                          Layer('Stone', [sounds['d']], when={'Surface': ['Stone']})])
    project.events.append(steps)
    project.locomotion.footstep_event = 'steps'
    project.locomotion.default_surface = 'Grass'
    project.locomotion.cadence['Run'] = 3.
    engine = engine_for(project)
    engine.set_listener(-500, -500, 0)
    engine.set_gait('Run')
    out = engine.render_seconds(2.)
    assert 5 <= onsets(out) <= 7
    assert energy_at(out, 300) > 20 * energy_at(out, 3000)
    engine.set_listener(500, 500, 0)
    out = engine.render_seconds(1.)
    assert energy_at(out, 3000) > 20 * energy_at(out, 300)
    engine.set_gait('Idle')
    engine.render_seconds(.3)
    assert np.abs(engine.render_seconds(.5)).max() == 0


def test_ducking_lowers_ambience_during_combat(sounds):
    project = world(sounds)
    project.zones[1].reverb = 'None'
    punch = Event(id='punch', name='Punch', bus='Combat', spatial='2D',
                  layers=[Layer('L', [sounds['b']], pitch_random=0, volume_random=0)])
    project.events.append(punch)
    project.ducks = [Duck('Combat', 'Ambience', -12, 5, 200, 300)]
    engine = engine_for(project)
    engine.set_listener(-500, -500, 0)
    engine.render_seconds(.5)
    before = engine.snapshot['peaks']['Ambience']
    engine.trigger('punch')
    engine.render_seconds(.15)
    assert engine.snapshot['peaks']['Ambience'] < before * .35
    engine.render_seconds(1.2)
    assert engine.snapshot['peaks']['Ambience'] == pytest.approx(before, rel=.1)


def test_zone_reverb_adds_a_tail(sounds):
    project = world(sounds)
    for zone in project.zones:
        zone.beds = []
    project.zones[1].reverb_wet_db = 0
    hit = Event(id='hit', name='Hit', spatial='2D', reverb_send=1.,
                layers=[Layer('L', [sounds['a']], pitch_random=0, volume_random=0)])
    project.events.append(hit)
    engine = engine_for(project)
    engine.set_listener(500, 500, 0)
    engine.render_seconds(.6)
    engine.trigger('hit')
    out = engine.render_seconds(1.5)
    tail = out[int(.6 * SR):int(.9 * SR)]
    assert np.abs(tail).max() > .01
    engine.set_listener(-500, -500, 0)
    project.zones[0].reverb = 'None'
    engine.set_project(project)
    engine.render_seconds(4.)
    engine.trigger('hit')
    out = engine.render_seconds(1.)
    assert np.abs(out[int(.6 * SR):]).max() < 1e-3


def test_repeat_events_and_limiter(sounds):
    project, event, _ = simple([sounds['a']], spatial='2D', kind='repeat', repeat_min=.3, repeat_max=.3)
    event.layers[0].gain_db = 12
    project.emitters = []
    engine = engine_for(project)
    engine.toggle_loop('ev')
    out = engine.render_seconds(2.)
    assert 5 <= onsets(out) <= 8
    assert np.abs(out).max() <= 10 ** (-1 / 20) + 1e-3
    engine.toggle_loop('ev')
    engine.render_seconds(.5)
    assert not engine.instances


def test_same_seed_renders_identically(sounds):
    project = starter_project()
    for event in project.events:
        for layer in event.layers:
            layer.files = [sounds['a'], sounds['b'], sounds['c']]
    renders = []
    for _ in range(2):
        engine = engine_for(project, seed=9)
        engine.set_gait('Walk')
        engine.trigger(project.events[4].id, {'Intensity': .9})
        renders.append(engine.render_seconds(3.))
    assert np.array_equal(*renders) and np.abs(renders[0]).max() > .01


def test_starter_world_runs_faster_than_real_time(sounds):
    import time
    project = starter_project()
    for event in project.events:
        for layer in event.layers:
            layer.files = [sounds['long'] if event.kind == 'loop' else sounds['a']]
    engine = engine_for(project)
    engine.set_gait('Run')
    engine.set_listener(-2000, -2000, 0)
    started = time.perf_counter()
    engine.render_seconds(5.)
    assert time.perf_counter() - started < 2.5


# ------------------------------------------------------------------ project
def test_project_round_trip_and_problems(tmp_path, sounds):
    project = starter_project()
    project.events[0].layers[0].files = [sounds['r44'], str(tmp_path / 'gone.wav')]
    project.events[4].layers[0].files = [sounds['stereo']]
    save_project(project, tmp_path / 'p.json')
    loaded = load_project(tmp_path / 'p.json')
    assert loaded == project
    data = json.loads((tmp_path / 'p.json').read_text())
    data['events'][0]['future_field'] = 1
    data.pop('ducks')
    (tmp_path / 'p.json').write_text(json.dumps(data))
    assert load_project(tmp_path / 'p.json').events[0].name == 'Footsteps'
    clips = me.ClipCache()
    found = problems(loaded, clips.info)
    text = ' '.join(found[project.events[0].id])
    assert '44100 Hz' in text and 'Missing: gone.wav' in text
    assert 'stereo in a 3D one-shot' in ' '.join(found[project.events[4].id])
