import bpy,json
from pathlib import Path
p=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/audit_pommel_lotus.py')
code=p.read_text(encoding='utf-8').split('\ntry:\n    main()')[0]
exec(compile(code,str(p),'exec'))
art=bpy.data.collections['SPEAR • editable components']
pommel=[o for o in art.objects if o.type=='MESH' and o.name.startswith(('02 •','Pommel •'))]
shaft=next(o for o in art.objects if o.name.startswith('01 •'))
rows={}
for ob in pommel:
    row,planes=mesh_audit(ob)
    ob.data.calc_loop_triangles();uv=ob.data.uv_layers['UV0_SurfaceAtlas'].data
    dots=[];areas=[]
    for tri in ob.data.loop_triangles:
        a,b,c=[uv[i].uv for i in tri.loops];ab=b-a;ac=c-a;areas.append(abs(ab.x*ac.y-ab.y*ac.x)*.5)
        dots.extend(ob.data.corner_normals[i].vector.dot(tri.normal) for i in tri.loops)
    require(min(dots)>0,(ob.name,'inward normal',min(dots)));require(min(areas)>1e-12,(ob.name,'collapsed UV'))
    row['minimum_normal_dot']=min(dots);row['minimum_UV_triangle_area']=min(areas);rows[ob.name]=row
wood_joint_audit(shaft,pommel)
report['parts']=rows
report['status']='LOTUS_SOURCE_PREFLIGHT_PASSED'
target=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics/ImperialSpear/PommelLotus/Source_Preflight.json')
target.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'meshes':len(rows),'wood_join':report['wood_joint']['status'],'wood_outside_samples':report['wood_joint']['outside_samples']}))
