"""Global wind assets + foliage inventory.
 MPC_GlobalWind  : WindOrigin (field origin x, y cm, size cm, time s), WindMean (dir x, y, speed m/s, any gust), Gust0A..5A
                   (front x, y cm, dir x, y), Gust0B..5B (strength m/s x envelope, length m, width m, phase)
 RT_WindField    : 128 x 128 RGBA16f, camera-centred; RG = burst wind (m/s, encoded v/40 + 0.5), B = intensity 0..1
 M_WindFieldGen  : draws the bursts into RT_WindField (only while a burst is alive)
 MF_WindBurst    : what a foliage material adds to its own WPO: bend + canopy waves + leaf flutter from the field
Run in the open editor (Tools/RunUnrealRemote.py Exports/Wind/setup_wind.py); the inventory is read only."""
import os, json
import unreal

DEST = "/Game/Prophecy/Ambient/Wind"
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "WindTest", "setup.json")
AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
MP = unreal.MaterialProperty
rep = {"errors": [], "warnings": []}
NG = 6


def fresh(name, cls, factory, path=DEST):
    """Reuse the asset if it exists (materials already reference it), else create it."""
    full = f"{path}/{name}"
    if EAL.does_asset_exist(full):
        a = unreal.load_asset(full)
        if isinstance(a, cls):
            if isinstance(a, unreal.Material):
                MEL.delete_all_material_expressions(a)
            return a
        EAL.delete_asset(full)
    return AT.create_asset(name, path, cls, factory)


NAMES = ["WindOrigin", "WindMean"] + [f"Gust{i}A" for i in range(NG)] + [f"Gust{i}B" for i in range(NG)] + ["WindOriginPrev", "WindMeanPrev"]


def make_mpc():
    mpc = fresh("MPC_GlobalWind", unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    vecs = list(mpc.get_editor_property("vector_parameters"))		# keep the ids the materials already use
    have = [str(v.get_editor_property("parameter_name")) for v in vecs]
    for n in NAMES:
        if n in have:
            continue
        v = unreal.CollectionVectorParameter()
        v.set_editor_property("parameter_name", n)
        if n.startswith("WindOrigin"): d = unreal.LinearColor(0, 0, 25600, 0)
        elif n.startswith("WindMean"): d = unreal.LinearColor(1, 0, 3, 0)
        else: d = unreal.LinearColor(0, 0, 0, 0)
        v.set_editor_property("default_value", d)
        vecs.append(v)
    mpc.set_editor_property("vector_parameters", vecs)
    return mpc


def make_rt(name="RT_WindField"):
    f = unreal.TextureRenderTargetFactoryNew()
    rt = fresh(name, unreal.TextureRenderTarget2D, f)
    rt.set_editor_property("size_x", 128)
    rt.set_editor_property("size_y", 128)
    rt.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA16F)
    rt.set_editor_property("clear_color", unreal.LinearColor(0.5, 0.5, 0.0, 0.0))
    rt.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    rt.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    return rt


def custom(m, code, out_type, names, x, y, desc):
    c = MEL.create_material_expression(m, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code); c.set_editor_property("output_type", out_type); c.set_editor_property("description", desc)
    ins = []
    for n in names:
        ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
    c.set_editor_property("inputs", ins)
    return c


def mpc_node(m, mpc, name, x, y, func=None):
    e = MEL.create_material_expression_in_function(func, unreal.MaterialExpressionCollectionParameter, x, y) if func else MEL.create_material_expression(m, unreal.MaterialExpressionCollectionParameter, x, y)
    e.set_editor_property("collection", mpc)
    e.set_editor_property("parameter_name", name)
    return e


GEN = r"""
float2 P = Origin.xy + (UV - 0.5) * Origin.z;
float4 A[6] = { A0, A1, A2, A3, A4, A5 };
float4 B[6] = { B0, B1, B2, B3, B4, B5 };
float2 acc = 0; float peak = 0;
for (int i = 0; i < 6; i++)
{
    if (B[i].x <= 0.0001) continue;
    float2 d = A[i].zw; float2 pp = float2(-d.y, d.x);
    float2 rel = (P - A[i].xy) * 0.01;
    float L = B[i].y, W = B[i].z;
    float n = dot(rel, pp);
    float s = dot(rel, d) - 0.15 * n * n / W;           // bowed front
    float al = s > 0 ? exp(-pow(s / (0.15 * L), 2)) : exp(-pow(s / L, 2));   // quick rise, long decay
    float ac = exp(-pow(n / W, 4));                      // broad, flat-topped across the wind
    float v = B[i].x * al * ac;
    acc += v * d;
    peak = max(peak, v);
}
return float3(acc / 40.0 + 0.5, saturate(peak / 12.0));
"""


