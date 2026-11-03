"""Unreal export: copies WAVs with Unreal naming and writes an asset manifest.

The manifest uses Unreal's own property and enum names (FSoundAttenuationSettings,
EAttenuationDistanceModel, EMaxConcurrentResolutionRule, UReverbEffect ...) so an
editor script or a person can recreate each asset field by field.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
from pathlib import Path

from meta_model import (BUS_PREFIX, KIND_LABELS, REVERBS, SELECTION_LABELS, SAMPLE_RATE, db_to_gain,
                        project_to_dict)

SELECTION_NODES = {'random': 'Random Get (No Repeats)', 'shuffle': 'Shuffle', 'sequence': 'Get (incrementing index)'}


def pascal(text):
    words = re.findall(r'[A-Za-z0-9]+', text)
    return ''.join(w[:1].upper() + w[1:] for w in words) or 'Unnamed'


def unique(name, used):
    candidate, n = name, 2
    while candidate in used:
        candidate = f'{name}{n}'
        n += 1
    used.add(candidate)
    return candidate


def attenuation_settings(att):
    shape = att.shape
    if shape == 'Sphere':
        extents = [att.inner_radius, 0, 0]
    elif shape == 'Box':
        extents = [att.box_x, att.box_y, 400]
    elif shape == 'Capsule':
        extents = [att.capsule_half_height, att.capsule_radius, 0]
    else:
        extents = [att.inner_radius, att.cone_angle, att.cone_falloff_angle]
    settings = {
        'bAttenuate': att.attenuate,
        'bSpatialize': att.spatialize,
        'AttenuationShape': f'EAttenuationShape::{shape}',
        'AttenuationShapeExtents': extents,
        'FalloffDistance': att.falloff,
        'DistanceAlgorithm': f'EAttenuationDistanceModel::{att.model}',
        'dBAttenuationAtMax': att.db_at_max,
        'StereoSpread': att.stereo_spread,
        'NonSpatializedRadiusStart': att.nonspatial_radius,
        'NonSpatializedRadiusEnd': 0,
        'bAttenuateWithLPF': att.air_absorption,
        'AbsorptionMethod': 'EAirAbsorptionMethod::Linear',
        'LPFRadiusMin': att.air_min,
        'LPFRadiusMax': att.air_max,
        'LPFFrequencyAtMin': att.lpf_at_min,
        'LPFFrequencyAtMax': att.lpf_at_max,
        'HPFFrequencyAtMin': att.hpf_at_min,
        'HPFFrequencyAtMax': att.hpf_at_max,
        'bEnableLogFrequencyScaling': att.log_frequency,
        'bEnableReverbSend': att.reverb_send,
        'ReverbSendMethod': 'EReverbSendMethod::Linear',
        'ReverbWetLevelMin': att.reverb_min,
        'ReverbWetLevelMax': att.reverb_max,
        'ReverbDistanceMin': att.reverb_dist_min,
        'ReverbDistanceMax': att.reverb_dist_max,
    }
    if att.model == 'Custom':
        settings['CustomAttenuationCurve'] = [{'Time': x, 'Value': y} for x, y in sorted(att.custom_curve)]
    return settings


def reverb_settings(name):
    spec = REVERBS[name]
    return {
        'DecayTime': spec['decay'],
        'DecayHFRatio': round(min(2., max(.1, 1 - .8 * spec['damping'])), 3),
        'ReflectionsDelay': round(min(.3, spec['predelay'] / 1000), 4),
        'LateDelay': round(min(.1, spec['early'] * 2 / 1000), 4),
        'Density': 1.,
        'Diffusion': 1.,
        'AirAbsorptionGainHF': round(1 - .1 * spec['damping'], 3),
    }


def graph_recipe(event, layer_assets):
    steps = []
    if event.kind == 'repeat':
        steps.append(f'On Play -> Trigger Repeat (period = Random Float {event.repeat_min:g}-{event.repeat_max:g} s, '
                     're-rolled each tick); On Stop stops it')
    else:
        steps.append('On Play trigger starts every layer')
    for index, layer in enumerate(event.layers):
        parts = []
        if layer.when:
            conditions = '; '.join(f'{k} in {v}' for k, v in layer.when.items() if v)
            if conditions:
                parts.append(f'only when {conditions} (Trigger Route on the Int32 input)')
        if layer.chance < 1:
            parts.append(f'probability gate {layer.chance:.0%} (Random Float < chance)')
        if layer.delay_ms:
            parts.append(f'Trigger Delay {layer.delay_ms / 1000:g} s')
        parts.append(f'{SELECTION_NODES.get(layer.selection, "Random Get")} over {len(layer_assets[index])} waves')
        pitch = f'{layer.pitch_st:+g} st' + (f' + Random Float ±{layer.pitch_random:g} st' if layer.pitch_random else '')
        parts.append(f'Wave Player (Pitch Shift {pitch}'
                     + (', Loop on, Start Time = Random Float 0-duration' if event.kind == 'loop' else '') + ')')
        gain = f'{layer.gain_db:+g} dB' + (f' ± {layer.volume_random:g} dB random' if layer.volume_random else '')
        parts.append(f'gain {gain} (Decibels To Linear Gain -> Multiply)')
        steps.append(f"Layer '{layer.name}': " + ' -> '.join(parts))
    if event.bindings:
        for b in event.bindings:
            where = 'event' if b.layer < 0 else f"layer '{event.layers[b.layer].name}'" if b.layer < len(event.layers) else 'layer ?'
            steps.append(f'Map Range ({b.parameter} {b.x0:g}..{b.x1:g} -> {b.y0:g}..{b.y1:g}, clamped) drives {where} {b.target}')
    steps.append(f'Mixer ({len(event.layers)} inputs)')
    d = event.dsp
    if d.filter != 'Off':
        steps.append(f'Biquad Filter {d.filter} {d.cutoff:g} Hz, Q {d.q:g}')
    if d.drive > 0:
        steps.append(f'WaveShaper amount {d.drive:.2f}')
    if d.delay_ms >= 30:
        steps.append(f'Delay {d.delay_ms:g} ms, feedback {d.feedback:.2f}, wet {d.delay_mix:.2f}')
    if d.attack_ms or d.hold_ms:
        steps.append(f'AD/ADSR Envelope attack {d.attack_ms:g} ms'
                     + (f', hold {d.hold_ms:g} ms, release {d.release_ms:g} ms' if d.hold_ms else '') + ' -> Multiply')
    if d.limiter:
        steps.append('Limiter (safety, -0.2 dBFS)')
    steps.append('Outputs: Out Mono / Out Left+Right' + ('; On Finished when all players finish (UE.Source.OneShot)'
                                                           if event.kind == 'oneshot' else ''))
    return steps


def export_unreal(project, destination, info=None, timestamp=None):
    """Write an export folder; returns (folder, report dict)."""
    stamp = timestamp or _dt.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    folder = Path(destination) / f'Unreal Export {stamp}'
    sounds = folder / 'Sounds'
    sounds.mkdir(parents=True, exist_ok=False)
    warnings = []
    used = set()

    attenuation_assets = {a.id: unique(f'ATT_{pascal(a.name)}', used) for a in project.attenuations}
    event_assets = {e.id: unique(f'MSS_{pascal(e.name)}', used) for e in project.events}

    waves, sources = [], []
    copied = 0
    for event in project.events:
        prefix = BUS_PREFIX.get(event.bus, 'SFX')
        layer_assets = []
        for layer in event.layers:
            names = []
            for number, path in enumerate(layer.files, 1):
                base = unique(f'{prefix}_{pascal(event.name)}_{pascal(layer.name)}_{number:02d}', used)
                target = sounds / event.bus / pascal(event.name) / f'{base}.wav'
                meta = info(path) if info else None
                if not Path(path).is_file():
                    warnings.append(f'{event.name} / {layer.name}: missing file {path}')
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                copied += 1
                if meta and meta[0] != SAMPLE_RATE:
                    warnings.append(f'{base}: {meta[0]} Hz source (project standard is 48 kHz)')
                if meta and event.spatial == '3D' and event.kind == 'oneshot' and meta[1] > 1:
                    warnings.append(f'{base}: stereo file in a 3D one-shot; Unreal will spread it as two emitters')
                waves.append({'asset': f'SW_{base}', 'file': target.relative_to(folder).as_posix(),
                              'source': str(path), 'looping': event.kind == 'loop',
                              'sample_rate': meta[0] if meta else None, 'channels': meta[1] if meta else None})
                names.append(f'SW_{base}')
            layer_assets.append(names)
        outputs = 'Stereo' if any(w.get('channels') == 2 for w in waves if w['asset'] in sum(layer_assets, [])) else 'Mono'
        interfaces = ['UE.Source', 'UE.OutputFormat.' + outputs]
        if event.kind == 'oneshot':
            interfaces.append('UE.Source.OneShot')
        if event.spatial == '3D':
            interfaces += ['UE.Attenuation', 'UE.Spatialization']
        inputs = []
        for p in event.parameters:
            if p.kind == 'enum':
                inputs.append({'name': p.name, 'type': 'Int32', 'options': p.options, 'default': 0,
                               'set_by': 'world (automatic)' if p.automatic else 'gameplay'})
            else:
                inputs.append({'name': p.name, 'type': 'Float', 'default': p.default, 'range': [p.minimum, p.maximum],
                               'set_by': 'world (automatic)' if p.automatic else 'gameplay'})
        if event.kind != 'oneshot':
            inputs.append({'name': 'On Stop', 'type': 'Trigger', 'note': 'fade out over the release time'})
        sources.append({
            'asset': event_assets[event.id], 'name': event.name, 'kind': KIND_LABELS[event.kind],
            'sound_class': f'SC_{event.bus}', 'submix': f'SMX_{event.bus}',
            'concurrency': f'SCON_{pascal(event.name)}', 'interfaces': interfaces, 'output_format': outputs,
            'is_spatialized': event.spatial == '3D',
            'attenuation': attenuation_assets.get(event.attenuation) if event.spatial == '3D' else None,
            'volume_db': event.volume_db, 'pitch_semitones': event.pitch_st,
            'reverb_send_2d': event.reverb_send if event.spatial == '2D' else None,
            'inputs': inputs,
            'layers': [{'name': layer.name, 'waves': layer_assets[i], 'selection': SELECTION_LABELS[layer.selection],
                        'delay_s': layer.delay_ms / 1000, 'gain_db': layer.gain_db, 'probability': layer.chance,
                        'pitch_semitones': layer.pitch_st, 'pitch_random_semitones': layer.pitch_random,
                        'volume_random_db': layer.volume_random, 'plays_when': layer.when}
                       for i, layer in enumerate(event.layers)],
            'parameter_mappings': [{'input': b.parameter, 'target': b.target,
                                    'layer': None if b.layer < 0 else b.layer,
                                    'map_range': {'in': [b.x0, b.x1], 'out': [b.y0, b.y1], 'clamped': True}}
                                   for b in event.bindings],
            'processing': {'attack_s': event.dsp.attack_ms / 1000, 'hold_s': event.dsp.hold_ms / 1000,
                           'release_s': event.dsp.release_ms / 1000, 'filter': event.dsp.filter,
                           'cutoff_hz': event.dsp.cutoff, 'q': event.dsp.q, 'waveshaper': event.dsp.drive,
                           'delay_s': event.dsp.delay_ms / 1000, 'feedback': event.dsp.feedback,
                           'delay_wet': event.dsp.delay_mix, 'limiter': event.dsp.limiter},
            'timed_repeat_s': [event.repeat_min, event.repeat_max] if event.kind == 'repeat' else None,
            'graph_recipe': graph_recipe(event, layer_assets),
        })

    attenuations = []
    for att in project.attenuations:
        notes = []
        if att.shape == 'Capsule':
            notes.append('Capsule lies along the emitter yaw. Unreal capsules extend along local Z, so pitch the '
                         'component 90 degrees. The app pans from the nearest point on the capsule '
                         '(spline-emitter style); for the same effect in Unreal move the sound along a spline.')
        if att.shape == 'Box':
            notes.append('Box Z extent was not authored in the 2D map; 400 cm is a starting value.')
        attenuations.append({'asset': attenuation_assets[att.id], 'name': att.name,
                             'settings': attenuation_settings(att), 'notes': notes,
                             'used_by': [event_assets[e.id] for e in project.events if e.attenuation == att.id]})

    reverbs = sorted({z.reverb for z in project.zones if REVERBS.get(z.reverb)})
    zone_assets = {z.id: unique(f'AGV_{pascal(z.name)}', used) for z in project.zones}
    volumes, palettes = [], []
    for zone in project.zones:
        tag = f'Soundscape.Zone.{pascal(zone.name)}'
        components = []
        if REVERBS.get(zone.reverb):
            components.append({'type': 'AudioGameplayVolume Reverb', 'reverb_effect': f'RVB_{pascal(zone.reverb)}',
                               'volume': round(db_to_gain(zone.reverb_wet_db), 4), 'fade_time_s': zone.fade_in,
                               'priority': zone.priority})
        if zone.interior:
            components.append({'type': 'AudioGameplayVolume Filter + Attenuation (outside sounds, listener inside)',
                               'lowpass_hz': zone.outside_lpf, 'volume_db': zone.outside_db, 'priority': zone.priority})
            components.append({'type': 'AudioGameplayVolume Filter + Attenuation (inside sounds, listener outside)',
                               'lowpass_hz': zone.inside_lpf, 'volume_db': zone.inside_db, 'priority': zone.priority})
        xs, ys = [p[0] for p in zone.points], [p[1] for p in zone.points]
        volumes.append({
            'actor': zone_assets[zone.id], 'name': zone.name, 'default_zone': zone.is_default,
            'polygon_xy_cm': zone.points, 'bounds_cm': ([min(xs), min(ys), max(xs), max(ys)] if xs else None),
            'priority': zone.priority, 'edge_blend_cm': zone.edge_blend, 'fade_in_s': zone.fade_in,
            'fade_out_s': zone.fade_out, 'footstep_surface': zone.surface or None, 'gameplay_tag': tag,
            'components': components,
            'note': ('Default zone: active wherever no other zone is; implement as the Soundscape palette with no '
                     'volume, or a world-sized AGV with the lowest priority.') if zone.is_default else
                    'Enter/leave sets/clears the gameplay tag on the Soundscape subsystem.'})
        palettes.append({
            'asset': f'SSP_{pascal(zone.name)}', 'activation_tag': tag,
            'beds': [{'sound': event_assets.get(b.event), 'volume_db': b.gain_db, 'fade_in_s': zone.fade_in,
                      'fade_out_s': zone.fade_out, 'play_when_states': b.when, 'spatial': '2D'} for b in zone.beds],
            'colors': [{'asset': f'SSC_{pascal(zone.name)}_{pascal(project.event(s.event).name if project.event(s.event) else "Missing")}',
                        'sound': event_assets.get(s.event), 'volume_db': s.gain_db,
                        'spawn_interval_s': [s.interval_min, s.interval_max],
                        'spawn_distance_cm': [s.distance_min, s.distance_max], 'max_concurrent': s.max_active,
                        'spawn_chance': s.chance, 'inside_zone_only': s.inside_only,
                        'continuously_respawn': True, 'play_when_states': s.when} for s in zone.spots]})

    ambient = [{'actor': f'AMB_{pascal(e.name)}', 'sound': event_assets.get(e.event),
                'location_cm': [e.x, e.y, e.z], 'rotation': {'pitch': 0, 'yaw': e.yaw, 'roll': 0},
                'attenuation_override': attenuation_assets.get(e.attenuation), 'volume_db': e.gain_db,
                'play_when_states': e.when} for e in project.emitters]

    loco = project.locomotion
    surface_options = []
    footstep = project.event(loco.footstep_event)
    if footstep and footstep.parameter('Surface'):
        surface_options = footstep.parameter('Surface').options
    manifest = {
        'generator': 'Prophecy Sound Studio - MetaSounds', 'schema': 1,
        'exported': stamp, 'project': project.name,
        'units': {'distance': 'centimetres (Unreal units)', 'level': 'dB', 'pitch': 'semitones', 'sample_rate': SAMPLE_RATE},
        'coordinates': 'Map X/Y are world X/Y in cm, drawn as in the Top viewport (X right, Y down). '
                       'Check one landmark after import and flip Y if your level is mirrored.',
        'sound_waves': waves,
        'metasound_sources': sources,
        'attenuations': attenuations,
        'concurrency': [{'asset': f'SCON_{pascal(e.name)}', 'MaxCount': e.max_count,
                         'ResolutionRule': f'EMaxConcurrentResolutionRule::{e.rule}', 'VolumeScale': 1.}
                        for e in project.events],
        'sound_classes': [{'asset': f'SC_{b.name}', 'Volume': round(db_to_gain(b.volume_db), 4),
                           'volume_db': b.volume_db, 'submix': f'SMX_{b.name}'} for b in project.buses],
        'control_bus_mixes': [{'asset': f'CBM_Duck_{d.target}_By_{d.source}', 'control_bus': f'CB_{d.target}_Volume',
                               'value_db': d.amount_db, 'attack_s': d.attack_ms / 1000,
                               'hold_s': d.hold_ms / 1000, 'release_s': d.release_ms / 1000,
                               'activate': f'while {d.source} sounds are playing (Activate/Deactivate Control Bus Mix)'}
                              for d in project.ducks],
        'master': {'volume_db': project.master_db, 'reverb_return_db': project.reverb_return_db,
                   'limiter_ceiling_db': project.limiter_ceiling_db},
        'reverb_effects': [{'asset': f'RVB_{pascal(r)}', 'preset': r, 'settings': reverb_settings(r)} for r in reverbs],
        'audio_gameplay_volumes': volumes,
        'soundscape_palettes': palettes,
        'ambient_sounds': ambient,
        'game_states': {group: [f'State.{group}.{pascal(v)}' for v in values] for group, values in project.states.items()},
        'locomotion': {
            'footsteps': event_assets.get(loco.footstep_event), 'cloth': event_assets.get(loco.cloth_event),
            'cloth_chance': loco.cloth_chance, 'start': event_assets.get(loco.start_event),
            'stop': event_assets.get(loco.stop_event), 'jump': event_assets.get(loco.jump_event),
            'land': event_assets.get(loco.land_event), 'air_time_s': loco.air_time_ms / 1000,
            'surface_input': 'Surface', 'surface_to_physical_material': {s: f'PM_{pascal(s)}' for s in surface_options},
            'cadence_steps_per_s': loco.cadence, 'speed_cm_per_s': loco.speed, 'gait_gain_db': loco.gain_db,
            'note': 'In Unreal, fire footsteps from anim notifies on foot contact; cadence here only drives the '
                    'preview. Set Surface from the physical material under the foot, Gait/Speed from movement.'},
        'warnings': warnings,
    }
    (folder / 'unreal_manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    (folder / 'metasounds_project.json').write_text(json.dumps(project_to_dict(project), indent=1), encoding='utf-8')
    (folder / 'README_UNREAL.md').write_text(_readme(manifest), encoding='utf-8')
    report = {'folder': str(folder), 'waves': copied, 'sources': len(sources), 'attenuations': len(attenuations),
              'zones': len(volumes), 'emitters': len(ambient), 'warnings': warnings}
    return folder, report


def _readme(m):
    lines = [
        f"# {m['project']} - MetaSounds export ({m['exported']})", '',
        'Import order:', '',
        '1. Drag the `Sounds` folder into the Content Browser. Each WAV becomes the Sound Wave named in '
        '`sound_waves` (set Looping on the ones marked `looping`).',
        '2. Create Sound Classes / Submixes from `sound_classes`, and Control Buses + Control Bus Mixes from '
        '`control_bus_mixes` (Audio Modulation plugin).',
        '3. Create a Sound Attenuation asset per `attenuations` entry; every key is the Unreal property name.',
        '4. Create Sound Concurrency assets from `concurrency`.',
        '5. Build each MetaSound Source from `metasound_sources`: add the listed interfaces and inputs, then follow '
        '`graph_recipe` node by node. Assign attenuation, concurrency and sound class in Source settings.',
        '6. Create Reverb Effect assets from `reverb_effects` (starting values; tune by ear).',
        '7. Place Audio Gameplay Volumes from `audio_gameplay_volumes` (polygon in cm) with the listed components, '
        'and Soundscape palettes/colours from `soundscape_palettes` keyed by each zone\'s gameplay tag.',
        '8. Place Ambient Sound actors from `ambient_sounds`.',
        '9. Wire locomotion: footsteps from anim notifies, Surface from physical materials.', '',
        f"Contents: {len(m['sound_waves'])} waves, {len(m['metasound_sources'])} MetaSound Sources, "
        f"{len(m['attenuations'])} attenuations, {len(m['audio_gameplay_volumes'])} zones, "
        f"{len(m['ambient_sounds'])} emitters.", '',
        m['coordinates'], '']
    if m['warnings']:
        lines += ['## Warnings', ''] + [f'- {w}' for w in m['warnings']] + ['']
    return '\n'.join(lines)
