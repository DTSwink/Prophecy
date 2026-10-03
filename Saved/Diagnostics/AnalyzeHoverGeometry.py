import json,pathlib,numpy as np
base=pathlib.Path('Saved/Diagnostics')
ns={'__file__':str((base/'InspectPelvis159Geometry.py').resolve())}
exec((base/'InspectPelvis159Geometry.py').read_text().split('def evaluate')[0],ns)
minimum=ns['minimum'];clean=ns['clean'];rot=ns['rot'];w=ns['w']
for r in map(json.loads,(base/'Hover260-nn.jsonl').read_text().splitlines()):
 n=round(r['time']*60)
 if not r['actor'].endswith('_C_1') or not 255<=n<=271:continue
 raw=clean(np.array(r['lower_input'][:41])+r['lower_delta'][:41]);pub=np.array(r['published_lower'])
 print(n,'sole raw/pub',round((raw[11]-minimum(raw,0))*100,4),round((pub[11]-minimum(pub,0))*100,4),'required ankleZ',round(minimum(pub,0)*100,3),'rotation change',round(np.linalg.norm(rot(raw,12)-rot(pub,12)),6),'toe',round(pub[24],3),'tempering',r.get('tempering'))
