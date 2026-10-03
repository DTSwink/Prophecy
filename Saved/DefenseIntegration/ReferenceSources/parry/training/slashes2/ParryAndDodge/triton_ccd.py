from __future__ import annotations

"""Graph-capturable hard first-contact search with in-kernel early exit.

One Triton program owns one defender/attacker OBB pair. The loop is genuinely
data dependent inside the GPU kernel, so completed or rejected colliders stop
without expanding thousands of PyTorch operations into the CUDA graph.
"""

import torch
import triton
import triton.language as tl
from triton_cylinder import cylinder_gap
try:
    # Triton >= 3 exposes CUDA libdevice through language.extra.
    from triton.language.extra import libdevice
except ImportError:  # Triton 2.1 (the established RunPod PyTorch runtime)
    # This maps acos to the same __nv_acosf/__nv_acos libdevice symbols; it is
    # an import-layout compatibility shim, not a numerical approximation.
    from triton.language import math as libdevice


@triton.jit
def _normalize3(x, y, z):
    inverse = libdevice.rsqrt(tl.maximum(x * x + y * y + z * z, 1.0e-24))
    return x * inverse, y * inverse, z * inverse


@triton.jit
def _quaternion_from_rows(a00, a01, a02, a10, a11, a12, a20, a21, a22):
    # Standard quaternion formula applied to transpose(row-axis matrix).
    qw = 0.5 * tl.sqrt(tl.maximum(1.0 + a00 + a11 + a22, 0.0))
    qx_abs = 0.5 * tl.sqrt(tl.maximum(1.0 + a00 - a11 - a22, 0.0))
    qy_abs = 0.5 * tl.sqrt(tl.maximum(1.0 - a00 + a11 - a22, 0.0))
    qz_abs = 0.5 * tl.sqrt(tl.maximum(1.0 - a00 - a11 + a22, 0.0))
    # Column-matrix signs after transpose: m21-m12=a12-a21, etc.
    qx = tl.where(a12 - a21 >= 0.0, qx_abs, -qx_abs)
    qy = tl.where(a20 - a02 >= 0.0, qy_abs, -qy_abs)
    qz = tl.where(a01 - a10 >= 0.0, qz_abs, -qz_abs)
    inverse = libdevice.rsqrt(tl.maximum(qw * qw + qx * qx + qy * qy + qz * qz, 1.0e-24))
    return qw * inverse, qx * inverse, qy * inverse, qz * inverse


@triton.jit
def _slerp(q0w, q0x, q0y, q0z, q1w, q1x, q1y, q1z, fraction):
    dot = q0w * q1w + q0x * q1x + q0y * q1y + q0z * q1z
    flip = dot < 0.0
    q1w = tl.where(flip, -q1w, q1w)
    q1x = tl.where(flip, -q1x, q1x)
    q1y = tl.where(flip, -q1y, q1y)
    q1z = tl.where(flip, -q1z, q1z)
    dot = tl.minimum(tl.abs(dot), 1.0)
    theta = libdevice.acos(dot)
    sine = tl.sin(theta)
    linear = dot > 0.9995
    safe_sine = tl.maximum(sine, 1.0e-8)
    scale0 = tl.where(linear, 1.0 - fraction, tl.sin((1.0 - fraction) * theta) / safe_sine)
    scale1 = tl.where(linear, fraction, tl.sin(fraction * theta) / safe_sine)
    qw = scale0 * q0w + scale1 * q1w
    qx = scale0 * q0x + scale1 * q1x
    qy = scale0 * q0y + scale1 * q1y
    qz = scale0 * q0z + scale1 * q1z
    inverse = libdevice.rsqrt(tl.maximum(qw * qw + qx * qx + qy * qy + qz * qz, 1.0e-24))
    return qw * inverse, qx * inverse, qy * inverse, qz * inverse


