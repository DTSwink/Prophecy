import unreal


material = unreal.load_asset("/Game/Prophecy/MetaHumanPipeline/M_ProphecyPlaceholderHeadSkin")
unreal.log("[ProphecyMaterialProbe] material methods " + str([name for name in dir(material) if "skeletal" in name.lower() or "usage" in name.lower() or "used" in name.lower()]))
unreal.log("[ProphecyMaterialProbe] editing methods " + str([name for name in dir(unreal.MaterialEditingLibrary) if "usage" in name.lower() or "used" in name.lower()]))
unreal.log("[ProphecyMaterialProbe] material usage enum " + str([name for name in dir(unreal) if "MaterialUsage" in name]))
try:
    unreal.log("[ProphecyMaterialProbe] used_with_skeletal_mesh=" + str(material.get_editor_property("used_with_skeletal_mesh")))
except Exception as exc:
    unreal.log("[ProphecyMaterialProbe] used_with_skeletal_mesh failed: " + str(exc))
try:
    unreal.log("[ProphecyMaterialProbe] b_used_with_skeletal_mesh=" + str(material.get_editor_property("b_used_with_skeletal_mesh")))
except Exception as exc:
    unreal.log("[ProphecyMaterialProbe] b_used_with_skeletal_mesh failed: " + str(exc))
