"""Experimental contact coefficient reuse; same FP32 expressions and Hessian assembly."""
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver, types, math

@wp.kernel(enable_backward=False)
def prepare_cone(opt_impratio_invsqrt:wp.array(dtype=float),
    contact_dist_in:wp.array(dtype=float),contact_includemargin_in:wp.array(dtype=float),
    contact_friction_in:wp.array(dtype=types.vec5),contact_dim_in:wp.array(dtype=int),
    contact_efc_address_in:wp.array2d(dtype=int),contact_worldid_in:wp.array(dtype=int),
    efc_D_in:wp.array2d(dtype=float),efc_state_in:wp.array2d(dtype=int),
    naconmax_in:int,nacon_in:wp.array(dtype=int),ctx_Jaref_in:wp.array2d(dtype=float),
    ctx_done_in:wp.array(dtype=bool),cone_values:wp.array2d(dtype=float),eligible:wp.array(dtype=int)):
    conid=wp.tid()
    eligible[conid]=0
    if conid>=min(nacon_in[0],naconmax_in):return
    worldid=contact_worldid_in[conid]
    if ctx_done_in[worldid]:return
    condim=contact_dim_in[conid]
    if condim==1:return
    if contact_dist_in[conid]-contact_includemargin_in[conid]>=0.:return
    efcid0=contact_efc_address_in[conid,0]
    if efc_state_in[worldid,efcid0]!=types.ConstraintState.CONE:return
    fri = contact_friction_in[conid]
    mu = fri[0] * opt_impratio_invsqrt[worldid]

    mu2 = mu * mu
    dm = math.safe_div(efc_D_in[worldid, efcid0], mu2 * (1.0 + mu2))


    if dm == 0.0:return
    eligible[conid]=1
    n = ctx_Jaref_in[worldid, efcid0] * mu
    u = types.vec6(n, 0.0, 0.0, 0.0, 0.0, 0.0)

    tt = float(0.0)
    for j in range(1, condim):
      efcidj = contact_efc_address_in[conid, j]
      uj = ctx_Jaref_in[worldid, efcidj] * fri[j - 1]
      tt += uj * uj
      u[j] = uj

    if tt <= 0.0:
      t = 0.0
    else:
      t = wp.sqrt(tt)
    t = wp.max(t, types.MJ_MINVAL)
    ttt = wp.max(t * t * t, types.MJ_MINVAL)

    for dim1id in range(condim):
      ui=u[dim1id]
      for dim2id in range(dim1id+1):
        uj=u[dim2id]
        # set first row/column: (1, -mu/t * u)
        if dim1id == 0 and dim2id == 0:
          hcone = 1.0
        elif dim1id == 0:
          hcone = -math.safe_div(mu, t) * uj
        elif dim2id == 0:
          hcone = -math.safe_div(mu, t) * ui
        else:
          hcone = mu * math.safe_div(n, ttt) * ui * uj

          # add to diagonal: mu^2 - mu * n / t
          if dim1id == dim2id:
            hcone += mu2 - mu * math.safe_div(n, t)

        # pre and post multiply by diag(mu, friction) scale by dm
        if dim1id == 0:
          fri1 = mu
        else:
          fri1 = fri[dim1id - 1]

        if dim2id == 0:
          fri2 = mu
        else:
          fri2 = fri[dim2id - 1]

        hcone *= dm * fri1 * fri2

        cone_values[conid,dim1id*(dim1id+1)//2+dim2id] = hcone

@wp.kernel(enable_backward=False)
def consume_cone(
  # Model:
  opt_impratio_invsqrt: wp.array(dtype=float),
  dof_tri_row: wp.array(dtype=int),
  dof_tri_col: wp.array(dtype=int),
  # Data in:
  contact_dist_in: wp.array(dtype=float),
  contact_includemargin_in: wp.array(dtype=float),
  contact_friction_in: wp.array(dtype=types.vec5),
  contact_dim_in: wp.array(dtype=int),
  contact_efc_address_in: wp.array2d(dtype=int),
  contact_worldid_in: wp.array(dtype=int),
  efc_J_in: wp.array3d(dtype=float),
  efc_D_in: wp.array2d(dtype=float),
  efc_state_in: wp.array2d(dtype=int),
  naconmax_in: int,
  nacon_in: wp.array(dtype=int),
  # In:
  ctx_Jaref_in: wp.array2d(dtype=float),
  ctx_done_in: wp.array(dtype=bool),
  nblocks_perblock: int,
  dim_block: int,
  # Out:
  cone_values: wp.array2d(dtype=float),
  eligible:wp.array(dtype=int),
  ctx_h_out: wp.array3d(dtype=float),
):
  conid_start, elementid = wp.tid()

  dof1id = dof_tri_row[elementid]
  dof2id = dof_tri_col[elementid]

  for i in range(nblocks_perblock):
    conid = conid_start + i * dim_block

    if conid >= min(nacon_in[0], naconmax_in):
      return

    worldid = contact_worldid_in[conid]
    if ctx_done_in[worldid]:
      continue

    condim = contact_dim_in[conid]

    if condim == 1:
      continue

    # check contact status
    if contact_dist_in[conid] - contact_includemargin_in[conid] >= 0.0:
      continue

    efcid0 = contact_efc_address_in[conid, 0]
    if efc_state_in[worldid, efcid0] != types.ConstraintState.CONE:
      continue

    if eligible[conid]==0:continue
    h = float(0.0)

    for dim1id in range(condim):
      if dim1id == 0:
        efcid1 = efcid0
      else:
        efcid1 = contact_efc_address_in[conid, dim1id]

      efc_J11 = efc_J_in[worldid, efcid1, dof1id]
      efc_J12 = efc_J_in[worldid, efcid1, dof2id]


      for dim2id in range(0, dim1id + 1):
        if dim2id == 0:
          efcid2 = efcid0
        else:
          efcid2 = contact_efc_address_in[conid, dim2id]

        efc_J21 = efc_J_in[worldid, efcid2, dof1id]
        efc_J22 = efc_J_in[worldid, efcid2, dof2id]


        hcone = cone_values[conid,dim1id*(dim1id+1)//2+dim2id]

        if hcone != 0.0:
          h += hcone * efc_J11 * efc_J22

          if dim1id != dim2id:
            h += hcone * efc_J12 * efc_J21

    ctx_h_out[worldid, dof1id, dof2id] += h


@wp.kernel(enable_backward=False)
def audit_cone(
  # Model:
  opt_impratio_invsqrt: wp.array(dtype=float),
  dof_tri_row: wp.array(dtype=int),
  dof_tri_col: wp.array(dtype=int),
  # Data in:
  contact_dist_in: wp.array(dtype=float),
  contact_includemargin_in: wp.array(dtype=float),
  contact_friction_in: wp.array(dtype=types.vec5),
  contact_dim_in: wp.array(dtype=int),
  contact_efc_address_in: wp.array2d(dtype=int),
  contact_worldid_in: wp.array(dtype=int),
  efc_J_in: wp.array3d(dtype=float),
  efc_D_in: wp.array2d(dtype=float),
  efc_state_in: wp.array2d(dtype=int),
  naconmax_in: int,
  nacon_in: wp.array(dtype=int),
  # In:
  ctx_Jaref_in: wp.array2d(dtype=float),
  ctx_done_in: wp.array(dtype=bool),
  nblocks_perblock: int,
  dim_block: int,
  # Out:
  cone_values:wp.array2d(dtype=float),
  eligible:wp.array(dtype=int),
  maxdiff:wp.array2d(dtype=float),
  counts:wp.array2d(dtype=int),
):
  conid_start, elementid = wp.tid()

  dof1id = dof_tri_row[elementid]
  dof2id = dof_tri_col[elementid]

  for i in range(nblocks_perblock):
    conid = conid_start + i * dim_block

    if conid >= min(nacon_in[0], naconmax_in):
      return

    worldid = contact_worldid_in[conid]
    if ctx_done_in[worldid]:
      continue

    condim = contact_dim_in[conid]

    if condim == 1:
      continue

    # check contact status
    if contact_dist_in[conid] - contact_includemargin_in[conid] >= 0.0:
      continue

    efcid0 = contact_efc_address_in[conid, 0]
    if efc_state_in[worldid, efcid0] != types.ConstraintState.CONE:
      continue

    fri = contact_friction_in[conid]
    mu = fri[0] * opt_impratio_invsqrt[worldid]

    mu2 = mu * mu
    dm = math.safe_div(efc_D_in[worldid, efcid0], mu2 * (1.0 + mu2))

    if dm == 0.0:
      continue

    n = ctx_Jaref_in[worldid, efcid0] * mu
    u = types.vec6(n, 0.0, 0.0, 0.0, 0.0, 0.0)

    tt = float(0.0)
    for j in range(1, condim):
      efcidj = contact_efc_address_in[conid, j]
      uj = ctx_Jaref_in[worldid, efcidj] * fri[j - 1]
      tt += uj * uj
      u[j] = uj

    if tt <= 0.0:
      t = 0.0
    else:
      t = wp.sqrt(tt)
    t = wp.max(t, types.MJ_MINVAL)
    ttt = wp.max(t * t * t, types.MJ_MINVAL)

    h = float(0.0)
    new_h = float(0.0)

    for dim1id in range(condim):
      if dim1id == 0:
        efcid1 = efcid0
      else:
        efcid1 = contact_efc_address_in[conid, dim1id]

      efc_J11 = efc_J_in[worldid, efcid1, dof1id]
      efc_J12 = efc_J_in[worldid, efcid1, dof2id]

      ui = u[dim1id]

      for dim2id in range(0, dim1id + 1):
        if dim2id == 0:
          efcid2 = efcid0
        else:
          efcid2 = contact_efc_address_in[conid, dim2id]

        efc_J21 = efc_J_in[worldid, efcid2, dof1id]
        efc_J22 = efc_J_in[worldid, efcid2, dof2id]

        uj = u[dim2id]

        # set first row/column: (1, -mu/t * u)
        if dim1id == 0 and dim2id == 0:
          hcone = 1.0
        elif dim1id == 0:
          hcone = -math.safe_div(mu, t) * uj
        elif dim2id == 0:
          hcone = -math.safe_div(mu, t) * ui
        else:
          hcone = mu * math.safe_div(n, ttt) * ui * uj

          # add to diagonal: mu^2 - mu * n / t
          if dim1id == dim2id:
            hcone += mu2 - mu * math.safe_div(n, t)

        # pre and post multiply by diag(mu, friction) scale by dm
        if dim1id == 0:
          fri1 = mu
        else:
          fri1 = fri[dim1id - 1]

        if dim2id == 0:
          fri2 = mu
        else:
          fri2 = fri[dim2id - 1]

        hcone *= dm * fri1 * fri2

        cached=cone_values[conid,dim1id*(dim1id+1)//2+dim2id]
        if cached != 0.0:
          new_h += cached * efc_J11 * efc_J22
          if dim1id != dim2id:
            new_h += cached * efc_J12 * efc_J21
        if hcone != 0.0:
          h += hcone * efc_J11 * efc_J22

          if dim1id != dim2id:
            h += hcone * efc_J12 * efc_J21

    wp.atomic_add(counts,worldid,0,1)
    if h != new_h:wp.atomic_add(counts,worldid,1,1)
    if not wp.isfinite(h) or not wp.isfinite(new_h):wp.atomic_add(counts,worldid,2,1)
    wp.atomic_max(maxdiff,worldid,0,wp.abs(h-new_h))
    wp.atomic_max(maxdiff,worldid,1,wp.abs(h-new_h)/wp.max(wp.abs(h),1.e-10))


class CachedCone:
    def __init__(self,m,d):
        self.m,self.d=m,d
        self.original_launch=wp.launch
        self.original_kernel=solver.update_gradient_JTCJ_dense
        self.values=wp.zeros((d.naconmax,21),dtype=float,device=d.qpos.device)
        self.eligible=wp.zeros(d.naconmax,dtype=int,device=d.qpos.device)
        self.maxdiff=wp.zeros((d.nworld,2),dtype=float,device=d.qpos.device)
        self.counts=wp.zeros((d.nworld,3),dtype=int,device=d.qpos.device)
        self.hits=0
    def prepare(self,inputs):
        # Original positional arguments are pinned to MJWarp 3.5.0.2.
        selected=[inputs[i] for i in [0,3,4,5,6,7,8,10,11,12,13,14,15]]
        self.original_launch(prepare_cone,dim=self.d.naconmax,inputs=selected,outputs=[self.values,self.eligible])
    def apply(self,kernel,dim,inputs,outputs,audit=False,**kwargs):
        self.hits+=1
        self.prepare(inputs)
        if audit:
            self.original_launch(kernel,dim=dim,inputs=inputs,outputs=outputs,**kwargs)
            return self.original_launch(audit_cone,dim=dim,inputs=inputs+[self.values,self.eligible],outputs=[self.maxdiff,self.counts],**kwargs)
        return self.original_launch(consume_cone,dim=dim,inputs=inputs+[self.values,self.eligible],outputs=outputs,**kwargs)
    @contextmanager
    def capture(self,audit=False):
        previous=wp.launch
        self.original_launch=previous
        def wrapped(kernel,dim=None,inputs=None,outputs=None,**kwargs):
            inputs=[] if inputs is None else inputs
            outputs=[] if outputs is None else outputs
            if kernel is self.original_kernel:
                return self.apply(kernel,dim,inputs,outputs,audit,**kwargs)
            return self.original_launch(kernel,dim=dim,inputs=inputs,outputs=outputs,**kwargs)
        try:
            wp.launch=wrapped
            yield self
        finally:wp.launch=previous
