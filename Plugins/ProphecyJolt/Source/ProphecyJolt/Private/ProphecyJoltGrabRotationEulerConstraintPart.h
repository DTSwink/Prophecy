// Jolt Physics Library (https://github.com/jrouwe/JoltPhysics)
// SPDX-FileCopyrightText: 2021 Jorrit Rouwe
// SPDX-License-Identifier: MIT

#pragma once
// Adapted from pinned Jolt 5.6.0 (including our numerical-safety patch).
// Only this constraint uses the scaled effective mass/inertia; bodies are never modified.

#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/StateRecorder.h>

namespace ProphecyJolt {


/// Constrains rotation around all axis so that only translation is allowed
///
/// Based on: "Constraints Derivation for Rigid Body Simulation in 3D" - Daniel Chappuis, section 2.5.1
///
/// Constraint equation (eq 129):
///
/// \f[C = \begin{bmatrix}\Delta\theta_x, \Delta\theta_y, \Delta\theta_z\end{bmatrix}\f]
///
/// Jacobian (eq 131):
///
/// \f[J = \begin{bmatrix}0 & -E & 0 & E\end{bmatrix}\f]
///
/// Used terms (here and below, everything in world space):\n
/// delta_theta_* = difference in rotation between initial rotation of bodies 1 and 2.\n
/// x1, x2 = center of mass for the bodies.\n
/// v = [v1, w1, v2, w2].\n
/// v1, v2 = linear velocity of body 1 and 2.\n
/// w1, w2 = angular velocity of body 1 and 2.\n
/// M = mass matrix, a diagonal matrix of the mass and inertia with diagonal [m1, I1, m2, I2].\n
/// \f$K^{-1} = \left( J M^{-1} J^T \right)^{-1}\f$ = effective mass.\n
/// b = velocity bias.\n
/// \f$\beta\f$ = baumgarte constant.\n
/// E = identity matrix.\n
class FGrabRotationEulerConstraintPart
{
private:
    float mHandScale = 1.f;
	/// Internal helper function to update velocities of bodies after Lagrange multiplier is calculated
	JPH_INLINE bool				ApplyVelocityStep(JPH::Body &ioBody1, JPH::Body &ioBody2, JPH::Vec3Arg inLambda) const
	{
		// Apply impulse if delta is not zero
		if (inLambda != JPH::Vec3::sZero())
		{
			// Calculate velocity change due to constraint
			//
			// Impulse:
			// P = J^T lambda
			//
			// Euler velocity integration:
			// v' = v + M^-1 P
			if (ioBody1.IsDynamic())
				ioBody1.GetMotionProperties()->SubAngularVelocityStep(mInvI1.Multiply3x3(inLambda));
			if (ioBody2.IsDynamic())
				ioBody2.GetMotionProperties()->AddAngularVelocityStep(mInvI2.Multiply3x3(inLambda));
			return true;
		}

		return false;
	}

public:
    void SetHandScale(float Scale) { mHandScale = Scale; }
	/// Return inverse of initial rotation from body 1 to body 2 in body 1 space
	static JPH::Quat					sGetInvInitialOrientation(const JPH::Body &inBody1, const JPH::Body &inBody2)
	{
		// q20 = q10 r0
		// <=> r0 = q10^-1 q20
		// <=> r0^-1 = q20^-1 q10
		//
		// where:
		//
		// q20 = initial orientation of body 2
		// q10 = initial orientation of body 1
		// r0 = initial rotation from body 1 to body 2
		return inBody2.GetRotation().Conjugated() * inBody1.GetRotation();
	}

