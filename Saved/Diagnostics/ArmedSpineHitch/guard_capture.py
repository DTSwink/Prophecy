from pathlib import Path
for file in ['capture.py','capture_after.py']:
 p=Path('Saved/Diagnostics/ArmedSpineHitch')/file;s=p.read_text(encoding='utf-8');pos=s.index("exec(compile(src,")
 s=s[:pos]+'''src=src.replace("if owned and ed.get_game_world():level.editor_request_end_play()", "if owned and s.get('owned_world') is not None and ed.get_game_world()==s['owned_world']:level.editor_request_end_play()")
src=src.replace("  t=unreal.GameplayStatics.get_time_seconds(w)", "  if s.get('owned_world') is None:s['owned_world']=w\\n  elif w!=s['owned_world']:finish('Owned world replaced');return\\n  t=unreal.GameplayStatics.get_time_seconds(w)")
'''+s[pos:];p.write_text(s,encoding='utf-8')
