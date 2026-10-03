import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active user Play'
log=p.parent/'Logs/GameAnimationSample3.log'
log_offset=log.stat().st_size
src=(p/'CaptureSupportingKneeLead.py').read_text(encoding='utf-8')
src=src.replace('SupportingKneeLead-live.json','FootHoverCurrent-live.json').replace('_supporting_knee_lead','_foot_hover_current')
src=src.replace('>=360','>=600').replace('>45','>65')
src=src.replace('q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])','q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],s=[x.scale3d.x,x.scale3d.y,x.scale3d.z])')
src=src.replace("s['last']=t", "s['last']=t\n  if not s['rows']:unreal.SystemLibrary.execute_console_command(w,'Prophecy.PhysicalFoot.TraceFrames 1400')")
src=src.replace("unreal.unregister_slate_post_tick_callback(s['cb'])", "unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.PhysicalFoot.TraceFrames 0')\n with log.open('rb') as f:\n  f.seek(log_offset);(log.parent.parent/'Diagnostics/FootHoverCurrent-drive.log').write_bytes(b'\\n'.join(x for x in f.read().splitlines() if b'FootRecoveryTarget' in x))")
src=src.replace("s['rows'].append(r)","r['magnetisation']={b:str(a.get_body_magnetization_settings(b)) for b in ('pelvis','calf_l','foot_l','calf_r','foot_r')}\n   s['rows'].append(r)")
exec(compile(src,str(p/'CaptureFootHover.py'),'exec'),{'__name__':'foot_hover_current','log':log,'log_offset':log_offset})
