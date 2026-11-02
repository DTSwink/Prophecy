"""Measured concept04 handoff; preserve unrelated journal work."""
import json,hashlib,re,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2];O=R/'Exports/ImperialSpear';W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
a=json.loads((O/'Asset_Report.json').read_text());v=json.loads((O/'Export_Verification.json').read_text());p=json.loads((O/'Pommel_Lotus_Verification.json').read_text())
g=json.loads((W/'Geometry_Report.json').read_text());body=g['body_design']
bud=next(c['design_report'] for c in g['components'] if c['name']=='Pommel • six carved lotus petals')
cavity=json.loads((W/'Cavity_Material_Report.json').read_text())
protected_render=json.loads((W/'RefinementV4/Protected_Surface_Render_Check.json').read_text())
assert p['status']=='LOTUS_POMMEL_SOURCE_AND_ACTUAL_GAME_COLLISION_AUDITED'
assert a['render_triangles']==v['triangles']==p['source_game_comparison']['source_triangles']
assert body['main_body_lobes']==4 and body['full_three_dimensional_section']
assert body['secondary_carved_panels']==4 and body['secondary_border_integral_geometry']
assert bud['design'].startswith('Lotus bud V5:')
assert body['localized_cavity_mask'] and cavity['attribute']=='PommelCavity'
assert cavity['material']==g['material']=='M_ImperialSpear_PBR'
assert not cavity['original_textures_changed'] and not cavity['protected_source_color_layers_modified']
assert not cavity['roughness_metallic_normal_specular_changed']
assert cavity['source_presence_gate'].startswith('Color.R > 0.01;')
assert protected_render['status']=='PASS' and protected_render['maximum_channel_difference']<.001 and protected_render['mean_channel_difference']<1e-5
assert v['cavity_vertex_color']['enabled'] and v['cavity_vertex_color']['fbx_color_space']=='LINEAR'
assert v['glb_cavity']['standard_vertex_color_multiply_count']==1
shade_min=min(row['minimum_shade'] for row in cavity['components']);shade_max=max(row['maximum_shade'] for row in cavity['components'])
assert g['triangles']==p['source_game_comparison']['pommel_triangles']
tri=a['render_triangles'];lods=[r['triangles'] for r in a['lods']];hulls=a['collision_hull_count'];length=a['overall_length_m'];grip=a['grip_from_pommel_m']
assert hulls==17 and a['material_slots']==1 and v['material_slots']==1
for src,dst in [('Gold_oblique.png','Preview_Pommel.png'),('Gold_detail.png','Preview_Pommel_Detail.png'),('Gold_front.png','Preview_Pommel_Front.png'),
                ('Gold_end.png','Preview_Pommel_End.png'),('Gold_diagonal.png','Preview_Pommel_Diagonal.png'),
                ('Gold_reference.png','Preview_Pommel_Reference.png')]:
    assert (W/src).is_file(),src;shutil.copy2(W/src,O/dst)
for src,dst in [('Geometry_Report.json','Pommel_Lotus_Geometry.json'),('Source_Preflight.json','Pommel_Lotus_Preflight.json'),
                ('Cavity_Material_Report.json','Cavity_Material_Report.json'),
                ('RefinementV4/Protected_Surface_Render_Check.json','Protected_Surface_Render_Check.json')]:
    shutil.copy2(W/src,O/dst)
