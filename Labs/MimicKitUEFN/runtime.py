"""PHAT limits for the separate compound asset; never patches files on disk.

Use install_limits(solver.mj_model, solver.mjw_model) after construction and
before graph capture. A version-checked in-process hook adds solver rows only
for registered models. Existing/unregistered models follow upstream unchanged.
"""
import ast
import inspect
import importlib.metadata
import json
from pathlib import Path
import sys
import numpy as np
import mujoco
import warp as wp
from mujoco_warp._src import constraint, types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'PhysicalRecoveryLab'))
# Reuse the independently tested Jolt coordinate equations and solver-row writer.
from phat_constraints import RowData, coordinates, coordinate_gradients, write_row


@wp.func
def product(a: wp.quat, b: wp.quat):
    # These quaternions are WXYZ, unlike Warp's quaternion helper convention.
    return wp.quat(a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
                   a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
                   a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
                   a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0])


@wp.kernel
def locked_rows(r: RowData, reference: wp.array(dtype=wp.quat)):
    world,index=wp.tid(); joint=r.joints[index]; qa=r.qadr[joint]
    q=product(reference[index],wp.quat(r.qpos[world,qa],r.qpos[world,qa+1],r.qpos[world,qa+2],r.qpos[world,qa+3]))
    v=coordinates(q); gt,gy,gz=coordinate_gradients(q); modes=r.modes[index]
    if modes[0]==2: write_row(r,world,joint,v[0],gt,True)
    if modes[1]==2: write_row(r,world,joint,v[1],gy,True)
    if modes[2]==2: write_row(r,world,joint,v[2],gz,True)


@wp.kernel
def limited_rows(r: RowData, reference: wp.array(dtype=wp.quat)):
    world,index=wp.tid(); joint=r.joints[index]; qa=r.qadr[joint]
    q=product(reference[index],wp.quat(r.qpos[world,qa],r.qpos[world,qa+1],r.qpos[world,qa+2],r.qpos[world,qa+3]))
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


def install_hook():
    if getattr(constraint.make_constraint, '_uefn_compound_hook', False): return
    version=importlib.metadata.version('mujoco-warp')
    if version not in ('3.5.0.2','3.6.0'):
        raise RuntimeError(f'Untested MuJoCo Warp {version}; refusing unrestricted PHAT joints')
    # Insert at verified category boundaries. Do not replace upstream kernels,
    # edit site-packages, reorder contact rows or add post-step pose clipping.
    source=inspect.getsource(constraint.make_constraint)
    anchors=[('    if not (m.opt.disableflags & types.DisableBit.FRICTIONLOSS):','equalities'),
             ('    # contact\n    if not (m.opt.disableflags & types.DisableBit.CONTACT):','limits')]
    for anchor,method in anchors:
        if source.count(anchor)!=1: raise RuntimeError('MuJoCo Warp constraint layout changed')
        source=source.replace(anchor,
            '    if getattr(m, "uefn_compound_limits", None) is not None:\n'
            f'      m.uefn_compound_limits.{method}(m, d)\n\n'+anchor)
    code=ast.parse(source)
    # A fresh namespace retains upstream globals while leaving the original
    # module namespace unchanged until the validated replacement is ready.
    scope=dict(constraint.__dict__)
    exec(compile(code,'<uefn-compound-limit-hook>','exec'),scope)
    replacement=scope['make_constraint']; replacement._uefn_compound_hook=True
    constraint.make_constraint=replacement


class CompoundLimits:
    def __init__(self, model, warp_model, metadata):
        device=warp_model.jnt_qposadr.device
        joints=[]; modes=[]; angles=[]; references=[]
        for j in metadata['joints']:
            if j['kind']!='ball': continue
            # Newton prefixes names with the articulation name. Require a unique
            # suffix and validate type; no dependence on numeric joint order.
            converted='_'.join(j['name']+'_'+axis for axis in 'xyz')
            matches=[i for i in range(model.njnt) if model.joint(i).name==j['name']
                     or model.joint(i).name.endswith('/'+j['name'])
                     or model.joint(i).name.endswith('_'+converted)]
            if len(matches)!=1: raise ValueError(f"Cannot uniquely map {j['name']}: {matches}")
            ident=matches[0]
            assert model.jnt_type[ident]==mujoco.mjtJoint.mjJNT_BALL
            assert not model.jnt_limited[ident]
            joints.append(ident);modes.append(j['modes']);angles.append(j['limits_rad']);references.append(j['reference_wxyz'])
        expected=sum(j['kind']=='ball' for j in metadata['joints'])
        assert len(joints)==expected and len(set(joints))==expected
        self.joints=wp.array(joints,dtype=int,device=device)
        self.modes=wp.array(modes,dtype=wp.vec3i,device=device)
        self.angles=wp.array(angles,dtype=wp.vec3,device=device)
        self.reference=wp.array(references,dtype=wp.quat,device=device)
        self.bound={}

    def rows(self,m,d):
        if id(d) in self.bound:return self.bound[id(d)]
        r=RowData();r.nv=m.nv;r.njmax=d.njmax;r.disableflags=m.opt.disableflags
        r.sparse=constraint.SPARSE_CONSTRAINT_JACOBIAN
        r.timestep=m.opt.timestep;r.qpos=d.qpos;r.qvel=d.qvel;r.qadr=m.jnt_qposadr;r.dadr=m.jnt_dofadr
        r.invweight=m.dof_invweight0;r.solref=m.jnt_solref;r.solimp=m.jnt_solimp
        r.joints=self.joints;r.modes=self.modes;r.angles=self.angles
        r.ne=d.ne;r.nl=d.nl;r.nefc=d.nefc;r.J=d.efc.J
        r.rownnz=d.efc.J_rownnz;r.rowadr=d.efc.J_rowadr;r.colind=d.efc.J_colind
        for field in ('pos','margin','D','vel','aref','frictionloss'):setattr(r,field,getattr(d.efc,field))
        r.efc_type=d.efc.type;r.efc_id=d.efc.id
        self.bound[id(d)]=r
        return r

    def equalities(self,m,d):
        if not m.opt.disableflags & types.DisableBit.EQUALITY:
            wp.launch(locked_rows,dim=(d.nworld,len(self.joints)),inputs=[self.rows(m,d),self.reference],device=self.reference.device)

    def limits(self,m,d):
        if not m.opt.disableflags & types.DisableBit.LIMIT:
            wp.launch(limited_rows,dim=(d.nworld,len(self.joints)),inputs=[self.rows(m,d),self.reference],device=self.reference.device)


def install_limits(model, warp_model, metadata=None):
    if metadata is None: metadata=json.loads((HERE/'limits.json').read_text())
    if getattr(warp_model,'uefn_compound_limits',None) is not None:raise RuntimeError('Already installed')
    extension=CompoundLimits(model,warp_model,metadata)
    install_hook()
    warp_model.uefn_compound_limits=extension
    return extension
