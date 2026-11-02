"""Authored Imperial Spear. Execute only through the Blender MCP bridge."""
import bpy, bmesh, math, json, random
from mathutils import Vector
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT=ROOT/'Exports/ImperialSpear'
random.seed(271027)
# This script owns the factory-startup session; no user scene is opened.
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob,do_unlink=True)
for col in list(bpy.data.collections):
    if col.name.startswith(('SPEAR','STUDIO')): bpy.data.collections.remove(col)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
def collection(name):
    c=bpy.data.collections.new(name); scene.collection.children.link(c); return c
art=collection('SPEAR • editable components')
collision=collection('SPEAR • UCX collision')
markers=collection('SPEAR • attachment markers')
studio=collection('STUDIO • presentation only')
regions={'steel':(0,.5,.5,1),'gold':(.5,1,.5,1),'wood':(0,.5,0,.5),
         'leather':(.5,.75,0,.5),'silk':(.75,1,0,.5)}
mat=bpy.data.materials.new('M_ImperialSpear'); mat.use_nodes=True
nodes=mat.node_tree.nodes; links=mat.node_tree.links
p=nodes.get('Principled BSDF'); p.inputs['Roughness'].default_value=.3
for typ,suffix,space in [('base','BaseColor','sRGB'),('orm','ORM','Non-Color'),('normal','NormalGL','Non-Color')]:
    node=nodes.new('ShaderNodeTexImage'); node.name='Atlas_'+typ
    node.image=bpy.data.images.load(str(OUT/'Textures'/('T_ImperialSpear_'+suffix+'.png')),check_existing=True)
    node.image.reload()
    node.image.colorspace_settings.name=space
    if typ=='base': links.new(node.outputs['Color'],p.inputs['Base Color'])
    elif typ=='orm':
        sep=nodes.new('ShaderNodeSeparateColor'); links.new(node.outputs['Color'],sep.inputs[0])
        links.new(sep.outputs['Green'],p.inputs['Roughness']); links.new(sep.outputs['Blue'],p.inputs['Metallic'])
    else:
        normal=nodes.new('ShaderNodeNormalMap'); links.new(node.outputs['Color'],normal.inputs['Color'])
        links.new(normal.outputs[0],p.inputs['Normal'])
def atlas(u,v,kind):
    a,b,c,d=regions[kind]; inset=.003
    return (a+inset+u*(b-a-2*inset),c+inset+v*(d-c-2*inset))
def mesh(name,verts,faces,kind='gold',uvfaces=None,col=art,smooth=False):
    data=bpy.data.meshes.new(name); data.from_pydata(verts,[],faces); data.update()
    ob=bpy.data.objects.new(name,data); col.objects.link(ob)
    if col==art:
        data.materials.append(mat)
        uv=data.uv_layers.new(name='UV0_SurfaceAtlas')
        mins=[min(v[i] for v in verts) for i in range(3)]; maxs=[max(v[i] for v in verts) for i in range(3)]
        for poly in data.polygons:
            poly.use_smooth=smooth
            for j,li in enumerate(poly.loop_indices):
                co=data.vertices[data.loops[li].vertex_index].co
                a,b=(uvfaces[poly.index][j] if uvfaces else ((co.x-mins[0])/max(.001,maxs[0]-mins[0]),(co.z-mins[2])/max(.001,maxs[2]-mins[2])))
                uv.data[li].uv=atlas(a,b,kind)
    bm=bmesh.new(); bm.from_mesh(data); bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(data); bm.free()
    return ob
def activate(ob):
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active=ob
def bevel(ob,width=.00065,segments=2):
    activate(ob); mod=ob.modifiers.new('Machined edge radii','BEVEL'); mod.width=width; mod.segments=segments
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return ob
def lathe(name,profile,kind='gold',sides=32,center=(0,0),phase=0,col=art):
    verts=[]; faces=[]; uvs=[]
    for z,r in profile:
        for j in range(sides):
            a=j*2*math.pi/sides+phase; verts.append((center[0]+r*math.cos(a),center[1]+r*math.sin(a),z))
    for k in range(len(profile)-1):
        for j in range(sides):
            faces.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j))
            lo=(profile[k][0]-profile[0][0])/max(.001,profile[-1][0]-profile[0][0]); hi=(profile[k+1][0]-profile[0][0])/max(.001,profile[-1][0]-profile[0][0])
            uvs.append([(j/sides,lo),((j+1)/sides,lo),((j+1)/sides,hi),(j/sides,hi)])
    faces.extend([tuple(reversed(range(sides))),tuple((len(profile)-1)*sides+j for j in range(sides))])
    uvs.extend([[(.5+.45*math.cos(j*2*math.pi/sides),.5+.45*math.sin(j*2*math.pi/sides)) for j in reversed(range(sides))],[(.5+.45*math.cos(j*2*math.pi/sides),.5+.45*math.sin(j*2*math.pi/sides)) for j in range(sides)]])
    ob=mesh(name,verts,faces,kind,uvs,col,smooth=True)
    if col==art:
        ob.data.polygons[-1].use_smooth=False; ob.data.polygons[-2].use_smooth=False
    return ob