status={'status':'FOUR_LOBE_LOTUS_BUD_V5_REVIEW_BUILD','authoritative_scene':'ImperialSpear_Source.blend',
 'selected_concept':'04 — Lotus bud','previous_flattened_leaf_model_rejected':True,'pommel_model_user_acceptance_recorded':False,
 'protected_other_components':70,'protected_geometry_uv_normals_material_assignments_transforms_unchanged':True,
 'original_four_atlas_files_unchanged':True,'pommel_material':'M_ImperialSpear_PBR','same_gold_material_as_spearhead':True,
 'pommel_uses_existing_plain_gold_atlas':True,'material_slots':1,'render_triangles':tri,'lod_triangles':lods,'pommel_triangles':p['source_game_comparison']['pommel_triangles'],
 'body_cross_section':'four-peaked flower','body_design':body,'bud_design':bud,
 'cavity_material_report':'Cavity_Material_Report.json','cavity_vertex_color':cavity,
 'protected_head_shader_render_check':'Protected_Surface_Render_Check.json','protected_head_shader_render_result':protected_render,
 'unreal_base_color_connection':'BaseColor texture RGB * VertexColor RGB; preserve original other material inputs',
 'overall_length_m':length,'grip_from_bud_tip_m':grip,'bud_extension_below_old_cap_m':-p['source_game_comparison']['source_bottom_z_m'],
 'collision_hulls':hulls,'maximum_hull_vertices':p['maximum_hull_vertices'],'pommel_collision_hulls':3,
 'source_audit':'Pommel_Lotus_Verification.json','export_audit':'Export_Verification.json','source_preflight':'Pommel_Lotus_Preflight.json',
 'detail_views':['Preview_Pommel.png','Preview_Pommel_Detail.png','Preview_Pommel_Front.png','Preview_Pommel_Diagonal.png','Preview_Pommel_End.png','Preview_Pommel_Reference.png','Preview_Full.png'],
 'body_cross_section_view':'Preview_Pommel_End.png','diagonal_view':'Preview_Pommel_Diagonal.png',
 'reference_angle_view':'Preview_Pommel_Reference.png',
 'unreal_import_validated':False,'unreal_collision_cooking_validated':False,'unreal_physics_validated':False,
 'scope':'Rebuilt pommel only; other spear surfaces preserved. New bud extends31mm below prior end. No Unreal/lab changes.'}
(O/'DELIVERY_STATUS.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')

