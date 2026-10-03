import pathlib,json,sys
p=pathlib.Path(sys.argv[1]);cfg=json.loads(pathlib.Path('Content/locomotion/NN/prophecy_slash_native.json').read_text())
rows=[json.loads(l) for l in (p/'metrics.jsonl').read_text().splitlines()]
steps=[json.loads(l) for l in (p/'slash.jsonl').read_text().splitlines()]
print('frames',max(r['frame'] for r in rows),'steps',len(steps),'bones',cfg['bone_names'])
for side in ['l','r']:
 samples=[r for r in rows if r['attack'] and r['frame']>60 and r['agent'].endswith('_1') and r['side']==side]
 for source in ['future','presented','physical']:
  r=min(samples,key=lambda r:r['poses'][source]['points'][2][2])
  step=min(steps,key=lambda s:abs(s['time']-r['time']) if s['actor']==r['agent'] else 1e9)
  i=cfg['bone_names'].index('foot_'+side)
  rawz=(step['output'][131+3*i+1]-cfg['root_position'][1])*100+step['anchor'][2]
  print(side,source,'min ankle',r['poses'][source]['points'][2][2],'t',r['time'],'frame',r['frame'],'phase',r['attack'],'raw_z',rawz,'anchorZ',step['anchor'][2],'step_dt',step['time']-r['time'])
  print('raw feet y',[(b,step['output'][131+cfg['bone_names'].index(b)*3+1]*100+step['anchor'][2]) for b in ['foot_l','ball_l','foot_r','ball_r']])
  print('display ankle/toe',r['poses'][source]['points'][2:])
