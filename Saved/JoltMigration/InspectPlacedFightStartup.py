import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cls = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyJoltFightSetup")
actors = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
print("SETUPS", [a.get_path_name() for a in actors])
for actor in actors:
    for name in ["bEnableJolt", "EnableJolt", "SceneCollision", "StartedAgentCount", "LastError"]:
        try:
            print(name, str(actor.get_editor_property(name)))
        except Exception as error:
            print(name, str(error))
