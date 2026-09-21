import json,math,pathlib,collections
for path in pathlib.Path('Saved/Diagnostics').glob('SwordJump_*.json'):
    p=json.loads(path.read_text());r=p['rows'];angles=[];moves=[]
    for a,b in zip(r,r[1:]):
        q=a['sword']['transform']['q'];v=b['sword']['transform']['q']
        angle=math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(q,v))))))
        angles.append((angle,b['tick']));moves.append((math.dist(a['sword']['transform']['p'],b['sword']['transform']['p']),b['tick']))
    print(path.name,'error',p['error'],'rows',len(r))
    print('max angles',sorted(angles,reverse=True)[:8]);print('80-110 angle',max((a for a in angles if 80<=a[1]<=110),default=None))
    print('max motion',sorted(moves,reverse=True)[:5]);print('events',collections.Counter((e['other'],e['component']) for e in p['events']))
    print('cube events',[(round(e['t'],4),round(math.dist(e['impulse'],[0,0,0]),2)) for e in p['events'] if e['other']=='StaticMeshActor_2'][:20])
