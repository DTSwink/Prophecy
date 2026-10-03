import json,pathlib,numpy as np
from ReplayTemperedLeg import rot,offsets
D=pathlib.Path('Saved/Diagnostics');rows={r['tick']:r for r in json.loads((D/'Hover260.json').read_text())['rows']}
for x in map(json.loads,(D/'Hover260-nn.jsonl').read_text().splitlines()):
 n=round(x['time']*60)
 if not x['actor'].endswith('_C_1') or not 255<=n<=271:continue
 s=np.array(x['published_lower']);hip=s[:3]+offsets[17]@rot(s,3);knee=hip+offsets[18]@rot(s,18);end=s[9:12];L=np.linalg.norm(offsets[19]);Dlt=end-knee
 out=knee+Dlt*(L/np.linalg.norm(Dlt));rootZ=x['roots'][9]*100
 target=np.array(rows[n]['targets']['foot_l'][1]['p'])
 print(n,'length excess cm',round((np.linalg.norm(Dlt)-L)*100,5),'clamp lift',round((out[2]-end[2])*100,5),'unclamp worldZ',round(end[2]*100+rootZ,5),'clamp worldZ',round(out[2]*100+rootZ,5),'actual worldZ',round(target[2],5),'pelvis match',round(rows[n]['targets']['pelvis'][1]['p'][2]-(s[2]*100+rootZ),5))
r=json.loads((D/'Hover260KneeCheck.json').read_text())['rows'][-1]
print('sameinput smoothing difference',np.array(r['targets']['foot_l'][2]['p'])-r['without_knee_smoothing']['foot_l'][2]['p'])
a=json.loads((D/'Hover260.json').read_text())['rows'];b=json.loads((D/'Hover260KneeCheck.json').read_text())['rows'];print('prefix equal',max(np.linalg.norm(np.array(x['targets']['foot_l'][1]['p'])-y['targets']['foot_l'][1]['p']) for x,y in zip(a,b)))
