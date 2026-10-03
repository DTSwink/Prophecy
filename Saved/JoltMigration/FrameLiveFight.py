import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world
agents = sorted(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent), key=lambda a:a.get_name())
assert len(agents) == 2 and all(a.is_jolt_physical_animation_enabled() for a in agents)
for agent in agents:
    if not agent.get_held_sword():
        assert agent.equip_sword(True), 'Native sword equip failed'
controller = unreal.GameplayStatics.get_player_controller(world, 0)
assert controller
controller.set_view_target_with_blend(agents[0], 0.0)
print('LIVE_VIEW_TARGET', controller.get_view_target())
