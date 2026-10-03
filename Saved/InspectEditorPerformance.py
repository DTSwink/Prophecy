import unreal

settings_class = unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")
settings = unreal.get_default_object(settings_class)
print("EDITOR_PERFORMANCE_CLASS=" + str(settings_class))
print("EDITOR_PERFORMANCE_DIR=" + ",".join(name for name in dir(settings) if "thrott" in name.lower() or "cpu" in name.lower()))
