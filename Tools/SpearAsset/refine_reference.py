"""Reference-led revision02. Run in the owned source session through MCP."""
raise RuntimeError('REJECTED silhouette experiment. User requires the original blade geometry. Use restore_shape_refine_details.py, not this script.')
import bpy,bmesh,math,json,ast,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']; mat=next(o for o in art.objects if o.type=='MESH').data.materials[0]
# Reuse only pure geometry helper definitions, never the original scene reset.
tree=ast.parse((ROOT/'Tools/SpearAsset/build_spear.py').read_text(encoding='utf-8'))
names={'atlas','mesh','activate','bevel','lathe','tube','path'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'spear_geometry_helpers','exec'))
regions={'steel':(0,.25,.5,1),'edge':(.25,.375,.5,1),'ridge':(.375,.4375,.5,1),'steel_shadow':(.4375,.5,.5,1),
         'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1),'lacquer':(.8125,.875,.5,1),'gold_etched':(.875,1,.5,1),
         'wood':(0,.5,0,.5),'leather':(.5,.75,0,.5),'silk':(.75,1,0,.5)}
random.seed(271028)
for o in list(art.objects):
    if o.name.startswith(('06 •','07 •','08 •','Blade •','Tassel •','Socket • raised','Socket • sweeping','Socket • chased')):
        bpy.data.objects.remove(o,do_unlink=True)
# Retain the user's approved forward grip and blunt pommel. Remap gold only.
for o in art.objects:
    if o.type!='MESH' or not o.data.uv_layers: continue
    for uv in o.data.uv_layers[0].data:
        if uv.uv.y>.5 and uv.uv.x>=.5: uv.uv.x=.5+(uv.uv.x-.5)*.5
    if o.name.startswith('05 •'):
        for uv in o.data.uv_layers[0].data:
            uv.uv.x=.875+(uv.uv.x-.5)*.5
    if o.name.startswith(('05 •','Socket • turned')):
        for v in o.data.vertices:
            if v.co.z>1.72: v.co.z=1.72+(v.co.z-1.72)*.35
for image in bpy.data.images:
    if image.source=='FILE': image.reload()

# Screenshot coordinates are traced design data: axis along the straight nervure.
def ref(p):
    dx=p[0]-172; dy=p[1]-9
    return ((dx*.603-dy*.798)*.00096,2.2-(dx*.798+dy*.603)*.00096)
left=[(172,9),(216,62),(263,108),(309,151),(351,180),(389,208),(411,230),(421,252),(426,279),(453,284),(483,296),(510,316),(537,340)]
right=[(172,9),(222,33),(282,65),(337,101),(373,131),(393,152),(418,175),(442,186),(464,189),(494,179),(503,202),(520,226),(545,247),(551,267)]
left=sorted([(z,max(.00003,-x)) for x,z in map(ref,left)])
right=sorted([(z,max(.00003,x)) for x,z in map(ref,right)])
def interp(points,z):
    if z<=points[0][0]: return points[0][1]
    if z>=points[-1][0]: return points[-1][1]
    for i,(a,b) in enumerate(zip(points,points[1:])):
        if a[0]<=z<=b[0]:
            t=(z-a[0])/(b[0]-a[0]); sec=(b[1]-a[1])/(b[0]-a[0])
            before=(a[1]-points[max(0,i-1)][1])/max(1e-9,a[0]-points[max(0,i-1)][0])
            after=(points[min(len(points)-1,i+2)][1]-b[1])/max(1e-9,points[min(len(points)-1,i+2)][0]-b[0])
            da=sec if i==0 else 0 if before*sec<=0 else 2*before*sec/(before+sec)
            db=sec if i==len(points)-2 else 0 if after*sec<=0 else 2*after*sec/(after+sec)
            # Explicit shoulder corners remain sharp.
            if abs(z-1.855)<.014: da=db=sec
            d=b[0]-a[0]
            return (2*t**3-3*t*t+1)*a[1]+(t**3-2*t*t+t)*d*da+(-2*t**3+3*t*t)*b[1]+(t**3-t*t)*d*db
