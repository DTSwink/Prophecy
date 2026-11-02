"""Publish verified asset files and concise current handoff, without lab edits."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028';D=R/'Exports/ImperialSpear'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
fbx=json.loads((O/'FBX_Verification.json').read_text());source=json.loads((O/'Source_Audit.json').read_text());trials=json.loads((O/'Reduction_Trials.json').read_text());images=json.loads((O/'Render_Comparison.json').read_text());readback=json.loads((O/'Blender_FBX_Readback.json').read_text())
assert readback['status']=='PASS'
assert sha(D/'SM_ImperialSpear.fbx')==sha(O/'Before_UserFinal.fbx'),'Main FBX changed outside this task'
assert sha(O/'SM_ImperialSpear.fbx')==fbx['sha256']
assert sha(R/'Saved/Diagnostics/ImperialSpear/PommelLotus/Working.blend')==sha(O/'Before_UserFinal.blend')
shutil.copy2(O/'SM_ImperialSpear.fbx',D/'SM_ImperialSpear.fbx')
for view in ('head','pommel'):
 shutil.copy2(O/(view+'_After.png'),D/('Preview_Optimized_'+view.title()+'.png'))
changes=[{'component':c['name'],'before':c['before'],'after':c['after'],'max_sampled_deviation_mm':next((t['deviation']['max_mm'] for t in c['trials'] if t['passed']),0)} for c in trials['components'] if c['accepted']]
report={'status':'VERIFIED_SOURCE_AND_MAIN_FBX','date':'2026-10-28','before_triangles':source['before_triangles'],'after_triangles':source['after_triangles'],'triangles_removed':source['before_triangles']-source['after_triangles'],'reduction_percent':100*(1-source['after_triangles']/source['before_triangles']),'vertices':source['vertices'],'max_sampled_surface_deviation_mm':max(c['max_sampled_deviation_mm'] for c in changes),'components':changes,'render_comparison':images,'fbx_readback':readback,'fbx_sdk_readback':fbx,'collision_hulls':17,'sockets':4,'collision_and_sockets_unchanged':True,'source_manual_transforms_preserved':True,'original_working_blend_untouched':True,'texture_hashes':source['texture_hashes'],'files':{name:sha(D/name) for name in ('ImperialSpear_Optimized.blend','SM_ImperialSpear.fbx')},'unreal_import_tested':False,'lab_cache_refreshed':False,'historical_not_refreshed':['ImperialSpear_Source.blend','ImperialSpear_Game.blend','SM_ImperialSpear.glb','SM_ImperialSpear_LOD1.fbx','SM_ImperialSpear_LOD2.fbx','Asset_Report.json','Export_Verification.json'],'backup':str(O)}
(D/'Optimization_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
status=D/'DELIVERY_STATUS.json'
if status.exists():shutil.copy2(status,O/'Before_DELIVERY_STATUS.json')
status.write_text(json.dumps({k:report[k] for k in ('status','date','before_triangles','after_triangles','reduction_percent','files','historical_not_refreshed','unreal_import_tested','lab_cache_refreshed','backup')},indent=2),encoding='utf-8')
body='''**October28 — reviewed selective topology reduction.**
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
and were not refreshed by this pass. Throw Lab cache and Unreal remain untouched.
This block supersedes the previous current-source and polygon-count claims below.

'''
p=R/'Docs/ImperialSpear.md';text=p.read_text(encoding='utf-8');heading='# Imperial spear — current handoff\n\n';assert text.startswith(heading);p.write_text(heading+body+text[len(heading):],encoding='utf-8')
p=D/'README.md'
if p.exists():
 text=p.read_text(encoding='utf-8');shutil.copy2(p,O/'Before_README.md');p.write_text('# Current optimized delivery — October28\n\n'+body+text,encoding='utf-8')
journal=R/'ProjectJournal.md';text=journal.read_text(encoding='utf-8');marker='## Resume here\n\n';assert marker in text
entry='''**Imperial spear October28 — selective topology reduction complete:**
New editable `Exports/ImperialSpear/ImperialSpear_Optimized.blend` and refreshed
mainFBX preserve final user grip/blade transforms.59,460→43,494triangles(-26.85%);
guard/crown/scrolls/pommel selectively reduced, sampled deviation<0.04mm.
Matched PBR close-ups, source UV/normal/topology checks and actualFBX readback pass.
Original atlas/shared material,17 corrected UCX hulls and4 sockets preserved.
Original Working.blend/open user Blender and all lab/Unreal state untouched.
Older GLB/LODs/Source/Game blends/reports remain historical. Current details and
recovery: [Imperial spear handoff](Docs/ImperialSpear.md).

'''
journal.write_text(text.replace(marker,marker+entry,1),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('before_triangles','after_triangles','reduction_percent','max_sampled_surface_deviation_mm','files')},indent=2))
