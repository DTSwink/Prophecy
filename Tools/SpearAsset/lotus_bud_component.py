"""Pure-Python, closed lotus-bud component for the Imperial Spear pommel.

No bpy, file I/O or scene mutation.  All dimensions are metres.  The collar
interface is z=+0.003; the small rounded terminal button ends at z=-0.031.
The six petal boundaries are integrated carved surfaces, not added tubes.

build_lotus_bud() returns vertices, faces, flattened per-corner uvs/normals/cavity and
a report. UVs are a local 0..1 cylindrical island plus a polar top cap; the
caller maps these into its gold tile.  Give all polygons smooth shading and
install the returned split normals to preserve the small machined chamfers.
"""
import math

TAU = math.tau
PETALS = 6
# Petal boundaries are closed leaf-shaped arches, not constant-U meridians.
# Each section has 20 lanes per petal. Their positions move with Z while their
# topology stays paired, so the lips sweep away from a tight root and converge
# again directly above the small terminal button.
BODY_PROFILE = ((-.02625, .00240), (-.0255, .00470), (-.0244, .00720),
                (-.0230, .00950), (-.0213, .01200), (-.0170, .01555),
                (-.0145, .01655), (-.0120, .01665), (-.0094, .01650),
                (-.0068, .01615), (-.0045, .01560),
                (-.0024, .01500), (-.0004, .01455),
                (.0004, .01445), (.0007, .01385),
                (.0012, .01385), (.003, .01400))
BODY_Z_BASE = (-.02625, -.0255, -.0244, -.0230, -.0213, -.0193,
          -.0170, -.0145, -.0120, -.0094, -.0068, -.0045,
          -.0024, -.0004, .0004, .0007, .0012, .003)
# Split long curvature intervals, retaining economical rows on the tiny root
# shoulder. These are shape samples, not a subdivision modifier.
BODY_Z = tuple(sorted(set(BODY_Z_BASE + tuple((a+b)*.5 for a,b in zip(BODY_Z_BASE,BODY_Z_BASE[1:]) if b-a>.0009))))
BUTTON_PROFILE = ((-.031, 0.), (-.0307, .00130), (-.0301, .00208),
                  (-.0293, .00270), (-.0284, .00285), (-.0275, .00262),
                  (-.0268, .00204), (-.02660, .00200))


def _add(a, b):
    return tuple(x+y for x,y in zip(a,b))


def _sub(a, b):
    return tuple(x-y for x,y in zip(a,b))


def _dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unit(v):
    n = math.sqrt(_dot(v,v))
    if n < 1e-16:
        raise ValueError('Zero tangent or normal')
    return tuple(x/n for x in v)


def _pchip(knots, x):
    xs,ys = zip(*knots)
    hs = [b-a for a,b in zip(xs,xs[1:])]
    ds = [(b-a)/h for a,b,h in zip(ys,ys[1:],hs)]
    ms = [ds[0]]
    for i in range(1,len(xs)-1):
        if ds[i-1]*ds[i] <= 0:
            ms.append(0.)
        else:
            aa,bb = 2*hs[i]+hs[i-1], hs[i]+2*hs[i-1]
            ms.append((aa+bb)/(aa/ds[i-1]+bb/ds[i]))
    ms.append(ds[-1])
    if x <= xs[0]:
        return ys[0]+ms[0]*(x-xs[0])
    if x >= xs[-1]:
        return ys[-1]+ms[-1]*(x-xs[-1])
    i = next(i for i in range(len(hs)) if x <= xs[i+1])
    t,h = (x-xs[i])/hs[i], hs[i]
    return ((2*t*t*t-3*t*t+1)*ys[i] + (t*t*t-2*t*t+t)*h*ms[i]
            + (-2*t*t*t+3*t*t)*ys[i+1] + (t*t*t-t*t)*h*ms[i+1])


def _smooth(t):
    t = max(0.,min(1.,t))
    return t*t*(3-2*t)


