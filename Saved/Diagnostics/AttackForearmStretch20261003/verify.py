import unreal,pathlib,json
p=pathlib.Path(unreal.Paths.project_dir()).resolve()
d=p/'Saved/Diagnostics/AttackForearmStretch20261003'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
assert '/Game/testNN' in ed.get_editor_world().get_path_name()
assert hasattr(unreal.ProphecyAttackWristLibrary,'set_attack_forearm_stretch_return')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.WireForearmStretchReturn')
report=(d/'wiring.txt').read_text(encoding='utf-8-sig')
assert 'connections_ok=1 status=3' in report,report
assert 'wrist_free_defaults_changed=1' in report,report
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
inspection=(p/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in inspection and 'native_properties=0 pin_types=0' in inspection,inspection
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(d/'after-graph.txt').write_bytes((p/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
(d/'editor-verification.json').write_text(json.dumps(dict(wiring=report,inspection=inspection,saved=True)))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Attack.ForearmStretch.Return+Prophecy.Jolt.Joints.WristSignedReturn+Prophecy.NN.AttackWrist.Math+Prophecy.NN.AttackWrist.Modes+Prophecy.NN.AttackEntry.HandReference+Prophecy.NN.AttackEntry.HandLifecycle')
print('WIRED_SAVED_AND_TESTS_STARTED',report)
