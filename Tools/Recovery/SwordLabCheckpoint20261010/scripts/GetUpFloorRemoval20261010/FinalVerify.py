import unreal,pathlib,json,hashlib,re
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpFloorRemoval20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
verification=json.loads((out/'verification.json').read_text());smoke=json.loads((out/'smoke.json').read_text());assert smoke['reason']=='passed',smoke
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
assert (root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes()==(out/'graph-after.txt').read_bytes()
assert hashlib.sha256((root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset').read_bytes()).hexdigest()==verification['blueprint_sha256']
build=(out/'build3.log').read_text(encoding='utf-8-sig');assert 'Result: Succeeded' in build
receipt={'date':'2026-10-10','removed':'Automatic get-up PHAT floor-clearance lift, support cache, profile flag, Blueprint setter and feature-only tests/diagnostic fields.',
 'preserved':'Original clip-height alignment and Ground Offset, entry blend, magnetization, simulation, handoffs and all user Blueprint settings apart from removal of the obsolete call.',
 'editor_restarts':1,'restart_reason':'Retained native profile/active-state layout and reflected function removal; not safe for Live Coding.',
 'build_seconds':re.findall(r'Total execution time: (.*)',build)[-1],'first_build_attempt':'Refused during graceful editor shutdown while Live Coding was still active; retried after exit, no extra restart.',
 'second_build_attempt':'Runtime compiled; editor helper had an auto-pointer deduction error for TObjectPtr graph nodes. Fixed with explicit UEdGraphNode pointer; final build recompiles editor module only.',
 'verification':verification,'play':smoke,'map':ed.get_editor_world().get_path_name(),'dirty':[],
 'full_evidence':'Saved/Diagnostics/GetUpFloorRemoval20261010'}
(root/'Tools/Recovery/GetUpFloorRemoval20261010.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