def _section_parameters(z):
    t=max(0.,min(1.,(.003-z)/.02925))
    width=.035+.390*math.sin(math.pi*t)**.78
    left,right=.5-width,.5+width
    def smooth_min(a,b,k=.006):
        return min(a,b)-max(k-abs(a-b),0.)**2/(4*k)
    b=smooth_min(smooth_min(.065,width*.20),(.5-width)*.78)
    return width,left,right,b


def _cheek_knots(z):
    width,left,right,b=_section_parameters(z)
    return ((left+2.15*b,.00020),(left+width*.62,.00045),
            (.5,.00065),(right-width*.62,.00045),(right-2.15*b,.00020))


def _petal_section(z):
    width,left,right,b=_section_parameters(z)
    cheek=_cheek_knots(z)
    toe,mid=cheek[0][0],cheek[1][0]
    qlow,qhigh=(toe+mid)*.5,(mid+.5)*.5
    return ((0.,-.00018),
            (left-b,-.00018),(left-.40*b,-.00085),
            (left+.30*b,.00095),(left+1.15*b,.00095),
            (left+1.90*b,.00025),(left+2.15*b,.00020),
            (qlow,_pchip(cheek,qlow)),(left+width*.62,.00045),
            (qhigh,_pchip(cheek,qhigh)),(.5,.00065),
            (1-qhigh,_pchip(cheek,1-qhigh)),(right-width*.62,.00045),
            (1-qlow,_pchip(cheek,1-qlow)),(right-2.15*b,.00020),
            (right-1.90*b,.00025),(right-1.15*b,.00095),
            (right-.30*b,.00095),(right+.40*b,-.00085),
            (right+b,-.00018),(1.,-.00018))


def _cavity(z,u):
    """Geometry-derived mask: full at gutters, reduced at inner bevel toes.

    It is zero on every lip land, broad petal field and outer background.  The
    caller can use it for restrained occlusion without darkening all the gold.
    """
    if not BODY_Z[0]<=z<=BODY_Z[-1]:
        return 0.
    q=(u*PETALS)%1.
    section=_petal_section(z)
    values=(0.,0.,1.,0.,0.,.72,.32,.16,0.,0.,0.,0.,0.,.16,.32,.72,0.,0.,1.,0.,0.)
    fade=_smooth((z+.02625)/.0028)*_smooth((.003-z)/.0025)
    for i,((a,_),(b,_)) in enumerate(zip(section,section[1:])):
        if a<=q<=b:
            return max(0.,min(1.,(values[i]+(values[i+1]-values[i])*(q-a)/(b-a))*fade))
    raise ValueError((z,u,q))


def _unrounded_relief(z,u):
    section=_petal_section(z)
    cheek=_cheek_knots(z)
    if cheek[0][0]<=u<=cheek[-1][0]:
        return _pchip(cheek,u)
    for (a,ra),(b,rb) in zip(section,section[1:]):
        if a<=u<=b:
            return ra+(rb-ra)*(u-a)/(b-a)
    raise ValueError((z,u))


def _relief(z,u):
    u %= 1.
    section=_petal_section(z)
    b=_section_parameters(z)[3]
    # Small C1 fillets on the inner-wall bottom and its toe remove the abrupt
    # machined cutoff while preserving the full flat land and0.70mm wall.
    # Their physical half-width is roughly0.08mm at the belly.
    half=.08*b
    for index in (5,6,14,15):
        q=section[index][0]
        if q-half<=u<=q+half:
            a,c=q-half,q+half;h=c-a;t=(u-a)/h
            fa,fc=_unrounded_relief(z,a),_unrounded_relief(z,c)
            eps=half*.001
            ma=(_unrounded_relief(z,a+eps)-_unrounded_relief(z,a-eps))/(2*eps)
            mc=(_unrounded_relief(z,c+eps)-_unrounded_relief(z,c-eps))/(2*eps)
            return ((2*t**3-3*t*t+1)*fa+(t**3-2*t*t+t)*h*ma
                    +(-2*t**3+3*t*t)*fc+(t**3-t*t)*h*mc)
    return _unrounded_relief(z,u)


