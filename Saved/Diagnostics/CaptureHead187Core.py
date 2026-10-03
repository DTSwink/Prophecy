import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
mode=sys.argv[1];switch=137 if mode=='coreearly' else 171
call='unreal.ProphecyCoreTemperingLibrary.set_locomotion_fk_core_tempering(agent,False,1.0)'
base=(p/'CaptureHead187.py').read_text()
base=base.replace("exec(compile(src,'CaptureHead187','exec'))", "src=src.replace('  if clock>=20:', \"  if clock>=\"+str(switch)+\" and not s.get('switched'):\\n   for agent in agents:\\n    if agent.is_player_controlled():\\n     assert \"+call+\"\\n     s['switched']=clock\\n  if clock>=20:\")\nexec(compile(src,'CaptureHead187','exec'))")
exec(compile(base,'Head187Core','exec'))
