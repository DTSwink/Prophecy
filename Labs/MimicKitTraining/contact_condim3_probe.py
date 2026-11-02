# Copyright 2025 The Newton Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

# Derived from google-deepmind/mujoco_warp solver.py (Apache-2.0).
# Same arithmetic and accumulation order; static three-axis contact loops.
import warp as wp
from mujoco_warp._src import types, math

@wp.kernel
def contact_hessian_condim3(
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

    if contact_dim_in[conid] == 1:
      continue
    condim = wp.static(3)

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

        if hcone != 0.0:
          h += hcone * efc_J11 * efc_J22

          if dim1id != dim2id:
            h += hcone * efc_J12 * efc_J21

    ctx_h_out[worldid, dof1id, dof2id] += h