def make_gen(mpc):
    m = fresh("M_WindFieldGen", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    tc = MEL.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -1400, 0)
    names = ["UV", "Origin"] + [f"A{i}" for i in range(NG)] + [f"B{i}" for i in range(NG)]
    c = custom(m, GEN, unreal.CustomMaterialOutputType.CMOT_FLOAT3, names, -400, 0, "Wind bursts")
    MEL.connect_material_expressions(tc, "", c, "UV")
    MEL.connect_material_expressions(mpc_node(m, mpc, "WindOrigin", -1000, -200), "", c, "Origin")
    for i in range(NG):
        MEL.connect_material_expressions(mpc_node(m, mpc, f"Gust{i}A", -1000, 0 + i * 120), "", c, f"A{i}")
        MEL.connect_material_expressions(mpc_node(m, mpc, f"Gust{i}B", -1000, 760 + i * 120), "", c, f"B{i}")
    MEL.connect_material_property(c, "", MP.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    return m


def make_copy(rt):
    """Copies RT_WindField into RT_WindFieldPrev (drawn just before the new field: last frame's field)."""
    m = fresh("M_WindFieldCopy", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    t = MEL.create_material_expression(m, unreal.MaterialExpressionTextureSample, -500, 0)
    t.set_editor_property("texture", rt)
    try: t.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    except Exception as e: rep["warnings"].append("copy sampler: " + str(e))
    MEL.connect_material_property(t, "RGB", MP.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    return m


BURST = r"""
// Global wind burst on a plant (Docs/Wind.md). Free when calm: one uniform branch, no texture fetch.
struct WindFns
{
    float h(float2 p) { float3 p3 = frac(p.xyx * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return frac((p3.x + p3.y) * p3.z); }
    float vn(float2 p)
    {
        float2 i = floor(p); float2 f = frac(p); float2 u = f * f * (3.0 - 2.0 * f);
        return lerp(lerp(h(i), h(i + float2(1, 0)), u.x), lerp(h(i + float2(0, 1)), h(i + float2(1, 1)), u.x), u.y);
    }
};
WindFns w;
if (Mean.w < 0.5) return float3(0, 0, 0);
float2 uv = (P.xy - Origin.xy) / Origin.z + 0.5;
float edge = saturate(min(min(uv.x, uv.y), min(1.0 - uv.x, 1.0 - uv.y)) * 10.0);
if (edge <= 0.0) return float3(0, 0, 0);
float3 f = Texture2DSampleLevel(Field, FieldSampler, uv, 0).rgb;
if (f.z * edge <= 0.0005) return float3(0, 0, 0);
float2 g = (f.xy - 0.5) * 40.0 * edge;                 // the burst here, smooth (m/s)
float G = length(g);
float2 gd = g / max(G, 0.001);
// gust patches ("cat's paws"): 3 octaves of noise, stretched along the wind, drifting downwind with it
// (amplitude per octave ~k^-1/3, the -5/3 spectrum). Same noise as AGlobalWind::GustPatches (leaves, SFX).
float2 md = Mean.xy; float2 mp = float2(-md.y, md.x);
float Vt = 1.4 * Mean.z + 3.0;
float2 Pm = P.xy * 0.01;
float2 q = Pm - md * (Vt * T);
float2 qa = float2(dot(q, md) * 0.5, dot(q, mp));
float nz = 0.55 * w.vn(qa / 7.0) + 0.30 * w.vn(qa / 3.0 + 17.3) + 0.15 * w.vn(qa / 1.3 + 41.7);
nz = saturate((nz - 0.5) * 1.8 + 0.5);
float Ue = G * lerp(0.3, 1.5, nz);                       // irregular: 0.3x to 1.5x the burst
float va = (w.vn(qa / 9.0 + 5.1) - 0.5) * 0.5;           // the direction wanders +-14 deg
float cs = cos(va), sn = sin(va);
float2 dir = float2(gd.x * cs - gd.y * sn, gd.x * sn + gd.y * cs);
// the plant: a static lean from the drag (~U^2, saturating), bent from the root, plus a smaller sway about that lean
// at its own natural frequency, coherent along the wind (de Langre 2008; Py, de Langre & Moulia 2006)
float H = max(Height, 1.0);
float m = saturate(L.z / H);
float hw = max(H * length(S), 5.0);
float st = saturate(Stiffness);
float U0 = lerp(4.0, 20.0, st);
float lean = 1.0 - exp(-(Ue * Ue) / (U0 * U0));
float thmax = lerp(0.8, 0.06, st);
float ph = 6.2832 * Freq * (T - dot(Pm, md) / Vt) + w.vn(Pm * 0.35 + 9.7) * 3.0;
float th = thmax * lean * (1.0 + 0.25 * (0.4 + 0.6 * nz) * sin(ph));
float x = min(hw * th * m * m, 0.75 * hw * m);
float3 disp = float3(dir * x, -x * x / (2.0 * max(hw * m, 1.0)));
// the crown: outer branches move more than the trunk, each crown patch with its own phase
float rb = saturate(length(L.xy) / max(0.3 * H, 1.0)) * Branch;
float bph = 6.2832 * Freq * 2.6 * T + w.vn(Pm * 0.25 + 3.3) * 6.2832;
float ba = rb * lean * hw * 0.05 * (0.55 + 0.45 * sin(bph));
disp += float3(dir * ba + mp * (ba * 0.35 * sin(bph * 1.37 + 1.0)), ba * 0.25 * sin(bph + 2.0));
// leaves: fast flutter (~6 Hz), phase varying smoothly over the crown so each cluster has its own rhythm
float fph = w.vn(Pm * 3.0 + P.z * 0.02) * 25.0;
float fl = Flutter * saturate(Ue / 7.0) * m * sin(37.7 * T + fph);
return disp + N * fl;
"""


def make_mf(mpc, rt, rt_prev):
    path = f"{DEST}/MF_WindBurst"
    mf = unreal.load_asset(path) if EAL.does_asset_exist(path) else None
    if mf:
        MEL.delete_all_material_expressions_in_function(mf)
    else:
        mf = AT.create_asset("MF_WindBurst", DEST, unreal.MaterialFunction, unreal.MaterialFunctionFactoryNew())
    mf.set_editor_property("description", "Global wind bursts: add the output to the material's own World Position Offset. Height = plant height in its local units (cm; the bend grows from the pivot to that height, scaled by the instance), Stiffness 0 (grass) .. 1 (trunk), Flutter = leaf shimmer in a burst (cm), Branch 0..1 = crown motion (trees), Freq = natural sway frequency (Hz: grass 1-3, trees 0.2-0.5).")
    mf.set_editor_property("expose_to_library", True)
    def inp(name, x, y, default, prio):
        e = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionFunctionInput, x, y)
        e.set_editor_property("input_name", name)
        e.set_editor_property("input_type", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR)
        e.set_editor_property("use_preview_value_as_default", True)
        try:
            pv = e.get_editor_property("preview_value")		# Vector4f: no constructor arguments in Python
            pv.x = float(default)
            e.set_editor_property("preview_value", pv)
        except Exception as ex:
            rep["warnings"].append("preview %s: %s" % (name, ex))
        e.set_editor_property("sort_priority", prio)
        return e
    height = inp("Height", -1200, 150, 100.0, 0)
    stiff = inp("Stiffness", -1200, 300, 0.5, 1)
    flut = inp("Flutter", -1200, 450, 0.0, 2)
    branch = inp("Branch", -1200, 525, 0.0, 3)
    freq = inp("Freq", -1200, 560, 1.0, 4)
    tm = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionTime, -1200, -750)
    wp = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionWorldPosition, -1200, -300)
    lp = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionLocalPosition, -1200, -450)
    up = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionConstant3Vector, -1500, -600)
    up.set_editor_property("constant", unreal.LinearColor(0, 0, 1, 0))
    tr = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionTransform, -1200, -600)
    tr.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    tr.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    MEL.connect_material_expressions(up, "", tr, "")
    nrm = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionVertexNormalWS, -1200, 600)
    tex = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionTextureObject, -1200, 750)
    tex.set_editor_property("texture", rt)
    try: tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    except Exception as e: rep["warnings"].append("sampler: " + str(e))
    texp = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionTextureObject, -1200, 900)
    texp.set_editor_property("texture", rt_prev)
    try: texp.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    except Exception as e: rep["warnings"].append("sampler prev: " + str(e))
    def burst(y, field, origin, mean, desc):
        c = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionCustom, -500, y)
        c.set_editor_property("code", BURST); c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        c.set_editor_property("description", desc)
        ins = []
        for n in ["P", "L", "S", "N", "T", "Field", "Origin", "Mean", "Height", "Stiffness", "Flutter", "Branch", "Freq"]:
            ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
        c.set_editor_property("inputs", ins)
        for e, n in ((wp, "P"), (lp, "L"), (tr, "S"), (nrm, "N"), (tm, "T"), (field, "Field"), (height, "Height"), (stiff, "Stiffness"), (flut, "Flutter"), (branch, "Branch"), (freq, "Freq")):
            MEL.connect_material_expressions(e, "", c, n)
        MEL.connect_material_expressions(mpc_node(None, mpc, origin, -900, y - 150, mf), "", c, "Origin")
        MEL.connect_material_expressions(mpc_node(None, mpc, mean, -900, y - 50, mf), "", c, "Mean")
        return c
    cur = burst(0, tex, "WindOrigin", "WindMean", "Wind burst WPO")
    prv = burst(500, texp, "WindOriginPrev", "WindMeanPrev", "Wind burst WPO, previous frame (motion vectors)")
    sw = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionPreviousFrameSwitch, -200, 200)
    rep["switch_cur"] = next((n for n in ("CurrentFrame", "Current Frame", "") if MEL.connect_material_expressions(cur, "", sw, n)), None)
    rep["switch_prev"] = next((n for n in ("PreviousFrame", "Previous Frame") if MEL.connect_material_expressions(prv, "", sw, n)), None)
    c = sw if (rep["switch_cur"] is not None and rep["switch_prev"]) else cur		# no switch: current frame only
    o = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionFunctionOutput, -100, 0)
    o.set_editor_property("output_name", "WPO")
    MEL.connect_material_expressions(c, "", o, "")
    MEL.update_material_function(mf)
    return mf


