import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'on';switch=int(sys.argv[2]) if len(sys.argv)>2 else 320
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=99999','clock>=300').replace('clock>=1600','clock>=520').replace('SimFootFinal','PelvisWide-'+mode)
if mode!='on':
 src=src.replace('  if clock>=20:', "  if clock>="+str(switch)+" and not s.get('switched'):\n   for agent in agents:\n    if agent.is_player_controlled():\n     assert unreal.ProphecyLegChainDebugLibrary.set_leg_chain_reconstruction(agent,False)\n     s['switched']=clock;print('RECONSTRUCTION_DISABLED_AT',clock)\n  if clock>=20:")
src=src.replace("    s['rows'].append(r)","    r['actor_transform']=tr(a.get_actor_transform())\n    s['rows'].append(r)")
exec(compile(src,'CapturePelvisWide','exec'))