zs=sorted(set([round(1.728+i*(2.2-1.728)/64,7) for i in range(65)]+[round(p[0],7) for p in left+right]))
zs=[z for z in zs if 1.728<=z<=2.2]
profile=[(z,interp(left,z),interp(right,z)) for z in zs]
verts=[]; faces=[]; uv=[]; kinds=[]
for z,wl,wr in profile:
    t=max(.003,(2.2-z)/.46)
    verts.extend([(x,y,z) for x,y in [(-wl,0),(-.78*wl,-.0024*t),(-.0025*t,-.0105*t),(-.0008*t,-.0114*t),(0,-.0114*t),(.0008*t,-.0114*t),(.0025*t,-.0105*t),(.78*wr,-.0024*t),(wr,0),(.78*wr,.0024*t),(.0025*t,.0105*t),(.0008*t,.0114*t),(0,.0114*t),(-.0008*t,.0114*t),(-.0025*t,.0105*t),(-.78*wl,.0024*t)]])
bands=['edge','steel','ridge','steel_shadow','steel_shadow','ridge','steel','edge','edge','steel','ridge','steel_shadow','steel_shadow','ridge','steel','edge']
for k in range(len(profile)-1):
    for j in range(16):
        face=(k*16+j,k*16+(j+1)%16,(k+1)*16+(j+1)%16,(k+1)*16+j); faces.append(face); kinds.append(bands[j])
        uv.append([(0,(profile[k][0]-1.728)/.472),(1,(profile[k][0]-1.728)/.472),(1,(profile[k+1][0]-1.728)/.472),(0,(profile[k+1][0]-1.728)/.472)])
faces.extend([tuple(reversed(range(16))),tuple((len(profile)-1)*16+i for i in range(16))]); kinds+=['steel','ridge']; uv += [[(.5,.1)]*16,[(.5,.9)]*16]
blade=mesh('06 • forged blade with straight steel nervure',verts,faces,'steel',uv,smooth=True)
for poly in blade.data.polygons:
    for j,li in enumerate(poly.loop_indices): blade.data.uv_layers[0].data[li].uv=atlas(*uv[poly.index][j],kinds[poly.index])
custom=[]
for poly in blade.data.polygons:
    if poly.index>=(len(profile)-1)*16: custom.extend([poly.normal[:]]*len(poly.loop_indices)); continue
    k,j=divmod(poly.index,16)
    for li in poly.loop_indices:
        ring=blade.data.loops[li].vertex_index//16
        ns=[blade.data.polygons[s*16+j].normal for s in [ring-1,ring] if 0<=s<len(profile)-1]
        custom.append(sum(ns,Vector()).normalized()[:])
blade.data.normals_split_custom_set(custom)
(OUT/'BladeProfile_Refined.json').write_text(json.dumps(profile),encoding='utf-8')
# A continuous, straight, inset gold hairline. No tube and no bend into the scroll.
for side in [-1,1]:
    coords=[]
    for z in [1.735,1.80,1.90,2.00,2.10,2.19,2.198]:
        t=(2.2-z)/.46
        coords.extend([(x*t,side*(.0114*t+.000035),z) for x in [-.00015,.00055]])
    fs=[(i*2,i*2+1,i*2+3,i*2+2) for i in range(6)]
    mesh('Blade • continuous straight gold inlay',coords,fs,'gold')

# Trace the cast collar silhouette rather than an invented shield outline.
rim_pixels=[(538,285),(553,273),(569,266),(600,270),(613,280),(611,290),(600,291),(604,310),(623,327),(608,350),(589,342),(575,342),(564,350),(558,371),(544,351),(537,330),(536,308)]
rim=[ref(p) for p in rim_pixels]; centre=Vector((0,1.729)); verts=[]
for side,factor,depth in [(-1,.84,.0205),(-1,1,.012),(1,1,.012),(1,.84,.0205)]:
    for x,z in rim:
        q=centre+(Vector((x,z))-centre)*factor; verts.append((q.x,side*depth,q.y))
