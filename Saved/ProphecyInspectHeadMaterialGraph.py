import traceback
import unreal


MATERIAL_PATH = "/Game/Prophecy/MetaHumanPipeline/M_ProphecyPlaceholderHeadSkin"


def log(message):
    unreal.log(f"[ProphecyHeadMaterialGraph] {message}")


def node_path(node):
    return f"{node.get_class().get_name()}:{node.get_name()}" if node else "None"


def inspect_property(material, prop):
    node = unreal.MaterialEditingLibrary.get_material_property_input_node(material, prop)
    output_name = unreal.MaterialEditingLibrary.get_material_property_input_node_output_name(material, prop)
    log(f"{prop}: node={node_path(node)} output={output_name}")


try:
    material = unreal.load_asset(MATERIAL_PATH)
    if material is None:
        raise RuntimeError(f"Missing material: {MATERIAL_PATH}")
    log(f"expressions={unreal.MaterialEditingLibrary.get_num_material_expressions(material)}")
    inspect_property(material, unreal.MaterialProperty.MP_BASE_COLOR)
    inspect_property(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    inspect_property(material, unreal.MaterialProperty.MP_ROUGHNESS)
    inspect_property(material, unreal.MaterialProperty.MP_SPECULAR)
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
