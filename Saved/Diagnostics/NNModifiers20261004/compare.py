import ast, collections, json, math, pathlib, re, sys
p=pathlib.Path(__file__).parent
left=sys.argv[1] if len(sys.argv)>1 else 'before'
right=sys.argv[2] if len(sys.argv)>2 else 'observe'
a=json.loads((p/(left+'.json')).read_text()); b=json.loads((p/(right+'.json')).read_text())
assert a['reason']==b['reason']=='Complete',(a['reason'],b['reason'])
assert len(a['rows'])==len(b['rows'])==260
differences=collections.Counter(); maximum={}; examples={}
def compare(x,y,path=''):
 if isinstance(x,dict):
  assert x.keys()==y.keys(),(path,x.keys(),y.keys())
  for k in x:compare(x[k],y[k],path+'/'+k)
 elif isinstance(x,list):
  assert len(x)==len(y),(path,len(x),len(y))
  for i,(u,v) in enumerate(zip(x,y)):compare(u,v,path+'/'+str(i))
 elif x!=y:
  group=re.sub(r'/\d+','/i',path)
  differences[group]+=1
  if isinstance(x,(int,float)) and isinstance(y,(int,float)):maximum[group]=max(maximum.get(group,0),abs(x-y))
  examples.setdefault(group,[x,y])
for x,y in zip(a['rows'],b['rows']):
 compare({k:v for k,v in x.items() if k!='report'},{k:v for k,v in y.items() if k!='report'})
def graph(name):
 text=(p/(name+'-graph.txt')).read_text(encoding='utf-16')
 text=re.sub(r'/Script/\w+\.Default__(\w+)',r'CDO_\1',text)
 return re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+)_\d+',r'CDO_\1',text)
native_a=[json.loads(x) for x in (p/(left+'-nn.jsonl')).read_text().splitlines()]
native_b=[json.loads(x) for x in (p/(right+'-nn.jsonl')).read_text().splitlines()]
native_equal=native_a==native_b
assert len(native_a)==len(native_b)
reports={}
for row in b['rows']:
 if 'report' not in row:continue
 count,report=ast.literal_eval(row['report'])
 assert count==len(report.splitlines())
 phase='locomotion' if not row['attack'] else str(row['attack'][0])+('/half' if row['attack'][1] else '/full')
 if phase not in reports:reports[phase]=dict(tick=row['tick'],count=count,report=report)
 if 'Attack FK return / lab inertia' in report:reports.setdefault('return',dict(tick=row['tick'],count=count,report=report))
result=dict(left=left,right=right,frames=len(a['rows']),graph_equal=graph(left)==graph(right),native_records=len(native_a),native_exact=native_equal,differences=dict(differences),max_absolute=maximum,examples=examples,reports=reports)
(p/(left+'-'+right+'-comparison.json')).write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('reports','examples')},indent=2))
for phase,v in reports.items():print(phase,'tick',v['tick'],'rows',v['count']);print(v['report'])