def tube(name,pts,radius=.0015,kind='gold',sides=6):
    verts=[]; faces=[]; uv=[]
    for i,pt in enumerate(pts):
        q=Vector(pt); tangent=Vector(pts[min(i+1,len(pts)-1)])-Vector(pts[max(i-1,0)])
        tangent.normalize(); side=tangent.cross(Vector((0,1,0)))
        if side.length<.01: side=tangent.cross(Vector((1,0,0)))
        side.normalize(); up=tangent.cross(side).normalized()
        r=radius*(.5+.5*math.sin(math.pi*(i+.5)/len(pts))**.35)
        for j in range(sides):
            a=2*math.pi*j/sides; v=q+r*(math.cos(a)*side+math.sin(a)*up); verts.append(tuple(v))
    for i in range(len(pts)-1):
        for j in range(sides):
            faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
            uv.append([(j/sides,i/(len(pts)-1)),((j+1)/sides,i/(len(pts)-1)),((j+1)/sides,(i+1)/(len(pts)-1)),(j/sides,(i+1)/(len(pts)-1))])
    faces.extend([tuple(reversed(range(sides))),tuple((len(pts)-1)*sides+j for j in range(sides))]); uv.extend([[(.5,.5)]*sides]*2)
    return mesh(name,verts,faces,kind,uv,smooth=True)
def path(name,coords,r=.0014,kind='gold'):
    # Catmull-Rom path, sampled modestly for controlled curvature.
    pts=[]
    for i in range(len(coords)-1):
        p0=Vector(coords[max(i-1,0)]); p1=Vector(coords[i]); p2=Vector(coords[i+1]); p3=Vector(coords[min(i+2,len(coords)-1)])
        for k in range(5):
            t=k/5; pts.append(tuple(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)))
    pts.append(coords[-1]); return tube(name,pts,r,kind)
def plate(name,outline,depth=.010,y=0,kind='gold'):
    verts=[(x,y-depth/2,z) for x,z in outline]+[(x,y+depth/2,z) for x,z in outline]
    n=len(outline); faces=[tuple(reversed(range(n))),tuple(n+i for i in range(n))]
    faces.extend([(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)])
    return bevel(mesh(name,verts,faces,kind),.00065,2)

# Tapered lacquered hardwood shaft; no excessive circumferential segmentation.
lathe('01 • rosewood shaft',[(.09,.014),(.15,.0153),(.55,.0159),(1.12,.016),(1.48,.0157),(1.66,.015)],'wood',32)
# Slim blunt third-reference ferrule; no rear spearhead.
pommel=lathe('02 • tapered gold pommel',[(0,.0095),(.003,.011),(.016,.0122),(.108,.0173),(.122,.0178),(.127,.0165)],'gold',12,phase=math.pi/12)
for p in pommel.data.polygons: p.use_smooth=False
bevel(pommel,.00065,2)
for z in [.108,.119,.127]: lathe('Pommel • fine rim',[(z-.0011,.0175),(z,.0181),(z+.0011,.0175)],'gold',32)
for a in [math.pi/6*j+math.pi/12 for j in range(12)]:
    tube('Pommel • chased longitudinal rail',[(r*math.cos(a),r*math.sin(a),z) for z,r in [(.012,.0124),(.035,.0137),(.075,.016),(.105,.0177)]],.00065,'gold',5)

# Shifted grip: centre 1.235m, spanning 1.115..1.355m.
lathe('03 • leather grip underlay',[(1.115,.0175),(1.124,.0181),(1.345,.0181),(1.355,.0175)],'leather',32)
turns=10.5; steps=round(turns*32); verts=[]; faces=[]; uv=[]
for i in range(steps+1):
    t=i/steps; a=t*turns*2*math.pi; mid=1.126+t*.217
    for j in range(4):
        dz=[-.011,-.009,.009,.011][j]; r=[.0182,.019,.019,.01825][j]
        verts.append((r*math.cos(a),r*math.sin(a),max(1.117,min(1.353,mid+dz))))
