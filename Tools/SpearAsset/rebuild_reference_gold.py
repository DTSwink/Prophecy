"""Reference-traced gold housing, pierced eye, unequal collars and tied tassel.

Keeps the accepted blade mesh/recess, shaft, moved grip and blunt pommel geometry.
Reference pixels are design evidence; this script never changes that blade.
"""
import bpy,bmesh,math,json,ast,hashlib,random
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']
blade=next(o for o in art.objects if o.name.startswith('06 •'))
mat=blade.data.materials[0]
regions={'steel':(0,.25,.5,1),'edge':(.25,.375,.5,1),'ridge':(.375,.4375,.5,1),'steel_shadow':(.4375,.5,.5,1),
 'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1),'lacquer':(.8125,.875,.75,1),'cord':(.8125,.875,.5,.75),
 'gold_etched':(.875,1,.5,1),'wood':(0,.5,0,.5),'leather':(.5,.75,0,.5),'silk':(.75,1,0,.5)}
for filename,names in [('build_spear.py',{'atlas','mesh','activate','lathe','tube','path'}),('refine_cast_gold.py',{'turn','fingerprint'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
protected={o.name:fingerprint(o) for o in art.objects if o.name.startswith(('01 •','02 •','03 •','04 •','06 •','Grip •','Pommel •'))}
for o in list(art.objects):
 if o.name.startswith(('05 •','07 •','08 •','Socket •','Blade • crown','Blade • Crown','Blade • flame','Tassel •')):
  bpy.data.objects.remove(o,do_unlink=True)
AX,AY=.798,.603; norm=math.hypot(AX,AY); AX/=norm; AY/=norm; S=.00096
def ref(p):
 dx=p[0]-172; dy=p[1]-9
 return Vector(((dx*AY-dy*AX)*S,2.2-(dx*AX+dy*AY)*S))
def r3(p,y=0):
 q=ref(p); return Vector((q.x,y,q.y))
def cubic(a,b,c,d,t): return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
def bezier_chain(start,segments,step=1.6):
 result=[Vector(start)]; a=Vector(start)
 for c1,c2,end in segments:
  b,c,d=map(Vector,(c1,c2,end)); count=max(4,math.ceil(((b-a).length+(c-b).length+(d-c).length)/step))
  for j in range(1,count+1): result.append(cubic(a,b,c,d,j/count))
  a=d
 return result
def smooth_polygon(points,sharp=(),samples=4):
 result=[]; n=len(points); pts=list(map(Vector,points))
 for i,p in enumerate(pts):
  nxt=pts[(i+1)%n]; before=pts[(i-1)%n]; after=pts[(i+2)%n]
  t0=Vector((0,0)) if i in sharp else (nxt-before)*.18
  t1=Vector((0,0)) if (i+1)%n in sharp else (after-p)*.18
  for j in range(samples): result.append(cubic(p,p+t0,nxt-t1,nxt,j/samples))
 return result
def extrude(name,pixels,back,front,kind='gold'):
 points=[ref(p) for p in pixels]; n=len(points)
 verts=[(p.x,y,p.y) for y in (back,front) for p in points]
 faces=[tuple(reversed(range(n))),tuple(n+i for i in range(n))]
 faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 return mesh(name,verts,faces,kind)
def boolean(target,cutter,operation='DIFFERENCE'):
 activate(target); mod=target.modifiers.new('Reference casting operation','BOOLEAN'); mod.operation=operation; mod.solver='EXACT'; mod.object=cutter
 bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(cutter,do_unlink=True)
def finish_bevel(ob,width,segments=3):
 activate(ob); mod=ob.modifiers.new('Small cast edge radius','BEVEL'); mod.width=width; mod.segments=segments; mod.limit_method='ANGLE'; mod.angle_limit=math.radians(25); mod.harden_normals=True
 bpy.ops.object.modifier_apply(modifier=mod.name)
 for p in ob.data.polygons: p.use_smooth=abs(p.normal.y)<.999
 ob.data.set_sharp_from_angle(angle=math.radians(75))
 return ob

# Compact closed body with the reference's hooked lower crescent. No open bracket.
body_outline=[(537,285),(550,279),(571,266),(590,267),(604,271),(612,277),(615,285),(613,296),(610,304),(615,313),(627,321),(619,333),(610,348),(602,362),(584,352),(573,347),(565,349),(560,355),(556,371),(548,362),(542,351),(539,335),(538,316)]
body=extrude('07 • reference cast housing with pierced eye',smooth_polygon(body_outline,{10,13,18},4),.0115,-.0115)
eye=ref((604,287))
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.0080,depth=.065,location=(eye.x,0,eye.y),rotation=(math.pi/2,0,0))
cutter=bpy.context.object; cutter.name='TEMP • through eye cutter'
boolean(body,cutter); finish_bevel(body,.00135,3)

# Long upper socket, broad central ring, and short lower cuff before the wood.
NECK=ref((616,344)).y; BROAD=ref((681,395)).y; END=ref((727,426)).y
profile=[(END-.002,.0161),(END+.001,.0187),(END+.006,.0192),(BROAD-.013,.0190),
 (BROAD+.012,.0191),(NECK-.007,.0192),(NECK+.005,.0177),(NECK+.018,.0156)]
turn('05 • long engraved socket and short end cuff',profile,'gold_etched',40)
turn('Socket • thin flared neck ring',[(NECK-.0040,.0191),(NECK-.003,.0218),(NECK-.001,.0250),(NECK+.0006,.0256),(NECK+.0020,.0247),(NECK+.0033,.0213),(NECK+.0040,.0181)],'gold',40)
turn('Socket • broad asymmetrical middle ring',[(BROAD-.0095,.0188),(BROAD-.0080,.0214),(BROAD-.0055,.0247),(BROAD-.0020,.0262),(BROAD+.0020,.0264),(BROAD+.0055,.0255),(BROAD+.0080,.0227),(BROAD+.0095,.0192)],'gold',40)
turn('Socket • narrow terminal cuff rim',[(END-.0018,.0160),(END-.0005,.0194),(END+.0010,.0196),(END+.0022,.0187)],'gold',40)

# Accurate forked stalk and compact spiral, cast as flat-backed rounded metal.
stalk=[(466,218),(474,227),(487,232),(494,233),(496,225),(498,234),(509,235),(519,241),(525,252),(520,258),(515,246),(508,241),(498,239),(493,243),(492,238),(479,235),(470,229)]
spiral=bezier_chain((548,249),[
 ((558,245),(568,251),(569,261)),((570,273),(558,283),(547,285)),
 ((532,288),(521,279),(520,267)),((518,258),(522,252),(531,252)),
 ((537,251),(543,256),(543,262)),((543,267),(538,269),(534,266)),
 ((531,264),(532,261),(534,260)),((535,260),(536,261),(537,262)),
 ((535,262),(535,264),(537,264)),((540,265),(540,260),(537,258)),
 ((532,254),(526,256),(526,263)),((525,270),(532,276),(541,277)),
 ((552,278),(562,269),(561,260)),((562,255),(557,251),(548,249))],1.6)[:-1]
bvh=BVHTree.FromObject(blade,bpy.context.evaluated_depsgraph_get())
for side in [-1,1]:
 crown=extrude('Blade • flame and compact cast spiral',spiral,side*.0084,side*.0125)
 branch=extrude('TEMP • forked flame',smooth_polygon(stalk,{0,4,9,13},3),side*.0084,side*.0125)
 boolean(crown,branch,'UNION'); finish_bevel(crown,.0012,3)
 # Follow the steel face, keeping the thin relief seated rather than floating.
 for v in crown.data.vertices:
  hit=bvh.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  depth=abs(hit.y) if hit else .0083
  v.co.y=side*(abs(v.co.y)-.0084+depth-.00015)

# One continuous inverted-S motif. A shallow recess surrounds the cast relief.
guide=[(563,318),(565,316),(568,319),(566,324),(561,325),(556,322),(553,316),(552,309),(555,301),(560,297),(568,296),(575,300),(579,308),(583,321),(588,333),(594,338),(601,338),(607,334),(610,329),(607,326),(604,327)]
pts=[]
gv=list(map(Vector,guide))
for i in range(len(gv)-1):
 a,b,c,d=gv[max(0,i-1)],gv[i],gv[i+1],gv[min(len(gv)-1,i+2)]
 for j in range(5):
  t=j/5; pts.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
pts.append(gv[-1]); total=len(pts)
def width_at(u):
 knots=[(0,1.4),(.20,3.2),(.35,6.5),(.48,9.5),(.64,8.0),(.80,5.5),(.92,3.4),(1,1.1)]
 for (a,x),(b,y) in zip(knots,knots[1:]):
  if a<=u<=b:
   t=(u-a)/(b-a); return x*(1-t)+y*t
 return knots[-1][1]
def ribbon_outline(extra):
 left=[]; right=[]
 for i,p in enumerate(pts):
  tangent=(pts[min(i+1,total-1)]-pts[max(i-1,0)]).normalized(); n=Vector((-tangent.y,tangent.x)); w=width_at(i/(total-1))+extra
  left.append(p+n*w*.5); right.append(p-n*w*.5)
 return left+list(reversed(right))
for side in [-1,1]:
 # A narrow oxidized border is seated on the casting; the separate relief
 # embeds below the face. Avoid a self-overlapping concave Boolean operand.
 border=extrude('Socket • relief patina border',ribbon_outline(1.1),side*.01148,side*.01154,'gold_shadow')
 verts=[]; faces=[]; n=9
 for i,p in enumerate(pts):
  tangent=(pts[min(i+1,total-1)]-pts[max(i-1,0)]).normalized(); normal=Vector((-tangent.y,tangent.x)); width=width_at(i/(total-1))
  for a,h in [(-.5,0),(-.46,.32),(-.28,.85),(0,1),(.28,.85),(.46,.32),(.5,0),(.45,-.2),(-.45,-.2)]:
   q=ref(p+normal*a*width); top=.0012+min(.0016,width*S*.17)
   verts.append((q.x,side*(.01055+h*top),q.y))
 for i in range(total-1):
  for j in range(n): faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
 faces += [tuple(reversed(range(n))),tuple((total-1)*n+j for j in range(n))]
 relief=mesh('Socket • continuous cast inverted S',verts,faces,'gold',smooth=True)
 for p in relief.data.polygons:
  if p.index>=n*(total-1): p.use_smooth=False
for p in body.data.polygons: p.use_smooth=abs(p.normal.y)<.999

# Rough leather loop threads the actual opening, around its right-hand bridge.
loop=[((605,285),-.014),((599,284),-.011),((599,284),.012),((606,286),.014),((616,290),.009),((616,292),-.011),((609,291),-.014),((605,285),-.014)]
path('Tassel • threaded leather attachment loop',[r3(p,y) for p,y in loop],.00185,'cord')
cord_pixels=[(608,288),(618,291),(632,295),(644,298),(666,305),(686,311),(702,316),(708,319)]
cord=[r3(p,-.012 if i<2 else -.010) for i,p in enumerate(cord_pixels)]
path('Tassel • rough leather cord through beads',cord,.00185,'cord')
axis=(r3((702,316))-r3((632,295))).normalized()
cross=axis.cross(Vector((0,1,0))).normalized(); up=axis.cross(cross).normalized()
def bead(name,pixel,radius,elongation):
 centre=r3(pixel,-.010); sides=32; rings=16; theta=math.asin(.0025/radius); vs=[]; fs=[]; uv=[]
 for k in range(rings+1):
  a=theta+(math.pi-2*theta)*k/rings; radius_here=radius*math.sin(a); along=radius*math.cos(a)*elongation
  for j in range(sides):
   phi=math.tau*j/sides; vs.append(tuple(centre+axis*along+(cross*math.cos(phi)+up*math.sin(phi))*radius_here))
 for k in range(rings):
  for j in range(sides):
   fs.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j)); uv.append([(j/sides,k/rings),((j+1)/sides,k/rings),((j+1)/sides,(k+1)/rings),(j/sides,(k+1)/rings)])
 for j in range(sides):
  fs.append((j,rings*sides+j,rings*sides+(j+1)%sides,(j+1)%sides)); uv.append([(0,0),(0,1),(1,1),(1,0)])
 return mesh(name,vs,fs,'lacquer',uv,smooth=True)
