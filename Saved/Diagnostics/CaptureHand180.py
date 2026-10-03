import pathlib
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureKnee202.py').read_text()
src=src.replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag='hand180'")
src=src.replace("clock>=175","clock>=140").replace("s['frame']>=280","s['frame']>=235")
src=src.replace("bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')","bones=('pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r','neck_01','neck_02','head')")
src=src.replace('    a.set_foot_pinning_debug_enabled(True)','')
src=src.replace("s['cb']=unreal.register_slate_post_tick_callback(tick)","unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')\ns['cb']=unreal.register_slate_post_tick_callback(tick)")
exec(compile(src,'CaptureHand180','exec'))
