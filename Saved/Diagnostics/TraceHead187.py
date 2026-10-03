exec(open('Saved/Diagnostics/AnalyzeHead187.py').read().split("for t in range(1,max(r)+1)")[0])
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def rot(s,o):
 a=unit(s[o:o+3]);c=unit(np.cross(a,s[o+3:o+6]));return np.array([a,np.cross(c,a),c])
nn={round(x['time']*60):x for x in map(json.loads,(p/'Head187-baseline-nn.jsonl').read_text().splitlines()) if x['actor']==r[181]['actor']}
report=[]
for t in range(173,194,2):
 x=nn[t];raw=np.array(x['upper_input'][90:180])+x['upper_delta'];actual=np.array(nn[t+2]['previous_upper']);errors=[]
 for o in range(0,60,6):errors.append(np.degrees((R.from_matrix(rot(raw,o).T)*R.from_matrix(rot(actual,o).T).inv()).magnitude()))
 rawlower=np.array(x['lower_input'][:41])+x['lower_delta'][:41];pelvis_error=np.linalg.norm(rawlower[:3]-x['published_lower'][:3])*100
 head=np.array(b(t+1,'head')['p']);old=np.array(b(t-1,'head')['p']);pv=(np.array(b(t+1,'pelvis')['p'])-b(t-1,'pelvis')['p'])/2
 q=R.from_quat(b(t+1,'pelvis')['q']);qp=R.from_quat(b(t-1,'pelvis')['q']);oldlocal=qp.inv().apply(old-np.array(b(t-1,'pelvis')['p']));newlocal=q.inv().apply(head-np.array(b(t+1,'pelvis')['p']))
 rotation=(q.apply(oldlocal)-qp.apply(oldlocal))/2;local=q.apply(newlocal-oldlocal)/2
 rec=dict(tick=t,head_velocity=((head-old)/2).tolist(),pelvis_translation=pv.tolist(),pelvis_rotation=rotation.tolist(),upper_relative=local.tolist(),raw_to_final_core_max_degrees=max(errors),raw_to_final_pelvis_position_cm=pelvis_error)
 report.append(rec);print(t,'head',np.round(rec['head_velocity'],3),'pelvisT',np.round(pv,3),'pelvisR',np.round(rotation,3),'upper',np.round(local,3),'core error',max(errors),'pelvis error',pelvis_error,'tempering',x.get('tempering'))
(p/'Head187-decomposition.json').write_text(json.dumps(report,indent=2))
