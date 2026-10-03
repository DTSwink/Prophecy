exec(open('Saved/Diagnostics/AnalyzeHead187.py').read().split("for t in range(1,max(r)+1)")[0])
base=r;report={}
for mode in ('baseline','repeat','chainoff','armoff'):
 d=json.loads((p/f'Head187-{mode}-capture.json').read_text());assert d['reason']=='Complete',d['reason'];r={x['tick']:x for x in d['rows']}
 prefix=max(np.linalg.norm(np.array(b(t,n)['p'])-base[t]['targets'][n]['target']['p']) for t in range(20,171) for n in r[t]['targets'])
 pos=max(np.linalg.norm(np.array(b(t,'head')['p'])-base[t]['targets']['head']['target']['p']) for t in range(181,190))
 velocities={t:v(t,'head').tolist() for t in (180,182,184,186,188,190)}
 report[mode]={'prefix_position_error_cm':prefix,'head_difference_181_189_cm':pos,'head_velocity_cm_per_tick':velocities}
 print(mode,'prefix',prefix,'headDifference',pos,'Xvel',[(t,round(x[0],4)) for t,x in velocities.items()])
(p/'Head187-comparison.json').write_text(json.dumps(report,indent=2))
