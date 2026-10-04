import unreal,pathlib,json
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/NNModifiers20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert ed.get_game_world() is None,'Preserve user Play'
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNModifierDebugLibrary');assert cls,'New node not reflected'
for c in ('Prophecy.Editor.RepairLibraryDefaults','Prophecy.Editor.LiveAgentTypes Inspect'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
(p/'verification.json').write_text(json.dumps(dict(node_class=cls.get_path_name(),inspection=r,play=False),indent=2))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'after-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.Modifiers+Prophecy.NN.FKReturn+Prophecy.Attack.MotionInertia.ReturnHandoff+Prophecy.Blends.SixtyTickClock')
print('REFLECTION_BP_VERIFIED_AND_TESTING',r)