def _twist(z):
    t = max(0.,min(1.,(.003-z)/.02925))
    return .10*math.sin(math.pi*t)**1.2+.015*t


def _body_point(z, u):
    radius = _pchip(BODY_PROFILE,z)
    # Relief terminates in the small throat immediately above the button, and
    # stays visible at the root before disappearing beneath the collar.
    gain = _smooth((z+.02625)/.0028) * (.15+.85*_smooth((.003-z)/.0038))
    radius += _relief(z,u*PETALS)*gain
    theta = TAU*u+_twist(z)
    return (radius*math.cos(theta),radius*math.sin(theta),z)


def _button_point(z,u):
    radius = _pchip(BUTTON_PROFILE,z)
    theta = TAU*u+_twist(BODY_Z[0])
    return (radius*math.cos(theta),radius*math.sin(theta),z)


def _surface_normal(z,u,side,body):
    point = _body_point if body else _button_point
    # The one-sided U derivative is intentional only at carved-wall breaks.
    du = 1e-7
    a,b = (u,u+du) if side>=0 else (u-du,u)
    across = _sub(point(z,b),point(z,a))
    dz = 1e-7
    lo,hi = (BODY_Z[0],BODY_Z[-1]) if body else (BUTTON_PROFILE[0][0],BUTTON_PROFILE[-1][0])
    zz0,zz1 = max(lo,z-dz),min(hi,z+dz)
    if body:
        # Follow the same moving petal lane for the longitudinal derivative.
        # A derivative at fixed physical theta would cross the sharp moving
        # border and average its two normals, erasing the carved-wall break.
        petal=math.floor(u*PETALS);q=u*PETALS-petal
        section=_petal_section(z)
        probe=max(0.,min(1.-1e-12,q+(1e-7 if side>=0 else -1e-7)))
        band=next(i for i in range(len(section)-1) if section[i][0]<=probe<=section[i+1][0])
        qa,qb=section[band][0],section[band+1][0]
        alpha=max(0.,min(1.,(q-qa)/(qb-qa)))
        s0,s1=_petal_section(zz0),_petal_section(zz1)
        q0=s0[band][0]+alpha*(s0[band+1][0]-s0[band][0])
        q1=s1[band][0]+alpha*(s1[band+1][0]-s1[band][0])
        along=_sub(point(zz1,(petal+q1)/PETALS),point(zz0,(petal+q0)/PETALS))
    else:
        along = _sub(point(zz1,u),point(zz0,u))
    return _unit(_cross(across,along))


def _validate(vertices,faces,uvs,normals):
    edge_uses = {}
    volume = 0.
    area_min = math.inf
    uv_area_min = math.inf
    minimum_dot = 1.
    cursor = 0
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):
            edge_uses.setdefault(tuple(sorted((a,b))),[]).append((a,b))
        for j in range(1,len(f)-1):
            a,b,c = (vertices[i] for i in (f[0],f[j],f[j+1]))
            cross = _cross(_sub(b,a),_sub(c,a))
            area_min = min(area_min,.5*math.sqrt(_dot(cross,cross)))
            volume += _dot(a,_cross(b,c))/6
            normal = _unit(cross)
            ua,ub,uc = (uvs[cursor+k] for k in (0,j,j+1))
            uv_area_min = min(uv_area_min,abs((ub[0]-ua[0])*(uc[1]-ua[1])-(ub[1]-ua[1])*(uc[0]-ua[0]))*.5)
            for k in (0,j,j+1):
                minimum_dot = min(minimum_dot,_dot(normal,normals[cursor+k]))
        cursor += len(f)
    bad = [edge for edge,uses in edge_uses.items() if len(uses)!=2 or uses[0]!=(uses[1][1],uses[1][0])]
    if bad or volume<=0 or area_min<=1e-14 or uv_area_min<=1e-12 or minimum_dot<=0:
        raise ValueError({'bad_edges':len(bad),'volume':volume,'min_area':area_min,'minimum_dot':minimum_dot})
    if cursor!=len(uvs) or cursor!=len(normals):
        raise ValueError('Corner attribute length mismatch')
    return {'closed_consistently_wound':True,'volume_m3':volume,
            'minimum_fan_triangle_area_m2':area_min,
            'minimum_uv_triangle_area':uv_area_min,
            'minimum_custom_normal_face_dot':minimum_dot}


