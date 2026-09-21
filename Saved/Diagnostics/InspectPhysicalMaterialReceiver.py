import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_game_world() or ed.get_editor_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
    for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
        if c.get_name()=='PhysicalMesh':print(a.get_name(),c.get_class().get_name())
