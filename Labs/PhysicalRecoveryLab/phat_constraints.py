"""Explicit PHAT swing/twist constraint rows for pinned MuJoCo Warp 3.6.

Ball joints retain their three angular DOFs. Locked axes add bilateral solver
rows; limited axes add unilateral rows. No pose clipping or external holding
torques. The small, version-checked extension points run only while constructing
the CUDA graph (or on uncaptured steps), and are attached to one model.
"""
from pathlib import Path
import importlib
import importlib.metadata
import json
import numpy as np
import warp as wp
import mujoco
from mujoco_warp._src import constraint, math as mm, types


def install_extension_points():
    if importlib.metadata.version("mujoco-warp") != "3.6.0":
        raise RuntimeError("PHAT constraint extension is verified only against MuJoCo Warp 3.6.0")
    path=Path(constraint.__file__)
    source=path.read_text(encoding="utf-8")
    if "# Prophecy PHAT extension" in source:
        return
    eq_anchor="    if not (m.opt.disableflags & types.DisableBit.FRICTIONLOSS):"
    lim_anchor="    # contact\n    if not (m.opt.disableflags & types.DisableBit.CONTACT):"
    if source.count(eq_anchor)!=1 or source.count(lim_anchor)!=1:
        raise RuntimeError("Unexpected MuJoCo Warp constraint source; refusing to patch it")
    source=source.replace(eq_anchor,
        '    # Prophecy PHAT extension: bilateral rows precede friction rows.\n'
        '    if getattr(m, "phat_extension", None) is not None:\n'
        '      m.phat_extension.equalities(m, d)\n\n'+eq_anchor)
    source=source.replace(lim_anchor,
        '    # Prophecy PHAT extension: unilateral angular limits.\n'
        '    if getattr(m, "phat_extension", None) is not None:\n'
        '      m.phat_extension.limits(m, d)\n\n'+lim_anchor)
    path.write_text(source,encoding="utf-8")
    importlib.reload(constraint)


@wp.func
def coordinates(q: wp.quat):
    # MuJoCo Warp stores WXYZ in wp.quat; do NOT call Warp's XYZW quaternion helpers.
    w,x,y,z=q[0],q[1],q[2],q[3]
    n2=wp.max(w*w+x*x,1.0e-12)
    n=wp.sqrt(n2)
    sy=(w*y-x*z)/n
    sz=(x*y+w*z)/n
    tw=2.0*wp.atan2(x,w)
    if tw>wp.pi: tw-=2.0*wp.pi
    if tw< -wp.pi: tw+=2.0*wp.pi
    return wp.vec3(tw,sy,sz)


@wp.func
def coordinate_gradients(q: wp.quat):
    w,x,y,z=q[0],q[1],q[2],q[3]
    n2=wp.max(w*w+x*x,1.0e-12); n=wp.sqrt(n2)
    sy=(w*y-x*z)/n; sz=(x*y+w*z)/n
    # Derivatives under q <- q * exp(omega*dt/2): ball qvel is body-local.
    dq0=wp.vec4(-x,w,z,-y)*0.5
    dq1=wp.vec4(-y,-z,w,x)*0.5
    dq2=wp.vec4(-z,y,-x,w)*0.5
    gy=wp.vec4(y/n-sy*w/n2,-z/n-sy*x/n2,w/n,-x/n)
    gz=wp.vec4(z/n-sz*w/n2,y/n-sz*x/n2,x/n,w/n)
    gt=wp.vec3(1.0,(x*y-w*z)/n2,(x*z+w*y)/n2)
    return gt,wp.vec3(wp.dot(gy,dq0),wp.dot(gy,dq1),wp.dot(gy,dq2)),wp.vec3(wp.dot(gz,dq0),wp.dot(gz,dq1),wp.dot(gz,dq2))


