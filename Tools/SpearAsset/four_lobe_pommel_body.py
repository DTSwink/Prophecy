"""Fourfold sculpted body: cubic concave panels between four radial gold ribs.

Pure geometry, no bpy or file mutations. The forward rib, two lateral ribs and
hidden rear rib produce the user's clarified flower cross-section.
"""
import math

def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def length(v):return math.sqrt(dot(v,v))
def unit(v):
    n=length(v)
    if n<1e-16:raise ValueError('Zero surface tangent')
    return mul(v,1/n)

def cubic(knots,z):
    xx,yy=zip(*knots);hh=[xx[i+1]-xx[i] for i in range(len(xx)-1)]
    dd=[(yy[i+1]-yy[i])/hh[i] for i in range(len(hh))];mm=[dd[0]]
    for i in range(1,len(xx)-1):
        aa=2*hh[i]+hh[i-1];bb=hh[i]+2*hh[i-1]
        mm.append(0 if dd[i-1]*dd[i]<=0 else (aa+bb)/(aa/dd[i-1]+bb/dd[i]))
    mm.append(dd[-1]);i=next((i for i in range(len(hh)) if z<=xx[i+1]),len(hh)-1)
    t=max(0,min(1,(z-xx[i])/hh[i]));h=hh[i]
    return (2*t**3-3*t*t+1)*yy[i]+(t**3-2*t*t+t)*h*mm[i]+(-2*t**3+3*t*t)*yy[i+1]+(t**3-t*t)*h*mm[i+1]

OUTER=((.0125,.0128),(.020,.0134),(.031,.0190),(.049,.0243),(.058,.0245),(.073,.0223),(.085,.0189),(.092,.0174),(.100,.0167),(.1085,.0168))
VALLEY=((.0125,.0128),(.020,.0128),(.031,.0131),(.049,.0134),(.058,.0135),(.073,.0137),(.085,.0148),(.092,.0156),(.100,.0167),(.1085,.0168))
ZS=(.0125,.015,.018,.020,.023,.026,.029,.032,.035,.039,.043,.047,.051,.055,.058,.061,.064,.067,.070,.073,.076,.079,.082,.085,.088,.091,.094,.097,.100,.103,.106,.1085)
ZS=tuple(sorted(set(ZS)|{(a+b)*.5 for a,b in zip(ZS,ZS[1:]) if b-a>=.00299}|{.019,.021,.022,.098,.099}))
def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)

