import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm_body_first_attack'").replace('clock>=140','clock>=110').replace("s['frame']>=235","s['frame']>=260")
inject="""   r['pairs']={arm+'|'+body:str(a.get_jolt_body_pair_self_collision_enabled(arm,body)) for arm in ('upperarm_r','lowerarm_r','hand_r') for body in ('pelvis','spine_01','spine_03','spine_05','head')}
   r['hand_physical']=str(a.get_physical_body_state('hand_r'))
"""
src=src.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   s['rows'].append(r)\",inject+\"   s['rows'].append(r)\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(src,'CaptureArmBody','exec'))
