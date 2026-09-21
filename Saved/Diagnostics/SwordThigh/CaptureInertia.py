import builtins,json,pathlib,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Stop Play before starting the diagnostic'
factor=float(sys.argv[1])
label='WeldInertia_'+str(factor)
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordThigh'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Jolt.WeldInertiaDiagnostic '+str(factor))
builtins._sword_thigh_force_block=False
code=(root.parent/'CaptureSwordThigh.py').read_text()
code=code.replace("out.mkdir(parents=True,exist_ok=True)","out=out/'"+label+"'\nout.mkdir(parents=True,exist_ok=True)")
code=code.replace("r['thigh_physics']=str(a.get_physical_body_state('thigh_r'))", "r['thigh_physics']=str(a.get_physical_body_state('thigh_r'))\n                r['hand_physics']=str(a.get_physical_body_state('hand_r'))")
exec(compile(code,'CaptureSwordInertia','exec'))
