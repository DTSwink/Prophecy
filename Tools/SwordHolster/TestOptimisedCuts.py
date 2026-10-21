"""Owned current-scene cut capture. Overrides affect PIE only; saved assets untouched."""
import json, pathlib, sys, time, traceback, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'User Play is preserved'
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SwordOptimised'
out.mkdir(parents=True, exist_ok=True)
mode = 'flesh' if '--flesh' in sys.argv else ('pike' if '--pike' in sys.argv else 'slash')
suffix = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else mode
physics = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))
original = {}
for actor in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.Actor):
    if actor.get_class().get_name() == 'A_Sword_C':
        mesh = actor.get_editor_property('sword')
        original[actor.get_name()] = mesh.get_world_transform()
s = dict(start=time.monotonic(), world=None, last=None, samples=[], first=None, handle=None, initialized=set())

def v(x): return [x.x, x.y, x.z]
def prop(c, name):
    # User-defined struct property names are stable GUID-qualified engine names.
    names = {'constraint':'constraint_2_A220519843A91487F4B96091E1292F70',
        'victimcomp':'victimcomp_8_E920B57A4FEF4892559CA19BB304C19D',
        'bone':'bonename_29_18F73D5E41A0314363F49E9FE4D23A1E',
        'impact':'localimpact_18_C5A9727B4F3C635ED6CE39A68580BF05',
        'type':'typecut_26_E696872E4D78CD342DE03E8254E2D1D5',
        'matter':'typematter_15_407254D74A4A8B8B99007DB7AF8B4FA5'}
    return c.get_editor_property(names[name])

def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s['handle'])
    if s['world'] and ed.get_game_world() == s['world']: le.editor_request_end_play()
    (out / (suffix + '.json')).write_text(json.dumps(dict(error=error, mode=mode,
        first=s['first'], samples=s['samples']), indent=2), encoding='utf-8')

def tick(dt):
    try:
        world = ed.get_game_world()
        if not world:
            if s['world'] or time.monotonic() - s['start'] > 40: finish('Play ended or failed to start')
            return
        s['world'] = world
        t = unreal.GameplayStatics.get_time_seconds(world)
        if t == s['last']: return
        s['last'] = t
        for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
            if a.get_class().get_name() != 'A_Sword_C': continue
            mesh = a.get_editor_property('sword')
            if a.get_name() not in s['initialized']:
                a.set_editor_property('Optimised', '--legacy' not in sys.argv)
                if mode in ('pike','flesh'):
                    pose = original[a.get_name()]
                    velocity = unreal.Vector(1000,0,0)
                    if mode == 'flesh':
                        victims = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkeletalMeshActor)
                        victim = next(x for x in victims if 'UEFN' in str(x.skeletal_mesh_component.get_editor_property('skeletal_mesh_asset')))
                        head = victim.skeletal_mesh_component.get_socket_location('head') + unreal.Vector(0,0,10)
                        # Approach from the open side of the mannequin. Keep all
                        # scene collision policies and shared physics unchanged.
                        pose.rotation = unreal.MathLibrary.compose_rotators(mesh.get_world_rotation(), unreal.Rotator(0,180,0)).quaternion()
                        axis = unreal.MathLibrary.transform_direction(pose, unreal.Vector(0,0,1))
                        pose.translation = head - axis * (a.get_editor_property('hilt half length') + a.get_editor_property('blade length') + 25)
                        velocity = axis * 1000
                    physics.call_method('K2_SetWorldTransform', (mesh, pose, False, True))
                    physics.call_method('SetPhysicsLinearVelocity', (mesh, velocity, False, unreal.Name('None')))
                s['initialized'].add(a.get_name())
            cuts = list(a.get_editor_property('cuts'))
            if cuts and s['first'] is None: s['first'] = t
            row = dict(t=t, name=a.get_name(), position=v(mesh.get_world_location()), rotation=str(mesh.get_world_rotation()),
                velocity=v(physics.call_method('GetPhysicsLinearVelocity', (mesh, unreal.Name('None')))),
                cuts=[], wound=bool(a.get_editor_property('wound NS')), axis=v(mesh.get_up_vector()), incoming=v(a.get_editor_property('current vel')))
            material = mesh.get_material(0)
            if isinstance(material, unreal.MaterialInstanceDynamic):
                row['stain_depth'] = material.get_scalar_parameter_value('BladeBloodDepth')
            for cut in cuts:
                victim, bone = prop(cut,'victimcomp'), prop(cut,'bone')
                transform = victim.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD)
                wound = unreal.MathLibrary.transform_location(transform, prop(cut,'impact'))
                hilt = mesh.get_world_location() + mesh.get_up_vector() * a.get_editor_property('hilt half length')
                delta = wound - hilt
                row['cuts'].append(dict(type=prop(cut,'type'), matter=prop(cut,'matter'),
                    victim=victim.get_owner().get_name(), bone=str(bone),
                    joint=prop(cut,'constraint').get_name(), wound=v(wound),
                    plane=unreal.MathLibrary.dot_vector_vector(delta, mesh.get_forward_vector()), axial=unreal.MathLibrary.dot_vector_vector(delta, mesh.get_up_vector()),
                    lateral=unreal.MathLibrary.dot_vector_vector(delta, mesh.get_right_vector()),
                    length=a.get_editor_property('blade length'), halfwidth=a.get_editor_property('blade half width')))
            s['samples'].append(row)
            if mode == 'flesh':
                skels=unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkeletalMeshActor)
                row['heads']={x.get_name(): v(x.skeletal_mesh_component.get_socket_location('head')) for x in skels}
            if cuts and '--audit' in sys.argv:
                unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.ConstraintAudit A_Sword')
                row['native'] = json.loads((out.parent / 'StandardConstraints/World.json').read_text(encoding='utf-8-sig'))
            withdraw_at = float(sys.argv[sys.argv.index('--withdraw-at')+1]) if '--withdraw-at' in sys.argv else 1
            if cuts and '--withdraw' in sys.argv and t > withdraw_at and not s.get('withdrew'):
                s['withdrew'] = t
                physics.call_method('SetPhysicsLinearVelocity', (mesh, mesh.get_up_vector() * -5000, False, unreal.Name('None')))
        duration = float(sys.argv[sys.argv.index('--duration')+1]) if '--duration' in sys.argv else 4
        if t > duration or time.monotonic() - s['start'] > 100: finish()
    except Exception: finish(traceback.format_exc())
s['handle'] = unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('Owned Optimised cut capture started: ' + suffix)