n=len(rim); fs=[tuple(reversed(range(n))),tuple(3*n+i for i in range(n))]
for k in range(3):
    for i in range(n): fs.append((k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i))
plate=mesh('07 • hooked chased-gold housing',verts,fs,'gold',smooth=False)
bevel(plate,.00055,2)
# Sculpted broad relief ribbons are nested in recessed channels, with tapered ends.
def curve2(points,sub=5):
    pts=[Vector(p) for p in points]; result=[]
    for i in range(len(pts)-1):
        a,b,c,d=pts[max(i-1,0)],pts[i],pts[i+1],pts[min(i+2,len(pts)-1)]
        for q in range(sub):
            t=q/sub; result.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    return result+[pts[-1]]
def ribbon(name,points,side,width,height,depth,kind):
    pts=curve2(points,4); vs=[]; fs=[]
    for i,q in enumerate(pts):
        d=pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]; d.normalize(); normal=Vector((-d.y,d.x))
        taper=.18+.82*math.sin(math.pi*(i+.5)/len(pts))**.45
        for a,h in [(-.5,0),(-.32,.70),(0,1),(.32,.70),(.5,0)]:
            p=q+normal*a*width*taper; vs.append((p.x,side*(depth+height*h*taper),p.y))
    for i in range(len(pts)-1):
        for j in range(4): fs.append((i*5+j,i*5+j+1,(i+1)*5+j+1,(i+1)*5+j))
    return mesh(name,vs,fs,kind,smooth=True)
curl=list(map(ref,[(567,319),(562,321),(557,318),(554,312),(556,304),(561,299),(568,298),(574,302),(578,311),(582,323),(588,335),(595,338),(601,336),(603,331)]))
upper=list(map(ref,[(543,298),(549,289),(557,286),(566,288),(575,296),(582,306),(588,316)]))
crown=list(map(ref,[(469,220),(479,231),(493,234),(508,239),(519,249),(519,263),(525,273),(536,276),(548,272),(557,263),(559,254),(553,249),(547,250)]))
inner=list(map(ref,[(536,268),(529,265),(529,258),(534,255),(540,256),(542,261),(539,264),(536,262)]))
for side in [-1,1]:
    for name,points,w in [('Main cloud',curl,.0048),('Upper sweep',upper,.0056)]:
        ribbon('Socket • '+name+' recessed channel',points,side,w+.0026,.0002,.02065,'gold_shadow')
        ribbon('Socket • '+name+' sculpted relief',points,side,w,.0022,.0208,'gold')
    # Freestanding cast crown, separate from the uninterrupted straight ridge.
    for name,points,w in [('Crown',crown,.0050),('Crown inner curl',inner,.0030)]:
        ribbon('Blade • '+name+' shaded flank',points,side,w+.001,.0008,.0105,'gold_shadow')
        ribbon('Blade • '+name+' cast relief',points,side,w,.0023,.0112,'gold')

