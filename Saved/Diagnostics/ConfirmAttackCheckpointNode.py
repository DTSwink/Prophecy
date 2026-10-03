import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('WORLD',ed.get_editor_world().get_path_name())
print('CHECKPOINT_NODES',[n for n in dir(unreal.ProphecyAttackCheckpointLibrary) if 'checkpoint' in n])
print('CHOICES',unreal.ProphecyAttackCheckpoint.CURRENT174664,unreal.ProphecyAttackCheckpoint.PREDICTIVE_PIN160664)
print('PLAY_RUNNING',ed.get_game_world() is not None)