for i in range(steps):
    for j in range(3):
        faces.append((i*4+j,(i+1)*4+j,(i+1)*4+j+1,i*4+j+1))
        uv.append([(i/steps,j/3),((i+1)/steps,j/3),((i+1)/steps,(j+1)/3),(i/steps,(j+1)/3)])
mesh('04 • overlapping leather winding',verts,faces,'leather',uv,smooth=True)
for z in [1.112,1.358]:
    lathe('Grip • gold keeper',[(z-.010,.0168),(z-.008,.0196),(z-.005,.0202),(z+.005,.0202),(z+.008,.0196),(z+.010,.0168)],'gold',32)
    for dz in [-.0055,.0055]: lathe('Grip • keeper wire',[(z+dz-.0006,.0202),(z+dz,.0209),(z+dz+.0006,.0202)],'gold',32)

# Stepped ornamental socket, using the same gold as the pommel.
lathe('05 • engraved gold socket',[(1.602,.0155),(1.607,.021),(1.625,.021),(1.63,.019),(1.676,.0195),(1.686,.022),(1.70,.022),(1.713,.0185),(1.75,.020),(1.769,.025),(1.783,.022)],'gold',32)
for z,r in [(1.607,.0217),(1.627,.021),(1.686,.023),(1.705,.0215),(1.752,.023)]:
    lathe('Socket • turned collar',[(z-.003,r-.001),(z-.001,r+.001),(z+.002,r+.001),(z+.004,r-.001)],'gold',32)

# Refined leaf blade with a hard central arris and broad cutting bevels.
profile=[(1.745,.020,.020),(1.765,.028,.025),(1.79,.044,.035),(1.812,.059,.043),
         (1.825,.058,.052),(1.836,.045,.050),(1.850,.036,.039),(1.868,.030,.032),
         (1.887,.029,.030),(1.91,.034,.033),(1.94,.041,.038),(1.97,.046,.043),
         (2.00,.046,.044),(2.03,.041,.040),(2.07,.031,.030),(2.11,.020,.019),
         (2.15,.0108,.0105),(2.18,.0041,.004),(2.20,.00015,.00015)]
# Monotone Hermite silhouette: spend polygons on the visible outline.
coarse=profile
slopes=[]
for i,pf in enumerate(coarse):
    row=[]
    for k in [1,2]:
        before=(pf[k]-coarse[max(0,i-1)][k])/max(1e-9,pf[0]-coarse[max(0,i-1)][0])
        after=(coarse[min(len(coarse)-1,i+1)][k]-pf[k])/max(1e-9,coarse[min(len(coarse)-1,i+1)][0]-pf[0])
        row.append(after if i==0 else before if i==len(coarse)-1 else 0 if before*after<=0 else 2*before*after/(before+after))
    slopes.append(row)
profile=[]
for i,(a,b) in enumerate(zip(coarse,coarse[1:])):
    for q in range(4):
        t=q/4; dz=b[0]-a[0]
        widths=[(2*t**3-3*t*t+1)*a[k]+(t**3-2*t*t+t)*dz*slopes[i][k-1]+(-2*t**3+3*t*t)*b[k]+(t**3-t*t)*dz*slopes[i+1][k-1] for k in [1,2]]
        profile.append((a[0]+dz*t,*widths))
profile.append(coarse[-1])
verts=[]; faces=[]; uv=[]
for z,wl,wr in profile:
    t=.0085*min(1,(2.201-z)/.16)+.0001
    for x,y in [(-wl,0),(-wl*.72,-t*.58),(0,-t),(wr*.72,-t*.58),(wr,0),(wr*.72,t*.58),(0,t),(-wl*.72,t*.58)]: verts.append((x,y,z))
for k in range(len(profile)-1):
    for j in range(8):
        face=(k*8+j,k*8+(j+1)%8,(k+1)*8+(j+1)%8,(k+1)*8+j); faces.append(face)
        uv.append([(.5+verts[q][0]/.135,(verts[q][2]-1.74)/.465) for q in face])
faces.extend([tuple(reversed(range(8))),tuple((len(profile)-1)*8+j for j in range(8))]); uv.extend([[(.5,.01)]*8,[(.5,.99)]*8])
blade=mesh('06 • forged leaf blade',verts,faces,'steel',uv,smooth=True)
# Smooth the blade longitudinally; preserve each crisp diamond-section arris.
custom=[]
for poly in blade.data.polygons:
    if poly.index >= (len(profile)-1)*8:
        custom.extend([poly.normal[:]]*len(poly.loop_indices)); continue
    k,j=divmod(poly.index,8)
    for li in poly.loop_indices:
        ring=blade.data.loops[li].vertex_index//8
        faces_at=[blade.data.polygons[s*8+j] for s in [ring-1,ring] if 0<=s<len(profile)-1]
        normal=sum((f.normal for f in faces_at),Vector()).normalized()
        custom.append(normal[:])