@wp.struct
class RowData:
    nv:int
    njmax:int
    disableflags:int
    sparse:bool
    timestep:wp.array(dtype=float)
    qpos:wp.array2d(dtype=float)
    qvel:wp.array2d(dtype=float)
    qadr:wp.array(dtype=int)
    dadr:wp.array(dtype=int)
    invweight:wp.array2d(dtype=float)
    solref:wp.array2d(dtype=wp.vec2)
    solimp:wp.array2d(dtype=types.vec5)
    joints:wp.array(dtype=int)
    modes:wp.array(dtype=wp.vec3i)
    angles:wp.array(dtype=wp.vec3)
    ne:wp.array(dtype=int)
    nl:wp.array(dtype=int)
    nefc:wp.array(dtype=int)
    J:wp.array3d(dtype=float)
    rownnz:wp.array2d(dtype=int)
    rowadr:wp.array2d(dtype=int)
    colind:wp.array3d(dtype=int)
    efc_type:wp.array2d(dtype=int)
    efc_id:wp.array2d(dtype=int)
    pos:wp.array2d(dtype=float)
    margin:wp.array2d(dtype=float)
    D:wp.array2d(dtype=float)
    vel:wp.array2d(dtype=float)
    aref:wp.array2d(dtype=float)
    frictionloss:wp.array2d(dtype=float)


@wp.func
def write_row(r:RowData,world:int,joint:int,pos:float,gradient:wp.vec3,bilateral:bool):
    norm=wp.length(gradient)
    if norm<1.0e-9: return
    g=gradient/norm; p=pos/norm
    row=wp.atomic_add(r.nefc,world,1)
    if bilateral: wp.atomic_add(r.ne,world,1)
    else: wp.atomic_add(r.nl,world,1)
    if row>=r.njmax: return
    da=r.dadr[joint]
    if r.sparse:
        r.rownnz[world,row]=3
        offset=row*r.nv
        r.rowadr[world,row]=offset
        for k in range(3):
            r.colind[world,0,offset+k]=da+k
            r.J[world,0,offset+k]=g[k]
    else:
        for k in range(r.nv): r.J[world,row,k]=0.0
        for k in range(3): r.J[world,row,da+k]=g[k]
    velocity=float(0.0); inv=float(0.0)
    for k in range(3):
        velocity+=g[k]*r.qvel[world,da+k]
        inv+=g[k]*g[k]*r.invweight[world%r.invweight.shape[0],da+k]
    kind=int(types.ConstraintType.LIMIT_JOINT)
    if bilateral: kind=int(types.ConstraintType.EQUALITY)
    constraint._efc_row(r.disableflags,world,r.timestep[world%r.timestep.shape[0]],row,p,p,inv,
        r.solref[world%r.solref.shape[0],joint],r.solimp[world%r.solimp.shape[0],joint],0.0,velocity,0.0,kind,joint,
        r.efc_type,r.efc_id,r.pos,r.margin,r.D,r.vel,r.aref,r.frictionloss)


@wp.kernel
def locked_rows(r:RowData):
    world,index=wp.tid(); joint=r.joints[index]; qa=r.qadr[joint]
    q=wp.quat(r.qpos[world,qa],r.qpos[world,qa+1],r.qpos[world,qa+2],r.qpos[world,qa+3])
    v=coordinates(q); gt,gy,gz=coordinate_gradients(q)
    modes=r.modes[index]
    if modes[0]==2: write_row(r,world,joint,v[0],gt,True)
    if modes[1]==2: write_row(r,world,joint,v[1],gy,True)
    if modes[2]==2: write_row(r,world,joint,v[2],gz,True)


