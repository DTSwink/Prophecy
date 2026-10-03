exec(open('Saved/Diagnostics/AnalyzeHand180.py').read().split('last=None')[0])
out={}
for tag in ['hand180','hand180_zero','hand180_zero_no_return','hand180_no_clamps','hand180_isolated_exit']:
 d=json.loads((p/(tag+'.json')).read_text());rr={r['tick']:r for r in d['rows']}
 def local(t,b='hand_r'):
  r=rr[t]['targets'];s=r['spine_05']['future'];h=r[b]['future']
  return R.from_quat(s['q']).inv().apply(np.array(h['p'])-s['p'])
 print(tag,d['reason'])
 v=[]
 for t in range(188,213,2):
  v.append(dict(tick=t,local=local(t).tolist(),step_cm=float(np.linalg.norm(local(t)-local(t-2)))))
  print(t,round(v[-1]['step_cm'],4),np.round(local(t),3))
 out[tag]=v
(p/'hand180_comparison.json').write_text(json.dumps(out,indent=2))
nn=[json.loads(x) for x in (p/'hand180_nn.jsonl').read_text().splitlines()]
print('NN attack/half',[(round(x['time']*60),x['attack'],x['half']) for x in nn if x['actor']==rows[0]['actor'] and 165<=round(x['time']*60)<=197])
