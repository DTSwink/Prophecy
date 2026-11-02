"""Selected concept 03: closed flattened leaf, integrated channels and turned end fittings."""
import bpy,bmesh,math,json,hashlib
from mathutils import Vector
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
WORK=ROOT/'Saved/Diagnostics/ImperialSpear/PommelLeaf'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
art=bpy.data.collections['SPEAR • editable components'];mat=bpy.data.materials['M_ImperialSpear_PBR']
baseline=json.loads((WORK/'Baseline_Source_Components.json').read_text())
def fingerprint(o):
    m=o.data
    d={'v':[list(v.co) for v in m.vertices],'f':[list(p.vertices) for p in m.polygons],
       'uv':{l.name:[list(v.uv) for v in l.data] for l in m.uv_layers},
       'normals':[list(n.vector) for n in m.corner_normals],
       'materials':[sl.material.name if sl.material else None for sl in o.material_slots],
       'matrix':[list(r) for r in o.matrix_world]}
    return hashlib.sha256(json.dumps(d,separators=(',',':')).encode()).hexdigest()
def assert_protected():
    protected={n:v for n,v in baseline.items() if not n.startswith(('02 •','Pommel •'))}
    assert len(protected)==70
    assert all(n in art.objects and fingerprint(art.objects[n])==v['fingerprint'] for n,v in protected.items()),'Accepted component changed'
assert_protected()

# Shape-preserving cubic interpolation avoids oscillations at the necks.
def pchip(knots,z):
    xx=[p[0] for p in knots];yy=[p[1] for p in knots]
    hh=[xx[i+1]-xx[i] for i in range(len(xx)-1)];dd=[(yy[i+1]-yy[i])/hh[i] for i in range(len(hh))]
    mm=[dd[0]]
    for i in range(1,len(xx)-1):
        if dd[i-1]*dd[i]<=0:mm.append(0.)
        else:
            a=2*hh[i]+hh[i-1];b=hh[i]+2*hh[i-1]
            mm.append((a+b)/(a/dd[i-1]+b/dd[i]))
    mm.append(dd[-1])
    i=next((i for i in range(len(hh)) if z<=xx[i+1]),len(hh)-1)
    t=max(0,min(1,(z-xx[i])/hh[i]));h=hh[i]
    return (2*t**3-3*t*t+1)*yy[i]+(t**3-2*t*t+t)*h*mm[i]+(-2*t**3+3*t*t)*yy[i+1]+(t**3-t*t)*h*mm[i+1]

width=[(.0125,.0122),(.020,.0128),(.031,.0180),(.047,.0238),(.057,.0245),(.070,.0232),(.084,.0193),(.096,.0162),(.1085,.0167)]
depth=[(.0125,.0100),(.025,.0103),(.055,.0107),(.072,.0112),(.082,.0134),(.090,.0162),(.100,.0170),(.1085,.0170)]
zs=[.0125+i*.096/36 for i in range(37)]
def blend_at(z):
    t=max(0,min(1,(z-.078)/.014))
    return t*t*(3-2*t)
def section(z):
    w=pchip(width,z);h=pchip(depth,z)
    t=(z-.0125)/(.1085-.0125)
    # Inset borders sweep into the necks, broadening with the leaf's belly.
    border=.0046+(w-.0122)*1.04
    border=min(border,w-.0029)
    bevel=w-.00080
    xp=[0,.0010,.00135,.00175,.00215,
        (.00215+border-.00095)*.5,border-.00095,border-.00060,border-.00020,
        border+.00020,border+.00065,bevel,w-.00030,w]
    assert all(xp[i+1]>xp[i]+1e-7 for i in range(len(xp)-1)),(z,xp)
    fade=min(1,max(0,(z-.013)/.010),max(0,(.108-z)/.012))
    # Transverse surfaces are beveled/chased, not separate cylindrical rails.
    relief=[.00012,.00012,-.00038,-.00038,0,0,0,-.00025,-.00032,.00022,0,0,-.00035,-.00060]
    def ymag(x,i):
        # A circular envelope near the wood transition prevents shaft breakthrough.
        circular=math.sqrt(max(0,1-(x/w)**2))
        flatten=1-.53*(x/w)**2
        blend=blend_at(z)
        base=h*((1-blend)*flatten+blend*max(circular,.22))
        return base+relief[i]*fade
    pos=[(x,-ymag(x,i),z) for i,x in enumerate(xp)]
    front=[(-x,y,z) for x,y,z in reversed(pos[1:])]+pos
    back=[(x,-y,z) for x,y,z in reversed(front)]
    return front+back

