# Imperial spear — current handoff

**October28 — reviewed selective topology reduction.**
Current editable asset: `Exports/ImperialSpear/ImperialSpear_Optimized.blend`.
Current game FBX: `Exports/ImperialSpear/SM_ImperialSpear.fbx`.
59,460 → 43,494 triangles (26.85% fewer),22,559 source/control vertices.
Guard7,312→3,290; crown3,692→1,660; S reliefs1,606→1,204 each;
pommel body16,640→9,152; bud7,776→6,608. Conservative bead/keeper reductions.
Unchanged steel, wood shaft, leather sleeve and tassel strands; original four
atlas PNGs and shared PBR material retained. Grip/blade manual transforms retained.
Sampled bidirectional surface deviation remains below0.04mm; stronger trials
were rejected. UV, manifold, degenerate geometry/UV and outward-normal checks pass.
Identical48-sample head/pommel PBR views retain bevel highlights and dark veins.
Source normals are carried through reduction as corner attributes; the rejected
nearest-normal-transfer candidate is not delivered. All17 existing corrected UCX
hulls and4 sockets remain exact in FBX; source inspection hulls now match them.
SDK readback is exact; independent Blender readback checks130,482 corners in
both directions, UV/color error0, max position error0.000014mm, min normal dot
0.99999983. Current evidence: `Exports/ImperialSpear/Optimization_Report.json`.
Your original `PommelLotus/Working.blend` and open Blender session were not changed.
Recovery: `Saved/Diagnostics/ImperialSpear/Optimization20261028/Before_UserFinal.blend`
and `Before_UserFinal.fbx`. Open the new Optimized.blend to inspect reduced topology.
Older Source/Game blends, GLB, LOD FBXs and Asset/Export reports below are historical
and were not refreshed by this pass. Unreal remains untouched. Subsequent user-
requested Throw Lab refresh now imports this optimized mainFBX (22,559 vertices/
43,494 triangles), preserving the lab grip/scale and authored collision; see
[Throw Lab handoff](../Labs/ThrowLab/README.md).
This block supersedes the previous current-source and polygon-count claims below.

**October28 Throw Lab grip mismatch correction:** Current saved `Working.blend`
SHA25677218d933d1dc010e9482caccdf423e2f9d69a60c506cb096803c8f834e94b73
contains later transforms: leather and two gold keepers move-0.17637485m on Z;
blade scales X0.97923148/Z1.03221095 and translates Z-0.04963303m. Other source
geometry matches the prior main FBX. The main FBX and Throw Lab cache now include
these saved transforms. Grip centre is source Z1.05862513m, blade tip2.221231m,
overall length2.252231m. The pivot is recentered on the new leather grip; affected
shaft/grip/blade collision hulls and sockets follow, with blade normals transformed.
Topology, UVs/colors and protected geometry are retained. Counts remain30,542
vertices/59,460 triangles/17 hulls. Main FBX SHA256:
`adebec94c106705a6db9b6628a54e8403734f145b507cfc521b12dc25e533668`.
Readback/source-to-lab error0.0001404mm; Jolt/contact/aim checks and isolated viewer
pass. Live Blender source/scene and Throw Lab saved presets remain unchanged.
Backups and exact audit: `Saved/ThrowLab/SpearGripSync20261028/`; guarded candidate
builder: `Tools/SpearAsset/sync_grip_translation.py`. This is main FBX/lab only;
GLB, LODs and older reports below still require a coordinated full refresh.
`export_spear.py` and collision specs contain historical grip1.235/blade2.2
constants: reconcile them with these saved transforms before rerunning that full
export. Do not silently revert the moved grip or changed blade to older notes.

**Current selection, October28:** User accepted the appearance in screenshot
`codex-clipboard-c4f1748f-05b9-4eb6-9af4-0cc2d9a5077e.png` and requested views.
Freeze that exact live version: body65 axial rows/3.2mm crest, budV5, localized
darker grooves with the corrected Color.R presence gate. Authoritative saved
source is `Saved/Diagnostics/ImperialSpear/PommelLotus/Selected_Pommel_Preview.blend`;
`Working.blend` matches. `Gold_reference.png` and `Gold_oblique.png` there show it.
The later crown/outline proposal was NOT applied and must not be replayed.
Export refresh stopped at LOD1 color interpolation overshoot; the current export
folder contains partial newer outputs and is not a verified final package.
Finish export/LOD color handling and readback before using it in Unreal.