@triton.jit
def _rows_from_quaternion(w, x, y, z):
    # Transpose of the conventional column-vector quaternion matrix.
    a00 = 1.0 - 2.0 * (y * y + z * z)
    a01 = 2.0 * (x * y + z * w)
    a02 = 2.0 * (x * z - y * w)
    a10 = 2.0 * (x * y - z * w)
    a11 = 1.0 - 2.0 * (x * x + z * z)
    a12 = 2.0 * (y * z + x * w)
    a20 = 2.0 * (x * z + y * w)
    a21 = 2.0 * (y * z - x * w)
    a22 = 1.0 - 2.0 * (x * x + y * y)
    return a00, a01, a02, a10, a11, a12, a20, a21, a22


@triton.jit
def _axis_gap(
    x, y, z,
    dx, dy, dz,
    a00, a01, a02, a10, a11, a12, a20, a21, a22,
    ah0, ah1, ah2,
    b00, b01, b02, b10, b11, b12, b20, b21, b22,
    bh0, bh1, bh2,
):
    x, y, z = _normalize3(x, y, z)
    center = tl.abs(dx * x + dy * y + dz * z)
    radius_a = (
        ah0 * tl.abs(a00 * x + a01 * y + a02 * z)
        + ah1 * tl.abs(a10 * x + a11 * y + a12 * z)
        + ah2 * tl.abs(a20 * x + a21 * y + a22 * z)
    )
    radius_b = (
        bh0 * tl.abs(b00 * x + b01 * y + b02 * z)
        + bh1 * tl.abs(b10 * x + b11 * y + b12 * z)
        + bh2 * tl.abs(b20 * x + b21 * y + b22 * z)
    )
    return center - radius_a - radius_b


@triton.jit
def _sat_gap(
    dx, dy, dz,
    a00, a01, a02, a10, a11, a12, a20, a21, a22,
    ah0, ah1, ah2,
    b00, b01, b02, b10, b11, b12, b20, b21, b22,
    bh0, bh1, bh2,
):
    gap = _axis_gap(a00, a01, a02, dx, dy, dz, a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2)
    gap = tl.maximum(gap, _axis_gap(a10,a11,a12,dx,dy,dz,a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2))
    gap = tl.maximum(gap, _axis_gap(a20,a21,a22,dx,dy,dz,a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2))
    gap = tl.maximum(gap, _axis_gap(b00,b01,b02,dx,dy,dz,a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2))
    gap = tl.maximum(gap, _axis_gap(b10,b11,b12,dx,dy,dz,a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2))
    gap = tl.maximum(gap, _axis_gap(b20,b21,b22,dx,dy,dz,a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2))
    # The nine edge cross axes. Parallel pairs cannot separate and are skipped.
    for ai in tl.static_range(0, 3):
        ax = tl.where(ai == 0, a00, tl.where(ai == 1, a10, a20))
        ay = tl.where(ai == 0, a01, tl.where(ai == 1, a11, a21))
        az = tl.where(ai == 0, a02, tl.where(ai == 1, a12, a22))
        for bi in tl.static_range(0, 3):
            bx = tl.where(bi == 0, b00, tl.where(bi == 1, b10, b20))
            by = tl.where(bi == 0, b01, tl.where(bi == 1, b11, b21))
            bz = tl.where(bi == 0, b02, tl.where(bi == 1, b12, b22))
            cx, cy, cz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
            norm2 = cx * cx + cy * cy + cz * cz
            cross_gap = _axis_gap(cx,cy,cz,dx,dy,dz,a00,a01,a02,a10,a11,a12,a20,a21,a22,ah0,ah1,ah2,b00,b01,b02,b10,b11,b12,b20,b21,b22,bh0,bh1,bh2)
            gap = tl.where(norm2 > 1.0e-16, tl.maximum(gap, cross_gap), gap)
    return gap


