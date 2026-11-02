"""Publish measured selected-pommel handoff without touching unrelated journal work."""
import json,hashlib,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Exports/ImperialSpear';WORK=ROOT/'Saved/Diagnostics/ImperialSpear/PommelLeaf'
a=json.loads((OUT/'Asset_Report.json').read_text(encoding='utf-8'))
v=json.loads((OUT/'Export_Verification.json').read_text(encoding='utf-8'))
p=json.loads((OUT/'Pommel_Leaf_Verification.json').read_text(encoding='utf-8'))
assert p['status']=='LEAF_POMMEL_SOURCE_AND_ACTUAL_GAME_COLLISION_AUDITED'
tri=a['render_triangles'];lods=[r['triangles'] for r in a['lods']];hulls=a['collision_hull_count'];maxv=p['maximum_hull_vertices']
assert tri==v['triangles']==p['source_game_comparison']['source_triangles']
assert hulls==v['fbx_hulls']==17
shutil.copy2(WORK/'Leaf_ThreeQuarter.png',OUT/'Preview_Pommel.png')
shutil.copy2(WORK/'Leaf_Front.png',OUT/'Preview_Pommel_Front.png')
shutil.copy2(WORK/'Geometry_Report.json',OUT/'Pommel_Leaf_Geometry.json')
status={'status':'SELECTED_FLATTENED_LEAF_POMMEL_REVIEW_BUILD',
        'authoritative_scene':'ImperialSpear_Source.blend','working_checkpoint':'../../Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend',
        'selected_pommel_concept':'03 — Flattened leaf','selected_reference':'../../Design/ImperialSpear/PommelConcepts/03_FlattenedLeaf_Selected.png',
        'pommel_concept_accepted':True,'pommel_model_appearance_user_acceptance_recorded':False,
        'protected_other_components':70,'protected_geometry_uv_normals_materials_transforms_unchanged':True,
        'all_four_atlas_files_unchanged':True,'wood_finish_revision':'wood_v8','leather_finish_revision':'V5',
        'render_triangles':tri,'pommel_triangles':p['source_game_comparison']['pommel_triangles'],'lod_triangles':lods,
        'collision_hulls':hulls,'pommel_collision_hulls':3,'maximum_hull_vertices':maxv,
        'fbx_glb_lods_collision':'Regenerated; main and both LOD FBX readback passed',
        'source_audit':'Pommel_Leaf_Verification.json','export_audit':'Export_Verification.json',
        'historical_audits':['Handle_Finish_Verification.json','Wood_UV_Repack_Verification.json','Seven_Point_Live_Audit.json'],
        'detail_views':['Preview_Pommel.png','Preview_Pommel_Front.png','Preview_Full.png'],
        'wood_joint_sample_count':p['wood_joint']['samples'],'wood_joint_outside_samples':0,
        'unreal_import_validated':False,'unreal_collision_cooking_validated':False,'unreal_physics_validated':False,
        'scope':'Only the pommel geometry/UVs and its collision changed; exports/previews refreshed. Unreal/labs were not touched.'}
(OUT/'DELIVERY_STATUS.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')

