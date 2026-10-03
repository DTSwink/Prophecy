import traceback
import unreal


ASSETS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/Common/Materials/MI_Skin_Head_UI_LOD1_VT",
]


def path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def log(message):
    unreal.log(f"[ProphecyFaceSkinParams] {message}")


def inspect_material(material):
    log(f"ASSET {path(material)} class={material.get_class().get_name()}")
    try:
        parent = material.get_editor_property("parent")
        log(f"  parent={path(parent)}")
    except Exception:
        pass

    for kind, names_fn, value_fn, default_fn, source_fn in (
        ("texture", unreal.MaterialEditingLibrary.get_texture_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value,
         unreal.MaterialEditingLibrary.get_material_default_texture_parameter_value,
         unreal.MaterialEditingLibrary.get_texture_parameter_source),
        ("scalar", unreal.MaterialEditingLibrary.get_scalar_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value,
         unreal.MaterialEditingLibrary.get_material_default_scalar_parameter_value,
         unreal.MaterialEditingLibrary.get_scalar_parameter_source),
        ("vector", unreal.MaterialEditingLibrary.get_vector_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value,
         unreal.MaterialEditingLibrary.get_material_default_vector_parameter_value,
         unreal.MaterialEditingLibrary.get_vector_parameter_source),
        ("switch", unreal.MaterialEditingLibrary.get_static_switch_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_static_switch_parameter_value,
         unreal.MaterialEditingLibrary.get_material_default_static_switch_parameter_value,
         unreal.MaterialEditingLibrary.get_static_switch_parameter_source),
    ):
        try:
            names = names_fn(material)
        except Exception as exc:
            log(f"  {kind} names failed: {exc}")
            continue

        log(f"  {kind} names={len(names)}")
        for name in names:
            try:
                value = value_fn(material, name)
            except Exception as exc:
                value = f"<instance failed: {exc}>"
            try:
                default_value = default_fn(material, name)
            except Exception as exc:
                default_value = f"<default failed: {exc}>"
            try:
                source = source_fn(material, name)
            except Exception as exc:
                source = f"<source failed: {exc}>"
            log(f"    {name}: value={path(value)} default={path(default_value)} source={path(source)}")

    try:
        used = unreal.MaterialEditingLibrary.get_used_textures(material)
        log(f"  used_textures={len(used)}")
        for item in used[:80]:
            log(f"    used {path(item)}")
    except Exception as exc:
        log(f"  used_textures failed: {exc}")


try:
    for asset_path in ASSETS:
        material = unreal.load_asset(asset_path)
        if material is None:
            raise RuntimeError(f"Missing material: {asset_path}")
        inspect_material(material)
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
