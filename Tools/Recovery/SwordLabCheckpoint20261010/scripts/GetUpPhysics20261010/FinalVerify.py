import unreal,pathlib,json,hashlib,re
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpPhysics20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=(out.parent/'SwordThigh/BlueprintGraph.txt').read_bytes()
assert graph==(out/'graph-before.txt').read_bytes()
(out/'graph-final.txt').write_bytes(graph)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
types=(out.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'native_properties=0 pin_types=0 status=3' in types
log=(out.parent/'GetUpFloorRemoval20261010/editor.log').read_text(encoding='utf-8',errors='replace')
result={'implementation':'arms forced before lower marker; mode0 to1 at marker; material restored from slot1',
 'build':'Live Coding succeeded, 536.67 seconds; reload completed; normal DLL build required before cold launch',
 'editor_restarts':0,'graph_identical':True,'reflection':types.strip(),'play':False,
 'native_tests':'Extended and compiled; not executed in interactive editor. Actual Play checks below executed.',
 'dirty':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
 'checks':{},'assets':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset',root/'Content/testNN.umap']}}
for tag in ['material','null','cancel']:
 data=json.loads((out/(tag+'-smoke.json')).read_text(encoding='utf-8'))
 assert data['reason']=='passed',data
 motors={int(n):(int(l),int(r)) for n,l,r in re.findall(r'ARM_MOTORS,getupphysics_'+tag+r'_(\d+),left=(\d+),right=(\d+)',log)}
 assert motors[29]==(0,3) and motors[30]==(3,3) and motors[31]==(3,3),motors
 assert motors[data['rows'][-1]['tick']]==(0,3),motors
 result['checks'][tag]={'passed':True,'motors':motors,'entry':data['rows'][1]['inspect'],'release':data['rows'][-2]['inspect']}
assert result['assets']['Content\\testNN.umap']==json.loads((out/'before.json').read_text(encoding='utf-8'))['assets']['Content\\testNN.umap']
(root/'Tools/Recovery/GetUpPhysics20261010.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
