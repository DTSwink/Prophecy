"""Publish measured handoff after the correction build and FBX checks succeed."""
import hashlib,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Exports/ImperialSpear'
BACKUP=ROOT/'Saved/Diagnostics/ImperialSpear/BeforeSevenPointCorrections_v1'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
asset=read('Asset_Report.json');verified=read('Export_Verification.json')
live=read('Seven_Point_Live_Audit.json');source=read('Current_Detail_Audit.json')
bevel=read('Housing_Bevel_Verification.json');crown=read('Unified_Crown_Verification.json')
assert asset['render_triangles']==verified['triangles']==source['source_triangles']
assert asset['collision_hull_count']==verified['fbx_hulls']
assert asset['collision_version']==verified['collision_version']==2
for path in (ROOT/'Docs/ImperialSpear.md',OUT/'README.txt'):
    target=BACKUP/path.name
    if not target.exists():shutil.copy2(path,target)
tri=asset['render_triangles'];hulls=asset['collision_hull_count']
lod1,lod2=[row['triangles'] for row in asset['lods']]
max_hull=max(row['vertices'] for row in asset['collision'])
error=verified['max_vertex_readback_error_m']
status={'status':'CORRECTED_REVIEW_BUILD','authoritative_scene':'ImperialSpear_Source.blend',
        'working_checkpoint':'../../Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend',
        'appearance_accepted':False,'unreal_import_validated':False,
        'fbx_glb_lods_collision':'Regenerated from current source; FBX readback verified',
        'render_triangles':tri,'lod_triangles':[lod1,lod2],'collision_hulls':hulls,
        'comparison':'Reference_Comparison.html','current_render':'Comparison_Current.png',
        'detail_views':['Candidate_SevenFix_Oblique.png','Candidate_SevenFix_Front.png','Comparison_WoodDetail.png'],
        'corrections':['Sleeve seated below guard','Wide approximately45-degree guard chamfer',
                       'Round first bead','Unified crown with buried foot and blade clearance',
                       'Subtle socket normal chasing','Straight axis-aligned neck collar',
                       'Rounded middle ring and straight-sided neck collar'],
        'source_audit':'Seven_Point_Live_Audit.json','export_audit':'Export_Verification.json'}
