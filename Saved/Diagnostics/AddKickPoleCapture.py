from pathlib import Path
p=Path('Saved/Diagnostics/CapturePunchPole.py')
s=p.read_text().replace("mode=='enabled'", "mode.endswith('enabled')")
s=s.replace("exec(compile(src,'CapturePunchPole','exec'))", """if mode.startswith('kick'):
 src=src.replace(\"   r=dict(t=t\", \"   state=a.get_nn_attack_state()\\n   if state and str(state[0]).lower()=='overr':\\n    target=a.get_nn_attack_target()[0];victim=a.get_nn_attack_victim();side='kickL' if s.get('kicks',0)%2==0 else 'kickR';s['kicks']=s.get('kicks',0)+1\\n    a.stop_nn_attack();assert a.trigger_nn_attack(side,target,False,victim)\\n   r=dict(t=t\")
exec(compile(src,'CapturePunchPole','exec'))""")
p.write_text(s)
