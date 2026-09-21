import unreal, json, pathlib
def read(obj, field):
    try: return obj.get_editor_property(field)
    except Exception: return None
def material(m):
    if not m: return None
    return dict(path=m.get_path_name(), **{n:str(read(m,n)) for n in ('friction','static_friction','restitution','friction_combine_mode','override_friction_combine_mode','restitution_combine_mode','override_restitution_combine_mode')})
rows=[]
for obj in unreal.ObjectIterator():
    try:
        path=obj.get_path_name()
        cls=obj.get_class().get_name()
    except Exception: continue
    if cls == 'SkeletalBodySetup' and 'PA_UEFN_Mannequin.' in path:
        bone=str(read(obj,'bone_name'))
        if bone not in ('foot_l','foot_r','ball_l','ball_r'): continue
        body=read(obj,'default_instance')
        rows.append(dict(bone=bone, path=path, setup_material=material(read(obj,'phys_material')),
            instance_material=material(read(body,'phys_material_override'))))
    if cls == 'BodySetup' and 'Default__' not in path:
        rows.append(dict(body_setup=path, material=material(read(obj,'phys_material'))))
    if isinstance(obj,unreal.PhysicalMaterial): rows.append(dict(material=material(obj)))
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world:
    for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
        if 'floor' in a.get_actor_label().lower():
            for c in a.get_components_by_class(unreal.PrimitiveComponent):
                rows.append(dict(floor=a.get_actor_label(), bounds=str(a.get_actor_bounds(False)),
                    render_material_physics=material(read(c.get_material(0),'phys_material'))))
settings=unreal.get_default_object(unreal.PhysicsSettings)
rows.append(dict(settings={n:str(read(settings,n)) for n in ('friction_combine_mode','restitution_combine_mode','bounce_threshold_velocity')}))
path=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FootFloor/materials.json'
path.write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
