import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('ATTACK_CONTROLS_PIE_PRESERVED', bool(ed.get_game_world()))
lib = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAttackControlLibrary'))
# Newly Live-Coded enums lack Python wrappers until restart; use the native checks.
print('ATTACK_CONTROLS_EMPTY', lib.call_method('GetNNAttackColliders', (None,)))
agent = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAgent'))
for name in ('get_nn_attack_state', 'blend_physical_feedback_tolerance', 'blend_physical_feedback_tolerance_below', 'cancel_physical_feedback_tolerance_blend'):
    print('EXISTING_BP_API', name, hasattr(agent, name))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.Attack.Controls.HistoryAndColliders+Prophecy.Agent.PhysicalBlends.RuntimeAndBatch+Prophecy.Agent.PhysicalContext.SelectionAndAttacks')