@wp.kernel
def limited_rows(r:RowData):
    world,index=wp.tid(); joint=r.joints[index]; qa=r.qadr[joint]
    q=wp.quat(r.qpos[world,qa],r.qpos[world,qa+1],r.qpos[world,qa+2],r.qpos[world,qa+3])
    v=coordinates(q); gt,gy,gz=coordinate_gradients(q)
    modes=r.modes[index]; angles=r.angles[index]
    if modes[0]==1:
        p=angles[0]-wp.abs(v[0])
        if p<0.0: write_row(r,world,joint,p,-wp.sign(v[0])*gt,False)
    if modes[1]==1 and modes[2]==1:
        a=wp.sin(angles[1]*0.5); b=wp.sin(angles[2]*0.5)
        radius=wp.sqrt(v[1]*v[1]/(a*a)+v[2]*v[2]/(b*b))
        if radius>1.0:
            g=-(v[1]/(a*a)*gy+v[2]/(b*b)*gz)/radius
            write_row(r,world,joint,1.0-radius,g,False)
    elif modes[1]==1:
        p=wp.sin(angles[1]*0.5)-wp.abs(v[1])
        if p<0.0: write_row(r,world,joint,p,-wp.sign(v[1])*gy,False)
    elif modes[2]==1:
        p=wp.sin(angles[2]*0.5)-wp.abs(v[2])
        if p<0.0: write_row(r,world,joint,p,-wp.sign(v[2])*gz,False)


class PhatConstraints:
    def __init__(self,mj_model,warp_model,metadata,device="cuda:0"):
        install_extension_points()
        if getattr(warp_model,"phat_extension",None) is not None:
            raise ValueError("PHAT constraints already registered")
        joints=[]; modes=[]; angles=[]
        for j in metadata["joints"]:
            ident=mj_model.joint(j["name"]).id
            assert mj_model.jnt_type[ident]==mujoco.mjtJoint.mjJNT_BALL
            assert not mj_model.jnt_limited[ident],"Stock ball limit would double-constrain the joint"
            if 0 in j["modes"]:
                raise ValueError("A newly free PHAT axis requires validated free/cone mapping before training")
            # All current mannequin non-free ranges are within Jolt's accepted range.
            for mode,angle in zip(j["modes"],j["limits_rad"]):
                if mode==1 and not np.deg2rad(.5)<=angle<=np.deg2rad(179.5):
                    raise ValueError("Unsupported near-locked/free authored angular limit")
            joints.append(ident); modes.append(j["modes"]); angles.append(j["limits_rad"])
        self.joints=wp.array(joints,dtype=int,device=device)
        self.modes=wp.array(modes,dtype=wp.vec3i,device=device)
        self.angles=wp.array(angles,dtype=wp.vec3,device=device)
        self.bound_data={}
        warp_model.phat_extension=self

    def rows(self,m,d):
        key=id(d)
        if key in self.bound_data: return self.bound_data[key]
        r=RowData()
        r.nv=m.nv; r.njmax=d.njmax; r.disableflags=m.opt.disableflags
        r.sparse=types.SPARSE_CONSTRAINT_JACOBIAN; r.timestep=m.opt.timestep
        r.qpos=d.qpos; r.qvel=d.qvel; r.qadr=m.jnt_qposadr; r.dadr=m.jnt_dofadr
        r.invweight=m.dof_invweight0; r.solref=m.jnt_solref; r.solimp=m.jnt_solimp
        r.joints=self.joints; r.modes=self.modes; r.angles=self.angles
        r.ne=d.ne; r.nl=d.nl; r.nefc=d.nefc; r.J=d.efc.J
        r.rownnz=d.efc.J_rownnz; r.rowadr=d.efc.J_rowadr; r.colind=d.efc.J_colind
        for field in ("pos","margin","D","vel","aref","frictionloss"):
            setattr(r,field,getattr(d.efc,field))
        r.efc_type=d.efc.type; r.efc_id=d.efc.id
        self.bound_data[key]=r
        return r

    def equalities(self,m,d):
        if not m.opt.disableflags & types.DisableBit.EQUALITY:
            wp.launch(locked_rows,dim=(d.nworld,len(self.joints)),inputs=[self.rows(m,d)])

    def limits(self,m,d):
        if not m.opt.disableflags & types.DisableBit.LIMIT:
            wp.launch(limited_rows,dim=(d.nworld,len(self.joints)),inputs=[self.rows(m,d)])
