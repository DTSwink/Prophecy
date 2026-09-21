import json,pathlib,re,statistics,sys
root=pathlib.Path(__file__).parent/'Isolation'
log=(pathlib.Path(__file__).parents[2]/'Logs/GameAnimationSample3.log').read_text(errors='replace')
if (root/'native-capture.log').exists():log=(root/'native-capture.log').read_text()+log
data={}
for line in log.splitlines():
    if 'CONTACT_EXP,' not in line:continue
    f=line.split('CONTACT_EXP,',1)[1].split(',')
    try:
        name,td=f[0].rsplit('_',1);td=int(td)
        data.setdefault(name,{}).setdefault(td,{})[f[1]+':'+f[2]]=[float(x) for x in f[3:]]
    except (ValueError,IndexError):pass
report={}
for name,rows in data.items():
    stats={}
    for key,index in [('joint:hand_r',0),('joint:lowerarm_r',0),('contact:lowerarm_r_thigh_r',0),('contact:hand_r_thigh_l',1),('contact:hand_r_thigh_r',1)]:
        values=[r[key][index] for td,r in rows.items() if 95<=td<=140 and key in r]
        if values:stats[key]=dict(max=max(values),mean=statistics.mean(values),at115=rows.get(115,{}).get(key),at125=rows.get(125,{}).get(key))
    report[name]=dict(samples=len(rows),stats=stats,body_at100={k:v for k,v in rows.get(100,{}).items() if k.startswith('body:')})
root.mkdir(exist_ok=True)
(root/'native.json').write_text(json.dumps(data,indent=2))
(root/'summary.json').write_text(json.dumps(report,indent=2))
for name,r in report.items():
    print(name,r['samples'],{k:round(v['max'],3) for k,v in r['stats'].items()})
