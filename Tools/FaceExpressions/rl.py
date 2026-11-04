"""Minimal numpy RigLogic evaluator for MetaHuman DNA (raw controls -> skinned head mesh).

Run with py310 + Maya2024 dna bindings (see env.sh). Caches everything in an .npz so
later steps (Blender, transfer) only need numpy.
"""
import sys, numpy as np

def load(path):
    import dna
    s = dna.FileStream(path, dna.FileStream.AccessMode_Read, dna.FileStream.OpenMode_Binary)
    r = dna.BinaryStreamReader(s, dna.DataLayer_All); r.read()
    return r

def extract(r, mesh_index=0, lod=0):
    out = {}
    nraw = r.getRawControlCount(); npsd = r.getPSDCount()
    out['raw_names'] = np.array([r.getRawControlName(i) for i in range(nraw)])
    out['n_inputs'] = nraw + npsd
    out['psd_rows'] = np.array(r.getPSDRowIndices(), np.int32)
    out['psd_cols'] = np.array(r.getPSDColumnIndices(), np.int32)
    out['psd_vals'] = np.array(r.getPSDValues(), np.float64)
    # joints
    nj = r.getJointCount()
    out['joint_names'] = np.array([r.getJointName(i) for i in range(nj)])
    out['parent'] = np.array([r.getJointParentIndex(i) for i in range(nj)], np.int32)
    out['jt'] = np.stack([r.getNeutralJointTranslationXs(), r.getNeutralJointTranslationYs(), r.getNeutralJointTranslationZs()], 1)
    out['jr'] = np.stack([r.getNeutralJointRotationXs(), r.getNeutralJointRotationYs(), r.getNeutralJointRotationZs()], 1)
    rows, cols, vals = [], [], []
    for g in range(r.getJointGroupCount()):
        nrows = r.getJointGroupLODs(g)[lod]
        oi = np.array(r.getJointGroupOutputIndices(g))[:nrows]
        ii = np.array(r.getJointGroupInputIndices(g))
        if len(ii) == 0 or nrows == 0: continue
        v = np.array(r.getJointGroupValues(g)).reshape(-1, len(ii))[:nrows]
        rr, cc = np.nonzero(v)
        rows.append(oi[rr]); cols.append(ii[cc]); vals.append(v[rr, cc])
    out['jg_rows'] = np.concatenate(rows).astype(np.int32)
    out['jg_cols'] = np.concatenate(cols).astype(np.int32)
    out['jg_vals'] = np.concatenate(vals)
    # blendshape channels
    nbs = r.getBlendShapeChannelLODs()[lod]
    out['bs_in'] = np.array(r.getBlendShapeChannelInputIndices(), np.int32)[:nbs]
    out['bs_out'] = np.array(r.getBlendShapeChannelOutputIndices(), np.int32)[:nbs]
    # mesh
    m = mesh_index
    out['mesh_name'] = r.getMeshName(m)
    V = np.stack([r.getVertexPositionXs(m), r.getVertexPositionYs(m), r.getVertexPositionZs(m)], 1)
    out['V'] = V
    nv = len(V)
    sw_j, sw_w, sw_v = [], [], []
    for v in range(nv):
        js = r.getSkinWeightsJointIndices(m, v); ws = r.getSkinWeightsValues(m, v)
        sw_j += list(js); sw_w += list(ws); sw_v += [v] * len(js)
    out['sw_v'] = np.array(sw_v, np.int32); out['sw_j'] = np.array(sw_j, np.int32); out['sw_w'] = np.array(sw_w)
    tchan, tvi, tdel = [], [], []
    for t in range(r.getBlendShapeTargetCount(m)):
        ch = r.getBlendShapeChannelIndex(m, t)
        vi = np.array(r.getBlendShapeTargetVertexIndices(m, t), np.int32)
        d = np.stack([r.getBlendShapeTargetDeltaXs(m, t), r.getBlendShapeTargetDeltaYs(m, t), r.getBlendShapeTargetDeltaZs(m, t)], 1)
        tchan += [ch] * len(vi); tvi.append(vi); tdel.append(d)
    if tvi:
        out['bt_chan'] = np.array(tchan, np.int32); out['bt_vi'] = np.concatenate(tvi); out['bt_d'] = np.concatenate(tdel)
    else:
        out['bt_chan'] = np.zeros(0, np.int32); out['bt_vi'] = np.zeros(0, np.int32); out['bt_d'] = np.zeros((0, 3))
    # topology + uv
    out['uv'] = np.stack([r.getVertexTextureCoordinateUs(m), r.getVertexTextureCoordinateVs(m)], 1)
    out['lay_pos'] = np.array(r.getVertexLayoutPositionIndices(m), np.int32)
    out['lay_uv'] = np.array(r.getVertexLayoutTextureCoordinateIndices(m), np.int32)
    faces = [np.array(r.getFaceVertexLayoutIndices(m, f), np.int32) for f in range(r.getFaceCount(m))]
    out['face_len'] = np.array([len(f) for f in faces], np.int32)
    out['face_idx'] = np.concatenate(faces)
    return out

