from pathlib import Path
p=Path('Tools/NN/TestProphecySword.py');s=p.read_text(encoding='utf-8');s=s.replace(",'wall_start':time.monotonic()",'');s=s.replace('time.monotonic() - watchdog_start > 60','time.monotonic() - watchdog_start > 45');s=s.replace("        # Wall-clock watchdog also catches a Blueprint pausing game time.\n        if time.monotonic()-state['wall_start']>45:raise RuntimeError('Sword test timed out (check existing Blueprint pause logic)')\n",'');p.write_text(s,encoding='utf-8');compile(s,str(p),'exec')
log=Path('Saved/Logs/GameAnimationSample3.log').read_text(encoding='utf-8',errors='replace');start=log.rfind('LogPython: GOLDEN_RULES_TESTS_REQUESTED');Path('Saved/Diagnostics/GoldenRulesFix/tests-initial.log').write_text(log[start:],encoding='utf-8')
# Validate ownership/watchdog paths without starting Unreal Play or executing the test bodies.
import ast,types
checks=[]
for name in ['TestProphecySword.py','TestFistDeformation.py','TestProphecyInterpolation.py']:
 tree=ast.parse((Path('Tools/NN')/name).read_text(encoding='utf-8'));tick=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='tick');guard=next(n for n in tick.body if isinstance(n,ast.Try))
 prefix=[]
 for n in guard.body:
  # Guard block ends immediately before original test startup/body.
  if isinstance(n,ast.If) and ast.unparse(n.test) in ["state['phase'] == -1",'not world']:break
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='world' for t in n.targets):break
  prefix.append(n)
 module=ast.fix_missing_locations(ast.Module(body=prefix,type_ignores=[]))
 current=object();owner=object()
 env=dict(time=types.SimpleNamespace(monotonic=lambda:2),watchdog_start=0,owned_world=owner,editor_guard=types.SimpleNamespace(get_game_world=lambda:current))
 try:exec(compile(module,name,'exec'),env)
 except RuntimeError as e:assert 'ended or was replaced' in str(e)
 else:raise AssertionError(name+' accepted replacement world')
 env.update(watchdog_start=-100,owned_world=None)
 try:exec(compile(module,name,'exec'),env)
 except RuntimeError as e:assert 'timed out' in str(e)
 else:raise AssertionError(name+' missing watchdog')
 checks.append({'script':name,'replacement_world_rejected':True,'watchdog_fires':True,'syntax_valid':True})
import json
Path('Saved/Diagnostics/GoldenRulesFix/script-guards.json').write_text(json.dumps(checks,indent=2),encoding='utf-8');print(checks)
