"""Concept04 rebuild: deep carved panels, deliberate lips and lotus terminal."""
import bpy,bmesh,math,json,hashlib,runpy
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components']
base=json.loads((R/'Saved/Diagnostics/ImperialSpear/PommelLeaf/Baseline_Source_Components.json').read_text())
def fingerprint(o):
    m=o.data;d={'v':[list(v.co) for v in m.vertices],'f':[list(p.vertices) for p in m.polygons],
      'uv':{l.name:[list(v.uv) for v in l.data] for l in m.uv_layers},'normals':[list(n.vector) for n in m.corner_normals],
      'materials':[sl.material.name if sl.material else None for sl in o.material_slots],'matrix':[list(r) for r in o.matrix_world]}
    return hashlib.sha256(json.dumps(d,separators=(',',':')).encode()).hexdigest()
def protect():
    protected={n:r for n,r in base.items() if not n.startswith(('02 •','Pommel •'))}
    assert len(protected)==70
    assert all(n in art.objects and fingerprint(art.objects[n])==r['fingerprint'] for n,r in protected.items())
protect()
mat=bpy.data.materials['M_ImperialSpear_PBR']

def cubic(knots,z):
    xx=[p[0] for p in knots];yy=[p[1] for p in knots];hh=[xx[i+1]-xx[i] for i in range(len(xx)-1)]
    dd=[(yy[i+1]-yy[i])/hh[i] for i in range(len(hh))];mm=[dd[0]]
    for i in range(1,len(xx)-1):
        aa=2*hh[i]+hh[i-1];bb=hh[i]+2*hh[i-1]
        mm.append(0 if dd[i-1]*dd[i]<=0 else (aa+bb)/(aa/dd[i-1]+bb/dd[i]))
    mm.append(dd[-1]);i=next((i for i in range(len(hh)) if z<=xx[i+1]),len(hh)-1)
    t=max(0,min(1,(z-xx[i])/hh[i]));h=hh[i]
    return (2*t**3-3*t*t+1)*yy[i]+(t**3-2*t*t+t)*h*mm[i]+(-2*t**3+3*t*t)*yy[i+1]+(t**3-t*t)*h*mm[i+1]

body_data=runpy.run_path(str(R/"Tools/SpearAsset/four_lobe_pommel_body.py"))["build_four_lobe_body"]()
verts,faces,uvs,normals=(body_data[k] for k in ("vertices","faces","uvs","normals"))

new=[];reports=[]
def create(name,vertices,faces,uvs,normals=None,cavity=None):
    m=bpy.data.meshes.new(name);m.from_pydata(vertices,[],faces);m.update();m.materials.append(mat)
    layer=m.uv_layers.new(name='UV0_SurfaceAtlas');layer.active_render=True
    assert len(uvs)==len(m.loops)
    for i,(u,v) in enumerate(uvs):
        assert 0<=u<=1 and 0<=v<=1,(name,u,v)
        layer.data[i].uv=(.503+.244*u,.753+.244*v)
    for p in m.polygons:p.use_smooth=True
    if normals:m.normals_split_custom_set(normals)
    shades=m.color_attributes.new(name='PommelCavity',type='FLOAT_COLOR',domain='CORNER')
    if cavity is None:cavity=[0.]*len(m.loops)
    assert len(cavity)==len(m.loops)
    for item,mask in zip(shades.data,cavity):
        assert 0<=mask<=1
        value=1-.55*mask;item.color=(value,value,value,1)
    m.color_attributes.active_color=shades
    m.update();bm=bmesh.new();bm.from_mesh(m)
    closed=all(e.is_manifold and e.is_contiguous for e in bm.edges);volume=bm.calc_volume(signed=True)
    min_area=min(f.calc_area() for f in bm.faces);bm.free()
    assert closed and volume>0 and min_area>1e-14,(name,closed,volume,min_area)
    ob=bpy.data.objects.new('NEW '+name,m);art.objects.link(ob);ob['PommelDesign']='lotus_bud'
    new.append((ob,name));reports.append({'name':name,'vertices':len(m.vertices),'triangles':sum(len(f.vertices)-2 for f in m.polygons),'closed':closed,'volume_m3':volume})
    return ob
body=create('02 • carved lotus pommel body',verts,faces,uvs,normals,body_data.get('cavity'))
reports[-1]['design_report']=body_data['report']
body['PommelCollisionSplitLowM']=.004;body['PommelCollisionSplitHighM']=.104

