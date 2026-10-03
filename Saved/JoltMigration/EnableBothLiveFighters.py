import json
from datetime import datetime
from pathlib import Path
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
actors = {a.get_name():a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)}
first = actors['BP_ProphecyManualPoseAgent_C_0']
second = actors['BP_ProphecyManualPoseAgent_C_1']
assert not first.is_jolt_physical_animation_enabled() and not second.is_jolt_physical_animation_enabled()
first.hide_sword()
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
scratch = Path.home()/'.codex/tmp/ProphecyJolt'/('VisualBothBegin-'+stamp+'.json')
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.VisualBegin '+scratch.as_posix()+' '+first.get_name())
report = json.loads(scratch.read_text(encoding='utf-8-sig'))
target = Path(unreal.Paths.project_saved_dir()).resolve()/'JoltMigration'/('VisualBothBegin-'+stamp+'.json')
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
assert report.get('startup_success'), report.get('startup_error')
assert report.get('scene_bodies', 0) > 0, 'The fixed floor was not imported'
second.set_macd_enabled(False)
assert second.enable_jolt_physical_animation(), 'Second fighter did not enter Jolt'
assert first.is_jolt_physical_animation_enabled() and second.is_jolt_physical_animation_enabled()
if not second.get_held_sword():
    assert second.equip_sword(True), 'Second fighter sword equip failed'
assert first.get_held_sword() and second.get_held_sword()
print('BOTH_FIGHTERS_JOLT_ENABLED; floor bodies='+str(report['scene_bodies']))
controller=unreal.GameplayStatics.get_player_controller(world,0)
if controller: print('VIEW',controller.get_view_target())
