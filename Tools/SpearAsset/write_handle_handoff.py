"""Publish measured final handle-pass metadata after successful export readback."""
import hashlib,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Exports/ImperialSpear';WORK=ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
a=read(OUT/'Asset_Report.json');v=read(OUT/'Export_Verification.json');h=read(OUT/'Handle_Finish_Verification.json')
assert a['render_triangles']==v['triangles']==h['source_triangles']
assert a['collision_hull_count']==v['fbx_hulls']
texture_application=read(WORK/'Handle_Texture_Application.json')
wood_path=Path(texture_application['wood_report'])
if not wood_path.is_absolute():wood_path=ROOT/wood_path
grip_path=Path(texture_application.get('grip_manifest',str(WORK/'patches/HandlePatchManifest.json')))
if not grip_path.is_absolute():grip_path=ROOT/grip_path
wood=read(wood_path);grip_manifest=read(grip_path);patch=grip_manifest['patches']
wood_revision=wood_path.parent.name;wood_normal_gain=float(wood.get('normal_relief_gain',1.0))
wood_normal_note=(f'Normal gradients use a {wood_normal_gain:g}x relief gain; this strengthens shading without changing shaft geometry.'
                  if abs(wood_normal_gain-1)>1e-6 else 'Normals use physical height gradients at unit gain.')
wood_uv=read(WORK/'Wood_UV_Repack_Verification.json')
assert wood_uv['original_vertices_unchanged'] and wood_uv['protected_components_identical'] and wood_uv['seam_padding_passed']
assert h['shaft_uv_repack']['repack_report_sha256']==hashlib.sha256((WORK/'Wood_UV_Repack_Verification.json').read_bytes()).hexdigest()
assert h['shaft_uv_repack']['added_triangles']==wood_uv['added_triangles']
wood_density=wood_uv.get('density',wood_uv)
wood_px_axial=wood_density['axial_px_per_mm'];wood_px_circ_min=wood_density['circumferential_px_per_mm_min'];wood_px_circ_max=wood_density['circumferential_px_per_mm_max']
wood_rings=len(wood_uv['added_ring_z_m']);wood_added_vertices=wood_uv['added_vertices'];wood_added_triangles=wood_uv['added_triangles']
wood_strips=wood['strip_count'];wood_gutter=wood['gutter_px']
tri=a['render_triangles'];lods=[row['triangles'] for row in a['lods']];hulls=a['collision_hull_count'];maxv=max(row['vertices'] for row in a['collision'])
for path in (ROOT/'Docs/ImperialSpear.md',OUT/'README.txt'):
    target=WORK/'Before'/path.name
    if not target.exists():shutil.copy2(path,target)
for name in ('Handle_Texture_Application.json','Handle_Geometry_Report.json','Angular_S_Relief_Verification.json','Wood_UV_Repack_Verification.json'):
    shutil.copy2(WORK/name,OUT/name)
final_wood={**wood,'generation_status':wood.get('status'),
            'status':'WOOD_FINISH_APPLIED_AND_EXPORTED_REVIEW_BUILD','selected_revision':wood_revision,
            'uv_repack_audit':'Wood_UV_Repack_Verification.json','user_appearance_acceptance_recorded':False}
(OUT/'Final_Wood_Finish.json').write_text(json.dumps(final_wood,indent=2)+'\n',encoding='utf-8')
final_grip={**grip_manifest,'generation_scope':grip_manifest.get('scope'),
            'scope':'Current leather and retained keeper-gold patches applied to verified source and exports',
            'user_appearance_acceptance_recorded':False}
