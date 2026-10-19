"""Diagnostic Jolt manifold friction data, built entirely on the GPU.

Same-shape contacts share two tangential rows at their centroid and one spin
row. Tangential projection uses the contacting bodies' effective masses, as
Jolt does, rather than the articulated inverse mass. No training registration.
"""
import warp as wp
from mujoco_warp._src import support


@wp.struct
class ContactManifolds:
    enabled: bool
    count: wp.array(dtype=int)
    contact_ids: wp.array2d(dtype=int)
    group: wp.array2d(dtype=int)
    radius: wp.array2d(dtype=float)
    first: wp.array2d(dtype=int)
    size: wp.array2d(dtype=int)
    center: wp.array2d(dtype=wp.vec3)
    frame: wp.array2d(dtype=wp.mat33)
    friction: wp.array2d(dtype=float)
    J: wp.array4d(dtype=float)
    response: wp.array4d(dtype=float)
    diagonal: wp.array3d(dtype=float)
    impulse: wp.array3d(dtype=float)


def allocate(worlds,capacity,nv,device):
    p=ContactManifolds();p.enabled=True
    z=lambda shape,dtype=float:wp.zeros(shape,dtype=dtype,device=device)
    p.count=z(worlds,int);p.contact_ids=z((worlds,capacity),int)
    p.group=z((worlds,capacity),int);p.radius=z((worlds,capacity))
    p.first=z((worlds,capacity),int);p.size=z((worlds,capacity),int)
    p.center=z((worlds,capacity),wp.vec3);p.frame=z((worlds,capacity),wp.mat33)
    p.friction=z((worlds,capacity));p.J=z((worlds,capacity,3,nv))
    p.response=z((worlds,capacity,3,nv));p.diagonal=z((worlds,capacity,3));p.impulse=z((worlds,capacity,3))
    return p


@wp.kernel(enable_backward=False)
def group_contacts(p:ContactManifolds,ncontact:wp.array(dtype=int),mu:wp.array2d(dtype=float),
                   geom:wp.array(dtype=wp.vec2i),pos:wp.array(dtype=wp.vec3),
                   frame:wp.array(dtype=wp.mat33),error:wp.array(dtype=int)):
    w=wp.tid();count=int(0)
    for c in range(ncontact[w]):
        p.group[w,c]=-1
        if mu[w,c]<=0.:continue
        ident=p.contact_ids[w,c];pair=geom[ident];normal=frame[ident][0]
        found=int(-1)
        for g in range(count):
            other=geom[p.first[w,g]]
            if pair[0]==other[0] and pair[1]==other[1]:
                if wp.dot(normal,p.frame[w,g][0])<.99999:error[w]=9
                found=g
                break
        if found<0:
            found=count;count+=1;p.first[w,found]=ident;p.size[w,found]=0
            p.center[w,found]=wp.vec3(0.);p.friction[w,found]=mu[w,c]
            tangent=wp.vec3(0.,normal[2],-normal[1])
            if wp.abs(normal[0])>wp.abs(normal[1]):tangent=wp.vec3(normal[2],0.,-normal[0])
            tangent=wp.normalize(tangent)
            p.frame[w,found]=wp.matrix_from_rows(normal,tangent,wp.cross(normal,tangent))
        p.group[w,c]=found;p.size[w,found]+=1;p.center[w,found]+=pos[ident]
    p.count[w]=count
    for g in range(count):
        p.center[w,g]/=float(p.size[w,g])
        if p.size[w,g]>4:error[w]=7
    for c in range(ncontact[w]):
        g=p.group[w,c]
        if g<0:continue
        delta=pos[p.contact_ids[w,c]]-p.center[w,g];normal=p.frame[w,g][0]
        p.radius[w,c]=wp.length(delta-normal*wp.dot(delta,normal))