readme=f'''IMPERIAL SPEAR — concept04 Lotus bud V5 rebuild, October 28, 2026

CURRENT CHANGE
The user selected Lotus bud and clarified that the MAIN BODY must have a
four-peaked flower cross-section. After rejecting V3, the user requested
stronger carved forms and darker interiors. V5 refines curvature sampling and
carved-wall toes while retaining the fuller form. It awaits user review.
The body now has four radial longitudinal ribs and four broad Bezier concave
scoops. Width and depth are comparable. At the belly its axis diameter is
{2*body['belly_axis_radius_mm']:.2f}mm, diagonal valley radius{body['belly_diagonal_radius_mm']:.3f}mm and scoop depth
below the straight chord joining adjacent peaks is{body['belly_scoop_below_peak_chord_mm']:.3f}mm.
Rib crests are{body['crest_width_mm']:.2f}mm wide with{body['ridge_chamfer_depth_mm']:.2f}mm chamfer depth; the sculpted section
transitions into circular necks beneath the fittings. Each scoop contains a
closed leaf-shaped inset, recessed{body['secondary_recess_depth_mm']:.2f}mm, with an integral stepped border and
{body['secondary_lip_height_mm']:.2f}mm flat raised lip. Its tips close at source z{body['secondary_panel_tips_z_m'][0]*1000:.1f}/{body['secondary_panel_tips_z_m'][1]*1000:.1f}mm.
The primary shadow channels are{body['primary_shadow_channel_depth_mm']:.2f}mm deep; the panel relief fades over
{body['panel_relief_tip_fade_mm']:.2f}mm at each tip. The lower seat has a straight land and stepped separator.
The body uses{body['curvature_sampled_axial_rows']} axial rows and analytic axial shading normals to refine curvature.
Lotus bud V5 has a fuller{bud['maximum_radius_m']*1000:.2f}mm maximum radius and six sculpted petal overlaps,
{bud['lip_land_mid_belly_width_mm']:.3f}mm flat lip lands and{bud['inner_bevel_drop_mm']:.2f}mm inner bevel steps. The outer gutters sit
{bud['outer_gutter_depth_below_background_mm']:.2f}mm below the background; a seated root and beveled throat meet the rounded button.
Its{bud['axial_body_rings']} axial rows and{bud['transverse_lanes_per_petal']} transverse lanes per petal smooth the bulb and carved fields;
inner bevel toes have{bud['inner_bevel_toe_fillet_half_width_mm']:.3f}mm half-width fillets.
Four closed pommel components use
{p['source_game_comparison']['pommel_triangles']:,} triangles without live subdivisions or Booleans.
The other70 components retain exact geometry, UVs, custom normals, material
assignments and transforms. All original four atlas PNGs are byte-identical.
The pommel uses the same M_ImperialSpear_PBR material and existing plain gold
atlas region as the spearhead. Its authored PommelCavity linear grayscale
vertex colors multiply Base Color by{shade_min:.2f} in the deepest veins through{shade_max:.2f} outside.
The only shader addition is a presence-gated multiply: Color.R >0.01 enables
it, while missing source attributes return R0 and bypass it. Alpha is not used
as a presence signal. Roughness, metallic, specular and normal connections remain
original. Protected source color layers are untouched; unmasked export copies
receive neutral white colors.

FILES
ImperialSpear_Source.blend: editable components; accepted head camera retained.
ImperialSpear_Game.blend: combined mesh, simple collision and two LODs.
SM_ImperialSpear.fbx: render mesh,17 UCX hulls,4 sockets.
SM_ImperialSpear.glb: shared-material PBR preview; collision is in FBX.
SM_ImperialSpear_LOD1.fbx / LOD2.fbx: aligned distance meshes.
Preview_Pommel.png / Preview_Pommel_Detail.png / Preview_Pommel_Front.png:
current oblique, macro and front views. Preview_Full.png is refreshed.
Preview_Pommel_Diagonal.png: diagonal view of the three-dimensional body.
Preview_Pommel_End.png: isolated body end-on inspection of the four-peaked section.
Preview_Pommel_Reference.png: render from the reference comparison angle.
Cavity_Material_Report.json: authored cavity encoding and original-input preservation.
Protected_Surface_Render_Check.json: fixed-seed accepted-head render comparison.

SPECIFICATION
Overall length{length*100:.2f}cm; the bud extends3.1cm below the old cap. The shaft,
blade and grip did not move. +Z toward blade; grip pivot is{grip*100:.2f}cm from
the new bud tip. Leather source span111.5–135.5cm is unchanged.
LOD triangles {tri:,}/{lods[0]:,}/{lods[1]:,}. One material. UV0 surface / UV1 lightmap.
17 convex collision hulls, max{p['maximum_hull_vertices']} vertices each. Three fitted pommel hulls;
all other collision shapes preserved. Tassel/cord/beads excluded, no cloth rig.
Sockets: Grip, BladeTip, Pommel (actual new tip), Tassel.

UNREAL MATERIALS AND IMPORT
Import at scale1, retain grip pivot, import normals/tangents and verify length.
Use supplied UCX simple collision. Import LOD FBXs separately and tune distances.
The single M_ImperialSpear_PBR slot uses original4096px maps under Textures/.
It is opaque. Enable Two Sided for the thin tassel ribbons.
Import vertex colors from the supplied mesh (replace existing colors on reimport).
BaseColor sRGB ON -> Multiply with VertexColor RGB -> Base Color. Vertex colors
are linear grayscale; use the multiplier once. Alpha is1 on exported vertices.
ORM sRGB OFF with alpha
retained: R=AO, G=Roughness, B=Metallic, A=Specular. Alpha is not opacity.
NormalDX uses Normalmap compression, sRGB OFF -> Normal; do not flip green again.
NormalGL is for Blender/glTF. FBX wiring does not replace manual UE connections.
The large pommel carvings are geometry. Shared gold retains the original atlas
and surface inputs, with localized Base Color darkening inside carved veins.
GLB uses the unchanged BaseColor image and standard COLOR_0 multiplication once.

VERIFICATION
Pommel_Lotus_Verification.json is current. Closed surfaces, positive volume,
valid UVs/normals, protected source hashes and actual UCX containment pass.
The dense wood-join surface check passes; it is sampled, not a continuous proof.
The accepted-head camera was rendered with cavity shading enabled and bypassed:
maximum channel difference{protected_render['maximum_channel_difference']:.8f}, mean{protected_render['mean_channel_difference']:.8f}
over{protected_render['pixels']:,} pixels. This check validates that camera's visible surfaces;
the70 protected meshes are separately checked by source fingerprints.
Main/LOD FBX readback verifies positions, actual UV0, custom normals, cavity
colors and material assignments, plus all hulls/sockets and scale. GLB COLOR_0
and the unchanged BaseColor image are checked. Export_Verification.json is current.
Prior leaf/handle audits describe historical stages; the leaf result was rejected.
Unreal import, collision cooking, material appearance, contacts and CCD remain
untested. No Unreal/Play/Blueprint/lab state changed. Modeled result awaits review.

Plan: ../../Tools/SpearAsset/lotus_plan.md. Handoff: ../../Docs/ImperialSpear.md.
Pre-lotus recovery: ../../Saved/Diagnostics/ImperialSpear/PommelLotus/Before/.
Blender MCP used a hidden BelowNormal task-owned process,3 CPU render threads
and sequential bounded stills; the process was closed after final save.
'''
(O/'README.txt').write_text(readme,encoding='utf-8')
dp=R/'Docs/ImperialSpear.md';old=dp.read_text(encoding='utf-8');shutil.copy2(dp,W/'Before/ImperialSpear.md')
preserved=old[old.index('## Current finish and geometry'):old.index('## Delivery and verification')]
doc=f'''# Imperial spear — current handoff

The previous flattened-leaf pommel model was rejected. The user selected
concept04, **Lotus bud**, and requested a fresh planned rebuild with defined
carved geometry. The user then clarified that the MAIN BODY has a four-peaked
flower cross-section. Current source implements that full radial form. Its appearance has
not yet been accepted by the user. V3 was rejected; the stronger form and darker
carved interiors now have V5 curvature and fillet refinements. Do not restore a
rejected stage as approved.

Current source: `Exports/ImperialSpear/ImperialSpear_Source.blend`.
Current working copy: `Saved/Diagnostics/ImperialSpear/PommelLotus/Working.blend`;
also saved to `Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend`.
Reference: `Design/ImperialSpear/PommelConcepts/04_LotusBud_Selected.png`.
Written plan: `Tools/SpearAsset/lotus_plan.md`.

## Current pommel

Four closed meshes: four-lobed carved body, rolled socket/barrel, stepped lotus
seat and six-petal bud. The main body has four radial longitudinal ribs around
four broad Bezier concave scoops, with comparable width and depth. Belly axis
diameter{2*body['belly_axis_radius_mm']:.2f}mm; diagonal valley radius{body['belly_diagonal_radius_mm']:.3f}mm. The scoop sits
{body['belly_scoop_below_peak_chord_mm']:.3f}mm below the straight chord joining adjacent rib peaks. Each crest is
{body['crest_width_mm']:.2f}mm wide, with{body['ridge_chamfer_depth_mm']:.2f}mm chamfer depth. The full radial section transitions
into circular necks beneath the fittings; cap fans avoid needle UV tessellation.
Each of the four scoops contains a closed secondary leaf-shaped recess with
{body['secondary_recess_depth_mm']:.2f}mm inset depth and an integral stepped border. Its flat lip rises
{body['secondary_lip_height_mm']:.2f}mm; the leaf tips close at source z{body['secondary_panel_tips_z_m'][0]:.3f}/{body['secondary_panel_tips_z_m'][1]:.3f}m. These are connected
surface features. Primary shadow channels are{body['primary_shadow_channel_depth_mm']:.2f}mm deep, with a
{body['panel_relief_tip_fade_mm']:.2f}mm relief fade at each panel tip. The lower seat has a straight land and stepped separator.
The body has{body['curvature_sampled_axial_rows']} curvature-sampled axial rows and analytic axial shading normals,
using{body['triangles']:,} triangles.
Lotus bud V5 has a fuller{bud['maximum_radius_m']*1000:.2f}mm maximum radius and six sculpted petal overlaps,
with{bud['lip_land_mid_belly_width_mm']:.3f}mm flat lip lands at the belly and{bud['inner_bevel_drop_mm']:.2f}mm inner bevel drops.
Outer gutters sit{bud['outer_gutter_depth_below_background_mm']:.2f}mm below the background; peak-to-groove depth is{bud['petal_peak_to_groove_mm']:.2f}mm.
The seated root shoulder drops
{bud['root_seating_shoulder_radial_drop_mm']:.2f}mm radially. A{bud['button_throat_bevel_axial_mm']:.2f}mm axial/{bud['button_throat_bevel_radial_mm']:.2f}mm radial throat bevel leads into
the{bud['button_diameter_m']*1000:.2f}mm rounded terminal button. The bud uses{bud['triangles']:,} triangles in one closed shell.
Its{bud['axial_body_rings']} axial rows and{bud['transverse_lanes_per_petal']} transverse lanes per petal refine the curvature while preserving
the full bulb. The inner bevel toe fillet has{bud['inner_bevel_toe_fillet_half_width_mm']:.3f}mm half-width.
Pommel triangle count{p['source_game_comparison']['pommel_triangles']:,}; no live subdivision/Boolean modifier.

The bud extends to source z−0.031m. Overall length{length:.3f}m; shaft/head/grip
remain fixed, source grip1.235m, actual grip-to-bud distance{grip:.3f}m. Pommel
socket and metadata follow the new tip. The other70 source meshes retain exact
geometry, UVs, custom normals, material assignments and transforms. All original
atlas bytes remain unchanged. At the user's explicit request, the pommel uses
the same `M_ImperialSpear_PBR` material and existing plain gold atlas region
as the spearhead. The full asset has one shared material slot. Candidate
generated gold maps are abandoned diagnostics and are not part of the delivery.

The only shared-shader addition is a presence-gated Base Color multiply driven
by `PommelCavity` CORNER/FLOAT_COLOR. Its linear grayscale RGB ranges from
{shade_min:.2f} in deep veins to{shade_max:.2f} on unmasked surfaces, with alpha1. Source meshes missing
the attribute return Color.R0; `Color.R >0.01` enables the multiply only on valid
shades. Attribute alpha is not a presence signal in Blender5.1. Protected source color
layers remain unchanged; neutral white is added only to their export copies.
Original roughness, metallic, specular, normals and all atlas PNG bytes are
preserved. `Cavity_Material_Report.json` records the localized shading contract.
In Unreal, import the mesh vertex colors and connect **BaseColor texture RGB ×
VertexColor RGB** to Base Color, keeping the original other inputs. On reimport,
replace existing vertex colors. GLB uses standard `COLOR_0` multiplication once.

'''+preserved+f'''## Delivery and verification

Current source/game blend, FBX, GLB and LOD FBXs are refreshed. Triangle counts
{tri:,}/{lods[0]:,}/{lods[1]:,}; UV0 surface, UV1 lightmap, one material.17 convex
UCX hulls with max{p['maximum_hull_vertices']}vertices; three fit the pommel and the other shapes are unchanged.
Four sockets, posed cosmetic tassel without rigid collision or cloth.
Current views: `Preview_Pommel.png`, `Preview_Pommel_Detail.png`,
`Preview_Pommel_Front.png`, `Preview_Pommel_Diagonal.png`, `Preview_Pommel_End.png`,
`Preview_Pommel_Reference.png`, `Preview_Full.png`. The end-on view isolates the body to expose its four-peaked
cross-section. [End-on body inspection](../Exports/ImperialSpear/Preview_Pommel_End.png)
and [diagonal view](../Exports/ImperialSpear/Preview_Pommel_Diagonal.png).
[Reference-angle comparison](../Exports/ImperialSpear/Preview_Pommel_Reference.png).
Head/handle previews remain valid.

`Pommel_Lotus_Verification.json` is the current source audit;
`Pommel_Lotus_Preflight.json` checks UV areas, shading directions and the join.
`Protected_Surface_Render_Check.json` compares a fixed-seed accepted-head render
with cavity shading enabled and bypassed. Maximum channel difference is
{protected_render['maximum_channel_difference']:.8f}, mean{protected_render['mean_channel_difference']:.8f}, over{protected_render['pixels']:,} pixels.
This render checks the visible accepted-head camera surfaces; all70 protected
source meshes are checked separately by exact fingerprints.
`Export_Verification.json` checks main and LOD FBX positions, UV0, custom normals
and cavity colors, material identity, hulls, sockets and measured extent. It also
checks GLB `COLOR_0`, single multiplication and unchanged BaseColor image. Original atlas hashes
and all70 protected mesh fingerprints pass. Actual hull face planes enclose
the new pommel. Dense sampled wood-joint containment passes; see report for
the parity/winding method. Unreal import/cooking/materials/physics/CCD remain
untested. No Unreal/Play/Blueprint/lab state changed.

## Resume safely

Read the current source instead of replaying historical geometry scripts.
Current tools: `model_pommel_lotus.py`, `four_lobe_pommel_body.py`, `lotus_bud_component.py`,
`apply_pommel_cavity_material.py`, `check_cavity_protected_render.py`, `preflight_lotus_source.py`,
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
'''
dp.write_text(doc,encoding='utf-8')
j=R/'ProjectJournal.md';text=j.read_text(encoding='utf-8')
block=f'''**Imperial spear October28 — concept04 Lotus bud rebuild:**
Previous flattened-leaf model rejected. User selected Lotus bud and requested
a planned rebuild, then clarified a four-peaked FLOWER cross-section for the
MAIN BODY. Four radial ribs surround broad Bezier concave scoops; comparable
width/depth, axis diameter{2*body['belly_axis_radius_mm']:.2f}mm and{body['belly_scoop_below_peak_chord_mm']:.3f}mm scoop below peak chord.
The scoops now contain integral closed leaf insets ({body['secondary_recess_depth_mm']:.2f}mm recess,
{body['secondary_lip_height_mm']:.2f}mm raised flat lip) with tapered tips. Circular necks meet stepped collars;
the lower seat has a straight land and separator. V3 was rejected for weak forms.
The current body has{body['crest_width_mm']:.2f}mm crests/{body['ridge_chamfer_depth_mm']:.2f}mm chamfers and{body['primary_shadow_channel_depth_mm']:.2f}mm primary channels,
with{body['curvature_sampled_axial_rows']} axial rows and analytic axial normals for refined curvature.
BudV5 has{bud['maximum_radius_m']*1000:.2f}mm maximum radius, six sculpted petal overlaps,
{bud['lip_land_mid_belly_width_mm']:.3f}mm flat lip lands/{bud['inner_bevel_drop_mm']:.2f}mm inner bevels, seated root and beveled button throat.
The bulb uses{bud['axial_body_rings']} axial rows/{bud['transverse_lanes_per_petal']} lanes per petal and small carved-wall toe fillets.
70 other components and original4K atlas bytes
preserved. User explicitly requested the same existing head gold; the pommel
uses M_ImperialSpear_PBR and the plain gold atlas region. One material slot.
Localized PommelCavity linear vertex colors multiply Base Color ({shade_min:.2f}–{shade_max:.2f});
Color.R >0.01 gates the multiply; missing source attributes have R0 and bypass.
Attribute alpha is not used. Original other material inputs
and protected source color layers are unchanged; export copies default white.
Unreal requires BaseColor texture RGB * VertexColor RGB; import mesh colors.
Bud extends31mm below prior cap; total{length:.3f}m. Shaft/head/grip fixed; grip
is{grip:.3f}m from new tip. Source/game/FBX/GLB/LODs and previews refreshed.
End-on body and diagonal previews document the radial cross-section; a new
reference-angle preview documents the strengthened form and cavity shading.
Triangles{tri:,}/{lods[0]:,}/{lods[1]:,};17 convex hulls, max{p['maximum_hull_vertices']}vertices,4 sockets.
Current source/UV/normal/material preservation, actual collision containment,
wood join and main/LOD FBX readback (including cavity colors) checks pass.
GLB COLOR_0 and single multiplication are checked. Current audit:
`Pommel_Lotus_Verification.json`; previous leaf audits are rejected-stage history.
Fixed-seed accepted-head enabled/bypassed renders pass (maximum channel
difference{protected_render['maximum_channel_difference']:.8f}); see `Protected_Surface_Render_Check.json`.
Unreal import/cooking/physics remain untested; appearance awaits user review.
Owned hidden Blender closed after bounded3-thread CPU work. No Unreal/Play/BP/lab
state changed. [Current handoff](Docs/ImperialSpear.md).

'''
matches=list(re.finditer(r'^\*\*Imperial spear October(?:27|28)[^\n]*\n.*?(?=^\*\*|\Z)',text,flags=re.S|re.M));assert len(matches)==1
m=matches[0];updated=text[:m.start()]+block+text[m.end():];assert updated.startswith(text[:m.start()]) and updated.endswith(text[m.end():]);j.write_text(updated,encoding='utf-8')
files=[{'path':path.relative_to(O).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(O.rglob('*')) if path.is_file() and path.name!='SHA256_Manifest.json' and path.suffix!='.blend1']
(O/'SHA256_Manifest.json').write_text(json.dumps({'status':status['status'],'files':files},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'triangles':tri,'lods':lods,'length_m':length,'materials':1,'manifest_files':len(files)}))
