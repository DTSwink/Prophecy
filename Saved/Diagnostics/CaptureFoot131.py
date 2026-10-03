import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureKnee202.py').read_text().replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag='foot131'").replace('clock>=175','clock>=110').replace("s['frame']>=280","s['frame']>=155").replace('    a.set_foot_pinning_debug_enabled(True)','')
src=src.replace("   s['rows'].append(r)","   r['foot_owner']=str(unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a))\n   r['foot_physical']=str(a.get_physical_body_state('foot_r'))\n   s['rows'].append(r)")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
exec(compile(src,'CaptureFoot131','exec'))
