import json,pathlib,re
p=pathlib.Path('Saved/Diagnostics/MagnetizationLocal20261006')
result={}
for name in ['global-baseline','target-only','local-final']:
 f=p/(name+'.json')
 if not f.exists():continue
 d=json.loads(f.read_text());assert d['reason']=='complete',d['reason']
 rows=d['rows'];assert rows
 result[name]={'samples':len(rows),'last_tick':max(r['tick'] for r in rows),'peaks':{k:max(r[k] for r in rows) for k in ['max_speed','max_spin','max_distance_from_pelvis']},'agents':sorted(set(r['actor'] for r in rows))}
 assert result[name]['peaks']['max_distance_from_pelvis']<180,result[name]
 if name=='target-only':
  hold={r['tick']:r['mode'] for r in rows if r['actor'].endswith('Agent2') and r['tick']>=700}
  assert hold[730]==1 and hold[745]==.5 and hold[760]==0,hold
  result[name]['hold_samples']={t:hold[t] for t in [700,730,745,760,800]}
text=(p/'graph.txt').read_text(encoding='utf-16')
blocks=[b for b in text.split('\n\n') if re.search(r' \| Blend\w+ToSnapshot\n',b)]
assert blocks and all('HoldOutTime=0.000000' in b for b in blocks)
result['existing_snapshot_nodes_with_zero_hold']=len(blocks)
f=p/'editor-final.log'
if f.exists():
 log=f.read_text(encoding='utf-8-sig',errors='replace')
 tests=re.findall(r'Test Completed. Result=\{(\w+)\} Name=\{[^}]+\} Path=\{([^}]+)\}',log)
 if tests:
  assert len(tests)==24 and all(r=='Success' for r,n in tests),tests
  result['native_tests']=[n for r,n in tests]
(p/'validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))