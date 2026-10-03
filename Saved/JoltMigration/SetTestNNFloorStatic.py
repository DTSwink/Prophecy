import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name() == '/Game/testNN.testNN'
floors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if a.get_name() == 'Floor_0' and a.get_actor_label() == 'Floor']
assert len(floors) == 1
floor = floors[0].get_component_by_class(unreal.StaticMeshComponent)
assert floor and floor.get_editor_property('static_mesh').get_path_name() == '/Engine/MapTemplates/SM_Template_Map_Floor.SM_Template_Map_Floor'
assert not floor.is_simulating_physics()
before = str(floor.get_editor_property('mobility'))
transform = floor.get_world_transform()
with unreal.ScopedEditorTransaction('Set testNN fixed floor Static for Jolt'):
    floors[0].modify()
    floor.modify()
    floor.set_mobility(unreal.ComponentMobility.STATIC)
assert floor.get_editor_property('mobility') == unreal.ComponentMobility.STATIC
assert floor.get_world_transform() == transform
assert unreal.EditorLoadingAndSavingUtils.save_map(world, '/Game/testNN')
report = {'map':'/Game/testNN', 'actor':'Floor_0', 'before':before,
          'after':str(floor.get_editor_property('mobility')), 'transform_preserved':True, 'saved':True}
target = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/TestNNFloor-20260910/publication.json'
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
