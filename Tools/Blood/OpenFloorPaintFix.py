"""Open the existing manager for the user's manual floor-paint repair."""
import json, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
bp = unreal.load_asset("/Game/_mygame/blood2/A_DecalManager")
opened = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([bp])
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.Actor):
    if a.get_class().get_name().startswith("A_DecalManager_C"):
        floor = a.get_editor_property("floor")
        mesh = floor.get_component_by_class(unreal.StaticMeshComponent) if floor else None
        rows.append({"decal_manager": a.get_actor_label(),
                     "floor_material": mesh.get_material(0).get_path_name() if mesh else None,
                     "paint_manager": a.get_editor_property("paint manager").get_actor_label()})
print(json.dumps({"opened": opened, "actors": rows, "play": bool(ed.get_game_world())}))