@triton.jit
def _first_contact_kernel(
    dc0, da0, dc1, da1, dh, dr, doff,
    ac0, aa0, ac1, aa1, ah, ar, aoff,
    out_hit, out_time, out_gap, out_iterations,
    collider_count: tl.constexpr,
    tolerance: tl.constexpr,
    gap_epsilon: tl.constexpr,
    max_iterations: tl.constexpr,
    cylinder_sides: tl.constexpr,
):
    pid = tl.program_id(0)
    batch = pid // collider_count
    collider = pid - batch * collider_count
    center_offset = (batch * collider_count + collider) * 3
    axes_offset = (batch * collider_count + collider) * 9
    half_offset = center_offset
    attack_center_offset = batch * 3
    attack_axes_offset = batch * 9
    d0x = tl.load(dc0 + center_offset); d0y = tl.load(dc0 + center_offset + 1); d0z = tl.load(dc0 + center_offset + 2)
    d1x = tl.load(dc1 + center_offset); d1y = tl.load(dc1 + center_offset + 1); d1z = tl.load(dc1 + center_offset + 2)
    a000=tl.load(da0+axes_offset); a001=tl.load(da0+axes_offset+1); a002=tl.load(da0+axes_offset+2)
    a010=tl.load(da0+axes_offset+3); a011=tl.load(da0+axes_offset+4); a012=tl.load(da0+axes_offset+5)
    a020=tl.load(da0+axes_offset+6); a021=tl.load(da0+axes_offset+7); a022=tl.load(da0+axes_offset+8)
    a100=tl.load(da1+axes_offset); a101=tl.load(da1+axes_offset+1); a102=tl.load(da1+axes_offset+2)
    a110=tl.load(da1+axes_offset+3); a111=tl.load(da1+axes_offset+4); a112=tl.load(da1+axes_offset+5)
    a120=tl.load(da1+axes_offset+6); a121=tl.load(da1+axes_offset+7); a122=tl.load(da1+axes_offset+8)
    dh0 = tl.load(dh + half_offset); dh1 = tl.load(dh + half_offset + 1); dh2 = tl.load(dh + half_offset + 2)
    radius_d = tl.load(dr + batch * collider_count + collider)
    od0 = tl.load(doff + center_offset); od1 = tl.load(doff + center_offset + 1); od2 = tl.load(doff + center_offset + 2)
    c0x = tl.load(ac0 + attack_center_offset); c0y = tl.load(ac0 + attack_center_offset + 1); c0z = tl.load(ac0 + attack_center_offset + 2)
    c1x = tl.load(ac1 + attack_center_offset); c1y = tl.load(ac1 + attack_center_offset + 1); c1z = tl.load(ac1 + attack_center_offset + 2)
    b000=tl.load(aa0+attack_axes_offset); b001=tl.load(aa0+attack_axes_offset+1); b002=tl.load(aa0+attack_axes_offset+2)
    b010=tl.load(aa0+attack_axes_offset+3); b011=tl.load(aa0+attack_axes_offset+4); b012=tl.load(aa0+attack_axes_offset+5)
    b020=tl.load(aa0+attack_axes_offset+6); b021=tl.load(aa0+attack_axes_offset+7); b022=tl.load(aa0+attack_axes_offset+8)
    b100=tl.load(aa1+attack_axes_offset); b101=tl.load(aa1+attack_axes_offset+1); b102=tl.load(aa1+attack_axes_offset+2)
    b110=tl.load(aa1+attack_axes_offset+3); b111=tl.load(aa1+attack_axes_offset+4); b112=tl.load(aa1+attack_axes_offset+5)
    b120=tl.load(aa1+attack_axes_offset+6); b121=tl.load(aa1+attack_axes_offset+7); b122=tl.load(aa1+attack_axes_offset+8)
    bh0 = tl.load(ah + attack_center_offset); bh1 = tl.load(ah + attack_center_offset + 1); bh2 = tl.load(ah + attack_center_offset + 2)
    radius_a = tl.load(ar + batch)
    oa0 = tl.load(aoff + attack_center_offset); oa1 = tl.load(aoff + attack_center_offset + 1); oa2 = tl.load(aoff + attack_center_offset + 2)
    qa0w,qa0x,qa0y,qa0z = _quaternion_from_rows(a000,a001,a002,a010,a011,a012,a020,a021,a022)
    qa1w,qa1x,qa1y,qa1z = _quaternion_from_rows(a100,a101,a102,a110,a111,a112,a120,a121,a122)
    qb0w,qb0x,qb0y,qb0z = _quaternion_from_rows(b000,b001,b002,b010,b011,b012,b020,b021,b022)
    qb1w,qb1x,qb1y,qb1z = _quaternion_from_rows(b100,b101,b102,b110,b111,b112,b120,b121,b122)
    trace_d = a000*a100+a001*a101+a002*a102+a010*a110+a011*a111+a012*a112+a020*a120+a021*a121+a022*a122
    trace_a = b000*b100+b001*b101+b002*b102+b010*b110+b011*b111+b012*b112+b020*b120+b021*b121+b022*b122
    angle_d = libdevice.acos(tl.maximum(-1.0, tl.minimum(1.0, (trace_d - 1.0) * 0.5)))
    angle_a = libdevice.acos(tl.maximum(-1.0, tl.minimum(1.0, (trace_a - 1.0) * 0.5)))
    dow0x=od0*a000+od1*a010+od2*a020; dow0y=od0*a001+od1*a011+od2*a021; dow0z=od0*a002+od1*a012+od2*a022
    dow1x=od0*a100+od1*a110+od2*a120; dow1y=od0*a101+od1*a111+od2*a121; dow1z=od0*a102+od1*a112+od2*a122
    aow0x=oa0*b000+oa1*b010+oa2*b020; aow0y=oa0*b001+oa1*b011+oa2*b021; aow0z=oa0*b002+oa1*b012+oa2*b022
    aow1x=oa0*b100+oa1*b110+oa2*b120; aow1y=oa0*b101+oa1*b111+oa2*b121; aow1z=oa0*b102+oa1*b112+oa2*b122
    danchor0x=d0x-dow0x; danchor0y=d0y-dow0y; danchor0z=d0z-dow0z
    danchor1x=d1x-dow1x; danchor1y=d1y-dow1y; danchor1z=d1z-dow1z
    aanchor0x=c0x-aow0x; aanchor0y=c0y-aow0y; aanchor0z=c0z-aow0z
    aanchor1x=c1x-aow1x; aanchor1y=c1y-aow1y; aanchor1z=c1z-aow1z
    ddx=danchor1x-danchor0x; ddy=danchor1y-danchor0y; ddz=danchor1z-danchor0z
    adx=aanchor1x-aanchor0x; ady=aanchor1y-aanchor0y; adz=aanchor1z-aanchor0z
    sweep_d=radius_d+tl.sqrt(od0*od0+od1*od1+od2*od2)
    sweep_a=radius_a+tl.sqrt(oa0*oa0+oa1*oa1+oa2*oa2)
    speed = tl.sqrt(ddx*ddx+ddy*ddy+ddz*ddz) + sweep_d*angle_d
    speed += tl.sqrt(adx*adx+ady*ady+adz*adz) + sweep_a*angle_a
    current = 0.0
    gap = float("inf")
    hit = 0
    iteration = 0
    done = 0
    while (iteration < max_iterations) & (done == 0):
        aqw,aqx,aqy,aqz = _slerp(
            qa0w, qa0x, qa0y, qa0z,
            qa1w, qa1x, qa1y, qa1z, current,
        )
        bqw,bqx,bqy,bqz = _slerp(
            qb0w, qb0x, qb0y, qb0z,
            qb1w, qb1x, qb1y, qb1z, current,
        )
        ar00,ar01,ar02,ar10,ar11,ar12,ar20,ar21,ar22 = _rows_from_quaternion(aqw,aqx,aqy,aqz)
        br00,br01,br02,br10,br11,br12,br20,br21,br22 = _rows_from_quaternion(bqw,bqx,bqy,bqz)
        dax = danchor0x + current*(danchor1x-danchor0x) + od0*ar00+od1*ar10+od2*ar20
        day = danchor0y + current*(danchor1y-danchor0y) + od0*ar01+od1*ar11+od2*ar21
        daz = danchor0z + current*(danchor1z-danchor0z) + od0*ar02+od1*ar12+od2*ar22
        cbx = aanchor0x + current*(aanchor1x-aanchor0x) + oa0*br00+oa1*br10+oa2*br20
        cby = aanchor0y + current*(aanchor1y-aanchor0y) + oa0*br01+oa1*br11+oa2*br21
        cbz = aanchor0z + current*(aanchor1z-aanchor0z) + oa0*br02+oa1*br12+oa2*br22
        if cylinder_sides:
            gap = cylinder_gap(cbx-dax,cby-day,cbz-daz,ar00,ar01,ar02,ar10,ar11,ar12,ar20,ar21,ar22,
                               dh0,dh1,dh2,bh0,bh1,cylinder_sides)
        else:
            gap = _sat_gap(
            cbx-dax, cby-day, cbz-daz,
            ar00, ar01, ar02, ar10, ar11, ar12, ar20, ar21, ar22,
            dh0, dh1, dh2,
            br00, br01, br02, br10, br11, br12, br20, br21, br22,
            bh0, bh1, bh2,
        )
        reached = (gap <= gap_epsilon) | (gap <= speed*tolerance + gap_epsilon)
        hit = tl.where(reached, 1, hit)
        done = tl.where(reached, 1, done)
        no_motion = speed <= 1.0e-12
        step = tl.maximum(gap, 0.0) / tl.maximum(speed, 1.0e-12)
        following = current + step
        escaped = (current >= 1.0) & (gap > gap_epsilon)
        done = tl.where(no_motion | escaped, 1, done)
        current = tl.where(done == 0, tl.minimum(following, 1.0), current)
        iteration += 1
    unresolved = done == 0
    hit = tl.where(unresolved, 1, hit)
    gap = tl.where(unresolved, 0.0, gap)
    tl.store(out_hit + pid, hit)
    tl.store(out_time + pid, tl.where(hit != 0, current, float("inf")))
    tl.store(out_gap + pid, gap)
    tl.store(out_iterations + pid, iteration)


