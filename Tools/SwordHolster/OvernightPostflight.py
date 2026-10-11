"""Verify loaded graph/reflection and disk assets without saving anything."""
import unreal,pathlib,json,hashlib,argparse,re
p=argparse.ArgumentParser();p.add_argument('--label',default='postflight');a=p.parse_args()
r=pathlib.Path(unreal.Paths.project_dir());out=r/'Saved/Diagnostics/SwordOvernight20261011'
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=e.get_editor_world();assert not e.get_game_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
def read(p):
 b=p.read_bytes();return b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
def nodes(path):
 # Reload changes node iteration order; UTF-8 snapshots can double CRs.
 # Preserve every pin/default/link, including literal newline counts.
 text=re.sub(r'\r+\n','\n',read(path)).strip()
 blocks=re.split(r'\n(?=/Game/)',text)
 result={block.split('\n',1)[0]:block for block in blocks}
 assert len(result)==len(blocks),'Duplicate graph node identity'
 return result
assert nodes(r/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt')==nodes(out/'after-graph.txt'),'Unexpected graph changes'
files=['Content/testNN.umap','Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset','Content/_mygame/sword/A_Sword.uasset','Content/locomotion/SwordHolsterProfile.json']
result=dict(world=w.get_path_name(),play=False,graph_exact=True,dirty=[x.get_path_name() for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())],assets={n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in files},reflection=read(r/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt'))
assert not result['dirty'],result['dirty']
(out/(a.label+'.json')).write_text(json.dumps(result,indent=2));print(result)
