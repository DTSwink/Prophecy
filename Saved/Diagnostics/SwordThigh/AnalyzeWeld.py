import json,math,pathlib
root=pathlib.Path(__file__).parent
angle=lambda p,q:2*math.degrees(math.acos(min(1,abs(sum(x*y for x,y in zip(p[3:],q[3:]))))))
for f in [root/'capture.json',*root.glob('WeldInertia_*/capture.json')]:
    d=json.loads(f.read_text()); rows=d['rows']
    pairs=[(angle(a['hand'],b['hand']),b['tick'],math.dist(a['hand'][:3],b['hand'][:3]),angle(a['thigh'],b['thigh'])) for a,b in zip(rows,rows[1:]) if 80<=b['tick']<=110]
    allpairs=[(angle(a['hand'],b['hand']),b['tick']) for a,b in zip(rows,rows[1:]) if b['tick']>=20]
    print(f.parent.name,d['reason'],len(rows),'80-110', sorted(pairs,reverse=True)[:5], 'whole',sorted(allpairs,reverse=True)[:5])
