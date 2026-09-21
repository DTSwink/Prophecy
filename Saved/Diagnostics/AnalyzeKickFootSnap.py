import json,pathlib,math,collections,sys
p=pathlib.Path(__file__).with_name('KickFootSnap'+('' if len(sys.argv)<2 else '-'+sys.argv[1])+'.json');data=json.loads(p.read_text())
print('reason',data['reason'],'rows',len(data['rows']))
actors=collections.defaultdict(list)
for r in data['rows']:actors[r['actor']].append(r)
def length(r,side,kind):
    a=r['bones']['calf_'+side].get(kind);b=r['bones']['foot_'+side].get(kind)
    return math.dist(a['p'],b['p']) if a and b else None
for name,rs in actors.items():
    if not any('kick' in r['attack'] for r in rs):continue
    print('\nACTOR',name,'samples',len(rs))
    transitions=[i for i,r in enumerate(rs) if i and 'kick' in rs[i-1]['attack'] and 'kick' not in r['attack']]
    print('exits',len(transitions))
    for i in transitions[:5]:
        print('EXIT',round(rs[i]['t'],4),'before',rs[i-1]['attack'],'after',rs[i]['attack'])
        for r in rs[max(0,i-3):i+7]:
            print(round(r['t'],4),r['attack'],{s:{k:round(length(r,s,k),3) if length(r,s,k) is not None else None for k in ('physical','target','future')} for s in ('l','r')})
    for side in ('l','r'):
        jumps=[]
        for i in range(1,len(rs)):
            x=length(rs[i],side,'physical');y=length(rs[i-1],side,'physical')
            if x is not None and y is not None:jumps.append((abs(x-y),i,x-y))
        print('BIGGEST',side,[(round(d,3),round(rs[i]['t'],4),round(sign,3),rs[i]['attack']) for d,i,sign in sorted(jumps,reverse=True)[:6]])