bead('Tassel • pierced small dark lacquer bead',(644,298),.0094,1.08)
bead('Tassel • pierced oval dark lacquer bead',(686,311),.0115,1.13)
# A compact knot around the doubled eye strands; no floating ornamental ring.
knotcentre=r3((616,291),-.013)
for phase in [0,math.pi]:
 p=[]
 for j in range(25):
  t=j/24; a=phase+t*math.tau*1.15
  p.append(tuple(knotcentre+axis*((t-.5)*.0045)+(cross*math.cos(a)+up*math.sin(a))*.0026))
 tube('Tassel • compact attachment knot',p,.00095,'cord',6)
neck=r3((704,317),-.010)
for i in range(5):
 centre=neck+axis*((i-2)*.00145)
 p=[tuple(centre+(cross*math.cos(j*math.tau/24)+up*math.sin(j*math.tau/24))*(.0030+.0003*math.sin(i))) for j in range(25)]
 tube('Tassel • tight throat binding',p,.00075,'cord',6)

# Curved silk bundles in the reference pose; tapered spacing carries the fan.
random.seed(27102710)
def strand_pixel(f,t):
 top=cubic(Vector((706,314)),Vector((763,314)),Vector((850,330)),Vector((891,345)),t)
 bottom=cubic(Vector((706,321)),Vector((753,344)),Vector((824,392)),Vector((873,411)),t)
 return top.lerp(bottom,f)
