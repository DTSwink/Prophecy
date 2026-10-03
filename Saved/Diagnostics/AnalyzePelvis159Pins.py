import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics');a=json.loads((p/'CalfAnkleConnection-pelvis159-pins.json').read_text())['rows'];a={round(r['t']*60):r for r in a};b=json.loads((p/'CalfAnkleConnection-pelvis159-baseline.json').read_text())['rows'];b={round(r['t']*60):r for r in b if r['possessed']}
print('max pelvis capture error',max(np.max(np.abs(np.array(r['meshes']['PhysicalMesh']['pelvis']['p'])-b[f]['meshes']['PhysicalMesh']['pelvis']['p'])) for f,r in a.items()))
for f in range(151,164):
 r=a[f];z=r['targets'];print(f,'BP tick',r['debug_tick'],'pins',r['pinning'],'foot dz',[round(z['foot_'+s]['future']['p'][2]-z['foot_'+s]['previous']['p'][2],3) for s in ['l','r']])