(OUT/'Final_Grip_Finish.json').write_text(json.dumps(final_grip,indent=2)+'\n',encoding='utf-8')
status={'status':'FINAL_HANDLE_AND_ANGULAR_RELIEF_REVIEW_BUILD','authoritative_scene':'ImperialSpear_Source.blend',
        'working_checkpoint':'../../Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend',
        'spearhead_accepted_before_explicit_S_relief_exception':True,'other_head_geometry_UV_and_pixels_preserved':True,
        'final_handle_and_S_user_acceptance_recorded':False,'unreal_import_validated':False,
        'wood_finish_revision':wood_revision,'wood_normal_relief_gain':wood_normal_gain,'leather_finish_revision':grip_manifest['revision'],
        'wood_uv_repack_verified':True,'wood_uv_repack_audit':'Wood_UV_Repack_Verification.json',
        'render_triangles':tri,'lod_triangles':lods,'collision_hulls':hulls,
        'fbx_glb_lods_collision':'Regenerated and main/LOD FBX readback verified',
        'detail_views':['Candidate_Handle_Transition.png','Candidate_Handle_Full.png','Candidate_SevenFix_Oblique.png'],
        'source_audit':'Handle_Finish_Verification.json','export_audit':'Export_Verification.json'}
(OUT/'DELIVERY_STATUS.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
current={**h,'status':'CURRENT_SOURCE_AND_EXPORT_CHECKPOINT','export_status':'Main FBX and both LODs readback verified',
         'appearance_status':'Accepted head preserved except requested angular S; final handle/relief supplied for review'}
(OUT/'Current_Detail_Audit.json').write_text(json.dumps(current,indent=2)+'\n',encoding='utf-8')
wood_rough=wood['roughness_min_mean_max'][1];wood_spec=wood['specular_min_mean_max'][1]
leather_rough=patch['Leather']['roughness_mean'];leather_depth=patch['Leather']['score_depth_mm'];leather_spec=patch['Leather']['specular_ior_level']
leather_cell=patch['Leather']['pebbled_grain_mean_cell_mm'];leather_height=patch['Leather']['pebbled_grain_height_mm']
text=f'''IMPERIAL SPEAR — final handle and angular-relief pass, October 27, 2026

FILES
ImperialSpear_Source.blend: editable source and reference camera.
ImperialSpear_Game.blend: game mesh, simple collision and distance LODs.
SM_ImperialSpear.fbx: one render mesh, {hulls} UCX hulls and four sockets.
SM_ImperialSpear.glb: PBR preview; collision is supplied in FBX.
SM_ImperialSpear_LOD1.fbx / LOD2.fbx: aligned reduced render meshes.
Textures/: 4096px BaseColor, packed RGBA ORM, NormalGL and NormalDX.
Candidate_Handle_Transition.png: wood/gold/leather macro.
Candidate_Handle_Full.png: complete grip, both gold collars and adjacent wood.
Candidate_SevenFix_Oblique.png / Front.png: current angular S relief.
Preview_Full.png / Preview_Back.png / Preview_ThreeQuarter.png: current angles.

CURRENT DETAIL
The user accepted the spearhead, then explicitly requested angular facets on
its S relief. That relief alone now has a flat crest and sloped faces; every
other head component and all accepted head texture pixels are preserved.
The current wood finish has flowing fibres that split/rejoin, fine pores and shallow checks,
with roughness averaging {wood_rough:.3f} and specular {wood_spec:.3f}. Its shaft
UVs use {wood_strips} axial strips: {wood_px_axial:.2f}px/mm along the shaft and
{wood_px_circ_min:.2f}–{wood_px_circ_max:.2f}px/mm around it. The added {wood_rings} seam rings
preserve the original shaft vertices and add {wood_added_vertices} vertices/{wood_added_triangles} triangles.
Selected wood revision: {wood_revision}. {wood_normal_note}
Leather is a coarse matte sleeve with {leather_cell:.2f}mm pebbled grain, fine
pores and {leather_depth:.3f}mm scored incisions. Roughness averages {leather_rough:.3f},
specular {leather_spec:.3f}; sparse rubbed patches and clean worn lips break up
the uniform grain. Grip gold has straight engraved faces,
integral rims, fine hairlines and restrained edge patina. Its dedicated atlas
tile leaves all accepted head gold untouched. Grip position/length retained.

SPECIFICATION
Length220cm, +Z to blade; pivot123.5cm above blunt gold butt.
Leather spans111.5–135.5cm. Original blade and carved nervure remain fixed.
LOD0 {tri:,} triangles; LOD1 {lods[0]:,}; LOD2 {lods[1]:,}. One material.
UV0 is the surface atlas; UV1 is separately packed for lightmaps.
The tassel is posed cosmetic geometry, without cloth or rigid collision.
Recreated from screenshots; unseen surfaces are authored interpretations.

UNREAL
Import the main FBX at scale1, retain pivot, import normals/tangents and verify
220cm length. Use its {hulls} supplied convex UCX hulls for simple rigid collision;
do not replace them with generated collision. Small ornament openings are
filled by simplified hulls; tassel, cord and beads are excluded. Max{maxv} vertices
per hull. Sockets: Grip, BladeTip, Pommel and Tassel. Import LOD FBXs separately
and tune screen transitions for the target camera.

One opaque material. Enable Two Sided so the thin tassel ribbons show from both sides.
BaseColor: sRGB ON -> Base Color.
ORM: sRGB OFF, data/mask compression retaining alpha:
  R -> Ambient Occlusion, G -> Roughness, B -> Metallic, A -> Specular.
ORM alpha is specular data, not opacity. NormalDX: Normalmap compression,
sRGB OFF -> Normal; do not flip its green channel again. NormalGL is for
Blender/glTF. FBX material wiring does not replace explicit Unreal connections.

VERIFICATION
Handle_Finish_Verification.json checks {h['protected_component_count']} protected components,
closed edited meshes and shading-normal orientation. The separate wood UV
audit checks interpolation, strip density and padded seams. Texture-region hashes
prove accepted head/silk pixels unchanged. Main FBX and both LODs were read
back and checked for positions, actual UV0 values and custom corner normals.
Collision hulls are closed, convex and positive-volume. All four sockets and
scale verified. Unreal import, material rendering, collision cooking, actual
physics contacts and CCD remain untested. Existing Unreal/Play/Blueprint state
was not touched. Final appearance is supplied for review.

Source scripts: ../../Tools/SpearAsset/. Current handoff: ../../Docs/ImperialSpear.md.
Blender MCP used a hidden task-owned process, BelowNormal priority,3 CPU render
threads and sequential stills. The owned process was closed after saving.
'''
(OUT/'README.txt').write_text(text,encoding='utf-8')
doc=f'''# Imperial spear — current handoff

The user accepted the seven-point spearhead correction, then requested a final
wood/leather/grip-gold pass and specifically an angular cross-section for the
S relief. These are implemented in the current source and game exports.
The other {h['protected_component_count']} components keep their geometry and UVs; all accepted
head and silk texture pixels remain byte-identical to the retained baseline.
Final handle/S appearance is supplied for review, not yet user-confirmed.

Current editable source: `Exports/ImperialSpear/ImperialSpear_Source.blend`.
Working copy: `Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend`.
The FBX, GLB, GAME blend, both LODs, textures and previews are refreshed.

## Current finish and geometry

The current wood finish uses coherent curved fibres, split/rejoin grain, broken tapered runs,
pores, shallow checks and dents. Physical height drives the normal detail with
restrained correlated albedo. Measured average roughness {wood_rough:.3f} and
specular {wood_spec:.3f} come from `{wood_revision}/Wood_Patch_Report.json`, selected
by `Handle_Texture_Application.json`; unapplied candidates are not authoritative.
{wood_normal_note}
The shaft has {wood_strips} axial UV strips with
{wood_gutter}px gutters inside the same wood tile. Measured density is
{wood_px_axial:.2f}px/mm axially and {wood_px_circ_min:.2f}–{wood_px_circ_max:.2f}px/mm
circumferentially, avoiding the old single strip's stretched axial detail.
The {wood_rings} interpolated seam rings add {wood_added_vertices} vertices and {wood_added_triangles} triangles;
all original shaft vertices remain unchanged. `Wood_UV_Repack_Verification.json`
records the interpolation, shading and seam checks. No other protected
component is changed by the shaft repack.

Current leather revision: `{grip_manifest['revision']}`.
It is a taut matte sleeve with irregular {leather_cell:.2f}mm pebbled grain,
{leather_height[0]:.3f}–{leather_height[1]:.3f}mm grain relief, fine pits and angular scored lozenges
with compact crossing loops. Scoring is {leather_depth:.3f}mm; mean roughness
{leather_rough:.3f}, specular {leather_spec:.3f}. Sparse broad rubbed patches reduce
grain height locally; clean worn lips and restrained dark wear marks distinguish
the incisions. Large unrelated cloudy color variations are suppressed.
Puffy helical strips were removed. The sleeve retains
z1.115–1.355m and the grip pivot1.235m. Gold keepers retain axial bounds
1.102–1.122 and1.348–1.368m, with straight barrels and integral lips replacing
separate round wires. Fine chasing, hairlines and restrained border patina
live in a dedicated keeper tile, so no shared head-gold finish changed.

Atlas split: wood [0,2048,2048,4096] subdivided into {wood_strips} axial-strip columns;
leather [2048,2048,3072,3808]; keeper gold [2048,3808,3072,4096], Pillow top-origin
pixel boxes. Wood strips have {wood_gutter}px gutters; the grip tiles have12px gutters.
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

Length2.20m, +Z toward blade; moved grip pivot1.235m; blunt gold pommel.
LOD triangles {tri:,}/{lods[0]:,}/{lods[1]:,}; one material and4096px atlas.
UV0 is surface; UV1 is packed lightmap. {hulls} convex UCX hulls, at most{maxv}
vertices each, four sockets. Cosmetic tassel/cord/beads excluded; small negative
ornament spaces filled by simple collision. Tassel is static, no cloth rig.

Current images: `Candidate_Handle_Transition.png`, `Candidate_Handle_Full.png`,
`Candidate_SevenFix_Oblique.png`, `Comparison_Current.png` and `Preview_Full.png`.
`README.txt` gives portable import/material instructions. The new source audit
is `Handle_Finish_Verification.json`; prior `Seven_Point_Live_Audit.json` describes
the previous accepted stage. `Export_Verification.json` checks main and both
LOD FBX positions, actual UV0 and custom normals; all collision hulls/sockets
and scale pass. `SHA256_Manifest.json` covers current delivered files.
Unreal import, cooking, actual material appearance, physics contacts and CCD
remain untested. No Unreal/Play/Blueprint/lab state was changed in this pass.

## Resume safely

Use the saved current blend. Accepted rollback source, texture atlases and
images are under `Saved/Diagnostics/ImperialSpear/HandleFinish/Before/`.
`Accepted_Baseline.json` and `Handle_Probe.json` record the accepted geometry/UVs.
Older docs and incremental scripts are historical evidence; do not blindly
replay them. Earlier 3.5mm guard bevels, oval bead, twin crown slabs, sleeve
breakthrough and dark socket cuts remain superseded.

Current tools in `Tools/SpearAsset/`:

1. `mcp_client.py` calls upstream Blender MCP through localhost9876.
   `start_bridge.py` starts only a task-owned hidden session. Check process/port
   before starting. PID file may be stale after delivery. No global settings changed.
2. `make_handle_wood_patches.py` produces standalone wood candidates;
   `make_handle_grip_patches.py` produces leather/keeper candidates (see patch
   manifest for exact filenames and UV bounds). `apply_handle_patches.py` applies
   selected patches and asserts all accepted head/silk pixels remain identical.
3. `refine_handle_geometry.py` builds the taut sleeve and integrated keepers.
   `repack_wood_uv.py` inserts only interpolated shaft seam rings and applies
   the four-strip wood UV layout; its report verifies the other components.
   `generate_angular_s_relief.py` / `apply_angular_s_relief_only.py` create the S
   replacement from the retained probe. The importer expects the old S baseline;
   it intentionally refuses to apply twice to the changed S.
4. `audit_handle_finish.py` validates edited meshes and protected components.
   `export_spear.py` regenerates all exports and repairs only invalid decimated
   tassel-tip normals; `verify_exports.py` reads all three FBXs back in an isolated
   temporary scene and removes it. `finish_handle_delivery.py` saves current
   files and closes only the owned Blender. `write_handle_handoff.py` publishes
   measured metadata after verification. Do not run the older handoff writer.
5. Render scripts restore the matched head camera in finally. Renders use CPU,
   three threads, BelowNormal priority and sequential bounded stills. Final
   handle macro is48samples; other views32 or24. No desktop/browser takeover.

Original outer blade/cutting-bevel vertices and its actual recessed channel
remain fixed. The rejected silhouette experiment stays disabled. Current
source and texture backups preserve every earlier accepted stage.
'''
(ROOT/'Docs/ImperialSpear.md').write_text(doc,encoding='utf-8')
journal=ROOT/'ProjectJournal.md';data=journal.read_text(encoding='utf-8')
block=f'''**Imperial spear October27 — final handle finish and angular S relief:**
User accepted the spearhead, then requested wood/leather/grip-gold refinement
and angular S faces. Other {h['protected_component_count']} components retain geometry/UVs; all accepted
head/silk texture pixels are unchanged. Current wood ({wood_revision}) has flowing split/rejoin fibres,
pores/checks and {wood_strips} axial UV strips at about5px/mm in both directions;
{wood_rings} interpolated rings add {wood_added_vertices} vertices/{wood_added_triangles} triangles, preserving original shaft vertices.
The grip is matte pebbled scored leather with rubbed wear: roughness {leather_rough:.3f}, specular {leather_spec:.3f}.
Gold keepers have straight engraved faces and integral rims.
S relief has a flat crest and inclined facets with inherited folds removed.
Blade/recess, head/rings/beads, moved grip position and blunt pommel retained.
Source/game/FBX/GLB/LODs/previews refreshed. Triangles {tri:,}/{lods[0]:,}/{lods[1]:,};
one material; {hulls} convex hulls, max{maxv} vertices; four sockets. Main and both
LOD FBX positions/UV0/normals, hulls and2.2m scale verified. ORM alpha=Specular.
Unreal import/cooking/physics remain untested. Final handle/S appearance awaits
user review. Hidden owned Blender closed after bounded3-thread CPU stills.
No Unreal/Play/BP/lab state changed. [Current asset handoff](Docs/ImperialSpear.md).

'''
matches=list(re.finditer(r'^\*\*Imperial spear October27[^\n]*\n.*?(?=^\*\*|\Z)',data,flags=re.S|re.M))
assert len(matches)==1,'Expected exactly one spear journal block; preserve unrelated work'
match=matches[0]
updated=data[:match.start()]+block+data[match.end():]
assert updated.startswith(data[:match.start()]) and updated.endswith(data[match.end():])
journal.write_text(updated,encoding='utf-8')
for source,destination in [('Candidate_SevenFix_Oblique.png','Preview_Gold_Detail.png'),('Comparison_Current.png','Preview_Head.png')]:
    shutil.copy2(OUT/source,OUT/destination)
files=[]
for path in sorted(OUT.rglob('*')):
    if path.is_file() and path.name!='SHA256_Manifest.json' and path.suffix!='.blend1':
        files.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'SHA256_Manifest.json').write_text(json.dumps({'status':status['status'],'files':files},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'triangles':tri,'lods':lods,'hulls':hulls,'protected_components':h['protected_component_count'],'manifest_files':len(files)}))
