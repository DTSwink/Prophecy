"""Detail pass: seated cast volutes and broad turned rings. Blade stays exact."""
import bpy,bmesh,math,json,hashlib,ast
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']
blade=next(o for o in art.objects if o.name.startswith('06 •'))
plate=next(o for o in art.objects if o.name.startswith('07 •'))
mat=blade.data.materials[0]
def fingerprint(o):
    data={'vertices':[tuple(v.co) for v in o.data.vertices],'faces':[tuple(p.vertices) for p in o.data.polygons]}
    return hashlib.sha256(json.dumps(data,separators=(',',':')).encode()).hexdigest()
protected={o.name:fingerprint(o) for o in art.objects if o.name.startswith(('01 •','02 •','03 •','04 •','06 •','07 •','Grip •','Pommel •','Tassel •','08 •'))}
regions={'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1),'gold_etched':(.875,1,.5,1)}
tree=ast.parse((ROOT/'Tools/SpearAsset/build_spear.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'atlas','mesh','activate','lathe'}],type_ignores=[]),'geometry_helpers','exec'))
deps=bpy.context.evaluated_depsgraph_get()
bvh={'blade':BVHTree.FromObject(blade,deps),'plate':BVHTree.FromObject(plate,deps)}
def simplify(points,tol=.00010):
    if len(points)<3: return points
    a,b=points[0],points[-1]; delta=b-a; denom=delta.length_squared
    distances=[(p-(a+delta*max(0,min(1,(p-a).dot(delta)/denom)))).length if denom>1e-15 else (p-a).length for p in points]
    k=max(range(len(points)),key=distances.__getitem__)
    if distances[k]<=tol: return [a,b]
    return simplify(points[:k+1],tol)[:-1]+simplify(points[k:],tol)
guides=[]
for o in list(art.objects):
    if o.name.startswith(('Blade • crown scroll','Socket • raised S volute','Socket • sweeping lower scroll')):
        # Initial paths have six vertices per ring; their centres are retained.
        pts=[sum((o.data.vertices[k+j].co for j in range(6)),Vector())/6 for k in range(0,len(o.data.vertices),6)]
        side=-1 if sum(p.y for p in pts)<0 else 1
        guides.append((o.name,simplify([Vector((p.x,p.z)) for p in pts]),side,'blade' if o.name.startswith('Blade') else 'plate'))
        bpy.data.objects.remove(o,do_unlink=True)
    elif o.name.startswith(('Socket • turned collar','Socket • chased leaf','05 •')):
        bpy.data.objects.remove(o,do_unlink=True)

def curve_value(knots,u):
    for (a,x),(b,y) in zip(knots,knots[1:]):
        if a<=u<=b:
            t=(u-a)/(b-a); t=t*t*(3-2*t); return x*(1-t)+y*t
    return knots[-1][1]
misses=[]; maximum_standoff=0.; counts=[]
def surface_depth(x,z,side,kind):
    loc,normal,index,distance=bvh[kind].ray_cast(Vector((x,side*.2,z)),Vector((0,-side,0)),.4)
    if loc is None:
        misses.append((kind,x,z)); return None
    return abs(loc.y)
for name,pts,side,kind in guides:
    arc=[0.]
    for a,b in zip(pts,pts[1:]): arc.append(arc[-1]+(b-a).length)
    vs=[]; faces=[]; face_kind=[]; widths=[]
    for i,p in enumerate(pts):
        u=arc[i]/arc[-1]; tangent=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized(); cross=Vector((-tangent.y,tangent.x))
        if kind=='blade':
            width=curve_value([(0,.0011),(.10,.0023),(.23,.0035),(.40,.0070),(.57,.0090),(.68,.0072),(.80,.0042),(.94,.0024),(1,.00075)],u)
        elif 'raised S' in name:
            width=curve_value([(0,.0021),(.15,.0064),(.35,.0081),(.58,.0075),(.76,.0045),(1,.00085)],u)
        else:
            width=curve_value([(0,.0010),(.19,.0040),(.40,.0075),(.59,.0082),(.76,.0059),(1,.0009)],u)
        # Pull widths in only if an edge would leave its actual backing surface.
        for attempt in range(8):
            if all(surface_depth(*(p+cross*a*width),side,kind) is not None for a in [-.5,.5]): break
            width*=.82
        widths.append(width)
        height=min(.0022,width*.25)
        section=[(-.5,0),(-.455,.20),(-.28,.82),(0,1),(.28,.82),(.455,.20),(.5,0),(.5,-.16),(-.5,-.16)]
        for a,h in section:
            q=p+cross*a*width; depth=surface_depth(q.x,q.y,side,kind)
            assert depth is not None,('unseated ornament',name,q[:])
            vs.append((q.x,side*(depth-.00010+h*height),q.y))
    n=9
    for i in range(len(pts)-1):
        for j in range(n):
            faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
            face_kind.append('gold_shadow' if j in [0,5,6,7,8] else 'gold')
    faces.extend([tuple(reversed(range(n))),tuple((len(pts)-1)*n+j for j in range(n))]); face_kind+=['gold','gold']
    ob=mesh(name.replace('scroll','cast scroll').replace('volute','cast volute')+' • seated',vs,faces,'gold',smooth=True)
    for poly in ob.data.polygons:
        if poly.index>=n*(len(pts)-1): poly.use_smooth=False
        for li in poly.loop_indices:
            vi=ob.data.loops[li].vertex_index; row,col=divmod(vi,n)
            ob.data.uv_layers[0].data[li].uv=atlas(col/(n-1),arc[row]/arc[-1],face_kind[poly.index])
    bm=bmesh.new(); bm.from_mesh(ob.data); closed=all(e.is_manifold for e in bm.edges); bm.free()
    assert closed
    counts.append({'name':ob.name,'stations':len(pts),'min_width_mm':min(widths)*1000,'max_width_mm':max(widths)*1000,'max_height_mm':min(.0022,max(widths)*.25)*1000,'closed':closed})

def turn(name,profile,kind='gold',sides=40):
    ob=lathe(name,profile,kind,sides)
    # Analytic circumferential normals keep long cylindrical faces truly round.
    normals=[]
    for p in ob.data.polygons:
        if p.index >= (len(profile)-1)*sides:
            normals.extend([p.normal[:]]*len(p.loop_indices)); continue
        segment=p.index//sides
        cylindrical=abs(profile[segment+1][1]-profile[segment][1])<1e-8
        for li in p.loop_indices:
            vi=ob.data.loops[li].vertex_index; ring,j=divmod(vi,sides)
            low=max(0,ring-1); high=min(len(profile)-1,ring+1)
            slope=0 if cylindrical else (profile[high][1]-profile[low][1])/(profile[high][0]-profile[low][0])
            a=2*math.pi*j/sides; normals.append(Vector((math.cos(a),math.sin(a),-slope)).normalized()[:])
    ob.data.normals_split_custom_set(normals)
    return ob
socket_profile=[(1.602,.0155),(1.606,.0195),(1.626,.0195),(1.685,.0195),(1.706,.0195),(1.716,.0185),(1.740,.020),(1.770,.022),(1.783,.0215)]
turn('05 • engraved socket with seated relief',socket_profile,'gold_etched')
ring_specs=[('lower',1.617,.009,.0195,.0252),('upper',1.695,.0095,.0195,.0262)]
for label,centre,half,foot,crown in ring_specs:
    profile=[]
    for i in range(13):
        t=-1+2*i/12
        # Broad half-ellipse with a shallow, seated contact foot at either end.
        radius=foot+(crown-foot)*max(0,1-t*t)**.72
        profile.append((centre+half*t,radius))
    turn('Socket • broad domed '+label+' ring',profile,'gold')
    # A hairline cut at the shoulder is surface detail, not another wire ring.
    for endpoint in [centre-half+.0007,centre+half-.0007]:
        near=min(profile,key=lambda p:abs(p[0]-endpoint))[1]
        turn('Socket • shallow ring shoulder cut',[(endpoint-.00018,near-.00003),(endpoint+.00018,near-.00003)],'gold_shadow',40)
scene['Spear_revision']='04: seated tapered cast gold relief, broad domed rings, worn steel textures; accepted blade and recessed nervure unchanged.'
scene['GoldDetailCollisionVersion']=1
for name,digest in protected.items(): assert fingerprint(bpy.data.objects[name])==digest,('protected geometry changed',name)
report={'revision':4,'protected_objects':len(protected),'protected_geometry_sha256':protected,'blade_and_recess_geometry_unchanged':True,'cast_relief':counts,'seated_back_faces':True,'ring_specs':[{'name':n,'centre_m':c,'axial_width_mm':h*2000,'foot_radius_mm':f*1000,'crown_radius_mm':r*1000} for n,c,h,f,r in ring_specs],'floating_sleeve_strands_removed':True,'texture_based_socket_engraving':True}
(OUT/'Gold_Detail_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='protected_geometry_sha256'}))
