import os
import traceback
import unreal


ASSET_DIR = "/Game/Prophecy/MetaHumanPipeline"
ASSET_NAME = "MHC_ProphecyPlaceholder"
ASSET_PATH = f"{ASSET_DIR}/{ASSET_NAME}"
BUILD_ROOT = "/Game/Prophecy/MetaHumans"
COMMON_ROOT = f"{BUILD_ROOT}/Common"
BUILD_NAME = "ProphecyPlaceholder"


def log(message):
    unreal.log(f"[ProphecyMetaHuman] {message}")


def warn(message):
    unreal.log_warning(f"[ProphecyMetaHuman] {message}")


def err(message):
    unreal.log_error(f"[ProphecyMetaHuman] {message}")


def enum_member(enum_cls, *names):
    for name in names:
        candidates = (name, name.upper(), name.lower())
        for candidate in candidates:
            if hasattr(enum_cls, candidate):
                return getattr(enum_cls, candidate)
    raise RuntimeError(f"Could not find any of {names} on {enum_cls}")


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as exc:
        warn(f"Could not set {obj.__class__.__name__}.{name}: {exc}")
        return False


def set_prop_any(obj, names, value):
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return True
        except Exception:
            pass
    warn(f"Could not set any of {names} on {obj.__class__.__name__}")
    return False


def call_optional(obj, method_name, *args):
    method = getattr(obj, method_name, None)
    if method is None:
        warn(f"{obj.__class__.__name__}.{method_name} is not available in Python")
        return None
    return method(*args)


def save_asset(path):
    if hasattr(unreal.EditorAssetLibrary, "save_asset"):
        return unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_loaded_asset(unreal.load_asset(path), only_if_is_dirty=False)
    return True


def describe_character(character, subsystem):
    for method_name in (
        "is_character_valid",
        "has_face_dna",
        "has_face_dna_blendshapes",
        "has_high_resolution_textures",
    ):
        method = getattr(character, method_name, None)
        if method:
            try:
                log(f"{method_name}: {method()}")
            except Exception as exc:
                warn(f"{method_name} failed: {exc}")

    for method_name in ("is_object_added_for_editing", "is_auto_rigging_face"):
        method = getattr(subsystem, method_name, None)
        if method:
            try:
                log(f"{method_name}: {method(character)}")
            except Exception as exc:
                warn(f"{method_name} failed: {exc}")

    method = getattr(subsystem, "get_rigging_state", None)
    if method:
        try:
            log(f"get_rigging_state: {method(character)}")
        except Exception as exc:
            warn(f"get_rigging_state failed: {exc}")

    try:
        can_build = subsystem.can_build_meta_human(character, False)
        log(f"can_build_meta_human: {can_build}")
        return bool(can_build)
    except Exception as exc:
        warn(f"can_build_meta_human failed: {exc}")
        return False


def main():
    log(f"Unreal version: {unreal.SystemLibrary.get_engine_version()}")
    unreal.EditorAssetLibrary.make_directory(ASSET_DIR)
    unreal.EditorAssetLibrary.make_directory(BUILD_ROOT)
    unreal.EditorAssetLibrary.make_directory(COMMON_ROOT)

    character = unreal.load_asset(ASSET_PATH) if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH) else None
    if character:
        log(f"Loaded existing MetaHuman Character: {ASSET_PATH}")
    else:
        log(f"Creating MetaHuman Character asset: {ASSET_PATH}")
        factory = unreal.MetaHumanCharacterFactoryNew()
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        character = asset_tools.create_asset(
            asset_name=ASSET_NAME,
            package_path=ASSET_DIR,
            asset_class=unreal.MetaHumanCharacter,
            factory=factory,
        )
        if not character:
            raise RuntimeError("AssetTools.create_asset returned None")
        save_asset(ASSET_PATH)

    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    if subsystem is None:
        raise RuntimeError("MetaHumanCharacterEditorSubsystem is not available")

    log("Adding character to MetaHuman editor subsystem")
    added = call_optional(subsystem, "try_add_object_to_edit", character)
    log(f"try_add_object_to_edit: {added}")

    log("Running preview assembly pass")
    call_optional(subsystem, "assemble_for_preview", character)

    can_build = describe_character(character, subsystem)

    if not can_build:
        log("Requesting blocking auto-rig pass")
        rig_params = unreal.MetaHumanCharacterAutoRiggingRequestParams()
        rig_type = enum_member(unreal.MetaHumanRigType, "JOINTS_AND_BLEND_SHAPES", "JOINTS_AND_BLENDSHAPES", "JointsAndBlendShapes")
        set_prop_any(rig_params, ("rig_type", "RigType"), rig_type)
        set_prop_any(rig_params, ("report_progress", "b_report_progress", "bReportProgress"), False)
        set_prop_any(rig_params, ("blocking", "b_blocking", "bBlocking"), True)
        call_optional(subsystem, "request_auto_rigging", character, rig_params)
        save_asset(ASSET_PATH)
        can_build = describe_character(character, subsystem)

    if not can_build:
        texture_synthesis_dir = os.path.join(
            unreal.Paths.engine_plugins_dir(),
            "MetaHuman",
            "MetaHumanCharacter",
            "Content",
            "Optional",
            "TextureSynthesis",
        )
        if os.path.isdir(texture_synthesis_dir):
            log("Requesting blocking texture-source pass")
            tex_params = unreal.MetaHumanCharacterTextureRequestParams()
            set_prop_any(tex_params, ("report_progress", "b_report_progress", "bReportProgress"), False)
            set_prop_any(tex_params, ("blocking", "b_blocking", "bBlocking"), True)
            call_optional(subsystem, "request_texture_sources", character, tex_params)
            save_asset(ASSET_PATH)
            can_build = describe_character(character, subsystem)
        else:
            warn(f"Skipping texture-source request; optional texture synthesis payload is missing: {texture_synthesis_dir}")

    if can_build:
        log("Building optimized MetaHuman output")
        build_params = unreal.MetaHumanCharacterEditorBuildParameters()
        pipeline_type = enum_member(unreal.MetaHumanDefaultPipelineType, "OPTIMIZED", "Optimized")
        pipeline_quality = enum_member(unreal.MetaHumanQualityLevel, "HIGH", "High")
        set_prop(build_params, "pipeline_type", pipeline_type)
        set_prop(build_params, "pipeline_quality", pipeline_quality)
        set_prop(build_params, "animation_system_name", "AnimBP")
        set_prop(build_params, "absolute_build_path", BUILD_ROOT)
        set_prop(build_params, "common_folder_path", COMMON_ROOT)
        set_prop(build_params, "name_override", BUILD_NAME)
        call_optional(subsystem, "build_meta_human", character, build_params)
        unreal.EditorAssetLibrary.save_directory(BUILD_ROOT, only_if_is_dirty=False, recursive=True)
    else:
        warn("Character is still not buildable after local create/auto-rig/texture requests")

    save_asset(ASSET_PATH)

    assets = unreal.EditorAssetLibrary.list_assets(BUILD_ROOT, recursive=True, include_folder=True)
    log(f"Generated assets under {BUILD_ROOT}: {len(assets)}")
    for path in assets[:100]:
        log(f"Asset: {path}")
    if len(assets) > 100:
        log(f"... {len(assets) - 100} more assets omitted")

    log(f"PLACEHOLDER_CHARACTER={ASSET_PATH}")
    log(f"PLACEHOLDER_BUILD_ROOT={BUILD_ROOT}")
    log("DONE")


try:
    main()
except Exception:
    err(traceback.format_exc())
    raise
