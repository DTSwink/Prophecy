import unreal as u,json
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
u.EditorPythonScripting.set_keep_python_script_alive(True)
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Studio';out.mkdir(parents=True,exist_ok=True)
for cmd in ['t.MaxFPS 24','r.MotionBlurQuality 0']:u.SystemLibrary.execute_console_command(ed.get_editor_world(),cmd)
rows={}
for name in ['r.RefractionQuality','r.ReflectionEnvironment','r.SSR.Quality','r.ForwardShading','r.TranslucentLightingVolume','r.SeparateTranslucency','r.AllowStaticLighting','r.Lumen.TranslucencyReflections.FrontLayer.Enable','r.EyeAdaptationQuality']:
 rows[name]=u.SystemLibrary.get_console_variable_int_value(name)
rows['actors']=[{'label':a.get_actor_label(),'class':a.get_class().get_name(),'position':str(a.get_actor_location())} for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()]
rows['MaterialDoc']=u.Material.__doc__
rows['PPDoc']=u.PostProcessSettings.__doc__
rows['ThinOutput']=str(getattr(u,'MaterialExpressionThinTranslucentMaterialOutput',None))
rows['RefractionEnum']=str(dir(getattr(u,'RefractionMode',None)))
(out/'inspect.json').write_text(json.dumps(rows,indent=2))
print('OIL_STUDIO_READY')