@wp.kernel(enable_backward=False)
def prepare_rows(p:ContactManifolds,geom:wp.array(dtype=wp.vec2i),geom_body:wp.array(dtype=int),
                 parents:wp.array(dtype=int),roots:wp.array(dtype=int),dof_body:wp.array(dtype=int),
                 subtree:wp.array2d(dtype=wp.vec3),cdof:wp.array2d(dtype=wp.spatial_vector)):
    w,g,j=wp.tid()
    if g>=p.count[w]:return
    pair=geom[p.first[w,g]];center=p.center[w,g];frame=p.frame[w,g]
    linear=wp.vec3(0.);angular=wp.vec3(0.)
    for side in range(2):
        body=geom_body[pair[side]]
        if body==0:continue
        jp,jr=support.jac_dof(parents,roots,dof_body,subtree,cdof,center,body,j,w)
        sign=float(2*side-1);linear+=sign*jp;angular+=sign*jr
    p.J[w,g,0,j]=wp.dot(frame[1],linear)
    p.J[w,g,1,j]=wp.dot(frame[2],linear)
    p.J[w,g,2,j]=wp.dot(frame[0],angular)


@wp.kernel(enable_backward=False)
def prepare_metric(p:ContactManifolds,geom:wp.array(dtype=wp.vec2i),geom_body:wp.array(dtype=int),
                   mass:wp.array(dtype=float),inertia:wp.array(dtype=wp.vec3),
                   com:wp.array2d(dtype=wp.vec3),rotation:wp.array2d(dtype=wp.mat33)):
    w,g=wp.tid()
    if g>=p.count[w]:return
    pair=geom[p.first[w,g]];center=p.center[w,g];frame=p.frame[w,g];diag=wp.vec3(0.)
    for side in range(2):
        body=geom_body[pair[side]]
        if body==0:continue
        # Inertia axes are already world oriented by MJ's current kinematics.
        r=rotation[w,body];local=inertia[body];lever=center-com[w,body]
        for axis in range(3):
            direction=frame[(axis+1)%3]
            torque=direction
            if axis<2:torque=wp.cross(lever,direction)
            principal=wp.transpose(r)*torque
            value=principal[0]*principal[0]/local[0]+principal[1]*principal[1]/local[1]+principal[2]*principal[2]/local[2]
            if axis<2:value+=1./mass[body]
            diag[axis]+=value
    for axis in range(3):p.diagonal[w,g,axis]=diag[axis]


@wp.kernel(enable_backward=False)
def prepare_response(p:ContactManifolds,inverse:wp.array3d(dtype=float)):
    w,g,axis,j=wp.tid()
    if g>=p.count[w]:return
    value=float(0.)
    for k in range(inverse.shape[1]):value+=inverse[w,j,k]*p.J[w,g,axis,k]
    p.response[w,g,axis,j]=value


@wp.kernel(enable_backward=False)
def replace_point_friction(p:ContactManifolds,ncontact:wp.array(dtype=int),friction:wp.array2d(dtype=float),
                           jac:wp.array4d(dtype=float),diagonal:wp.array3d(dtype=float),response:wp.array4d(dtype=float)):
    w,c,j=wp.tid()
    if c>=ncontact[w]:return
    g=p.group[w,c]
    if g<0:return
    if p.contact_ids[w,c]!=p.first[w,g]:
        if j==0:friction[w,c]=0.
        return
    for axis in range(2):
        jac[w,c,axis+1,j]=p.J[w,g,axis,j]
        # Same Jacobian and mass: reuse the response prepared for the manifold.
        response[w,c,axis+1,j]=p.response[w,g,axis,j]
        if j==0:diagonal[w,c,axis+1]=p.diagonal[w,g,axis]


def prepare(p,ncontact,friction,model,data,inverse,error,mass,inertia):
    dev=data.qvel.device;n=data.nworld;capacity=p.J.shape[1];nv=model.nv
    wp.launch(group_contacts,dim=n,inputs=[p,ncontact,friction,data.contact.geom,data.contact.pos,data.contact.frame,error],device=dev)
    wp.launch(prepare_rows,dim=(n,capacity,nv),inputs=[p,data.contact.geom,model.geom_bodyid,model.body_parentid,
        model.body_rootid,model.dof_bodyid,data.subtree_com,data.cdof],device=dev)
    wp.launch(prepare_metric,dim=(n,capacity),inputs=[p,data.contact.geom,model.geom_bodyid,mass,inertia,data.xipos,data.ximat],device=dev)
    wp.launch(prepare_response,dim=(n,capacity,3,nv),inputs=[p,inverse],device=dev)