readme=f'''IMPERIAL SPEAR — selected flattened leaf pommel, October 27, 2026

CURRENT CHANGE
User selected concept 03, Flattened leaf. Three closed meshes replace the old
ribbed cylindrical pommel: a broad flattened leaf with curved shoulders,
integral recessed channels and beveled borders, a turned socket with rolled
lips, and a blunt round end cap. Front and back carry matching leaf detail.
The other70 components retain identical geometry, UVs, custom normals,
material assignments and transforms. All four existing atlas PNGs are byte-identical.
Blade, carved nervure, head, beads, wood, leather and grip position are preserved.
The selected concept is approved; this modeled interpretation is supplied for review.

FILES
ImperialSpear_Source.blend: editable components and accepted head camera.
ImperialSpear_Game.blend: combined game mesh, simple collision and two LODs.
SM_ImperialSpear.fbx: one render mesh, {hulls} UCX hulls and four sockets.
SM_ImperialSpear.glb: PBR preview; collision is supplied in FBX.
SM_ImperialSpear_LOD1.fbx / LOD2.fbx: aligned reduced render meshes.
Textures/:4096px BaseColor, packed RGBA ORM, NormalGL and NormalDX.
Preview_Pommel.png / Preview_Pommel_Front.png: current close inspection views.
Preview_Full.png: refreshed full-length view. Head and handle detail previews
remain valid because their source surfaces and material maps did not change.

SPECIFICATION
Length220cm, +Z toward blade; pivot123.5cm above the blunt gold butt.
Leather spans111.5–135.5cm; wood_v8 and leatherV5 finishes retained.
Pommel z0–12.81cm; leaf body maximum width about4.90cm.
LOD0 {tri:,} triangles; LOD1 {lods[0]:,}; LOD2 {lods[1]:,}. One material.
Pommel uses6,160 triangles, including both faces and closed end fittings.
UV0 is the surface atlas; UV1 is separately packed for lightmaps.
The tassel is posed cosmetic geometry without cloth or rigid collision.
Recreated from screenshots; unseen surfaces are authored interpretations.

UNREAL
Import main FBX at scale1, retain pivot, import normals/tangents and verify220cm
length. Use its {hulls} supplied convex UCX hulls for simple rigid collision;
do not replace them with generated collision. Three fitted hulls cover the
new pommel; the other collision shapes are preserved. Max{maxv} vertices per hull.
Small ornamental openings are filled by simple collision. Tassel, cord and beads
are excluded. Sockets: Grip, BladeTip, Pommel and Tassel. Import LOD FBXs separately
and tune screen transitions for the target camera.

One opaque material. Enable Two Sided so thin tassel ribbons show on both sides.
BaseColor: sRGB ON -> Base Color.
ORM: sRGB OFF, data/mask compression retaining alpha:
  R -> Ambient Occlusion, G -> Roughness, B -> Metallic, A -> Specular.
ORM alpha is specular data, not opacity. NormalDX: Normalmap compression,
sRGB OFF -> Normal; do not flip its green channel again. NormalGL is for
Blender/glTF. FBX material wiring does not replace explicit Unreal connections.

VERIFICATION
Pommel_Leaf_Verification.json is the current source audit. All three new parts
are closed, consistently wound and positive-volume, with valid tessellation.
Actual GAME hull face planes contain the pommel, with about0.15mm padding.
{p['wood_joint']['samples']:,} wood-joint surface samples found no protruding wood.
This is a dense sampled join check, not a continuous-solid proof.
All70 protected meshes and four atlas-file hashes match the pre-edit baseline.
Main and both LOD FBX readback passed positions, actual UV0 and custom normals;
all hulls, four sockets and2.2m scale passed. Export_Verification.json is current.
Handle_Finish_Verification.json and older audits describe historical stages.
Unreal import, material appearance, collision cooking, physics contacts and CCD
remain untested. No Unreal/Play/Blueprint/lab state changed in this task.

Recovery baseline: ../../Saved/Diagnostics/ImperialSpear/PommelLeaf/Before/.
Source scripts: ../../Tools/SpearAsset/. Handoff: ../../Docs/ImperialSpear.md.
Blender MCP used a hidden task-owned process at BelowNormal priority with three
CPU render threads and sequential stills. That process was closed after saving.
'''
(OUT/'README.txt').write_text(readme,encoding='utf-8')