def first_contact_pairs(
    defender_center0: torch.Tensor,
    defender_axes0: torch.Tensor,
    defender_center1: torch.Tensor,
    defender_axes1: torch.Tensor,
    defender_half: torch.Tensor,
    defender_radius: torch.Tensor,
    defender_center_offset_local: torch.Tensor,
    attacker_center0: torch.Tensor,
    attacker_axes0: torch.Tensor,
    attacker_center1: torch.Tensor,
    attacker_axes1: torch.Tensor,
    attacker_half: torch.Tensor,
    attacker_radius: torch.Tensor,
    attacker_center_offset_local: torch.Tensor,
    *,
    tolerance: float = 1.0 / 4096.0,
    gap_epsilon: float = 1.0e-7,
    max_iterations: int = 4096,
    cylinder_sides: int = 0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    if not defender_center0.is_cuda:
        raise RuntimeError("Triton CCD requires CUDA tensors")
    tensors = (
        defender_center0, defender_axes0, defender_center1, defender_axes1,
        defender_half, defender_radius, defender_center_offset_local,
        attacker_center0, attacker_axes0,
        attacker_center1, attacker_axes1, attacker_half, attacker_radius,
        attacker_center_offset_local,
    )
    if not all(value.is_contiguous() for value in tensors):
        raise RuntimeError("Triton CCD inputs must be pre-contiguous")
    batch, collider_count = defender_center0.shape[:2]
    hit = torch.empty((batch, collider_count), dtype=torch.int32, device=defender_center0.device)
    times = torch.empty((batch, collider_count), dtype=torch.float32, device=defender_center0.device)
    gaps = torch.empty_like(times)
    iterations = torch.empty((batch, collider_count), dtype=torch.int32, device=defender_center0.device)
    _first_contact_kernel[(batch * collider_count,)](
        *tensors, hit, times, gaps, iterations,
        collider_count=collider_count,
        tolerance=float(tolerance), gap_epsilon=float(gap_epsilon),
        max_iterations=int(max_iterations), cylinder_sides=int(cylinder_sides), num_warps=4 if cylinder_sides else 1,
    )
    return hit != 0, times, gaps, iterations
