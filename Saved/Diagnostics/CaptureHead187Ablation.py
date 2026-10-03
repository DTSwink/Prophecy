import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';mode=sys.argv[1]
src=(p/'CaptureHead187.py').read_text()
src=src.replace("exec(compile(src,'CaptureHead187','exec'))", "src=src.replace('  if clock>=20:', \"  if clock>=171 and not s.get('switched'):\\n   for agent in agents:\\n    if agent.is_player_controlled():\\n     assert \"+call+\"\\n     s['switched']=clock\\n  if clock>=20:\")\nexec(compile(src,'CaptureHead187','exec'))")
call='unreal.ProphecyLegChainDebugLibrary.set_leg_chain_reconstruction(agent,False)' if mode=='chainoff' else 'unreal.ProphecySlashReturnLibrary.set_slash_right_arm_return_to_neutral(agent,False,0,0,0)'
exec(compile(src,'Head187Ablation','exec'))
