import unreal


asset = unreal.load_asset("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent")
generated = asset.generated_class()
cdo = unreal.get_default_object(generated)
print("BLUEPRINT_CDO", cdo)
for component in cdo.get_components_by_class(unreal.ActorComponent):
    row = ["COMPONENT", component.get_name(), component.get_class().get_name()]
    if isinstance(component, unreal.SkinnedMeshComponent):
        row += ["asset", component.get_skinned_asset(), "materials"]
        for index in range(component.get_num_materials()):
            material = component.get_material(index)
            row.append(material.get_path_name() if material else None)
    print(*row)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
agent = unreal.GameplayStatics.get_all_actors_of_class(world, generated)[0]
print("LIVE_AGENT", agent)
for component in agent.get_components_by_class(unreal.ActorComponent):
    row = ["LIVE_COMPONENT", component.get_name(), component.get_class().get_name()]
    if isinstance(component, unreal.SkinnedMeshComponent):
        row += ["visible", component.is_visible(), "sim", component.is_simulating_physics(), "asset", component.get_skinned_asset(), "materials"]
        for index in range(component.get_num_materials()):
            material = component.get_material(index)
            row.append(material.get_path_name() if material else None)
    print(*row)
