"""Run only after blood captures, in live PIE. Four isolated physical-hit cases (~15 game seconds).

No asset/config saves or changes to existing bodies. Spawned actors live only in the PIE world.
Native BreakHitResult and deferred-spawn functions are called through existing reflection glue.
Use `cleanup` to stop an active run. Do not run another BloodVisualBody command concurrently.
"""
import builtins
import json
import math
import pathlib
import sys
import time
import traceback

import unreal

OUT = pathlib.Path(unreal.Paths.project_saved_dir()).resolve() / 'Diagnostics/BloodVisual-20260910'
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / 'hit-events.json'
KEY = '_prophecy_hit_event_check'
TAG = 'ProphecyHitEventCheck20260910'
SPEC = [('chaos', True), ('chaos', False), ('jolt', True), ('jolt', False)]
GS = unreal.GameplayStatics.get_default_object()


def path(obj):
    return obj.get_path_name() if obj else None


def vector(v):
    return [float(v.x), float(v.y), float(v.z)]


def save(s):
    REPORT.write_text(json.dumps(s['report'], indent=2))


def cleanup(s, complete=False):
    if s.get('tick') is not None:
        unreal.unregister_slate_post_tick_callback(s['tick'])
        s['tick'] = None
    for obj, event_name, fn in s.get('bindings', []):
        try:
            getattr(obj, event_name).remove_callable(fn)
        except Exception:
            pass
    s['bindings'] = []
    s['delegates'] = []
    errors = []
    for actor in reversed(s.get('actors', [])):
        try:
            if TAG in [str(t) for t in actor.tags]:
                actor.destroy_actor()
        except Exception as exc:
            errors.append(str(exc))
    s['actors'] = []
    s['report']['cleanup_errors'] = errors
    s['report']['complete'] = complete
    s['running'] = False
    save(s)
    print('HIT_EVENT_CHECK_FINISHED', str(REPORT), s['report'].get('comparison', s['report'].get('error')))


old = getattr(builtins, KEY, None)
if old and old.get('running'):
    if len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
        old['report']['stopped_by_request'] = True
        cleanup(old)
    else:
        raise RuntimeError('Hit-event check already running; use cleanup before starting another.')
elif len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
    print('No active hit-event check.')
else:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world and 'UEDPIE_' in world.get_path_name(), 'Run in live PIE only.'
    assert unreal.ProphecyJoltBlueprintLibrary.is_jolt_world_ready(world), 'Jolt world must already be ready.'
    scene_owners = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        for c in a.get_components_by_class(unreal.ProphecyJoltSceneCollisionComponent):
            if c.is_scene_collision_enabled():
                scene_owners.append(path(c))
    assert len(scene_owners) == 1, 'Requires the existing enabled Jolt static-scene importer.'
    origin = unreal.Vector(50000, 50000, 2000)
    cube_asset = unreal.load_asset('/Engine/BasicShapes/Cube')
    assert cube_asset
    s = {'world': world, 'actors': [], 'bindings': [], 'delegates': [], 'tick': None, 'running': True,
         'index': -1, 'phase': 'floor_wait', 'wait_frames': 0, 'wall_start': time.monotonic(),
         'report': {'complete': False, 'world': path(world), 'scene_owners': scene_owners,
                    'scope': 'Actual physical cube-floor collision delegates, matched downward velocity and gravity disabled. Checks component/actor event delivery, identities, impulse and notify-off control; not sweep/overlap/persistence or all gameplay contact types.',
                    'asset_saves_requested': False, 'origin': vector(origin), 'cases': []}}
    setattr(builtins, KEY, s)

    def spawn(name, location, scale, static=False):
        transform = unreal.Transform(location=location, scale=scale)
        actor = GS.call_method('BeginDeferredActorSpawnFromClass', args=(
            world, unreal.StaticMeshActor, transform,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None))
        assert actor, 'Deferred PIE actor spawn failed.'
        s['actors'].append(actor)
        actor.tags = list(actor.tags) + [TAG, 'BloodVisual20260910', 'BloodCheck_' + name]
        mesh = actor.static_mesh_component
        mesh.set_static_mesh(cube_asset)
        mesh.set_mobility(unreal.ComponentMobility.STATIC if static else unreal.ComponentMobility.MOVABLE)
        mesh.set_collision_profile_name('BlockAll')
        mesh.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        mesh.set_editor_property('generate_overlap_events', False)
        mesh.set_notify_rigid_body_collision(False)
        mesh.set_enable_gravity(False)
        if not static:
            mesh.set_mass_override_in_kg('None', 10.0, True)
            mesh.set_linear_damping(0.0)
            mesh.set_angular_damping(0.0)
        GS.call_method('FinishSpawningActor', args=(actor, transform))
        return actor, mesh

    def break_hit(hit):
        values = GS.call_method('BreakHitResult', args=(hit,))
        assert len(values) == 18, 'Unexpected engine BreakHitResult signature.'
        names = ('blocking', 'initial_overlap', 'time', 'distance', 'location', 'impact_point',
                 'normal', 'impact_normal', 'physical_material', 'hit_actor', 'hit_component',
                 'hit_bone', 'my_bone', 'item', 'element', 'face', 'trace_start', 'trace_end')
        data = dict(zip(names, values))
        for name in ('location', 'impact_point', 'normal', 'impact_normal', 'trace_start', 'trace_end'):
            data[name] = vector(data[name])
        for name in ('physical_material', 'hit_actor', 'hit_component'):
            data[name] = path(data[name])
        for name in ('hit_bone', 'my_bone'):
            data[name] = str(data[name])
        return data

    def console(command):
        unreal.SystemLibrary.execute_console_command(world, command)

    def ownership(name):
        console('Prophecy.Jolt.BloodVisualBody BloodCheck_' + name + ' state')
        return json.loads((OUT / 'body-state.json').read_text())

    def begin_case():
        s['index'] += 1
        if s['index'] == len(SPEC):
            rows = s['report']['cases']
            conclusive = all(r['collision_verified'] and r['ownership_verified']
                             and r['event_identities_valid'] for r in rows)
            chaos_on, chaos_off, jolt_on, jolt_off = rows
            counts = lambda r: (len(r['component_hits']), len(r['actor_hits']))
            positive = len(chaos_on['component_hits']) > 0 and chaos_on['nonzero_impulse_events'] > 0
            negative = not chaos_off['component_hits'] and not jolt_off['component_hits']
            comparable = conclusive and positive and negative
            actor_bindings_supported = all(r.get('actor_binding_supported', False) for r in rows)
            s['report']['comparison'] = {
                'conclusive_contact_and_controls': comparable,
                'acceptance_scope': 'OnComponentHit; OnActorHit is separate and unverified when Python binding is unsupported.',
                'chaos_notify_on_counts': counts(chaos_on), 'chaos_notify_off_counts': counts(chaos_off),
                'jolt_notify_on_counts': counts(jolt_on), 'jolt_notify_off_counts': counts(jolt_off),
                'jolt_matches_component_event_delivery': comparable and len(jolt_on['component_hits']) > 0
                                              and jolt_on['nonzero_impulse_events'] > 0,
                'actor_bindings_supported': actor_bindings_supported,
                'actor_event_comparison': (bool(chaos_on['actor_hits']) and bool(jolt_on['actor_hits'])
                    and not chaos_off['actor_hits'] and not jolt_off['actor_hits']) if actor_bindings_supported else None,
                'interpretation': ('Compare nonzero event delivery and valid identities, not exact impulse equality between solvers.'
                                   if comparable else 'Inconclusive: inspect physical contact, ownership or Chaos/negative controls.')}
            cleanup(s, complete=True)
            return
        backend, notify = SPEC[s['index']]
        name = 'HitEvent_' + backend + ('_on' if notify else '_off')
        actor, mesh = spawn(name, origin + unreal.Vector(0, 0, 225), unreal.Vector(.5, .5, .5))
        mesh.set_notify_rigid_body_collision(notify)
        row = {'backend': backend, 'notify': notify, 'actor': path(actor), 'component': path(mesh),
               'floor_actor': path(s['floor']), 'floor_component': path(s['floor_mesh']),
               'component_hits': [], 'actor_hits': [], 'samples': [], 'initial_z': actor.get_actor_location().z,
               'initial_velocity_cm_s': [0, 0, -300], 'mass_kg': 10.0, 'gravity_enabled': False}
        s['report']['cases'].append(row)
        s.update(actor=actor, mesh=mesh, row=row, name=name, phase='body_wait', wait_frames=0)

        def component_hit(hit_component, other_actor, other_component, impulse, hit):
            try:
                row['component_hits'].append({'self_component': path(hit_component), 'other_actor': path(other_actor),
                    'other_component': path(other_component), 'normal_impulse': vector(impulse), 'hit': break_hit(hit)})
            except Exception:
                row.setdefault('callback_errors', []).append(traceback.format_exc())

        def actor_hit(self_actor, other_actor, impulse, hit):
            try:
                row['actor_hits'].append({'self_actor': path(self_actor), 'other_actor': path(other_actor),
                    'normal_impulse': vector(impulse), 'hit': break_hit(hit)})
            except Exception:
                row.setdefault('actor_callback_errors', []).append(traceback.format_exc())

        component_delegate = mesh.on_component_hit
        component_delegate.add_callable(component_hit)
        # UE's callable proxy is weak on the native delegate. Keep the Python wrapper alive
        # throughout observation so GC cannot turn a valid binding into a false zero count.
        s['delegates'].append(component_delegate)
        s['bindings'].append((mesh, 'on_component_hit', component_hit))
        row['component_binding_supported'] = True
        try:
            actor_delegate = actor.on_actor_hit
            actor_delegate.add_callable(actor_hit)
            s['delegates'].append(actor_delegate)
            s['bindings'].append((actor, 'on_actor_hit', actor_hit))
            row['actor_binding_supported'] = True
        except Exception:
            row['actor_binding_supported'] = False
            row['actor_binding_error'] = traceback.format_exc()
        console('Prophecy.Jolt.BloodVisualBody BloodCheck_' + name + ' ' + backend + ' 0 0 -300 0 0 0')
        row['enable_result'] = json.loads((OUT / 'body-state.json').read_text())
        assert row['enable_result'].get('success'), row['enable_result']
        s['case_start'] = unreal.GameplayStatics.get_time_seconds(world)

    def finish_case():
        row = s['row']
        row['final_ownership'] = ownership(s['name'])
        own = row['final_ownership']
        row['ownership_verified'] = own.get('success') and (own.get('jolt') if row['backend'] == 'jolt'
            else own.get('chaos_simulating') and not own.get('jolt'))
        tail = row['samples'][-20:]
        final_z = tail[-1]['position'][2]
        tail_span = max(r['position'][2] for r in tail) - min(r['position'][2] for r in tail)
        # Floor top=origin.z+10, cube halfheight=25. Downward travel and stable support
        # exclude false zero-event results caused by failed admission or a missing native floor.
        row['collision_verified'] = (row['initial_z'] - final_z > 100
            and abs(final_z - (origin.z + 35)) < 3 and tail_span < 0.5)
        row['final_z_cm'] = final_z
        row['tail_z_span_cm'] = tail_span
        row['event_identities_valid'] = all(e['other_actor'] == row['floor_actor']
            and e['hit']['hit_actor'] == row['floor_actor'] and e['hit']['hit_component'] == row['floor_component']
            for e in row['component_hits']) and not row.get('callback_errors')
        row['nonzero_impulse_events'] = sum(math.sqrt(sum(v*v for v in e['normal_impulse'])) > 0
            for e in row['component_hits'])
        for obj, event_name, fn in s['bindings']:
            getattr(obj, event_name).remove_callable(fn)
        s['bindings'] = []
        s['delegates'] = []
        s['actor'].destroy_actor()
        s['actors'].remove(s['actor'])
        s['phase'] = 'between'
        s['wait_frames'] = 0
        save(s)

    def tick(_dt):
        try:
            if time.monotonic() - s['wall_start'] > 180:
                raise RuntimeError('180-second wall timeout: PIE paused, overloaded or world unavailable.')
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() == world, 'PIE world changed.'
            s['wait_frames'] += 1
            if s['phase'] in ('floor_wait', 'between'):
                if s['wait_frames'] >= 5:
                    begin_case()
                return
            if s['phase'] == 'body_wait':
                if s['wait_frames'] < 3:
                    return
                s['row']['initial_ownership'] = ownership(s['name'])
                s['phase'] = 'observe'
            if s['phase'] == 'observe':
                elapsed = unreal.GameplayStatics.get_time_seconds(world) - s['case_start']
                s['row']['samples'].append({'game_seconds': elapsed, 'position': vector(s['mesh'].get_world_location())})
                if elapsed >= 3.0:
                    finish_case()
        except Exception:
            s['report']['error'] = traceback.format_exc()
            cleanup(s)

    try:
        s['floor'], s['floor_mesh'] = spawn('HitEvent_Floor', origin, unreal.Vector(4, 4, .2), static=True)
        s['report']['floor_actor'] = path(s['floor'])
        s['tick'] = unreal.register_slate_post_tick_callback(tick)
        save(s)
        print('HIT_EVENT_CHECK_STARTED', str(REPORT))
    except Exception:
        s['report']['error'] = traceback.format_exc()
        cleanup(s)
        raise