(OUT/'DELIVERY_STATUS.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
source['status']='CURRENT_SOURCE_AND_EXPORT_CHECKPOINT'
source['export_status']='Current FBX/GLB/LODs generated; main FBX readback verified'
source['appearance_status']='Corrected render reviewed; user acceptance not recorded'
(OUT/'Current_Detail_Audit.json').write_text(json.dumps(source,indent=2)+'\n',encoding='utf-8')
readme=f'''IMPERIAL SPEAR — correction build, October 27, 2026

CURRENT FILES
ImperialSpear_Source.blend — editable components and matched studio camera.
ImperialSpear_Game.blend — grip-centred game mesh, collision and LODs.
SM_ImperialSpear.fbx — one render mesh, {hulls} UCX hulls and four sockets.
SM_ImperialSpear.glb — portable PBR preview; collision is supplied in FBX.
SM_ImperialSpear_LOD1.fbx / LOD2.fbx — reduced meshes at the same pivot.
Textures/ — 4096px BaseColor, packed ORM, NormalGL and NormalDX.
Reference_Comparison.html — original/current matched-camera comparison.
Candidate_SevenFix_Oblique.png / Front.png — current gold-assembly close views.
Preview_Full.png / Preview_Back.png / Preview_ThreeQuarter.png — current angles.
Asset_Report.json / Export_Verification.json / Seven_Point_Live_Audit.json — checks.

SPECIFICATION AND CORRECTIONS
Length220cm; +Z toward blade. Pivot123.5cm from the blunt gold butt.
Wrapped grip spans111.5–135.5cm. Accepted blade silhouette and actual recessed
nervure are preserved. LOD0 {tri:,} triangles; LOD1 {lod1:,}; LOD2 {lod2:,}.
One material. UV0 uses repeating atlas regions; UV1 is packed for lightmaps.
The sleeve stops4.4mm below the flat guard seat. The neck collar has straight
sides and a level seat; the middle ring has a rounded profile. First bead is
round. Gold housing has a broad4.8mm shoulder with approximately45-degree slope.
The crown is one closed solid with its terminal buried inside the guard and
clearance above the steel. Sleeve motifs use0.045mm normal depth and restrained
colour variation. Wood retains irregular fibres and pores, roughness~0.78 and
specular0.20 for contrast with the gold. Tassel is static cosmetic geometry.
Unseen surfaces are authored interpretations of the supplied screenshots.

UNREAL IMPORT
Import SM_ImperialSpear.fbx as a Static Mesh with uniform scale1; verify220cm.
Keep the exported pivot and import normals/tangents. Use the supplied collision,
with one convex hull per UCX; expect {hulls} simple hulls. Use simple collision
for rigid simulation. The tassel, cords and beads have no rigid collision;
the tiny pierced eye is filled by the simplified collision envelope.
Sockets: Grip, BladeTip, Pommel and Tassel. Import the two LOD FBXs separately
and tune screen-size transitions for the intended camera.

MATERIAL
One opaque Default Lit material. BaseColor: sRGB ON -> Base Color.
ORM: sRGB OFF, retain alpha, use data/mask compression:
  R -> Ambient Occlusion; G -> Roughness; B -> Metallic; A -> Specular.
The packed alpha is specular data, not opacity. It preserves the matte wood
contrast. NormalDX: Normalmap compression, sRGB OFF -> Normal. Do not flip
NormalDX green again. NormalGL is for Blender/glTF. FBX material wiring is not
an automatic substitute for creating these connections explicitly in Unreal.

VALIDATION AND LIMITS
Main FBX readback verified1 render mesh, {hulls} convex hulls,4 sockets,2 UV sets,
one material,220cm length and maximum vertex error {error:.3g}m.
Hulls are closed and positive-volume, at most {max_hull} vertices each.
Actual UV0 values and custom corner normals are checked during readback.
Seven_Point_Live_Audit.json checks fit, closed correction meshes, corner-normal
orientation and preserved component hashes. Numeric checks do not establish
reference fidelity; current images are supplied for visual review.
Unreal import, material setup, collision cooking, contacts and CCD remain
untested. No Unreal/editor/Play/Blueprint state was changed by this asset pass.

Created through upstream Blender MCP in a task-owned hidden Blender5.1 process.
CPU stills were limited to3 threads at BelowNormal priority; no GPU rendering.
The owned Blender process is closed after saving. Source scripts and handoff:
../../Tools/SpearAsset/ and ../../Docs/ImperialSpear.md.
'''
(OUT/'README.txt').write_text(readme,encoding='utf-8')
topic=f'''# Imperial spear — current handoff

The October27 correction build is saved in `Exports/ImperialSpear/`.
`ImperialSpear_Source.blend` is the current editable source; the matching working
checkpoint is `Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend`.
The FBX, GLB, GAME blend and two LODs now reflect this geometry and its current
textures. Appearance is supplied for user review; acceptance is not recorded.
No active goal object should be inferred from historical prose.

## Current corrections and evidence

The engraved sleeve ends at1.664m,4.4mm below the flat guard seat at1.6684m.
The5.2mm straight-sided neck collar ends at the same seat and is axis-aligned.
The middle ring is a closed rounded profile. The pierced first lacquer bead
is spherical. Existing blade/recess, moved grip, blunt gold pommel, shaft and
other protected components match their retained geometry hashes.

The gold housing uses explicit4.8mm chamfer bands,0.3mm edge eases and a0.6mm
eye lip; {bevel['triangles']} triangles, closed with positive volume.
The local width field is shared by all nested bands to prevent reversed slopes
beside the protected eye. Custom corner normals are checked against actual
face orientation. The crown is one closed solid ({crown['triangles']} triangles)
with a planar face above the blade;1.8mm hidden overlap buries its end inside
the actual guard. Minimum measured terminal burial is
{crown['minimum_terminal_burial_in_actual_guard_m']*1000:.3f}mm and blade clearance
{crown['minimum_vertex_blade_clearance_m']*1000:.3f}mm. The old depth fade caused
silver breakthrough and is removed.

Socket patterns retain their layout with0.045mm normal depth and3.5% maximum
albedo cut, replacing the older dark0.15mm cuts. Gold finish variation is
reduced; the housing S-border patch is preserved. Wood retains32 irregular
tapered/forked grain paths and1500 staggered pores, depth capped0.12mm,
roughness~0.784 and specular0.20. All unrelated atlas regions were hash-checked.
ORM is RGBA: AO/Roughness/Metallic/Specular. Treat alpha as CHANNEL_PACKED data,
not opacity. Source material is opaque. Use NormalDX in Unreal, NormalGL in Blender.

`Candidate_SevenFix_Oblique.png` and `Candidate_SevenFix_Front.png` show the current
assembly. `Comparison_Current.png` is a2400×1346 matched-camera render;
`Reference_Comparison.html` provides reference overlay/crops. Full, back,
three-quarter, recess and wood previews were refreshed. Lighting includes a
presentation-only135W reflection strip linked to the blade; it is not exported.

## Export state

The asset is2.20m long, +Z toward blade. Grip pivot1.235m above the butt;
wrapped grip spans1.115–1.355m. LOD0 {tri:,} triangles, LOD1 {lod1:,}, LOD2 {lod2:,};
one material,4096px atlas, surface UV0 and separately packed lightmap UV1.
{hulls} authored convex UCX pieces follow shaft, grip, pommel, socket, rings,
casting and blade sections; at most {max_hull} vertices per hull. Tassel/cord/beads
are cosmetic and excluded. The small eye aperture is filled in simple collision.
Four sockets: Grip, BladeTip, Pommel, Tassel. Tassel is posed geometry, no cloth rig.

`Asset_Report.json`, `Export_Verification.json`, `Seven_Point_Live_Audit.json`
and `SHA256_Manifest.json` describe this checkpoint. FBX readback checks geometry,
UV0 data, corner normals, collision convexity/closure, sockets and scale;
maximum vertex position error {error:.3g}m. No Unreal import, material validation,
collision cooking, CCD or physics contacts have been tested. Existing Unreal,
Blueprint, Play and lab state were not touched by this asset pass.

## Resume and reproduce safely

The current saved blend is the resume point. Do not replay old incremental
scripts indiscriminately. Pre-correction source/textures and prior handoff are
in `Saved/Diagnostics/ImperialSpear/BeforeSevenPointCorrections_v1/`.
Earlier revisions are historical evidence, not current build instructions.

Current tools under `Tools/SpearAsset/`:

1. `mcp_client.py` calls the actual upstream Blender MCP server through its local
   addon bridge. Textual execution errors produce failure exits. `start_bridge.py`
   binds127.0.0.1:9876 in a task-owned hidden Blender. Verify process/port before
   restart; PID records may be stale after delivery. Global preferences untouched.
2. `generate_clean_casting_mesh.py` and `install_explicit_casting.py` create the
   current housing. `generate_unified_crown.py` and `install_unified_crown.py`
   create its unified curl and check actual blade/guard clearance. The housing
   importer reseats the S relief from retained pre-bevel meshes without cumulative
   displacement. It keeps a single named `UV0_SurfaceAtlas` layer.
3. `fix_socket_bead_rings.py` builds the shortened sleeve, correct ring profiles
   and round bead. `soften_reference_gold.py` uses immutable gold-region backups
   while preserving current pixels outside gold. `refine_wood_structure.py`
   generated the retained wood detail. Re-running older full-atlas texture
   scripts would undo current alpha packing and finishes.
4. `audit_seven_point_corrections.py` also invokes protected-geometry auditing.
   `export_spear.py` preflights sources before replacing its GAME/collision data;
   `reference_collision_specs.py` supports the unified crown. `verify_exports.py`
   imports into a temporary scene and cleans up afterward.
5. Render scripts restore the matched camera in finally. CPU stills are limited
   to3 threads at BelowNormal process priority. `finish_seven_point_delivery.py`
   preserves that camera, saves both exports and the working checkpoint, then
   closes only the owned Blender. `write_delivery_handoff.py` updates measured
   metadata after successful verification.

Superseded: oval first bead; quarter-round3.5mm guard; folded independent width
fields; separate mirrored crown slabs; crown depth fade; dark socket cuts;
automatic bevel and Boolean chasing experiments. `refine_reference.py` is the
rejected blade-silhouette experiment and must remain disabled.
All438 original outer blade/cutting-bevel vertices remain fixed; the accepted
straight nervure is carved into both faces with the gold in its floor.

The upstream Blender MCP source/licence is retained in Saved. No paid service,
GPU render, user desktop takeover or recurring background task was used.
'''
(ROOT/'Docs/ImperialSpear.md').write_text(topic,encoding='utf-8')
journal=ROOT/'ProjectJournal.md';text=journal.read_text(encoding='utf-8')
section=f'''**Imperial spear October27 — seven reported defects corrected; exports refreshed:**
Current editable/game blends, FBX/GLB, two LODs and4096px textures are in
`Exports/ImperialSpear/`; working checkpoint remains under Saved/Diagnostics.
Sleeve ends4.4mm below the flat guard seat; straight neck collar is level,
middle ring is rounded and first bead spherical. Wide~45deg housing chamfer,
unified crown with buried foot and blade clearance, subtle socket normals.
Matte irregular wood retained. Accepted blade/recess, moved grip and blunt
pommel match protected geometry hashes. Current oblique/front and matched
reference views refreshed; user appearance acceptance is not recorded.
LOD triangles {tri:,}/{lod1:,}/{lod2:,}; one material; {hulls} convex UCX hulls
(max{max_hull} vertices), four sockets. FBX readback verifies positions, UV0,
corner normals, hulls and2.2m scale. ORM alpha carries Specular, not opacity.
Unreal import/cooking/material/physics remain untested. No Unreal/Play/BP/lab
state changed. Hidden owned Blender used3 CPU threads at BelowNormal and was
closed after saving. [Current asset handoff](Docs/ImperialSpear.md).

'''
text,count=re.subn(r'\*\*Imperial spear October27.*?(?=\*\*Broad storage cleanup)',section,text,count=1,flags=re.S)
assert count==1,'Journal spear section boundary changed; do not overwrite unrelated handoff'
journal.write_text(text,encoding='utf-8')
# Old proof images remain available in backups; common preview names now show current work.
shutil.copy2(OUT/'Candidate_SevenFix_Oblique.png',OUT/'Preview_Gold_Detail.png')
shutil.copy2(OUT/'Comparison_Current.png',OUT/'Preview_Head.png')
files=[]
for path in sorted(OUT.rglob('*')):
    if path.is_file() and path.name!='SHA256_Manifest.json' and path.suffix!='.blend1':
        files.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'SHA256_Manifest.json').write_text(json.dumps({'status':'CORRECTED_REVIEW_BUILD','files':files},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'triangles':tri,'lods':[lod1,lod2],'hulls':hulls,'manifest_files':len(files)}))