def bezier(p,t):
    b=((1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3)
    return tuple(sum(w*q[c] for w,q in zip(b,p)) for c in range(2))

def section(z):
    radius=cubic(OUTER,z);valley=min(radius,cubic(VALLEY,z))
    foot=(radius-.00175,.00335)
    controls=(foot,(.55*radius,.15*radius),(.15*radius,.55*radius),(foot[1],foot[0]))
    raw_mid=bezier(controls,.5);flower_valley=math.hypot(*raw_mid)
    amount=max(0,min(1,(radius-valley)/(radius-flower_valley)))
    def blend(point):
        x,y=point
        theta=math.atan2(y,x);cx,cy=radius*math.cos(theta),radius*math.sin(theta)
        return (cx+(x-cx)*amount,cy+(y-cy)*amount)
    # A second, CLOSED leaf recess lives inside each primary scoop. Its
    # boundary sweeps inward at the ends; relief fades with a C1 envelope.
    # All ledges/walls belong to this shell, with no overlaid wire objects.
    leaf_shape=smooth((z-.018)/.026)*smooth((.101-z)/.023)
    envelope=smooth((z-.018)/.003)*smooth((.101-z)/.003)
    edge=.445-.370*math.sqrt(leaf_shape)
    land=min(.034,(.5-edge)/3.4)
    inner=edge+2.7*land
    left=[(edge*.20,-.00025),(edge*.50,-.00028),(edge-land,0),
          (edge,.00022),(edge+land,.00022),
          (edge+1.35*land,.00012),(edge+2.3*land,-.00102),
          (inner,-.00110)]
    left += [(inner+(.5-inner)*t,-.00110+.00020*smooth(t)) for t in (.20,.40,.60,.80,1.)]
    inset=left+[(1-t,h) for t,h in reversed(left[:-1])]
    quarter=[blend(p) for p in [(radius,0),(radius,.00160),(radius-.00020,.00180),foot]]
    for t,height in inset:
        base=blend(bezier(controls,t));a=blend(bezier(controls,t-1e-5));b=blend(bezier(controls,t+1e-5))
        tangent=sub(b,a);out=unit((tangent[1],-tangent[0]))
        quarter.append(add(base,mul(out,height*envelope)))
    quarter += [blend(p) for p in [(foot[1],foot[0]),(.00180,radius-.00020),(.00160,radius)]]
    result=[]
    for k in range(4):
        a=k*math.pi/2;c=math.cos(a);s=math.sin(a)
        result.extend([(x*c-y*s,x*s+y*c,z) for x,y in quarter])
    # Split only the deliberate machined breaks, preserving smooth floor.
    hard={1,3,len(quarter)-3,len(quarter)-1}
    if envelope>.025:
        hard.update(4+i for i in (2,3,4,6,7))
        hard.update(4+len(inset)-1-i for i in (2,3,4,6,7))
    # Mask is localized to the inner wall/toe, not painted over the gold field.
    left_mask=[.60,.80,.10,0,0,.18,.82,1,.36,.06,0,0,0]
    inset_mask=left_mask+list(reversed(left_mask[:-1]))
    quarter_mask=[0]*4+[v*envelope for v in inset_mask]+[0]*3
    return result,amount,hard,quarter_mask*4

def build_four_lobe_body():
    section_data=[section(z) for z in ZS];rows=[r[0] for r in section_data]
    amplitudes=[r[1] for r in section_data];hard_rows=[r[2] for r in section_data];n=len(rows[0]);q=n//4
    tangents=[]
    for z in ZS:
        a=section(max(ZS[0],z-1e-5))[0];b=section(min(ZS[-1],z+1e-5))[0]
        tangents.append([sub(y,x) for x,y in zip(a,b)])
    vertices=[p for row in rows for p in row];faces=[];uvs=[];normals=[];cavity=[]
    # Physical arc lengths, one UV island per sculpted quarter-panel.
    arc=[]
    for row in rows:
        lengths=[0.]
        for j in range(q):lengths.append(lengths[-1]+length(sub(row[j+1],row[j])))
        arc.append(lengths)
    def normal(k,j,span):
        along=tangents[k][j]
        if j%q in hard_rows[k] and amplitudes[k]>.06:
            across=sub(rows[k][(span+1)%n],rows[k][span])
        else:
            aa=sub(rows[k][j],rows[k][(j-1)%n]);bb=sub(rows[k][(j+1)%n],rows[k][j])
            across=add(mul(unit(aa),length(bb)),mul(unit(bb),length(aa)))
        return unit(cross(across,along))
    for k in range(len(rows)-1):
        for j in range(n):
            jn=(j+1)%n;faces.append((k*n+j,k*n+jn,(k+1)*n+jn,(k+1)*n+j))
            u=j%q
            for kk,jj,local in ((k,j,u),(k,jn,u+1),(k+1,jn,u+1),(k+1,j,u)):
                uvs.append((.15+arc[kk][local]/.100,.02+(ZS[kk]-.0125)/.100))
                normals.append(normal(kk,jj,j))
                cavity.append(section_data[kk][3][jj])
    for k,sign in ((0,-1),(len(rows)-1,1)):
        ci=len(vertices);vertices.append((0,0,ZS[k]))
        for j in range(n):
            pair=(k*n+(j+1)%n,k*n+j) if sign<0 else (k*n+j,k*n+(j+1)%n)
            face=(ci,*pair);faces.append(face)
            for vi in face:
                x,y,z=vertices[vi];uvs.append((.5+x/.100,.5+y/.100));normals.append((0,0,sign));cavity.append(0.)
    belly,amount,hard,mask=section(.058)
    diagonal=min(length(p[:2]) for p in belly[:q+1]);peak=length(belly[0][:2])
    report={'design':'Four radial ribs with integral stepped leaf-shaped recesses inside four cubic concave panels',
            'main_body_lobes':4,'belly_axis_radius_mm':1000*peak,'belly_diagonal_radius_mm':1000*diagonal,
            'belly_peak_to_valley_mm':1000*(peak-diagonal),'belly_scoop_below_peak_chord_mm':1000*(peak/math.sqrt(2)-diagonal),
            'crest_width_mm':3.2,'ridge_chamfer_depth_mm':1.75,'body_span_m':[ZS[0],ZS[-1]],
            'primary_shadow_channel_depth_mm':.28,'panel_relief_tip_fade_mm':3.,
            'secondary_carved_panels':4,'secondary_recess_depth_mm':1.10,'secondary_lip_height_mm':.22,
            'localized_cavity_mask':True,
            'curvature_sampled_axial_rows':len(ZS),'analytic_axial_normal_step_m':1e-5,
            'secondary_panel_tips_z_m':[.018,.101],'secondary_border_integral_geometry':True,
            'width_and_depth_comparable':True,'full_three_dimensional_section':True,
            'triangles':sum(len(f)-2 for f in faces),'vertices':len(vertices)}
    return {'vertices':vertices,'faces':faces,'uvs':uvs,'normals':normals,'cavity':cavity,'report':report}
