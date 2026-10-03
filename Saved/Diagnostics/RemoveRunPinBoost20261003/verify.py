import unreal,pathlib,json,re
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert '/Game/testNN' in ed.get_editor_world().get_path_name()
assert ed.get_game_world() is None
for name in ('set_run_pinning_boost','get_run_pinning_boost','set_attack_recovery_run_pinning_boost'):
    assert not hasattr(unreal.ProphecyWalkPinningLibrary,name),name
assert not hasattr(unreal.ProphecyAgent,'set_locomotion_foot_pinning_threshold')
assert 'alpha_hold' in unreal.ProphecyFKReturnLibrary.set_attack_fk_return.__doc__
root=pathlib.Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/Diagnostics/RemoveRunPinBoost20261003'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
inspection=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in inspection and 'native_properties=0 pin_types=0' in inspection,inspection
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes()
def normalized(data):
    text=data.decode('utf-16' if data[:2]==b'\xff\xfe' else 'utf-8-sig')
    # Cold loading canonicalizes archived static-library CDOs and clears the
    # unused default of InputKey's unconnected output; actual key titles remain.
    text=re.sub(r'/Engine/Transient.BPGC_ARCH_FOR_CDO_(\w+)_\d+',r'/Script/GameAnimationSample3.Default__\1',text)
    sections=text.split('\n\n')
    return '\n\n'.join(s.replace('  Key=None None ->','  Key= None ->') if ' | K2Node_InputKey_' in s.split('\n')[0] else s for s in sections)
assert normalized(graph)==normalized((out/'after-graph.txt').read_bytes()),'Graph changed after cold restart'
(out/'cold-verification.json').write_text(json.dumps(dict(removed_apis=True,graph_unchanged_after_canonicalization=True,inspection=inspection,world=ed.get_editor_world().get_path_name()),indent=2))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackControls.ArmedGate+Prophecy.NN.AttackControls.EntryMagicAndTicks+Prophecy.NN.SpecialRecovery.RegionalOwnership+Prophecy.NN.WalkPinning+Prophecy.NN.RootWindow')
print('COLD_LOAD_VERIFIED; focused checks requested')
