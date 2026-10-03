import pathlib
p=pathlib.Path('Saved/Diagnostics')
s=(p/'ReplayPelvis159.py').read_text();s=s[:s.index('geometry=')]+'''
result=[]
for f in (363,365,367,369,371,373):
 r=rows[f];pr=rows[f-2];x=np.array(r['lower_input']);pub=np.array(pr['published_lower']);raw=clean(np.array(pr['lower_input'][:41])+pr['lower_delta'][:41]);variants={'baseline':x}
 for sides in ((0,),(1,),(0,1)):
  z=x.copy()
  for i in sides:
   o=18+16*i;carry=rot(pub,o).T@rot(x,o);z[o:o+6]=(rot(raw,o)@carry)[:2].ravel();z[o+76:o+82]=(z[o:o+6]-z[o+41:o+47])/c['pose_delta_scale_final']
  variants['previous_raw_thigh_'+str(sides)]=z
 for name,ix in [('left_thigh_velocity',range(94,100)),('right_thigh_velocity',range(110,116)),('both_thigh_velocities',list(range(94,100))+list(range(110,116)))]:
  z=x.copy();z[list(ix)]=0;variants['zero_'+name]=z
 yy=predict(list(variants.values()));rec={'frame':f,'delta_cm':{k:(v[:3]*100).tolist() for k,v in zip(variants,yy)}};result.append(rec);print(json.dumps(rec),flush=True)
(d/'Pelvis360-replay.json').write_text(json.dumps({'max_replay_error':err,'rows':result},indent=2))
'''
s=s.replace('FootVibration-nn-pelvis159-baseline.jsonl','Pelvis360-baseline-nn.jsonl')
(p/'ReplayPelvis360.py').write_text(s)
