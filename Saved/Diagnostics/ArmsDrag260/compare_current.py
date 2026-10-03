import pathlib,json,math
p=pathlib.Path(__file__).parent
exec((p/'analyze.py').read_text().split('allrows=')[0])
tags=['current_no_recoil','no_exit_inertia','no_post_armed_pose','no_post_cone','no_post_modifiers','current_trace']
rows={tag:read(tag) for tag in tags if (p/(tag+'.json')).exists()}
base=rows['current_no_recoil']
for tag,rr in rows.items():
 print('\n',tag,'pre-exit diff',max(dist(r['future']['hand_l']['p'],base[t]['future']['hand_l']['p']) for t,r in rr.items() if t<=183))
 for t in [183,195,210,220,230,240,250,260,280]:
  r=rr[t]; root=r['future']['pelvis']['p'];old=rr[t-10]['future']['pelvis']['p'];v=[root[0]-old[0],root[1]-old[1],0];length=math.sqrt(sum(x*x for x in v));v=[x/length for x in v]
  forward=[round(sum((r['future'][h]['p'][i]-root[i])*v[i] for i in range(3)),2) for h in ['hand_l','hand_r']]
  delta=[round(dist(r['local'][h],base[t]['local'][h]),3) for h in ['hand_l','hand_r']]
  print(t,'forward',forward,'diff',delta)
print('attack changes')
prev=None
for t,r in base.items():
 if r['attack']!=prev:print(t,r['attack']);prev=r['attack']