def build_lotus_bud():
    vertices=[];faces=[];uvs=[];normals=[]
    rings=[]
    # Keep the visually small button economical; the broad petals receive the
    # denser cross-section necessary for their paired bevels and smooth cheeks.
    for z in (p[0] for p in BUTTON_PROFILE[1:]):
        us=[i/24 for i in range(24)]
        indices=[]
        for u in us:
            indices.append(len(vertices));vertices.append(_button_point(z,u))
        rings.append({'z':z,'u':us,'ids':indices,'body':False})
    for z in BODY_Z:
        us=[(petal+item[0])/PETALS for petal in range(PETALS) for item in _petal_section(z)[:-1]]
        indices=[]
        for u in us:
            indices.append(len(vertices));vertices.append(_body_point(z,u))
        rings.append({'z':z,'u':us,'ids':indices,'body':True})

    def corner(ring,index,unwrapped_u,face_mid):
        z=ring['z'];u=unwrapped_u
        uv=(u,(z+.031)/.034)
        normal=_surface_normal(z,u,1 if face_mid>=u else -1,ring['body'])
        return ring['ids'][index%len(ring['ids'])],uv,normal

    def face(items,transition=None):
        if transition is not None:
            dz,dr=transition
            fixed=[]
            for index,uv,normal in items:
                x,y,z=vertices[index];angle=math.atan2(y,x)
                fixed.append((index,uv,_unit((dz*math.cos(angle),dz*math.sin(angle),-dr))))
            items=fixed
        faces.append([item[0] for item in items])
        uvs.extend(item[1] for item in items)
        normals.extend(item[2] for item in items)

    # Close the bottom with a smooth spherical pole.
    pole=len(vertices);vertices.append((0.,0.,-.031))
    ring=rings[0]
    for j,u in enumerate(ring['u']):
        un=ring['u'][j+1] if j+1<len(ring['u']) else 1.
        mid=(u+un)/2
        face([(pole,(mid,0.),(0.,0.,-1.)),
              corner(ring,j+1,un,mid),corner(ring,j,u,mid)])

    # Annular stitching handles the 24-to-84 vertex transition without loose
    # vertices, overlapping caps or a high-density button.
    for lower,upper in zip(rings,rings[1:]):
        i=j=0;nl=len(lower['u']);nu=len(upper['u'])
        if lower['body'] and upper['body']:
            # Identical lanes have deliberately different angular positions
            # along Z: preserve those curved petal boundaries with quads.
            for j in range(nl):
                ln=lower['u'][j+1] if j+1<nl else 1.
                un=upper['u'][j+1] if j+1<nu else 1.
                lu,uu=lower['u'][j],upper['u'][j]
                lm,um=(lu+ln)/2,(uu+un)/2
                face([corner(lower,j,lu,lm),corner(lower,j+1,ln,lm),
                      corner(upper,j+1,un,um),corner(upper,j,uu,um)])
            continue
        transition=None
        if lower['body']!=upper['body']:
            transition=(upper['z']-lower['z'],BODY_PROFILE[0][1]-BUTTON_PROFILE[-1][1])
        while i<nl or j<nu:
            lu=lower['u'][i] if i<nl else 1.
            uu=upper['u'][j] if j<nu else 1.
            ln=lower['u'][i+1] if i+1<nl else 1.
            un=upper['u'][j+1] if j+1<nu else 1.
            mid=(max(lu,uu)+min(ln,un))/2
            a=corner(lower,i,lu,mid);d=corner(upper,j,uu,mid)
            if abs(ln-un)<1e-12:
                face([a,corner(lower,i+1,ln,mid),corner(upper,j+1,un,mid),d],transition);i+=1;j+=1
            elif ln<un:
                face([a,corner(lower,i+1,ln,mid),d],transition);i+=1
            else:
                face([a,corner(upper,j+1,un,mid),d],transition);j+=1

    # Buried root cap: a separate polar UV island avoids collapsed UVs.
    top=rings[-1]
    centre=len(vertices);vertices.append((0.,0.,top['z']))
    for j,index in enumerate(top['ids']):
        items=[(centre,(.5,.5),(0.,0.,1.))]
        for ii in (index,top['ids'][(j+1)%len(top['ids'])]):
            x,y,z=vertices[ii]
            items.append((ii,(.5+x/.032,.5+y/.032),(0.,0.,1.)))
        face(items)
    checks=_validate(vertices,faces,uvs,normals)
    cavity=[]
    for f in faces:
        for index in f:
            x,y,z=vertices[index]
            u=(math.atan2(y,x)-_twist(z))/TAU
            cavity.append(_cavity(z,u))
    assert len(cavity)==len(uvs) and all(0<=c<=1 for c in cavity)
    report={'design':'Lotus bud V5: smoothly sampled full bulb, polished petal lands and filleted carved-wall toes',
            'vertices':len(vertices),'polygons':len(faces),
            'triangles':sum(len(f)-2 for f in faces),'petals':PETALS,
            'axial_body_rings':len(BODY_Z),
            'transverse_lanes_per_petal':len(_petal_section(-.012))-1,
            'inner_bevel_toe_fillet_half_width_mm':.08*_section_parameters(-.012)[3]*TAU/PETALS*.01665*1000,
            'z_span_m':[-.031,.003],
            'maximum_radius_m':max(math.hypot(v[0],v[1]) for v in vertices),
            'petal_peak_to_groove_mm':1.80,
            'outer_gutter_depth_below_background_mm':.67,
            'inner_bevel_drop_mm':.70,
            'inner_bevel_toe_drop_mm':.05,
            'petal_floor_crown_above_rim_toe_mm':.45,
            'lip_land_mid_belly_width_mm':.85*min(.065,(.5-(.035+.390*math.sin(math.pi*((.003+.0120)/.02925))**.78))*.78)*TAU/PETALS*.01665*1000,
            'root_seating_shoulder_z_m':[.0004,.0007,.0012],
            'root_seating_shoulder_radial_drop_mm':.60,
            'button_throat_bevel_axial_mm':.35,
            'button_throat_bevel_radial_mm':.40,
            'petal_boundary_shape':'paired lens arches; narrow root, broad belly, converged button throat',
            'maximum_boundary_sweep_degrees':math.degrees(max(_twist(z) for z in BODY_Z)),
            'root_radius_bound_m':max(math.hypot(vertices[i][0],vertices[i][1]) for i in top['ids']),
            'button_diameter_m':.0057,
            'cavity_mask':{'domain':'CORNER','range':[min(cavity),max(cavity)],
                           'nonzero_corners':sum(c>1e-7 for c in cavity),
                           'description':'0 on crests/fields;1 at deep outer gutters;0.72 at inner carved-wall toe'},
            'topology':'One closed shell; adaptive annular mesh; no attached tubes or overlapping parts',
            **checks}
    return {'vertices':vertices,'faces':faces,'uvs':uvs,'normals':normals,'cavity':cavity,'report':report}


if __name__=='__main__':
    import json
    print(json.dumps(build_lotus_bud()['report'],indent=2))
