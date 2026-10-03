import json,pathlib,numpy as np
root=pathlib.Path('Saved/Diagnostics/Knee202')
def read(mode):
 d=json.loads((root/('entry_hands_'+mode+'.json')).read_text());assert d['reason']=='Complete',d['reason'];return {r['tick']:r for r in d['rows']}
base=read('disabled')
for mode in ('zero','mixed','pelvis','spine'):
 if not (root/('entry_hands_'+mode+'.json')).exists():continue
 rows=read(mode);pre=0.;maxhand=0.;finite=True;first=None;ends=[];last=None
 for t,r in rows.items():
  if r['attack']!=last:ends.append((t,r['attack']));last=r['attack']
  if r['attack']!='None' and first is None:first=t
  for b,v in r['raw'].items():
   p=np.array(v['future']['p']);q=np.array(v['future']['q']);finite&=bool(np.isfinite(p).all() and np.isfinite(q).all() and abs(np.linalg.norm(q)-1)<1e-4)
   d=np.linalg.norm(p-base[t]['raw'][b]['future']['p'])
   if first is None:pre=max(pre,d)
   if b=='hand_r':maxhand=max(maxhand,d)
 print(mode,'rows',len(rows),'finite',finite,'pre-entry delta cm',pre,'max NN right hand delta cm',maxhand,'first attack',first)
 print('attack exit ticks',[t for t,a in ends if a=='None'])