blade.data.normals_split_custom_set(custom)
# Gold hairline down both central ridges; tapers before the tip.
for sign in [-1,1]:
    pts=[]
    for i in range(40):
        z=1.80+i/39*.378; t=.0085*min(1,(2.201-z)/.16)+.00023
        pts.append((0,sign*t,z))
    tube('Blade • inlaid gold spine',pts,.00095,'gold',6)

# Layered chased socket plate and volutes, with actual open silhouette curls.
outline=[(-.023,1.718),(-.036,1.724),(-.042,1.748),(-.047,1.770),(-.039,1.792),
         (-.028,1.809),(-.018,1.803),(-.011,1.786),(.007,1.781),(.030,1.793),
         (.044,1.788),(.047,1.776),(.035,1.767),(.030,1.749),(.021,1.734),(.020,1.716)]
plate('07 • gold palmette socket plate',outline,.050,0)
for side in [-1,1]:
    yy=side*.0265
    # Broad descending S-scroll.
    path('Socket • raised S volute',[(-.032,yy,1.784),(-.035,yy,1.775),(-.031,yy,1.764),(-.021,yy,1.759),(-.012,yy,1.765),(-.013,yy,1.775),(-.021,yy,1.779),(-.026,yy,1.774),(-.022,yy,1.769)],.0023)
    path('Socket • sweeping lower scroll',[(-.027,yy,1.754),(-.016,yy,1.748),(-.009,yy,1.734),(.003,yy,1.731),(.009,yy,1.740),(.008,yy,1.755),(.018,yy,1.770),(.033,yy,1.779)],.0021)
    # Blade-facing flourish echoes the large pierced curl in the photograph.
    path('Blade • crown scroll',[(-.019,side*.010,1.801),(-.015,side*.010,1.817),(-.022,side*.010,1.831),(-.012,side*.010,1.830),(.002,side*.010,1.815),(.018,side*.010,1.810),(.030,side*.010,1.819),(.029,side*.010,1.831),(.019,side*.010,1.835),(.013,side*.010,1.828),(.018,side*.010,1.822),(.024,side*.010,1.825)],.00205)
    # Three tapered spear-shaped leaf engravings on the long socket.
    for a in [-.010,0,.010]:
        path('Socket • chased leaf',[(a,side*.0202,1.636),(a-.004,side*.0208,1.648),(a+.001,side*.021,1.659),(a,side*.0204,1.675)],.00055)

# Cord eye, knotted cord, lacquer beads and a softly spreading silk tassel.
# Eye in the face plane, at the right edge of the collar.
eyepts=[(.044+.010*math.cos(i*2*math.pi/48),0,1.785+.009*math.sin(i*2*math.pi/48)) for i in range(49)]
tube('08 • tassel eye',eyepts,.0026,'gold',8)
path('Tassel • burgundy suspension cord',[(.044,-.001,1.786),(.066,-.002,1.773),(.082,-.004,1.755),(.099,-.006,1.733),(.119,-.006,1.710)],.0021,'silk')
for x,z,r in [(.079,1.759,.008),(.105,1.727,.0095)]:
    lathe('Tassel • lacquer bead',[(z-r,.0015),(z-r*.75,r*.65),(z,r),(z+r*.75,r*.65),(z+r,.0015)],'leather',16,center=(x,-.005))
    lathe('Tassel • gold bead washer',[(z-.001,r+.0003),(z+.001,r+.0003)],'gold',16,center=(x,-.005))
path('Tassel • bound neck',[(.119,-.006,1.710),(.125,-.006,1.702),(.131,-.006,1.694)],.0052,'silk')
# Narrow faceted ribbon strands give a dense textile read without alpha overdraw.
for k in range(42):
    f=k/41; phase=2*math.pi*k*.618; depth=.012*math.sin(phase)
    endx=.225+(f-.5)*.050+random.uniform(-.006,.006); endz=1.550+(f-.5)*.038+random.uniform(-.005,.005)
    pts=[]
    for j in range(9):
        t=j/8
        pts.append((.130+(endx-.130)*t,-.006+depth*t+.005*math.sin(t*math.pi+phase)*t,1.697+(endz-1.697)*t+.009*math.sin(t*math.pi)))
    tube('Tassel • silk strand %02d'%k,pts,.0010+random.random()*.0005,'silk',4)

