import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
name='Head187-'+(sys.argv[1] if len(sys.argv)>1 else 'baseline')
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=1600','clock>=240').replace('SimFootFinal',name)
src=src.replace("unreal.SystemLibrary.execute_console_command(w0,'Prophecy.PhysicalFoot.RecoveryLength 1')",'')
src=src.replace("'ball_r')","'ball_r','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head','clavicle_l','clavicle_r','hand_l','hand_r')")
src=src.replace('clock>=99999','clock>=155')
exec(compile(src,'CaptureHead187','exec'))
