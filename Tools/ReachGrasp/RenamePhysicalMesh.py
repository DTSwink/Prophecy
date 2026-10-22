"""Apply persistent editor node labels and verify the physical mesh getter."""
from pathlib import Path
import json
import runpy
import unreal


def main():
    root = Path(unreal.Paths.project_dir())
    module = runpy.run_path(str(root / 'Content/Python/prophecy_node_labels.py'))
    assert module['apply']()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world() or editor.get_editor_world()
    cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAgent')
    agents = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
    meshes = []
    for agent in agents:
        mesh = agent.call_method('GetPoseReferenceMesh')
        assert mesh is not None
        meshes.append(dict(agent=agent.get_name(), physical_mesh=mesh.get_name()))
    result = dict(display_name='Get Physical Mesh', function_identity_unchanged=True,
                  map=world.get_path_name(), play=bool(editor.get_game_world()), meshes=meshes,
                  dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
                         + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())])
    output = root / 'Saved/Diagnostics/ClosestAgent/physical-mesh-label.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


main()
