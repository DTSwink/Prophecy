import pathlib,re,json,math
f=pathlib.Path(__file__).parent
log=(f.parents[2]/'Saved/Logs/GameAnimationSample3.log').read_text(errors='replace')
log=log[log.rfind('HAND_CAPTURE_START'):]
lines=[l for l in log.splitlines() if 'HAND_STAGE' in l and 'actor=BP_ProphecyManualPoseAgent_C_1 ' in l]
def v(s):return [float(x) for x in re.findall(r'[XYZW]=([\d.eE+-]+)',s)]
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b)))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b)))))
rows=[]
for l in lines:
 d={k:v(s) for k,s in re.findall(r'(\w+)=\[([^]]+)\]',l)}
 d['t']=float(re.search(r't=([\d.]+)',l)[1]); d['bone']=re.search(r'bone=(\w+)',l)[1]
 d['pre_error']=angle(d['preq'],d['targetq']);d['post_error']=angle(d['postq'],d['targetq'])
 d['dw']=math.sqrt(sum((x-y)**2 for x,y in zip(d['servow'],d['postw'])))
 rows.append(d)
(f/'Stages.json').write_text(json.dumps(rows,indent=2))
print('samples',len(rows))
for r in sorted(rows,key=lambda r:r['post_error'],reverse=True)[:4]:print(json.dumps(r))
