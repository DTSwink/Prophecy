import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'CaptureKnee202.py').read_text()
src=src.replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag='armed_spine_before'")
src=src.replace("bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')", "bones=('pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')")
src=src.replace("if owned and clock>=175 and not s['tracing']:","if False:")
src=src.replace("if s['frame']>=280:","if s['frame']>=230:")
src=src.replace("if owned and ed.get_game_world():level.editor_request_end_play()", "if owned and s.get('owned_world') is not None and ed.get_game_world()==s['owned_world']:level.editor_request_end_play()")
src=src.replace("  t=unreal.GameplayStatics.get_time_seconds(w)", "  if s.get('owned_world') is None:s['owned_world']=w\n  elif w!=s['owned_world']:finish('Owned world replaced');return\n  t=unreal.GameplayStatics.get_time_seconds(w)")
exec(compile(src,'CaptureArmedSpineHitch','exec'))
