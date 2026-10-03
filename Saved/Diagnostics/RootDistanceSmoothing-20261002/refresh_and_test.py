import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootDistanceSmoothing-20261002'
w=ed.get_game_world()
d=dict(user_play_active=w is not None)
if w is None:
 w=ed.get_editor_world()
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshRootWindowDistance')
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
 (root/'graph-after.txt').write_bytes((root.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
 d['setter_report']=(root.parent/'RootWindowDistanceSetterPins.txt').read_text(encoding='utf-8-sig')
 d['getter_report']=(root.parent/'RootWindowDistanceGetterPins.txt').read_text(encoding='utf-8-sig')
 d['default_values']=unreal.get_default_object(unreal.ProphecyNNRootWindowLibrary).call_method('GetLocomotionRootWindowSmoothing',(None,))
 unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.RootWindow.IndependentFactors+Prophecy.NN.RootWindow.AccelerationDeceleration')
(root/'editor.json').write_text(json.dumps(d,indent=2,default=str),encoding='utf8')
print('ROOT_DISTANCE_UPDATED',d)