def inventory():
    """Which master materials the forest's foliage uses (read only)."""
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    opt = unreal.AssetRegistryDependencyOptions(True, True, True, True, True)
    meshes = set()
    for g in ["/Game/_mygame/pcg/PCG_Forest", "/Game/_mygame/assets/textures/forest_ground/PCG_SplineGrass"]:
        for p in ar.get_dependencies(g, opt) or []:
            a = unreal.load_asset(str(p))
            if isinstance(a, unreal.StaticMesh): meshes.add(str(p))
    masters = {}
    out = {}
    for mp in sorted(meshes):
        sm = unreal.load_asset(mp)
        b = sm.get_bounding_box()
        rec = {"h": round(b.max.z - b.min.z), "mats": []}
        try: rec["nanite"] = bool(sm.get_editor_property("nanite_settings").enabled)
        except Exception: pass
        for s in sm.static_materials:
            mi = s.material_interface
            if not mi: continue
            chain = [mi.get_path_name()]
            base = mi
            while isinstance(base, unreal.MaterialInstance) and base.get_editor_property("parent"):
                base = base.get_editor_property("parent"); chain.append(base.get_path_name())
            rec["mats"].append(chain)
            root = chain[-1]
            if root not in masters and isinstance(base, unreal.Material):
                d = {}
                for prop in ("use_material_attributes", "two_sided", "blend_mode", "shading_model", "used_with_nanite", "always_evaluate_world_position_offset", "max_world_position_offset_displacement"):
                    try: d[prop] = str(base.get_editor_property(prop))
                    except Exception as e: d[prop] = "?"
                for prop, key in ((MP.MP_WORLD_POSITION_OFFSET, "wpo"), (MP.MP_MATERIAL_ATTRIBUTES, "attributes")):
                    try:
                        n = MEL.get_material_property_input_node(base, prop)
                        d[key] = n.get_class().get_name() if n else None
                    except Exception as e: d[key] = "ERR " + str(e)
                d["users"] = []
                masters[root] = d
            if root in masters: masters[root]["users"].append(chain[0])
        out[mp] = rec
    return {"meshes": out, "masters": masters}


try:
    mpc = make_mpc()
    rt = make_rt()
    rt_prev = make_rt("RT_WindFieldPrev")
    make_gen(mpc)
    make_copy(rt)
    make_mf(mpc, rt, rt_prev)
    rep["saved"] = bool(EAL.save_directory(DEST, only_if_is_dirty=False, recursive=True))
    rep["assets"] = [str(p) for p in EAL.list_assets(DEST, recursive=True)]
except Exception:
    import traceback
    rep["errors"].append(traceback.format_exc())
if os.environ.get("WIND_INVENTORY", "0") == "1" or not os.path.exists(REPORT):
  try:
    rep["inventory"] = inventory()
  except Exception:
    import traceback
    rep["errors"].append("inventory: " + traceback.format_exc())
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w", encoding="utf-8") as f: json.dump(rep, f, indent=1)
unreal.log("WINDSETUP errors=%d" % len(rep["errors"]))
if "-WindSetupQuit" in unreal.SystemLibrary.get_command_line():
    unreal.SystemLibrary.quit_editor()
