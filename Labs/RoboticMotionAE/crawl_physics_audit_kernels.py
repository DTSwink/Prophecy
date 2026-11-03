"""Substep diagnostics only; never changes forces, contacts or positions."""
import warp as wp
from sequential_contact_gpu import ContactProblem

@wp.kernel
def sample(p:ContactProblem, counter:wp.array(dtype=int), geom:wp.array(dtype=wp.vec2i),
           body:wp.array(dtype=int), frames:wp.array(dtype=wp.mat33), gap:wp.array(dtype=float),
           mass:wp.array3d(dtype=float), start:wp.array2d(dtype=float),
           before:wp.array2d(dtype=float), after:wp.array2d(dtype=float), out:wp.array3d(dtype=float)):
    w=wp.tid();t=counter[0]
    motor=float(0.);contact=float(0.);limit=float(0.);ke=float(0.);normalwork=float(0.);tangentwork=float(0.)
    for a in range(p.nmotor):
        j=p.dofs[a];motor+=p.motor_impulse[w,a]*(p.free[w,j]+p.velocity[w,j])*.5
    for c in range(p.nlimit[w]):
        speed=float(0.)
        for j in range(p.nv):speed+=p.limit_J[w,c,j]*(p.free[w,j]+p.velocity[w,j])*.5
        limit+=p.limit_impulse[w,c]*speed
    for j in range(p.nv):
        for k in range(p.nv):ke+=.5*mass[w,j,k]*(p.velocity[w,j]*p.velocity[w,k]-p.free[w,j]*p.free[w,k])
    out[t,w,13]=1.e6;out[t,w,14]=1.e6
    for c in range(p.ncontact[w]):
        ident=p.manifold.contact_ids[w,c];pair=geom[ident];a=body[pair[0]];b=body[pair[1]]
        for axis in range(3):
            speed=float(0.)
            for j in range(p.nv):speed+=p.J[w,c,axis,j]*(p.free[w,j]+p.velocity[w,j])*.5
            work=p.contact_impulse[w,c,axis]*speed
            contact+=work
            if axis==0:normalwork+=work
            else:tangentwork+=work
        g=p.manifold.group[w,c]
        if g>=0 and ident==p.manifold.first[w,g]:
            spin=float(0.)
            for j in range(p.nv):spin+=p.manifold.J[w,g,2,j]*(p.free[w,j]+p.velocity[w,j])*.5
            work=p.manifold.impulse[w,g,2]*spin;contact+=work;tangentwork+=work
        if a==0 or b==0:
            out[t,w,15]+=p.contact_impulse[w,c,0]
            for h in range(2):
                hand=6+3*h
                if a==hand or b==hand:
                    out[t,w,5+h]+=p.contact_impulse[w,c,0]
                    out[t,w,9+h]+=1.
                    out[t,w,13+h]=wp.min(out[t,w,13+h],gap[ident])
                    f=frames[ident][0]*p.contact_impulse[w,c,0]
                    if g>=0:
                        f+=p.manifold.frame[w,g][1]*p.contact_impulse[w,c,1]+p.manifold.frame[w,g][2]*p.contact_impulse[w,c,2]
                    sign=float(1.)
                    if a==hand:sign=-1.
                    out[t,w,16+h]+=sign*f[0]
                    if g>=0 and ident==p.manifold.first[w,g]:
                        v1=float(0.);v2=float(0.)
                        for j in range(p.nv):
                            v1+=p.manifold.J[w,g,0,j]*p.velocity[w,j]
                            v2+=p.manifold.J[w,g,1,j]*p.velocity[w,j]
                        out[t,w,11+h]=wp.max(out[t,w,11+h],wp.sqrt(v1*v1+v2*v2))
                        out[t,w,7+h]+=wp.sqrt(p.contact_impulse[w,c,1]**2.+p.contact_impulse[w,c,2]**2.)
    out[t,w,0]=contact;out[t,w,1]=motor;out[t,w,2]=limit;out[t,w,3]=ke
    out[t,w,4]=ke-contact-motor-limit
    out[t,w,18]=normalwork;out[t,w,19]=tangentwork
    for j in range(3):out[t,w,20+j]=after[w,j]-before[w,j]
    greatest=float(0.)
    for j in range(3,after.shape[1]):greatest=wp.max(greatest,wp.abs(after[w,j]-before[w,j]))
    out[t,w,23]=greatest
    out[t,w,24]=after[w,0]-start[w,0]
    out[t,w,25]=before[w,0]-start[w,0]

@wp.kernel
def inc(counter:wp.array(dtype=int)):counter[0]+=1
