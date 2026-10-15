"""Diagnostic hard velocity axes from Jolt SwingTwistConstraintPart.

The original MJ PHAT rows differentiate the cone/twist coordinates. Jolt instead
uses the rotation from clamped to current swing, and the current twist axis.
These agree at small angles but are not the same rule at a finite swing angle.
Only the opt-in transfer profile calls this kernel. Limits themselves unchanged.
"""
import warp as wp
from sequential_contact_gpu import ContactProblem
from limit_projection_gpu import clamp_rotation


@wp.func
def directions(rotation:wp.quat,angles:wp.vec3):
    norm=wp.sqrt(rotation[0]*rotation[0]+rotation[3]*rotation[3])
    twist=wp.quat_identity()
    if norm>1e-12:twist=wp.quat(rotation[0]/norm,0.,0.,rotation[3]/norm)
    swing=rotation*wp.quat_inverse(twist)
    if twist[3]<0.:twist=-twist
    if swing[3]<0.:swing=-swing
    twist_active=wp.abs(twist[0])>wp.sin(.5*angles[0])
    a=wp.sin(.5*angles[1]);b=wp.sin(.5*angles[2])
    swing_active=swing[1]*swing[1]/(a*a)+swing[2]*swing[2]/(b*b)>1.
    # Rotate the same cross product into child axes before normalizing. Current
    # X is then exactly [1,0,0], avoiding cancellation in its zero X component.
    desired=wp.quat_rotate(wp.quat_inverse(rotation)*clamp_rotation(rotation,angles),wp.vec3(1.,0.,0.))
    axis=wp.cross(desired,wp.vec3(1.,0.,0.));length=wp.length(axis)
    sg=wp.vec3(0.)
    if length>0.:sg=-axis/length
    tg=wp.vec3(-wp.sign(twist[0]),0.,0.)
    return twist_active,swing_active,tg,sg


@wp.kernel(enable_backward=False)
def append(p:ContactProblem,qpos:wp.array2d(dtype=float),joints:wp.array(dtype=int),
            reference_wxyz:wp.array(dtype=wp.quat),angles:wp.array(dtype=wp.vec3),
            qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),
            mapping:wp.array2d(dtype=int),error:wp.array(dtype=int)):
    w=wp.tid()
    for index in range(joints.shape[0]):
        joint=joints[index];qa=qadr[joint];da=dadr[joint];ref=reference_wxyz[index]
        rotation=wp.quat(ref[1],ref[2],ref[3],ref[0])*wp.quat(qpos[w,qa+1],qpos[w,qa+2],qpos[w,qa+3],qpos[w,qa])
        twist_active,swing_active,tg,sg=directions(rotation,angles[index])
        # Preserve Jolt's swing-then-twist order. Generate the active rows
        # directly; don't depend on MJ's slightly different boundary tests.
        for axis in range(2):
            active=swing_active;gradient=sg
            if axis==1:active=twist_active;gradient=tg
            if not active or wp.length_sq(gradient)==0.:continue
            slot=p.nlimit[w]
            if slot>=p.limit_J.shape[1]:error[w]=8;continue
            p.nlimit[w]=slot+1;mapping[w,slot]=-1
            p.limit_target[w,slot]=0.;p.limit_compliance[w,slot]=0.;p.limit_bilateral[w,slot]=0
            for j in range(3):p.limit_J[w,slot,da+j]=gradient[j]
