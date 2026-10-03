import unreal

report_path = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BenchLogs\InspectTreeMaterialSlots.report.txt"
lines = []

assets = [
    "/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_01.PCG_Tree_01",
    "/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_02.PCG_Tree_02",
    "/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_03.PCG_Tree_03",
    "/PCG/SampleContent/SimpleForest/Materials/PCG_Trunk_01.PCG_Trunk_01",
    "/PCG/SampleContent/SimpleForest/Materials/PCG_Foliage_01.PCG_Foliage_01",
    "/PCG/SampleContent/SimpleForest/Materials/PCG_Foliage_01_Inst.PCG_Foliage_01_Inst",
    "/PCG/SampleContent/SimpleForest/Materials/PCG_Foliage_01_Inst_wpo.PCG_Foliage_01_Inst_wpo",
]

for path in assets:
    asset = unreal.load_asset(path)
    lines.append(f"ASSET {path} => {asset}")
    if isinstance(asset, unreal.StaticMesh):
        for index, material in enumerate(asset.static_materials):
            material_path = material.material_interface.get_path_name() if material.material_interface else "None"
            lines.append(f"  SLOT {index} name={material.material_slot_name} material={material_path}")
    if isinstance(asset, unreal.Material):
        lines.append(f"  MATERIAL blend={asset.get_editor_property('blend_mode')} two_sided={asset.get_editor_property('two_sided')} shading={asset.get_editor_property('shading_model')}")
    if isinstance(asset, unreal.MaterialInstanceConstant):
        parent = asset.get_editor_property("parent")
        lines.append(f"  MATERIAL_INSTANCE parent={parent.get_path_name() if parent else 'None'}")

with open(report_path, "w", encoding="utf-8") as report:
    report.write("\n".join(lines))
