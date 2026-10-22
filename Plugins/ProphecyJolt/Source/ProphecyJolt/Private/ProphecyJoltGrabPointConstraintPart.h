// Jolt Physics Library (https://github.com/jrouwe/JoltPhysics)
// SPDX-FileCopyrightText: 2021 Jorrit Rouwe
// SPDX-License-Identifier: MIT

#pragma once
// Adapted from pinned Jolt 5.6.0 (including our numerical-safety patch).
// Only this constraint uses the scaled effective mass/inertia; bodies are never modified.

#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/StateRecorder.h>

namespace ProphecyJolt {


/// Constrains movement along 3 axis
///
/// @see "Constraints Derivation for Rigid Body Simulation in 3D" - Daniel Chappuis, section 2.2.1
///
/// Constraint equation (eq 45):
///
/// \f[C = p_2 - p_1\f]
///
/// Jacobian (transposed) (eq 47):
///
/// \f[J^T = \begin{bmatrix}-E & r1x & E & -r2x^T\end{bmatrix}
/// = \begin{bmatrix}-E^T \\ r1x^T \\ E^T \\ -r2x^T\end{bmatrix}
/// = \begin{bmatrix}-E \\ -r1x \\ E \\ r2x\end{bmatrix}\f]
///
/// Used terms (here and below, everything in world space):\n
/// p1, p2 = constraint points.\n
/// r1 = p1 - x1.\n
/// r2 = p2 - x2.\n
/// r1x = 3x3 matrix for which r1x v = r1 x v (cross product).\n
/// x1, x2 = center of mass for the bodies.\n
/// v = [v1, w1, v2, w2].\n
/// v1, v2 = linear velocity of body 1 and 2.\n
/// w1, w2 = angular velocity of body 1 and 2.\n
/// M = mass matrix, a diagonal matrix of the mass and inertia with diagonal [m1, I1, m2, I2].\n
/// \f$K^{-1} = \left( J M^{-1} J^T \right)^{-1}\f$ = effective mass.\n
/// b = velocity bias.\n
/// \f$\beta\f$ = baumgarte constant.\n
/// E = identity matrix.
class FGrabPointConstraintPart
{
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
			{
				JPH::MotionProperties *mp1 = ioBody1.GetMotionProperties();
				mp1->SubLinearVelocityStep((mp1->GetInverseMass() * mHandScale) * inLambda);
				mp1->SubAngularVelocityStep(mInvI1_R1X * inLambda);
			}
			if (ioBody2.IsDynamic())
			{
				JPH::MotionProperties *mp2 = ioBody2.GetMotionProperties();
				mp2->AddLinearVelocityStep(mp2->GetInverseMass() * inLambda);
				mp2->AddAngularVelocityStep(mInvI2_R2X * inLambda);
			}
			return true;
		}

		return false;
	}