# Closed convex gameplay hulls. Render tassel is intentionally cosmetic.
def hull(name,coords):
    ob=mesh(name,coords,[],col=collision)
    bm=bmesh.new(); bm.from_mesh(ob.data)
    result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(ob.data); bm.free()
    ob.display_type='WIRE'; ob.hide_render=True; return ob
def hull_lathe(index,profile,sides=12):
    ob=lathe('UCX_SM_ImperialSpear_%02d'%index,profile,sides=sides,col=collision)
    ob.display_type='WIRE'; ob.hide_render=True; return ob
hull_lathe(0,[(.11,.016),(1.625,.016)],12)
hull_lathe(1,[(1.104,.0205),(1.368,.0205)],12)
hull_lathe(2,[(0,.0115),(.12,.018)],12)
hull_lathe(3,[(1.60,.0215),(1.713,.024)],12)
# Plate convex, then shoulder and leaf split so the waist is retained.
for idx,zlo,zhi in [(4,1.71,1.80),(5,1.79,1.867),(6,1.86,1.97),(7,1.96,2.2)]:
    coords=[]
    for z,wl,wr in profile:
        if zlo-.012<=z<=zhi+.012:
            t=max(.0015,.0085*min(1,(2.201-z)/.16))
            coords.extend([(-wl,-.001,z),(-wl,.001,z),(wr,-.001,z),(wr,.001,z),(0,-t,z),(0,t,z)])
    if idx==4: coords += [(x,y,z) for x,z in outline for y in [-.012,.012]]
    hull('UCX_SM_ImperialSpear_%02d'%idx,coords)
for name,z in [('SOCKET_Grip',1.235),('SOCKET_BladeTip',2.20),('SOCKET_Pommel',0),('SOCKET_Tassel',1.785)]:
    ob=bpy.data.objects.new(name,None); markers.objects.link(ob); ob.location=(0,0,z); ob.empty_display_size=.035; ob.empty_display_type='ARROWS'

# Modest CPU studio render; no viewport animation or continuous rendering.
world=bpy.data.worlds.new('Studio charcoal') if not scene.world else scene.world
scene.world=world; world.use_nodes=True; world.node_tree.nodes.clear()
bg=world.node_tree.nodes.new('ShaderNodeBackground'); wo=world.node_tree.nodes.new('ShaderNodeOutputWorld'); world.node_tree.links.new(bg.outputs[0],wo.inputs[0])
bg.inputs[0].default_value=(.11,.14,.18,1); bg.inputs[1].default_value=.45
def light(name,loc,power,size,color,target):
    d=bpy.data.lights.new(name,'AREA'); d.energy=power; d.shape='RECTANGLE'; d.size=size; d.size_y=size*.5; d.color=color
    o=bpy.data.objects.new(name,d); studio.objects.link(o); o.location=loc; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
light('Key • soft silver',(-1,-1.4,2.3),85,2.0,(.86,.93,1),(0,0,1.3))
light('Rim • warm gold',(1.2,.3,1.7),110,1.5,(1,.8,.54),(0,0,1.4))
light('Fill • long strip',(.6,-.7,.5),45,1.2,(1,.95,.85),(0,0,1.1))
camd=bpy.data.cameras.new('Studio Camera'); cam=bpy.data.objects.new('Studio Camera',camd); studio.objects.link(cam)
scene.camera=cam; cam.location=(.22,-4,1.16); target=Vector((.04,0,1.10)); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.rotation_euler.rotate_axis('Z',math.radians(-43)); camd.type='ORTHO'; camd.ortho_scale=2.15
scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED'; scene.render.threads=3
scene.render.resolution_x=1600; scene.render.resolution_y=1100; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=True
scene.view_settings.view_transform='AgX'
scene.render.filepath=str(OUT/'Preview_Full.png')
scene['Asset_Notes']='2.2m spear. Shifted grip centre1.235m. Third-reference blunt gold ferrule. UCX tassel excluded. Made via Blender MCP.'
scene['MCP_upstream']='https://github.com/ahujasid/blender-mcp'
scene['Render_budget']='CPU only, 3 threads, 32 samples, no animation.'
collision.hide_viewport=True
# Configure a convenient saved material viewport and preserve editable parts.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=2.8
            area.spaces.active.region_3d.view_location=(0,0,1.1)
            area.spaces.active.shading.type='SOLID'; area.spaces.active.shading.color_type='MATERIAL'
activate(blade)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ImperialSpear_Source.blend'))
print(json.dumps({'status':'authored','components':len(art.objects),'collision_hulls':len(collision.objects),'vertices':sum(len(o.data.vertices) for o in art.objects if o.type=='MESH'),'polygons':sum(len(o.data.polygons) for o in art.objects if o.type=='MESH')}))
