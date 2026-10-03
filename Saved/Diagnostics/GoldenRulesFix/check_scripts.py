from pathlib import Path
for name in ['TestFistDeformation.py','TestProphecyInterpolation.py']:
 p=Path('Tools/NN')/name;s=p.read_text()
 s=s.replace('finished = False','finished = False\ndiagnostic_ticks = 0\nlast_world_time = None')
 s=s.replace('global owned_world\n','global owned_world, diagnostic_ticks, last_world_time\n')
 mark='            owned_world = current_world\n'
 s=s.replace(mark,mark+'''        if current_world is not None:
            stamp = unreal.GameplayStatics.get_time_seconds(current_world)
            if stamp != last_world_time:
                last_world_time = stamp
                if not unreal.GameplayStatics.is_game_paused(current_world): diagnostic_ticks += 1
''')
 s=s.replace('def now(): return unreal.GameplayStatics.get_time_seconds(world)','def now(): return diagnostic_ticks / 60.0')
 s=s.replace('now = unreal.GameplayStatics.get_time_seconds(world)','now = diagnostic_ticks / 60.0')
 p.write_text(s)
 compile(s,str(p),'exec')
compile(Path('Tools/NN/TestProphecySword.py').read_text(),'TestProphecySword.py','exec')
print('Diagnostic scripts parse successfully')