**Previous delivery notes below are historical until that export refresh:**

The previous flattened-leaf pommel model was rejected. The user selected
concept04, **Lotus bud**, and requested a fresh planned rebuild with defined
carved geometry. The user then clarified that the MAIN BODY has a four-peaked
flower cross-section. Current source implements that full radial form. Its appearance has
not yet been accepted by the user. Do not restore the rejected leaf as approved.

Current source: `Exports/ImperialSpear/ImperialSpear_Source.blend`.
Current working copy: `Saved/Diagnostics/ImperialSpear/PommelLotus/Working.blend`;
also saved to `Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend`.
Reference: `Design/ImperialSpear/PommelConcepts/04_LotusBud_Selected.png`.
Written plan: `Tools/SpearAsset/lotus_plan.md`.

## Current pommel

Four closed meshes: four-lobed carved body, rolled socket/barrel, stepped lotus
seat and six-petal bud. The main body has four radial longitudinal ribs around
four broad Bezier concave scoops, with comparable width and depth. Belly axis
diameter49.00mm; diagonal valley radius12.973mm. The scoop sits
4.351mm below the straight chord joining adjacent rib peaks. Each crest is
1.20mm wide, with0.65mm chamfer depth. The full radial section transitions
into circular necks beneath the fittings; cap fans avoid needle UV tessellation.
Each of the four scoops contains a closed secondary leaf-shaped recess with
0.55mm inset depth and an integral stepped border. Its flat lip rises
0.10mm; the leaf tips close at source z0.018/0.101m. These are connected
surface features. The lower seat has a straight land and stepped separator.
The body alone uses8,192 triangles.
Lotus bud V3 has six recessed arched petals with0.405mm flat lip lands at
the belly and0.55mm inner bevel drops. The seated root shoulder drops
0.35mm radially. A0.35mm axial/0.40mm radial throat bevel leads into
the5.70mm rounded terminal button. The bud uses3,600 triangles in one closed shell.
Pommel triangle count14,984; no live subdivision/Boolean modifier.

The bud extends to source z−0.031m. Overall length2.231m; shaft/head/grip
remain fixed, source grip1.235m, actual grip-to-bud distance1.266m. Pommel
socket and metadata follow the new tip. The other70 source meshes retain exact
geometry, UVs, custom normals, material assignments and transforms. All original
atlas bytes remain unchanged. At the user's explicit request, the pommel uses
the same `M_ImperialSpear_PBR` material and existing plain gold atlas region
as the spearhead. The full asset has one shared material slot. Candidate
generated gold maps are abandoned diagnostics and are not part of the delivery.

## Current finish and geometry

The current wood finish uses coherent curved fibres, split/rejoin grain, broken tapered runs,
pores, shallow checks and dents. Physical height drives the normal detail with
restrained correlated albedo. Measured average roughness 0.527 and
specular 0.465 come from `wood_v8/Wood_Patch_Report.json`, selected
by `Handle_Texture_Application.json`; unapplied candidates are not authoritative.
Normal gradients use a 2.97702x relief gain; this strengthens shading without changing shaft geometry.
The shaft has 4 axial UV strips with
8px gutters inside the same wood tile. Measured density is
5.18px/mm axially and 4.94–5.65px/mm
circumferentially, avoiding the old single strip's stretched axial detail.
The 3 interpolated seam rings add 96 vertices and 192 triangles;
all original shaft vertices remain unchanged. `Wood_UV_Repack_Verification.json`
records the interpolation, shading and seam checks. No other protected
component is changed by the shaft repack.

