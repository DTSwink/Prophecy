"""Read-only editor capability/state inspection for a separate reduced rig."""
import unreal,json
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
pa=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin')
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
result=dict(play_active=sub.get_game_world() is not None,world=sub.get_editor_world().get_path_name(),
    dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    physics_methods=[n for n in dir(pa) if any(k in n.lower() for k in ('body','constraint','weld'))],
    classes=[n for n in dir(unreal) if 'PhysicsAsset' in n or 'SkeletalBodySetup' in n],
    spawn_help=unreal.EditorActorSubsystem.spawn_actor_from_class.__doc__)
for name in ('skeletal_body_setups','constraint_setup','collision_disable_table'):
    try:
        value=pa.get_editor_property(name)
        result[name]=dict(length=len(value),type=type(value).__name__)
        if name=='skeletal_body_setups' and value:
            b=value[0];result['body_methods']=[n for n in dir(b) if not n.startswith('_')]
    except Exception as e:result[name]=str(e)
(root/'Saved/MimicKitTransfer/unreal-inspection.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
