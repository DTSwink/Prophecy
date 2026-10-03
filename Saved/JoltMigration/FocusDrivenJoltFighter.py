"""PIE-only visual check using the fighter's existing drive settings."""
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
agents = {a.get_name(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)}
agent = agents['BP_ProphecyManualPoseAgent_C_1']
print('BEFORE', agent.get_actor_label(), agent.get_simulation_mode(), agent.is_jolt_physical_animation_enabled())
if not agent.is_jolt_physical_animation_enabled():
    agent.set_macd_enabled(False)
    assert agent.enable_jolt_physical_animation(), 'Jolt enable failed'
assert agent.is_jolt_physical_animation_enabled()
assert agent.get_held_sword() or agent.equip_sword(True)
controller = unreal.GameplayStatics.get_player_controller(world, 0)
assert controller
controller.set_view_target_with_blend(agent, 0.0)
print('AFTER', agent.get_simulation_mode(), agent.is_jolt_physical_animation_enabled(), controller.get_view_target())