for k in range(24):
 vs=[]; fs=[]; uv=[]; rows=13; end_jitter=random.uniform(-2.2,2.2)
 for layer in [-1,1]:
  for j in range(rows+1):
   t=.012+.988*j/rows
   for edge in [-1,1]:
    f=(k+.5+edge*.46)/24; p=strand_pixel(f,t); p.y+=end_jitter*t*t
    q=r3(p,-.009+.0018*math.sin(f*math.pi*22)*t+layer*.00012)
    vs.append(tuple(q))
 one=(rows+1)*2
 for layer in range(2):
  for j in range(rows):
   a=layer*one+j*2; face=(a,a+1,a+3,a+2) if layer==0 else (a+2,a+3,a+1,a)
   fs.append(face); uv.append([(k/24,j/rows),((k+1)/24,j/rows),((k+1)/24,(j+1)/rows),(k/24,(j+1)/rows)])
 mesh('Tassel • reference silk bundle',vs,fs,'silk',uv,smooth=True)
for k in range(20):
 f=k/19; points=[]
 for j in range(10):
  t=j/9; p=strand_pixel(f,t); p.y+=(-4 if k<3 else 2)*math.sin(t*math.pi)+random.uniform(-.3,.3)*t
  points.append(r3(p,-.011+.001*math.sin(k)))
 tube('Tassel • fine loose filament',points,.00022,'silk',4)