Current leather revision: `V5: crisp incised lozenges and sparse rubbed leather wear; gold preserved byte-for-byte`.
It is a taut matte sleeve with irregular 0.75mm pebbled grain,
0.055–0.085mm grain relief, fine pits and angular scored lozenges
with compact crossing loops. Scoring is 0.300mm; mean roughness
0.860, specular 0.180. Sparse broad rubbed patches reduce
grain height locally; clean worn lips and restrained dark wear marks distinguish
the incisions. Large unrelated cloudy color variations are suppressed.
Puffy helical strips were removed. The sleeve retains
z1.115–1.355m and the grip pivot1.235m. Gold keepers retain axial bounds
1.102–1.122 and1.348–1.368m, with straight barrels and integral lips replacing
separate round wires. Fine chasing, hairlines and restrained border patina
live in a dedicated keeper tile, so no shared head-gold finish changed.

Atlas split: wood [0,2048,2048,4096] subdivided into 4 axial-strip columns;
leather [2048,2048,3072,3808]; keeper gold [2048,3808,3072,4096], Pillow top-origin
pixel boxes. Wood strips have 8px gutters; the grip tiles have12px gutters.
ORM remains RGBA=AO/Roughness/Metallic/Specular, CHANNEL_PACKED;
source opacity stays1. NormalGL for Blender/glTF; NormalDX for Unreal.

The S relief now has a32%-width flat crest and broad inclined facets, retaining
the original traced bounds. Each S is805 vertices/1606 triangles. Constrained
triangulation removed three inherited folded quads per side; the largest local
curl-boundary correction is0.118mm, with0.0015mm² overlap cleaned. Both meshes
are closed, positive-volume and have no folded/degenerate visible triangles.
Other guard/crown/rings/blade/recess/beads remain unchanged. Never rerun the
housing reseating script against the new S topology without adapting it.

## Delivery and verification

Current source/game blend, FBX, GLB and LOD FBXs are refreshed. Triangle counts
46,836/25,758/13,114; UV0 surface, UV1 lightmap, one material.17 convex
UCX hulls with max60vertices; three fit the pommel and the other shapes are unchanged.
Four sockets, posed cosmetic tassel without rigid collision or cloth.
Current views: `Preview_Pommel.png`, `Preview_Pommel_Detail.png`,
`Preview_Pommel_Front.png`, `Preview_Pommel_Diagonal.png`, `Preview_Pommel_End.png`,
`Preview_Full.png`. The end-on view isolates the body to expose its four-peaked
cross-section. [End-on body inspection](../Exports/ImperialSpear/Preview_Pommel_End.png)
and [diagonal view](../Exports/ImperialSpear/Preview_Pommel_Diagonal.png).
Head/handle previews remain valid.

`Pommel_Lotus_Verification.json` is the current source audit;
`Pommel_Lotus_Preflight.json` checks UV areas, shading directions and the join.
`Export_Verification.json` checks main and LOD FBX positions, UV0, custom normals
and material identity, hulls, sockets and measured extent. Original atlas hashes
and all70 protected mesh fingerprints pass. Actual hull face planes enclose
the new pommel. Dense sampled wood-joint containment passes; see report for
the parity/winding method. Unreal import/cooking/materials/physics/CCD remain
untested. No Unreal/Play/Blueprint/lab state changed.

## Resume safely

Read the current source instead of replaying historical geometry scripts.
Current tools: `model_pommel_lotus.py`, `four_lobe_pommel_body.py`, `lotus_bud_component.py`,
`preflight_lotus_source.py`,
`export_spear.py`, `audit_pommel_lotus.py`, `verify_exports.py`,
`finish_pommel_lotus.py`, `write_lotus_handoff.py`.
Older leaf/handle finish and handoff writers would overwrite current metadata.
`make_lotus_gold.py` and `apply_lotus_gold.py` are abandoned candidate workflows;
do not apply them to the current shared-material delivery. Diagnostic candidate
sources remain under `Saved/Diagnostics/ImperialSpear/PommelLotus/Gold/`.
Pre-lotus rejected-state recovery is in `PommelLotus/Before/`; original accepted
non-pommel fingerprints remain in `PommelLeaf/Baseline_Source_Components.json`.
Use the upstream Blender MCP bridge via `mcp_client.py` and `start_bridge.py`.
Check port9876/process before starting; PID files may be stale after closure.
Run one bounded call at a time,3 CPU threads, BelowNormal hidden owned process.
Temporary studio lighting is removed after previews; the accepted camera stays.
