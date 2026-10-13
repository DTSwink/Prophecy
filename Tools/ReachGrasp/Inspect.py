import json
import pathlib
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world()
result = {'play': bool(world), 'map': editor.get_editor_world().get_path_name(), 'actors': []}
if world:
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
        result['actors'].append({'name': a.get_name(), 'tick': a.get_editor_property('absolute tick debug')})
print(json.dumps(result))
