import traceback
import unreal


FACE_MESH_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/SKM_MHC_ProphecyPlaceholder_FaceMesh"


def log(message):
    unreal.log(f"[ProphecyFaceSections] {message}")


def material_name(mesh, slot_index):
    materials = mesh.get_editor_property("materials")
    if slot_index < 0 or slot_index >= len(materials):
        return "<out-of-range>"
    material = materials[slot_index].get_editor_property("material_interface")
    return material.get_path_name() if material else "None"


def main():
    mesh = unreal.load_asset(FACE_MESH_PATH)
    if mesh is None:
        raise RuntimeError(f"Missing face mesh: {FACE_MESH_PATH}")

    subsystem = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    lod_count = subsystem.get_lod_count(mesh)
    log(f"lod_count={lod_count}")
    for lod_index in range(lod_count):
        section_count = subsystem.get_num_sections(mesh, lod_index)
        log(f"LOD {lod_index}: sections={section_count}")
        for section_index in range(section_count):
            slot_index = subsystem.get_lod_material_slot(mesh, lod_index, section_index)
            log(f"  section {section_index}: slot={slot_index} material={material_name(mesh, slot_index)}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