def lathe(name,profile,sides=40):
    v=[(r*math.cos(j*math.tau/sides),r*math.sin(j*math.tau/sides),z) for z,r in profile for j in range(sides)]
    f=[];uv=[];ns=[]
    for k in range(len(profile)-1):
        z0,r0=profile[k];z1,r1=profile[k+1];dz,dr=z1-z0,r1-r0
        for j in range(sides):
            f.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j))
            for jj,z in ((j,z0),(j+1,z0),(j+1,z1),(j,z1)):
                a=jj*math.tau/sides;row=k if z==z0 else k+1;tangent=Vector((dz,dr))
                if 0<row<len(profile)-1:
                    aa=Vector((profile[row][0]-profile[row-1][0],profile[row][1]-profile[row-1][1])).normalized()
                    bb=Vector((profile[row+1][0]-profile[row][0],profile[row+1][1]-profile[row][1])).normalized()
                    if aa.dot(bb)>math.cos(math.radians(36)):tangent=(aa+bb).normalized()
                uv.append((.02+.96*jj/sides,.20+(z-profile[0][0])/.100))
                ns.append(tuple(Vector((tangent.x*math.cos(a),tangent.x*math.sin(a),-tangent.y)).normalized()))
    f.extend([tuple(reversed(range(sides))),tuple((len(profile)-1)*sides+j for j in range(sides))])
    for order,sign in ((reversed(range(sides)),-1),(range(sides),1)):
        for j in order:uv.append((.5+.10*math.cos(j*math.tau/sides),.5+.10*math.sin(j*math.tau/sides)));ns.append((0,0,sign))
    return create(name,v,f,uv,ns)
lathe('Pommel • rolled socket and straight barrel',[
    (.105,.0172),(.1055,.0183),(.1062,.0188),(.1071,.0190),(.1080,.0187),(.1088,.0178),
    (.1095,.0175),(.1101,.0180),(.1109,.0185),(.1118,.0186),(.1126,.0182),(.1132,.0174),
    (.1238,.0170),(.1243,.0178),(.1251,.0184),(.1261,.0187),(.1270,.0183),(.1281,.0170)])
lathe('Pommel • stepped lotus seat',[
    (.0010,.0145),(.0015,.0158),(.0021,.0171),(.00235,.01745),(.00255,.0175),
    (.00475,.0175),(.00495,.0174),(.00515,.0172),(.00535,.01685),
    (.0055,.01685),(.0061,.01685),(.0063,.0171),(.00655,.01735),(.00685,.0175),
    (.0075,.0175),(.0084,.0173),(.0097,.0170),
    (.0104,.0162),(.0108,.0156),(.0118,.0156),(.0125,.0147),(.0145,.0137)])
budscript=R/'Tools/SpearAsset/lotus_bud_component.py'
if budscript.is_file():
    bud=runpy.run_path(str(budscript))['build_lotus_bud']()
    uv=[(.02+.96*u,.20+.34*v) for u,v in bud['uvs']]
    create('Pommel • six carved lotus petals',bud['vertices'],bud['faces'],uv,bud.get('normals'),bud.get('cavity'))
    reports[-1]['design_report']=bud.get('report',{})
else:print('BODY-ONLY CHECKPOINT: bud module not yet available')
protect()
for o in list(art.objects):
    if o.type=='MESH' and o.name.startswith(('02 •','Pommel •')):bpy.data.objects.remove(o,do_unlink=True)
for o,n in new:o.name=n
protect();s['Spear_revision']='09 WIP: concept04 lotus bud, deep carved panels';s['PommelDesign']='lotus_bud'
report={'concept':'04 — Lotus bud','components':reports,'triangles':sum(r['triangles'] for r in reports),
        'protected_components':70,'body_design':body_data['report'],
        'new_bottom_m':min(v.co.z for o,n in new for v in o.data.vertices),'material':mat.name,'same_gold_material_as_spearhead':True}
(W/'Geometry_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for im in bpy.data.images:
    if im.source=='FILE' and im.filepath:im.filepath=bpy.path.abspath(im.filepath)
bpy.ops.wm.save_as_mainfile(filepath=str(W/'Working.blend'))
print(json.dumps(report,indent=2))
