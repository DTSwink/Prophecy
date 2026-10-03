import pathlib,json,math
p=pathlib.Path(__file__).parent
exec((p/'analyze.py').read_text().split('allrows=')[0])
base,after=read('current_no_recoil'),read('fixed_feedback')
out={'pre_exit_max_cm':max(dist(base[t]['future'][h]['p'],after[t]['future'][h]['p']) for t in base if t<183 for h in ['hand_l','hand_r']), 'samples':[]}
for t in [195,210,220,230,240,250,260,280]:
 row={'tick':t}
 for tag,rr in [('before',base),('after',after)]:
  root=rr[t]['future']['pelvis']['p'];old=rr[t-10]['future']['pelvis']['p'];v=[root[0]-old[0],root[1]-old[1],0];length=math.sqrt(sum(x*x for x in v));v=[x/length for x in v]
  row[tag]=[round(sum((rr[t]['future'][h]['p'][i]-root[i])*v[i] for i in range(3)),3) for h in ['hand_l','hand_r']]
 out['samples'].append(row)
print(json.dumps(out,indent=2));(p/'fixed_analysis.json').write_text(json.dumps(out,indent=2))
