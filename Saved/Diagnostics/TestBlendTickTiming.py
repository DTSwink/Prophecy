import unreal, sys
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Leave user PIE untouched'
tests = ['Prophecy.Blends.SixtyTickClock', 'Prophecy.NN.LowerTempering.ReturnTimeline',
         'Prophecy.NN.PolicyBlend', 'Prophecy.Agent.PhysicalContext.SelectionAndAttacks',
         'Prophecy.Agent.PhysicalBlends.RuntimeAndBatch']
if len(sys.argv)>1:
    tests=sys.argv[1:]
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Automation RunTests ' + '+'.join(tests))
print('Requested focused blend timing checks; no gameplay scene or assets changed.')