	/// @brief Return inverse of initial rotation from body 1 to body 2 in body 1 space
	/// @param inAxisX1 Reference axis X for body 1
	/// @param inAxisY1 Reference axis Y for body 1
	/// @param inAxisX2 Reference axis X for body 2
	/// @param inAxisY2 Reference axis Y for body 2
	static JPH::Quat					sGetInvInitialOrientationXY(JPH::Vec3Arg inAxisX1, JPH::Vec3Arg inAxisY1, JPH::Vec3Arg inAxisX2, JPH::Vec3Arg inAxisY2)
	{
		// Store inverse of initial rotation from body 1 to body 2 in body 1 space:
		//
		// q20 = q10 r0
		// <=> r0 = q10^-1 q20
		// <=> r0^-1 = q20^-1 q10
		//
		// where:
		//
		// q10, q20 = world space initial orientation of body 1 and 2
		// r0 = initial rotation from body 1 to body 2 in local space of body 1
		//
		// We can also write this in terms of the constraint matrices:
		//
		// q20 c2 = q10 c1
		// <=> q20 = q10 c1 c2^-1
		// => r0 = c1 c2^-1
		// <=> r0^-1 = c2 c1^-1
		//
		// where:
		//
		// c1, c2 = matrix that takes us from body 1 and 2 COM to constraint space 1 and 2
		if (inAxisX1 == inAxisX2 && inAxisY1 == inAxisY2)
		{
			// Axis are the same -> identity transform
			return JPH::Quat::sIdentity();
		}
		else
		{
			JPH::Mat44 constraint1(JPH::Vec4(inAxisX1, 0), JPH::Vec4(inAxisY1, 0), JPH::Vec4(inAxisX1.Cross(inAxisY1), 0), JPH::Vec4(0, 0, 0, 1));
			JPH::Mat44 constraint2(JPH::Vec4(inAxisX2, 0), JPH::Vec4(inAxisY2, 0), JPH::Vec4(inAxisX2.Cross(inAxisY2), 0), JPH::Vec4(0, 0, 0, 1));
			return constraint2.GetQuaternion() * constraint1.GetQuaternion().Conjugated();
		}
	}

	/// @brief Return inverse of initial rotation from body 1 to body 2 in body 1 space
	/// @param inAxisX1 Reference axis X for body 1
	/// @param inAxisZ1 Reference axis Z for body 1
	/// @param inAxisX2 Reference axis X for body 2
	/// @param inAxisZ2 Reference axis Z for body 2
	static JPH::Quat					sGetInvInitialOrientationXZ(JPH::Vec3Arg inAxisX1, JPH::Vec3Arg inAxisZ1, JPH::Vec3Arg inAxisX2, JPH::Vec3Arg inAxisZ2)
	{
		// See comment at sGetInvInitialOrientationXY
		if (inAxisX1 == inAxisX2 && inAxisZ1 == inAxisZ2)
		{
			return JPH::Quat::sIdentity();
		}
		else
		{
			JPH::Mat44 constraint1(JPH::Vec4(inAxisX1, 0), JPH::Vec4(inAxisZ1.Cross(inAxisX1), 0), JPH::Vec4(inAxisZ1, 0), JPH::Vec4(0, 0, 0, 1));
			JPH::Mat44 constraint2(JPH::Vec4(inAxisX2, 0), JPH::Vec4(inAxisZ2.Cross(inAxisX2), 0), JPH::Vec4(inAxisZ2, 0), JPH::Vec4(0, 0, 0, 1));
			return constraint2.GetQuaternion() * constraint1.GetQuaternion().Conjugated();
		}
	}

	/// Calculate properties used during the functions below
	inline void					CalculateConstraintProperties(const JPH::Body &inBody1, JPH::Mat44Arg inRotation1, const JPH::Body &inBody2, JPH::Mat44Arg inRotation2)
	{
		// Calculate properties used during constraint solving
		mInvI1 = inBody1.IsDynamic()? (inBody1.GetMotionProperties()->GetInverseInertiaForRotation(inRotation1) * mHandScale) : JPH::Mat44::sZero();
		mInvI2 = inBody2.IsDynamic()? inBody2.GetMotionProperties()->GetInverseInertiaForRotation(inRotation2) : JPH::Mat44::sZero();

		// Calculate effective mass: K^-1 = (J M^-1 J^T)^-1
		JPH::Mat44 inertia_sum = mInvI1 + mInvI2;
		if (!mEffectiveMass.SetInversed3x3(inertia_sum))
		{
			// If a column is zero, the axis is locked and we set the column to identity.
			// This does not matter because any impulse will always be multiplied with mInvI1 or mInvI2 which will result in zero for the locked coordinate.
			JPH::Vec4 zero = JPH::Vec4::sZero();
			if (inertia_sum.GetColumn4(0) == zero)
				inertia_sum.SetColumn4(0, JPH::Vec4(1, 0, 0, 0));
			if (inertia_sum.GetColumn4(1) == zero)
				inertia_sum.SetColumn4(1, JPH::Vec4(0, 1, 0, 0));
			if (inertia_sum.GetColumn4(2) == zero)
				inertia_sum.SetColumn4(2, JPH::Vec4(0, 0, 1, 0));
			if (!mEffectiveMass.SetInversed3x3(inertia_sum))
				Deactivate();
		}
	}

