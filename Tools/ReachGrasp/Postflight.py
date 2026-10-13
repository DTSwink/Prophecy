import unreal, pathlib, hashlib, json
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/ReachGrasp20261012'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=['Content/testNN.umap','Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset','Content/_mygame/sword/A_Sword.uasset','Content/locomotion/SwordHolsterProfile.json','Labs/SwordHolsterLab/state.json']
result={'assets':{f:sha(root/f)==sha(out/(pathlib.Path(f).name+'.preserved')) for f in files},'graph_exact':(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes()==(out/'graph-before.txt').read_bytes(),'reach_library':bool(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyReachLibrary')),'dirty':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(out/'postflight.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
