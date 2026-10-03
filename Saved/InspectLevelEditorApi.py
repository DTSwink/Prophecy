import unreal
subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
print([name for name in dir(subsystem) if "focus" in name.lower() or "play" in name.lower() or "viewport" in name.lower()])