rows=[section(z) for z in zs];count=len(rows[0]);nfront=count//2
verts=[v for row in rows for v in row];faces=[];normals=[];uvs=[]
# Per-face UV atlas island, paired faces share the same unchanged plain gold tile.
def faceuv(v):
    x,y,z=v
    return (.625+.244*x/.104,.753+.244*((z-.010)/.104))
# Split the machined edges but keep the broad convex fields smoothly lit.
positive_sharp={1,2,3,4,6,7,8,9,10,11,12,13}
sharp=set()
for q in range(nfront):
    if abs(q-13) in positive_sharp:sharp.add(q)
sharp|={count-1-q for q in sharp}
def normal(k,j,span):
    lo=max(0,k-1);hi=min(len(rows)-1,k+1)
    longitudinal=Vector(rows[hi][j])-Vector(rows[lo][j])
    # Analytic transverse derivative keeps broad fields truly smooth, with no
    # faceted shading bands from widely spaced surface columns.
    end=(span+1)%count
    fi=lambda jj:abs((jj if jj<nfront else count-1-jj)-13)
    broad=(set((fi(span),fi(end))) in ({0,1},{4,5},{5,6},{10,11}) and (span<nfront)==(end<nfront))
    if broad:
        x,y,z=rows[k][j];w=pchip(width,z);h=pchip(depth,z);blend=blend_at(z)
        cir=math.sqrt(max(1e-12,1-(x/w)**2))
        dhdx=h*((1-blend)*(-1.06*x/(w*w))+blend*((-x/(w*w*cir)) if cir>.22 else 0))
        dydx=(-1 if y<0 else 1)*dhdx
        across=Vector((1,dydx,0))*(1 if span<nfront else -1)
    elif j in sharp:
        a=span;b=(span+1)%count
        across=Vector(rows[k][b])-Vector(rows[k][a])
    else:
        a=Vector(rows[k][j])-Vector(rows[k][(j-1)%count]);b=Vector(rows[k][(j+1)%count])-Vector(rows[k][j])
        across=a.normalized()+b.normalized()
    return tuple(across.cross(longitudinal).normalized())
for k in range(len(rows)-1):
    for j in range(count):
        jn=(j+1)%count;idx=(k*count+j,k*count+jn,(k+1)*count+jn,(k+1)*count+j)
        faces.append(idx)
        for kk,jj in ((k,j),(k,jn),(k+1,jn),(k+1,j)):
            if j in (nfront-1,count-1):
                x,y,z=rows[kk][jj]
                uvs.append((.60+.10*y/.02,.753+.244*((z-.010)/.104)))
            else:uvs.append(faceuv(rows[kk][jj]))
            normals.append(normal(kk,jj,j))
faces.extend([tuple(reversed(range(count))),tuple((len(rows)-1)*count+j for j in range(count))])
for k,order,sgn in ((0,reversed(range(count)),-1),(len(rows)-1,range(count),1)):
    for j in order:
        x,y,z=rows[k][j];uvs.append((.625+.11*x/.025,.875+.11*y/.020));normals.append((0,0,sgn))

created=[];reports=[]
def create(name,verts,faces,uvs,normals):
    m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update()
    m.materials.append(mat);layer=m.uv_layers.new(name='UV0_SurfaceAtlas');layer.active_render=True
    for i,value in enumerate(uvs):layer.data[i].uv=value
    for p in m.polygons:p.use_smooth=True
    m.normals_split_custom_set(normals);m.update()
    bm=bmesh.new();bm.from_mesh(m)
    closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
    minimum_area=min(f.calc_area() for f in bm.faces);bm.free()
    assert closed and volume>0 and minimum_area>1e-12,(name,closed,volume,minimum_area)
    ob=bpy.data.objects.new('NEW '+name,m);art.objects.link(ob)
    ob['PommelDesign']='flattened_leaf';ob['Concept']='03 — Flattened leaf; user-selected'
    created.append((ob,name))
    reports.append({'name':name,'triangles':sum(len(p.vertices)-2 for p in m.polygons),'vertices':len(m.vertices),
                    'closed':closed,'volume_m3':volume,'minimum_face_area_m2':minimum_area})
    return ob