# Reference-shaped smooth lacquer beads, with actual bores along the cord.
hole=ref((604,287)); bead1=ref((644,298)); bead2=ref((686,311)); neck=ref((705,320))
eye=[(hole[0]+.0075*math.cos(i*2*math.pi/40),-.001,hole[1]+.0068*math.sin(i*2*math.pi/40)) for i in range(41)]
tube('08 • tassel cast eye',eye,.0022,'gold',8)
cord=[(hole[0],-.008,hole[1]),(bead1[0],-.009,bead1[1]),(bead2[0],-.010,bead2[1]),(neck[0],-.011,neck[1])]
path('Tassel • braided red cord',cord,.00155,'silk')
axis=(Vector(cord[-1])-Vector(cord[0])).normalized()
def bead(name,centre,radius,elongation):
    axislocal=axis; x=axislocal.cross(Vector((0,1,0))).normalized(); y=axislocal.cross(x).normalized()
    sides=28; rings=15; vs=[]; fs=[]; uvs=[]; centre=Vector(centre)
    # Outside goes from one cord-entry lip to the other; inner wall closes bore.
    for k in range(rings+1):
        a=.12+(math.pi-.24)*k/rings; r=radius*math.sin(a); z=radius*math.cos(a)*elongation
        for j in range(sides):
            phi=2*math.pi*j/sides; vs.append(tuple(centre+axislocal*z+(math.cos(phi)*x+math.sin(phi)*y)*r))
    for k in range(rings):
        for j in range(sides):
            fs.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j))
            uvs.append([(j/sides,k/rings),((j+1)/sides,k/rings),((j+1)/sides,(k+1)/rings),(j/sides,(k+1)/rings)])
    for j in range(sides):
        fs.append((j,rings*sides+j,rings*sides+(j+1)%sides,(j+1)%sides)); uvs.append([(0,0),(0,1),(1,1),(1,0)])
    return mesh(name,vs,fs,'lacquer',uvs,smooth=True)
bead('Tassel • small red lacquer bead',(bead1[0],-.009,bead1[1]),.009,1.02)
bead('Tassel • larger oval red lacquer bead',(bead2[0],-.010,bead2[1]),.0113,1.14)
# Bound head and dense pleated fan: texture strands carry the fine weave.
neck3=(neck[0],-.011,neck[1]); endcentre=Vector((.134,1.445)); start=Vector((neck[0],neck[1]-.006))
for i in range(6):
    p=Vector(neck3)+axis*(i*.0011)
    x=axis.cross(Vector((0,1,0))).normalized(); y=axis.cross(x).normalized()
    tube('Tassel • neck binding', [tuple(p+.0032*(x*math.cos(k*math.pi/10)+y*math.sin(k*math.pi/10))) for k in range(21)],.0006,'silk',4)
vs=[]; fs=[]; uvs=[]; rows=12; cols=16
for side in [-1,1]:
    for j in range(rows+1):
        t=.012+.988*j/rows
        for i in range(cols+1):
            f=i/cols-.5; end=endcentre+Vector((.94,.34))*f*.078
            q=start.lerp(end,t); yy=-.011+.0028*math.sin(i*1.7)*t+side*.00018
            vs.append((q.x,yy,q.y+.006*math.sin(t*math.pi)))
layer=(rows+1)*(cols+1)
for side in range(2):
    for j in range(rows):
        for i in range(cols):
            a=side*layer+j*(cols+1)+i; fs.append((a,a+1,a+cols+2,a+cols+1))
            uvs.append([(i/cols,j/rows),((i+1)/cols,j/rows),((i+1)/cols,(j+1)/rows),(i/cols,(j+1)/rows)])
mesh('Tassel • fine pleated silk fan',vs,fs,'silk',uvs,smooth=True)
for k in range(24):
    f=k/23-.5; end=endcentre+Vector((.94,.34))*f*.078
    pts=[]
    for j in range(8):
        t=j/7; q=start.lerp(end,t); pts.append((q.x,-.011+.003*math.sin(k*1.7)*t,q.y+.006*math.sin(t*math.pi)-random.uniform(0,.001)*t))
    tube('Tassel • fine fringe',pts,.00038+random.random()*.00014,'silk',4)
scene['Spear_revision']='02: traced blade/collar, continuous nervure, cast relief, smooth pierced lacquer beads.'
scene['Tassel_socket']=list((hole[0],0,hole[1]))
activate(blade)
print(json.dumps({'revision':2,'source_components':len(art.objects),'source_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in art.objects if o.type=='MESH'),'bead_centres':[bead1,bead2],'plate_bounds':[min(v.co.z for v in plate.data.vertices),max(v.co.z for v in plate.data.vertices)]}))