# Neutral lighting separates subdued wood/cord from metallic highlights.
for name,power,size,size_y,color in [('Key • soft silver',85,1.3,.65,(1,1,1)),('Rim • warm gold',45,1.2,.6,(1,.94,.82)),('Fill • long strip',20,1.2,.5,(1,1,1))]:
 ob=bpy.data.objects.get(name)
 if ob: ob.data.energy=power; ob.data.size=size; ob.data.size_y=size_y; ob.data.color=color
for node in scene.world.node_tree.nodes:
 if node.type=='BACKGROUND' and node.name=='Background': node.inputs['Color'].default_value=(.10,.10,.10,1); node.inputs['Strength'].default_value=.20
principled=mat.node_tree.nodes.get('Principled BSDF')
if 'Coat Weight' in principled.inputs: principled.inputs['Coat Weight'].default_value=0
if 'IOR' in principled.inputs: principled.inputs['IOR'].default_value=1.45
for image in bpy.data.images:
 if image.source=='FILE' and image.name.startswith('T_ImperialSpear_'):
  filename=image.name.split('.png')[0]+'.png'
  image.filepath=str(OUT/'Textures'/filename); image.reload()
for name,digest in protected.items(): assert fingerprint(bpy.data.objects[name])==digest,('Protected geometry changed',name)
scene['Tassel_socket']=[eye.x,0,eye.y]
scene['Spear_revision']='05 WIP: reference-traced compact pierced housing, forked flame, unequal rings, threaded rough cord and material contrast.'
scene['Reference_rebuild_in_progress']=True
scene['GoldDetailCollisionVersion']=2
report={'revision':5,'status':'visual comparison in progress; exports/collision pending','protected_geometry_sha256':protected,
 'accepted_blade_and_recess_unchanged':True,'reference_camera':'Reference_Camera.json',
 'eye_reference_px':[604,287],'eye_through_housing':True,'separate_gold_ring_removed':True,
 'collar_centres_z_m':{'neck':NECK,'broad':BROAD,'terminal':END},'collar_axial_width_mm':{'neck':8,'broad':19,'terminal':4},
 'short_end_cuff_present':True,'rough_cord_threaded_and_bound':True,
 'source_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in art.objects if o.type=='MESH')}
(OUT/'Reference_Rebuild_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
scene.render.filepath=str(OUT/'Comparison_Current.png'); bpy.ops.render.render(write_still=True)
print(json.dumps({k:v for k,v in report.items() if k!='protected_geometry_sha256'}))