body=create('02 • flattened leaf pommel',verts,faces,uvs,normals)
body['PommelCollisionSplitLowM']=.017;body['PommelCollisionSplitHighM']=.104

def lathe(name,profile,sides=32):
    vs=[(r*math.cos(j*math.tau/sides),r*math.sin(j*math.tau/sides),z) for z,r in profile for j in range(sides)]
    fs=[];uv=[];ns=[]
    for k in range(len(profile)-1):
        z0,r0=profile[k];z1,r1=profile[k+1];dz,dr=z1-z0,r1-r0
        for j in range(sides):
            fs.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j))
            for jj,z in ((j,z0),(j+1,z0),(j+1,z1),(j,z1)):
                a=jj*math.tau/sides
                uv.append((.503+.244*jj/sides,.80+.244*(z-profile[0][0])/.104))
                row=k if z==z0 else k+1
                tangent=Vector((dz,dr))
                if 0<row<len(profile)-1:
                    aa=Vector((profile[row][0]-profile[row-1][0],profile[row][1]-profile[row-1][1])).normalized()
                    bb=Vector((profile[row+1][0]-profile[row][0],profile[row+1][1]-profile[row][1])).normalized()
                    if aa.dot(bb)>math.cos(math.radians(38)):tangent=(aa+bb).normalized()
                ns.append(tuple(Vector((tangent.x*math.cos(a),tangent.x*math.sin(a),-tangent.y)).normalized()))
    fs.extend([tuple(reversed(range(sides))),tuple((len(profile)-1)*sides+j for j in range(sides))])
    for order,sgn in ((reversed(range(sides)),-1),(range(sides),1)):
        for j in order:
            uv.append((.625+.105*math.cos(j*math.tau/sides),.875+.105*math.sin(j*math.tau/sides)));ns.append((0,0,sgn))
    return create(name,vs,fs,uv,ns)
lathe('Pommel • turned socket with rolled lips',[
    (.105,.0168),(.1055,.0180),(.1062,.0186),(.1070,.0188),(.1078,.0186),(.1085,.0179),
    (.1090,.0174),(.1096,.0175),(.1103,.0180),(.1110,.0182),(.1118,.0180),(.1124,.0173),
    (.1238,.0170),(.1244,.0177),(.1251,.0182),(.1260,.0185),(.1269,.0184),(.1276,.0178),(.1281,.0170)])
lathe('Pommel • blunt rolled end cap',[
    (0,.0138),(.0007,.0147),(.0016,.0153),(.0030,.0155),(.0048,.0155),(.0055,.0148),
    (.0062,.0141),(.0070,.0141),(.0076,.0148),(.0084,.0152),(.0092,.0153),(.0100,.0151),
    (.0108,.0143),(.0115,.0137),(.0140,.0132)])
assert_protected()
for ob in list(art.objects):
    if ob.type=='MESH' and ob.name.startswith(('02 •','Pommel •')):bpy.data.objects.remove(ob,do_unlink=True)
for ob,name in created:ob.name=name
assert_protected()
s['Spear_revision']='08 WIP: selected flattened leaf pommel'
s['PommelDesign']='flattened_leaf'
report={'concept':'03 — Flattened leaf','components':reports,'pommel_triangles':sum(r['triangles'] for r in reports),
        'protected_components_unchanged':70,'length_m':2.2,'pommel_span_m':[0,.1281],
        'texture_files_modified':False,'body_width_mm':49,'body_depth_mm':21.4}
(WORK/'Geometry_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Save a recoverable iteration without replacing the accepted delivery yet.
for im in bpy.data.images:
    if im.source=='FILE' and im.filepath:im.filepath=bpy.path.abspath(im.filepath)
bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'Working.blend'))
print(json.dumps(report,indent=2))