public:
    void SetHandScale(float Scale) { mHandScale = Scale; }
	/// Calculate properties used during the functions below
	/// @param inBody1 The first body that this constraint is attached to
	/// @param inBody2 The second body that this constraint is attached to
	/// @param inRotation1 The 3x3 rotation matrix for body 1 (translation part is ignored)
	/// @param inRotation2 The 3x3 rotation matrix for body 2 (translation part is ignored)
	/// @param inR1 Local space vector from center of mass to constraint point for body 1
	/// @param inR2 Local space vector from center of mass to constraint point for body 2
	inline void					CalculateConstraintProperties(const JPH::Body &inBody1, JPH::Mat44Arg inRotation1, JPH::Vec3Arg inR1, const JPH::Body &inBody2, JPH::Mat44Arg inRotation2, JPH::Vec3Arg inR2)
	{
		// Positions where the point constraint acts on (middle point between center of masses) in world space
		mR1 = inRotation1.Multiply3x3(inR1);
		mR2 = inRotation2.Multiply3x3(inR2);

		// Calculate effective mass: K^-1 = (J M^-1 J^T)^-1
		// Using: I^-1 = R * Ibody^-1 * R^T
		float summed_inv_mass;
		JPH::Mat44 inv_effective_mass;
		if (inBody1.IsDynamic())
		{
			const JPH::MotionProperties *mp1 = inBody1.GetMotionProperties();
			JPH::Mat44 inv_i1 = (mp1->GetInverseInertiaForRotation(inRotation1) * mHandScale);
			summed_inv_mass = (mp1->GetInverseMass() * mHandScale);

			JPH::Mat44 r1x = JPH::Mat44::sCrossProduct(mR1);
			mInvI1_R1X = inv_i1.Multiply3x3(r1x);
			inv_effective_mass = r1x.Multiply3x3(inv_i1).Multiply3x3RightTransposed(r1x);
		}
		else
		{
			JPH_IF_DEBUG(mInvI1_R1X = JPH::Mat44::sNaN();)

			summed_inv_mass = 0.0f;
			inv_effective_mass = JPH::Mat44::sZero();
		}

		if (inBody2.IsDynamic())
		{
			const JPH::MotionProperties *mp2 = inBody2.GetMotionProperties();
			JPH::Mat44 inv_i2 = mp2->GetInverseInertiaForRotation(inRotation2);
			summed_inv_mass += mp2->GetInverseMass();

			JPH::Mat44 r2x = JPH::Mat44::sCrossProduct(mR2);
			mInvI2_R2X = inv_i2.Multiply3x3(r2x);
			inv_effective_mass += r2x.Multiply3x3(inv_i2).Multiply3x3RightTransposed(r2x);
		}
		else
		{
			JPH_IF_DEBUG(mInvI2_R2X = JPH::Mat44::sNaN();)
		}

		inv_effective_mass += JPH::Mat44::sScale(summed_inv_mass);
		if (!mEffectiveMass.SetInversed3x3(inv_effective_mass))
			Deactivate();
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
	/// @param ioBody1 The first body that this constraint is attached to
	/// @param ioBody2 The second body that this constraint is attached to
	/// @param inWarmStartImpulseRatio Ratio of new step to old time step (dt_new / dt_old) for scaling the lagrange multiplier of the previous frame
	inline void					WarmStart(JPH::Body &ioBody1, JPH::Body &ioBody2, float inWarmStartImpulseRatio)
	{
		mTotalLambda *= inWarmStartImpulseRatio;
		ApplyVelocityStep(ioBody1, ioBody2, mTotalLambda);
	}

	/// Iteratively update the velocity constraint. Makes sure d/dt C(...) = 0, where C is the constraint equation.
	/// @param ioBody1 The first body that this constraint is attached to
	/// @param ioBody2 The second body that this constraint is attached to
	inline bool					SolveVelocityConstraint(JPH::Body &ioBody1, JPH::Body &ioBody2)
	{
		// Calculate lagrange multiplier:
		//
		// lambda = -K^-1 (J v + b)
		JPH::Vec3 lambda = mEffectiveMass * (ioBody1.GetLinearVelocity() - mR1.Cross(ioBody1.GetAngularVelocity()) - ioBody2.GetLinearVelocity() + mR2.Cross(ioBody2.GetAngularVelocity()));
		mTotalLambda += lambda; // Store accumulated lambda
		return ApplyVelocityStep(ioBody1, ioBody2, lambda);
	}

	/// Iteratively update the position constraint. Makes sure C(...) = 0.
	/// @param ioBody1 The first body that this constraint is attached to
	/// @param ioBody2 The second body that this constraint is attached to
	/// @param inBaumgarte Baumgarte constant (fraction of the error to correct)
	inline bool					SolvePositionConstraint(JPH::Body &ioBody1, JPH::Body &ioBody2, float inBaumgarte) const
	{
		if (ioBody1.HasNumericalFailure() || ioBody2.HasNumericalFailure())
			return false;
		JPH::Vec3 separation = (JPH::Vec3(ioBody2.GetCenterOfMassPosition() - ioBody1.GetCenterOfMassPosition()) + mR2 - mR1);
		if (separation != JPH::Vec3::sZero())
		{
			// Calculate lagrange multiplier (lambda) for Baumgarte stabilization:
			//
			// lambda = -K^-1 * beta / dt * C
			//
			// We should divide by inDeltaTime, but we should multiply by inDeltaTime in the Euler step below so they're cancelled out
			JPH::Vec3 lambda = mEffectiveMass * -inBaumgarte * separation;
			JPH::Vec3 position_step1 = JPH::Vec3::sZero(), rotation_step1 = JPH::Vec3::sZero();
			JPH::Vec3 position_step2 = JPH::Vec3::sZero(), rotation_step2 = JPH::Vec3::sZero();
			bool valid = true;
			if (ioBody1.IsDynamic())
			{
				position_step1 = (ioBody1.GetMotionProperties()->GetInverseMass() * mHandScale) * lambda;
				rotation_step1 = mInvI1_R1X * lambda;
				valid &= ioBody1.CanApplyPositionStep(-position_step1) && JPH::Body::sIsValidRotationStep(rotation_step1);
			}
			if (ioBody2.IsDynamic())
			{
				position_step2 = ioBody2.GetMotionProperties()->GetInverseMass() * lambda;
				rotation_step2 = mInvI2_R2X * lambda;
				valid &= ioBody2.CanApplyPositionStep(position_step2) && JPH::Body::sIsValidRotationStep(rotation_step2);
			}
			// Validate every increment before committing either endpoint. In particular,
			// do not move a body before discovering its rotation increment is invalid.
			if (!valid)
			{
				if (ioBody1.IsDynamic()) ioBody1.MarkNumericalFailure();
				if (ioBody2.IsDynamic()) ioBody2.MarkNumericalFailure();
				return false;
			}

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
			{
				ioBody1.SubPositionStep(position_step1);
				ioBody1.SubRotationStep(rotation_step1);
			}
			if (ioBody2.IsDynamic())
			{
				ioBody2.AddPositionStep(position_step2);
				ioBody2.AddRotationStep(rotation_step2);
			}

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
    float mHandScale = 1.f;
	JPH::Vec3						mR1;
	JPH::Vec3						mR2;
	JPH::Mat44						mInvI1_R1X;
	JPH::Mat44						mInvI2_R2X;
	JPH::Mat44						mEffectiveMass;
	JPH::Vec3						mTotalLambda { JPH::Vec3::sZero() };
};

}
