import traceback
import unreal


ASSETS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/BP_ProphecyPlaceholder",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/SKM_MHC_ProphecyPlaceholder_FaceMesh",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/SKM_MHC_ProphecyPlaceholder_BodyMesh",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Materials/MI_Body_Skin",
]


def log(message):
    unreal.log(f"[ProphecyMetaHumanInspect] {message}")


def object_path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def maybe_get(obj, prop_name):
    try:
        return obj.get_editor_property(prop_name)
    except Exception as exc:
        return f"<{exc}>"


def inspect_material_instance(asset):
    parent = maybe_get(asset, "parent")
    log(f"  parent={object_path(parent)}")
    for prop_name in ("base_property_overrides", "scalar_parameter_values", "vector_parameter_values", "texture_parameter_values"):
        values = maybe_get(asset, prop_name)
        if isinstance(values, str):
            log(f"  {prop_name}: {values}")
            continue
        try:
            log(f"  {prop_name}: {len(values)}")
            for value in values:
                info = maybe_get(value, "parameter_info")
                name = maybe_get(info, "name") if not isinstance(info, str) else "?"
                parameter_value = maybe_get(value, "parameter_value")
                log(f"    {name} = {object_path(parameter_value)}")
        except Exception as exc:
            log(f"  {prop_name}: <{exc}>")


def inspect_skeletal_mesh(asset):
    materials = maybe_get(asset, "materials")
    if isinstance(materials, str):
        log(f"  materials={materials}")
        return
    log(f"  material_slots={len(materials)}")
    for index, slot in enumerate(materials):
        slot_name = maybe_get(slot, "material_slot_name")
        mat = maybe_get(slot, "material_interface")
        log(f"    [{index}] {slot_name}: {object_path(mat)}")


def main():
    for path in ASSETS:
        asset = unreal.load_asset(path)
        log(f"ASSET {path}: {object_path(asset)} class={asset.get_class().get_name() if asset else 'None'}")
        if asset is None:
            continue
        class_name = asset.get_class().get_name()
        if "MaterialInstance" in class_name:
            inspect_material_instance(asset)
        if "SkeletalMesh" in class_name:
            inspect_skeletal_mesh(asset)


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
