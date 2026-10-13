"""Preserve the user's current assets before the new reflected reach/grab nodes build."""
import pathlib, shutil, json, unreal
root=pathlib.Path(unreal.Paths.project_dir())
out=root/'Saved/Diagnostics/ReachGrasp20261012'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User Play must remain untouched'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
allowed=['/Game/testNN','/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent','/Game/_mygame/sword/A_Sword']
assert all(p.get_path_name() in allowed for p in dirty),str([p.get_path_name() for p in dirty])
files=['Content/testNN.umap','Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset','Content/_mygame/sword/A_Sword.uasset','Content/locomotion/SwordHolsterProfile.json','Labs/SwordHolsterLab/state.json']
for f in files: shutil.copy2(root/f,out/(pathlib.Path(f).name+'.before-build'))
assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty,False)
for f in files: shutil.copy2(root/f,out/(pathlib.Path(f).name+'.preserved'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',out/'graph-before.txt')
(out/'preservation.json').write_text(json.dumps({'saved_dirty':[p.get_path_name() for p in dirty]}),encoding='utf-8')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'CLOSE_SLATE_MAINFRAME')
