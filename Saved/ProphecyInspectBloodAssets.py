import json
import os
import unreal


ASSETS = [
    "/Game/_mygame/blood2/NS_bloodrender.NS_bloodrender",
    "/Game/_mygame/blood2/NS_bloodsplat.NS_bloodsplat",
    "/Game/_mygame/blood2/NDC_test.NDC_test",
    "/Game/_mygame/blood2/A_DecalManager.A_DecalManager",
    "/Game/_mygame/blood2/A_decaltemp.A_decaltemp",
    "/Game/_mygame/blood2/M_blood_final.M_blood_final",
    "/Game/_mygame/blood2/_PPM_blood._PPM_blood",
]


def safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return "ERROR: {}".format(exc)


def names(items):
    return [str(x) for x in items]


def asset_info(path):
    obj = unreal.load_asset(path)
    info = {
        "path": path,
        "exists": obj is not None,
    }
    if obj is None:
        return info

    info["class"] = obj.get_class().get_name()
    info["name"] = obj.get_name()
    info["outer"] = str(obj.get_outer())
    info["dir_matches"] = sorted([
        name for name in dir(obj)
        if any(token in name.lower() for token in [
            "material", "domain", "blend", "transluc", "depth", "stencil",
            "scene", "texture", "custom", "render", "priority", "user"
        ])
    ])
    known_props = [
        "material_domain",
        "blend_mode",
        "translucency_blend_mode",
        "allow_custom_depth_writes",
        "b_allow_custom_depth_writes",
        "output_translucent_velocity",
        "post_process_blendable_location",
        "blendable_location",
        "blendable_priority",
        "enable_stencil_test",
        "stencil_compare",
        "stencil_ref_value",
        "custom_depth_stencil_value",
        "custom_depth_stencil_write_mask",
        "render_custom_depth",
        "cast_shadow",
        "fixed_bounds",
        "requires_persistent_ids",
    ]
    info["known_properties"] = {}
    for prop_name in known_props:
        try:
            value = obj.get_editor_property(prop_name)
            info["known_properties"][prop_name] = {
                "type": type(value).__name__,
                "value": str(value),
            }
        except Exception as exc:
            info["known_properties"][prop_name] = {
                "error": str(exc)[:300],
            }
    info["properties"] = []
    for prop in safe_call(lambda: obj.get_class().get_properties(), []):
        prop_name = prop.get_name() if hasattr(prop, "get_name") else str(prop)
        prop_class = prop.get_class().get_name() if hasattr(prop, "get_class") else type(prop).__name__
        entry = {"name": prop_name, "class": prop_class}
        try:
            value = obj.get_editor_property(prop_name)
            entry["value_type"] = type(value).__name__
            entry["value"] = str(value)[:500]
        except Exception as exc:
            entry["value_error"] = str(exc)[:300]
        info["properties"].append(entry)

    if obj.get_class().get_name() == "Blueprint":
        bp = obj
        info["generated_class"] = str(safe_call(lambda: bp.generated_class))
        cdo = safe_call(lambda: unreal.get_default_object(bp.generated_class), None)
        if cdo and hasattr(cdo, "get_class"):
            info["cdo_class"] = cdo.get_class().get_name()
            info["cdo_components"] = []
            try:
                comps = cdo.get_components_by_class(unreal.ActorComponent)
            except Exception:
                comps = []
            for comp in comps:
                info["cdo_components"].append({
                    "name": comp.get_name(),
                    "class": comp.get_class().get_name(),
                    "path": comp.get_path_name(),
                })
        else:
            info["cdo_error"] = str(cdo)
        bel = getattr(unreal, "BlueprintEditorLibrary", None)
        if bel:
            info["blueprint_editor_library"] = True
            info["variables"] = names(safe_call(lambda: bel.get_blueprint_variable_list(bp), []))
            info["functions"] = names(safe_call(lambda: bel.get_blueprint_function_list(bp), []))

    return info


def api_probe():
    result = {}
    for name in [
        "BlueprintEditorLibrary",
        "SubobjectDataSubsystem",
        "NiagaraEditorData",
        "NiagaraDataChannel",
        "NiagaraSystem",
        "NiagaraEmitter",
        "NiagaraScript",
        "NiagaraDataInterfaceArrayFloat3",
        "NiagaraDataInterfaceArrayFloat",
        "NiagaraDataInterfaceArrayColor",
        "NiagaraDataChannelAsset",
        "NiagaraDataChannelLibrary",
    ]:
        obj = getattr(unreal, name, None)
        result[name] = sorted([x for x in dir(obj) if not x.startswith("_")])[:200] if obj else None
    return result


payload = {
    "assets": [asset_info(path) for path in ASSETS],
    "api_probe": api_probe(),
}

out_path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "ProphecyInspectBloodAssets.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, sort_keys=True)

print("PROPHECY_BLOOD_ASSET_INSPECTION_BEGIN")
print(json.dumps(payload, indent=2, sort_keys=True))
print("WROTE {}".format(out_path))
print("PROPHECY_BLOOD_ASSET_INSPECTION_END")
