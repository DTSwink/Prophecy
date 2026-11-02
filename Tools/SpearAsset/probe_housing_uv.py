import bpy,json,math
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
art=bpy.data.collections['SPEAR • editable components']; body=next(o for o in art.objects if o.name.startswith('07 •'))
uv=body.data.uv_layers[0]; err=[]; samples=[]
for loop in body.data.loops:
 co=body.data.vertices[loop.vertex_index].co; expected=(.5+.25*(co.x+.06)/.12,.5+.25*(co.z-1.64)/.13); actual=uv.data[loop.index].uv
 error=max(abs(expected[i]-actual[i]) for i in (0,1));err.append(error)
 if len(samples)<8 and error>.0001: samples.append({'co':list(co),'expected':expected,'actual':list(actual)})
data={'matrix':list(map(list,body.matrix_world)),'uv_max_error':max(err),'samples':samples,'all_uvs':[(u.name,u.active_render) for u in body.data.uv_layers]}
(OUT/'Housing_UV_Probe.json').write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps(data))
