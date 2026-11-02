import json,re,pathlib,subprocess,numpy as np
from scipy.spatial import ConvexHull
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/SpearPike20261030'
scale=np.array([.8623427588789339,.8834927125312151,.7619161867885869])
rows=json.loads((out/'imported-collision.json').read_text())
points=[np.array([[float(x) for x in v] for v in re.findall(r'\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)',row['text'].split('IndexData=')[0])]) for row in rows]
def write(path,arrays):
    path.write_text(str(len(arrays))+'\n'+'\n'.join(str(len(p))+'\n'+'\n'.join(' '.join(format(x,'.12g') for x in v) for v in p*scale*.01) for p in arrays))
write(out/'collision-original.txt',points)
(out/'collision-points.json').write_text(json.dumps([p.tolist() for p in points]))
print('counts',[len(p) for p in points])
exe=root/'Intermediate/SpearCollisionLab/Release/SpearCollisionLab.exe'
def check(arrays):
    path=out/'collision-candidates.txt';write(path,arrays)
    r=subprocess.run([str(exe),str(path)],capture_output=True,text=True)
    lines=r.stdout.strip().splitlines();assert len(lines)==len(arrays),r.stdout+r.stderr
    return [line.endswith(' PASS') for line in lines]
passed=check(points);changes=[]
for index,ok in enumerate(passed):
    if ok:continue
    original=points[index].copy();current=original.copy();removed=[]
    for iteration in range(8):
        candidates=[np.delete(current,i,axis=0) for i in range(len(current))]
        good=check(candidates);scores=[]
        for i,p in enumerate(candidates):
            hull=ConvexHull(p);planes=hull.equations
            deficit=float(np.maximum(original@planes[:,:3].T+planes[:,3],0).max())
            scores.append((0 if good[i] else 1,deficit,i))
        _,error,choice=min(scores);assert error<.02,(index,error)
        removed.append(current[choice].tolist());current=candidates[choice]
        if good[choice]:break
    else:raise RuntimeError('No conservative hull repair found')
    points[index]=current
    changes.append({'hull':index,'before':len(original),'after':len(current),'removed':removed,'max_plane_deficit_cm':error,'volume_loss_fraction':1-ConvexHull(current).volume/ConvexHull(original).volume})
assert all(check(points))
(out/'collision-repaired.json').write_text(json.dumps({'points':[p.tolist() for p in points],'changes':changes},indent=2))
write(out/'collision-repaired.txt',points)
print(json.dumps(changes,indent=2))