	/// Deactivate this constraint
	inline void					Deactivate()
	{
		mEffectiveMass = JPH::Mat44::sZero();
		mTotalLambda = JPH::Vec3::sZero();
	}

	/// Check if constraint is active
	inline bool					IsActive() const
	{
		return mEffectiveMass(3, 3) != 0.0f;
	}

	/// Must be called from the WarmStartVelocityConstraint call to apply the previous frame's impulses
	inline void					WarmStart(JPH::Body &ioBody1, JPH::Body &ioBody2, float inWarmStartImpulseRatio)
	{
		mTotalLambda *= inWarmStartImpulseRatio;
		ApplyVelocityStep(ioBody1, ioBody2, mTotalLambda);
	}

	/// Iteratively update the velocity constraint. Makes sure d/dt C(...) = 0, where C is the constraint equation.
	inline bool					SolveVelocityConstraint(JPH::Body &ioBody1, JPH::Body &ioBody2)
	{
		// Calculate lagrange multiplier:
		//
		// lambda = -K^-1 (J v + b)
		JPH::Vec3 lambda = mEffectiveMass.Multiply3x3(ioBody1.GetAngularVelocity() - ioBody2.GetAngularVelocity());
		mTotalLambda += lambda;
		return ApplyVelocityStep(ioBody1, ioBody2, lambda);
	}

	/// Iteratively update the position constraint. Makes sure C(...) = 0.
	inline bool					SolvePositionConstraint(JPH::Body &ioBody1, JPH::Body &ioBody2, JPH::QuatArg inInvInitialOrientation, float inBaumgarte) const
	{
		// Calculate difference in rotation
		//
		// The rotation should be:
		//
		// q2 = q1 r0
		//
		// But because of drift the actual rotation is
		//
		// q2 = diff q1 r0
		// <=> diff = q2 r0^-1 q1^-1
		//
		// Where:
		// q1 = current rotation of body 1
		// q2 = current rotation of body 2
		// diff = error that needs to be reduced to zero
		JPH::Quat diff = ioBody2.GetRotation() * inInvInitialOrientation * ioBody1.GetRotation().Conjugated();

		// A quaternion can be seen as:
		//
		// q = [sin(theta / 2) * v, cos(theta/2)]
		//
		// Where:
		// v = rotation vector
		// theta = rotation angle
		//
		// If we assume theta is small (error is small) then sin(x) = x so an approximation of the error angles is:
		JPH::Vec3 error = 2.0f * diff.EnsureWPositive().GetXYZ();
		if (error != JPH::Vec3::sZero())
		{
			// Calculate lagrange multiplier (lambda) for Baumgarte stabilization:
			//
			// lambda = -K^-1 * beta / dt * C
			//
			// We should divide by inDeltaTime, but we should multiply by inDeltaTime in the Euler step below so they're cancelled out
			JPH::Vec3 lambda = -inBaumgarte * mEffectiveMass * error;

			// Directly integrate velocity change for one time step
			//
			// Euler velocity integration:
			// dv = M^-1 P
			//
			// Impulse:
			// P = J^T lambda
			//
			// Euler position integration:
			// x' = x + dv * dt
			//
			// Note we don't accumulate velocities for the stabilization. This is using the approach described in 'Modeling and
			// Solving Constraints' by Erin Catto presented at GDC 2007. On slide 78 it is suggested to split up the Baumgarte
			// stabilization for positional drift so that it does not actually add to the momentum. We combine an Euler velocity
			// integrate + a position integrate and then discard the velocity change.
			if (ioBody1.IsDynamic())
				ioBody1.SubRotationStep(mInvI1.Multiply3x3(lambda));
			if (ioBody2.IsDynamic())
				ioBody2.AddRotationStep(mInvI2.Multiply3x3(lambda));
			return true;
		}

		return false;
	}

	/// Return lagrange multiplier
	JPH::Vec3						GetTotalLambda() const
	{
		return mTotalLambda;
	}

	/// Save state of this constraint part
	void						SaveState(JPH::StateRecorder &inStream) const
	{
		inStream.Write(mTotalLambda);
	}

	/// Restore state of this constraint part
	void						RestoreState(JPH::StateRecorder &inStream)
	{
		inStream.Read(mTotalLambda);
	}

private:
	JPH::Mat44						mInvI1;
	JPH::Mat44						mInvI2;
	JPH::Mat44						mEffectiveMass;
	JPH::Vec3						mTotalLambda { JPH::Vec3::sZero() };
};

}
