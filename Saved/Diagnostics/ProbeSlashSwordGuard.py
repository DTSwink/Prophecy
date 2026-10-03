exec(open('Saved/Diagnostics/MeasureSlashSwordSweep.py').read().split("for row in d['rows']:")[0])
maxima={}
for row in d['rows']:
    if 'LOCOMOTION' not in row['state'] or not row.get('weapon'):continue
    h,q,p0,p1,w=blade(row,0)
    if score(h,q,p0,p1,w)>=1.04:continue
    direction=np.array([h[0]/.81,h[1],0]);direction/=np.linalg.norm(direction)
    low=0.;high=w
    while score(h+direction*high,q,p0,p1,w)<1.04 and high<500:high*=2
    for _ in range(20):
        mid=(low+high)/2
        if score(h+direction*mid,q,p0,p1,w)<1.04:low=mid
        else:high=mid
    if high>maxima.get(row['agent'],[0])[0]:maxima[row['agent']]=[high,row['frame'],list(h)]
print(maxima)