docpath=ROOT/'Docs/ImperialSpear.md';doc=docpath.read_text(encoding='utf-8')
head='''# Imperial spear — current handoff

The user selected pommel concept03, **Flattened leaf**. The current source models
that design: a flattened leaf body, integrated recessed channels and beveled
borders, a rounded socket collar and blunt end cap. The rest of the accepted
spear is unchanged:70 components retain exact geometry, UVs, custom normals,
material assignments and transforms. All four atlas PNGs are byte-identical.
The modeled pommel is supplied for review; the selected concept is approved.

Current editable source: `Exports/ImperialSpear/ImperialSpear_Source.blend`.
Working copy: `Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend`.
The FBX, GLB, GAME blend, both LODs, collision and full/pommel previews are refreshed.
Selected image: `Design/ImperialSpear/PommelConcepts/03_FlattenedLeaf_Selected.png`.

'''
assert '## Current finish and geometry' in doc
doc=head+doc[doc.index('## Current finish and geometry'):]
start=doc.index('## Delivery and verification');end=doc.index('## Resume safely')
doc=doc[:start]+f'''## Delivery and verification

Length2.20m, +Z toward blade; moved grip pivot1.235m. The new pommel spans
z0–0.1281m and has three closed components/6,160triangles. Its leaf belly is
about49mm wide; the upper neck becomes round enough to enclose the existing
shaft. Cross-section channels and border bevels are integrated surfaces,
with split normals at machined edges and smooth broad faces/rounded lips.
No subdivision or live Boolean modifier is needed. Existing gold atlas reused.

LOD triangles {tri:,}/{lods[0]:,}/{lods[1]:,}; one material and4096px atlas.
UV0 is surface; UV1 is packed lightmap. {hulls} convex UCX hulls, at most{maxv}
vertices each, four sockets. Three fitted envelopes replace the old single
pommel hull; all other collider shapes are preserved. Cosmetic tassel/cord/beads
are excluded. Small negative ornament spaces are filled by simple collision.
Tassel is static, no cloth rig.

Current images: `Preview_Pommel.png`, `Preview_Pommel_Front.png`, `Preview_Full.png`.
The accepted head and handle close-ups remain valid; their surfaces are unchanged.
`README.txt` gives portable import/material instructions. Current source audit:
`Pommel_Leaf_Verification.json`; `Handle_Finish_Verification.json` and previous
audits describe their earlier stages. All70 protected full-source fingerprints
and all four atlas hashes pass. All new parts are closed/positive-volume with
valid tessellation. Actual UCX face planes enclose the pommel with~0.15mm padding.
{p['wood_joint']['samples']:,} sampled wood-joint surface points are contained by its fitted parts.
`Export_Verification.json` checks main and both LOD FBX positions, actual UV0
and custom normals; all hulls/sockets and scale pass. `SHA256_Manifest.json`
covers current files. Unreal import, cooking, material appearance, physics
contacts and CCD remain untested. No Unreal/Play/Blueprint/lab state changed.

'''+doc[end:]
marker='## Resume safely\n'
doc=doc.replace(marker,marker+'''
For this stage use `model_pommel_leaf.py`, `audit_pommel_leaf.py`,
`export_spear.py`, `verify_exports.py`, `finish_pommel_leaf.py` and
`write_pommel_handoff.py`. Do not rerun older handle/geometry/handoff writers
against the current pommel. The current pre-pommel recovery snapshot and full
baseline fingerprints are in `Saved/Diagnostics/ImperialSpear/PommelLeaf/`;
`Before/` contains the accepted previous source/game. Only the pommel may change
without a new user request. Earlier workflows below document prior stages.
''',1)
docpath.write_text(doc,encoding='utf-8')

journal=ROOT/'ProjectJournal.md';data=journal.read_text(encoding='utf-8')
block=f'''**Imperial spear October27 — selected flattened leaf pommel:**
User chose concept03. Modeled a flattened gold leaf with integrated recessed
channels, beveled borders, turned socket and blunt round cap. Other70 components
retain exact geometry/UVs/normals/material assignments/transforms; all four atlas
files are byte-identical. Accepted head, carved nervure, beads, wood_v8, leatherV5,
grip position and overall2.2m length are preserved. Pommel concept accepted;
the modeled interpretation is supplied for review.
Source/game/FBX/GLB/LODs and full/pommel previews refreshed. Triangles
{tri:,}/{lods[0]:,}/{lods[1]:,}; one material; {hulls} convex hulls, max{maxv} vertices;
four sockets. Three fitted pommel hulls replace its old single hull. Actual UCX
containment and {p['wood_joint']['samples']:,} sampled wood-join points pass. Main and both LOD
FBX positions/UV0/custom normals, hulls and scale verified. ORM alpha=Specular.
Current audit `Pommel_Leaf_Verification.json`; older handle audits are historical.
Unreal import/cooking/physics remain untested. Hidden owned Blender closed after
bounded3-thread CPU stills. No Unreal/Play/BP/lab state changed.
[Current asset handoff](Docs/ImperialSpear.md).

'''
matches=list(re.finditer(r'^\*\*Imperial spear October27[^\n]*\n.*?(?=^\*\*|\Z)',data,flags=re.S|re.M))
assert len(matches)==1,'Expected one current spear block'
match=matches[0];updated=data[:match.start()]+block+data[match.end():]
assert updated.startswith(data[:match.start()]) and updated.endswith(data[match.end():])
journal.write_text(updated,encoding='utf-8')
files=[]
for path in sorted(OUT.rglob('*')):
    if path.is_file() and path.name!='SHA256_Manifest.json' and path.suffix!='.blend1':
        files.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'SHA256_Manifest.json').write_text(json.dumps({'status':status['status'],'files':files},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'triangles':tri,'lods':lods,'hulls':hulls,'protected_components':70,'manifest_files':len(files)}))
