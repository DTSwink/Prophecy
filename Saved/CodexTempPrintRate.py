import unreal


engine = unreal.get_default_object(unreal.Engine)
print("ENGINE_RATE", engine.get_editor_property("use_fixed_frame_rate"), engine.get_editor_property("fixed_frame_rate"))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world:
    print("WORLD_DT", world.get_delta_seconds())
