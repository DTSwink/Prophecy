import traceback

import unreal


MAP_PATH = "/Game/vfxmap"
GENERATED_FOLDER = "/Game/Prophecy/BloodTexturePainting/Generated"
SOURCE_MATERIALS = [
    "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial",
    "/Engine/EditorMeshes/ColorCalibrator/M_GreyBall.M_GreyBall",
    "/Game/Fab/Megascans/3D/Rock_shopk/Medium/shopk_tier_2/Materials/MI_shopk.MI_shopk",
]


def log(message):
    unreal.log(f"[ProphecyBloodRebuild] {message}")


def path_name(obj):
    if not obj:
        return ""
    try:
        return obj.get_path_name()
    except Exception:
        return str(obj)


def get_actors():
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem:
            return list(subsystem.get_all_level_actors())
    except Exception:
        pass
    return list(unreal.EditorLevelLibrary.get_all_level_actors())


def find_or_spawn_manager(actors):
    manager_class = getattr(unreal, "ProphecyBloodTexturePaintManager", None)
    if not manager_class:
        raise RuntimeError("ProphecyBloodTexturePaintManager C++ class is not loaded")

    for actor in actors:
        if isinstance(actor, manager_class):
            return actor

    return unreal.EditorLevelLibrary.spawn_actor_from_class(manager_class, unreal.Vector(0, 0, 0))


def iter_static_mesh_components(actors):
    for actor in actors:
        try:
            components = actor.get_components_by_class(unreal.StaticMeshComponent)
        except Exception:
            components = []

        for component in components:
            try:
                if component.get_static_mesh():
                    yield actor, component
            except Exception:
                continue


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    actors = get_actors()
    manager = find_or_spawn_manager(actors)

    manager.set_editor_property("editor_auto_create_blood_materials", True)
    manager.set_editor_property("editor_auto_update_blood_materials", True)
    manager.set_editor_property("editor_allow_generated_material_overwrite", True)
    manager.set_editor_property("editor_save_generated_blood_materials", True)
    manager.set_editor_property("debug_mode", False)
    manager.set_editor_property("debug_print_hits", False)
    manager.set_editor_property("debug_draw_hit_locations", False)
    manager.set_editor_property("debug_log_rejected_hits", False)
    manager.set_editor_property("debug_show_mask_on_painted_materials", False)

    seen_materials = set()
    rebuilt = []
    skipped_generated = []

    cube_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    temp_actor = None
    temp_component = None
    if cube_mesh:
        temp_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, -100000))
        if temp_actor:
            temp_component = temp_actor.get_component_by_class(unreal.StaticMeshComponent)
            if temp_component:
                temp_component.set_static_mesh(cube_mesh)

    if temp_component:
        for source_path in SOURCE_MATERIALS:
            material = unreal.EditorAssetLibrary.load_asset(source_path)
            if not material:
                log(f"Source material not found: {source_path}")
                continue

            temp_component.set_material(0, material)
            ok = manager.debug_paint_uv(temp_component, unreal.Vector2D(0.5, 0.5), 1.0, 0.0, 0)
            if ok:
                rebuilt.append(path_name(material))
                log(f"Directly rebuilt blood material for {path_name(material)}")
                manager.clear_runtime_paint_state(True)
            else:
                log(f"Direct rebuild failed for {path_name(material)}")

    for actor, component in iter_static_mesh_components(actors):
        try:
            material_count = component.get_num_materials()
        except Exception:
            material_count = 0

        for slot in range(material_count):
            material = component.get_material(slot)
            material_path = path_name(material)
            if not material_path:
                continue

            if material_path.startswith(f"{GENERATED_FOLDER}/"):
                skipped_generated.append(material_path)
                continue

            if material_path in seen_materials:
                continue
            seen_materials.add(material_path)

            ok = manager.debug_paint_uv(component, unreal.Vector2D(0.5, 0.5), 1.0, 0.0, slot)
            if ok:
                rebuilt.append(material_path)
                log(f"Rebuilt blood material for {material_path}")
            else:
                log(f"Skipped unsupported material/component {material_path} on {path_name(component)}")

    manager.clear_runtime_paint_state(True)
    if temp_actor:
        unreal.EditorLevelLibrary.destroy_actor(temp_actor)

    unreal.EditorAssetLibrary.save_directory(GENERATED_FOLDER)
    log(f"Rebuilt {len(rebuilt)} source material(s); skipped {len(set(skipped_generated))} already-generated assignment(s).")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
