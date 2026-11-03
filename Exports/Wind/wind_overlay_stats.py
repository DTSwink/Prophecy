"""Shader cost of the wind overlay: original masters vs their _Wind duplicates (run after shaders compiled)."""
import os, json
import unreal
MEL = unreal.MaterialEditingLibrary
OUT = os.path.join(unreal.Paths.project_saved_dir(), "WindTest", "overlay_stats.json")
pairs = {
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials/MA_Foliage_Trees": "/Game/Prophecy/Ambient/Wind/Masters/MA_Foliage_Trees_Wind4",
    "/Fab/Materials/Standard/M_MS_Foliage": "/Game/Prophecy/Ambient/Wind/Masters/M_MS_Foliage_Wind4",
    "/Fab/Materials/Standard/M_MS_Billboard": "/Game/Prophecy/Ambient/Wind/Masters/M_MS_Billboard_Wind4",
}
res = {}
for a, b in pairs.items():
    row = {}
    for k, p in (("orig", a), ("wind", b)):
        m = unreal.load_asset(p)
        try:
            s = MEL.get_statistics(m)
            row[k] = {"vs": s.num_vertex_shader_instructions, "ps": s.num_pixel_shader_instructions, "samplers": s.num_samplers,
                      "vs_tex": s.num_vertex_texture_samples, "ps_tex": s.num_pixel_texture_samples, "uv": s.num_uv_scalars, "interp": s.num_interpolator_scalars}
        except Exception as e:
            row[k] = {"err": str(e)}
    res[a.split("/")[-1]] = row
json.dump(res, open(OUT, "w"), indent=1)
unreal.log("WINDSTATS " + json.dumps(res))
