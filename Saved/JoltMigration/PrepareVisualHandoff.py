"""Enable the two original fighters in fresh PIE, then pause on the test floor."""
from pathlib import Path
import unreal

saved = Path(unreal.Paths.project_saved_dir()).resolve()
exec((saved / 'JoltMigration/EnableBothLiveFighters.py').read_text(encoding='utf-8'), {})
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
fighters = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
target = next(a for a in fighters if a.get_name() == 'BP_ProphecyManualPoseAgent_C_1')
controller = unreal.GameplayStatics.get_player_controller(world, 0)
assert controller
controller.set_view_target_with_blend(target, 0.0)

visual_handoff_state = {'world': world, 'elapsed': 0.0, 'handle': None}
def pause_visual_handoff(delta_seconds):
    state = visual_handoff_state
    state['elapsed'] += delta_seconds
    if state['elapsed'] < 2.0:
        return
    unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle'] = None
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() != state['world']:
        return
    unreal.GameplayStatics.set_game_paused(state['world'], True)
    unreal.SystemLibrary.execute_console_command(state['world'], 'HighResShot 1')
    print('VISUAL_HANDOFF_PAUSED_ON_FLOOR')

visual_handoff_state['handle'] = unreal.register_slate_post_tick_callback(pause_visual_handoff)
print('VISUAL_HANDOFF_WILL_PAUSE_AFTER_TWO_SECONDS')
