import hashlib
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
output = root / 'Saved/JoltMigration/FightStartup-20260910'
placement = json.loads((output / 'placement.json').read_text())
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyJoltFightSetup')
setups = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
actual_others = sorted(a.get_path_name() for a in actors if a not in setups)
report = {'world': world.get_path_name(), 'pie': unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
          'setups': [{'path': a.get_path_name(), 'enabled': a.get_editor_property('bEnableJolt')} for a in setups],
          'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
          'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
          'added_other_actors': sorted(set(actual_others) - set(placement['before_actors'])),
          'removed_other_actors': sorted(set(placement['before_actors']) - set(actual_others)),
          'disk_sha256': hashlib.sha256(Path(placement['source']).read_bytes()).hexdigest()}
print(json.dumps(report, indent=2))
(output / 'recovered-state.json').write_text(json.dumps(report, indent=2))