# ---------------- evaluation (numpy only) ----------------

def euler_xyz(deg):
    x, y, z = np.radians(deg).T
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    Rx = np.zeros((len(x), 3, 3)); Ry = Rx.copy(); Rz = Rx.copy()
    Rx[:, 0, 0] = 1; Rx[:, 1, 1] = cx; Rx[:, 1, 2] = -sx; Rx[:, 2, 1] = sx; Rx[:, 2, 2] = cx
    Ry[:, 1, 1] = 1; Ry[:, 0, 0] = cy; Ry[:, 0, 2] = sy; Ry[:, 2, 0] = -sy; Ry[:, 2, 2] = cy
    Rz[:, 2, 2] = 1; Rz[:, 0, 0] = cz; Rz[:, 0, 1] = -sz; Rz[:, 1, 0] = sz; Rz[:, 1, 1] = cz
    return Rz @ Ry @ Rx  # column vectors, X applied first (Maya xyz)

def inputs_from_raw(d, raw):
    n = int(d['n_inputs']); nraw = len(d['raw_names'])
    x = np.zeros(n); x[:nraw] = np.clip(raw, 0, 1)
    # PSD: product of participating inputs (times weight), clamped
    prod = {}
    for r_, c_, v_ in zip(d['psd_rows'], d['psd_cols'], d['psd_vals']):
        prod[r_] = prod.get(r_, 1.0) * x[c_] * v_
    for r_, p in prod.items():
        x[r_] = min(max(p, 0.0), 1.0)
    return x

def world_mats(d, local_t, local_R):
    nj = len(d['parent']); W = np.zeros((nj, 4, 4))
    for j in range(nj):  # DNA joints are ordered parent-before-child
        M = np.eye(4); M[:3, :3] = local_R[j]; M[:3, 3] = local_t[j]
        p = d['parent'][j]
        W[j] = M if p == j or p < 0 else W[p] @ M
    return W

def evaluate(d, raw):
    x = inputs_from_raw(d, raw)
    nj = len(d['parent'])
    delta = np.zeros(nj * 9)
    np.add.at(delta, d['jg_rows'], d['jg_vals'] * x[d['jg_cols']])
    delta = delta.reshape(nj, 9)
    R0 = euler_xyz(d['jr'])
    Wb = world_mats(d, d['jt'], R0)
    Wp = world_mats(d, d['jt'] + delta[:, 0:3], R0 @ euler_xyz(delta[:, 3:6]) @ np.array([np.diag(1 + s) for s in delta[:, 6:9]]))
    # blendshapes in bind space
    V = d['V'].copy()
    w = np.zeros(int(d['bs_out'].max()) + 1 if len(d['bs_out']) else 1)
    w[d['bs_out']] = x[d['bs_in']]
    if len(d['bt_vi']):
        np.add.at(V, d['bt_vi'], d['bt_d'] * w[d['bt_chan']][:, None])
    # linear blend skinning
    S = Wp @ np.linalg.inv(Wb)
    Vh = np.c_[V, np.ones(len(V))]
    out = np.zeros_like(V)
    contrib = np.einsum('kij,kj->ki', S[d['sw_j']], Vh[d['sw_v']])[:, :3] * d['sw_w'][:, None]
    np.add.at(out, d['sw_v'], contrib)
    wsum = np.zeros(len(V)); np.add.at(wsum, d['sw_v'], d['sw_w'])
    out[wsum == 0] = V[wsum == 0]
    return out

if __name__ == '__main__':
    path, mesh, lod, dst = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    r = load(path)
    np.savez_compressed(dst, **extract(r, mesh, lod))
    print('saved', dst)
