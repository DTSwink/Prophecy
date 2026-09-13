#include "ProphecyJoltJointConversion.h"
#include "ProphecyJoltConversions.h"
#include "ProphecyJoltRig.h"

namespace ProphecyJolt
{
namespace
{
bool IsRigidFrame(const FTransform& Frame)
{
    return Frame.IsValid() && Frame.GetScale3D().Equals(FVector::OneVector, 1.0e-6);
}

bool MapAngular(EAngularConstraintMotion Motion, float Degrees,
    JPH::SixDOFConstraintSettings::EAxis Axis, const TCHAR* Label,
    JPH::SixDOFConstraintSettings& Settings, FHardJointConversionReport& Report, FString& Error)
{
    switch (Motion)
    {
    case ACM_Locked:
        Settings.MakeFixedAxis(Axis);
        ++Report.FixedAngularAxisCount;
        return true;
    case ACM_Free:
        Settings.MakeFreeAxis(Axis);
        ++Report.FreeAngularAxisCount;
        return true;
    case ACM_Limited:
        if (!FMath::IsFinite(Degrees) || Degrees < 0.0f || Degrees > 180.0f)
        {
            Error = FString::Printf(TEXT("%s has invalid authored limit %.9g degrees."), Label, Degrees);
            return false;
        }
        // Exact endpoints have unambiguous physical meaning. Retain the requested
        // profile for UE, but canonicalize the native axis instead of rejecting
        // the whole joint when callers use Limited 180 for its unrestricted axes.
        if (Degrees == 180.0f)
        {
            Settings.MakeFreeAxis(Axis);
            ++Report.FreeAngularAxisCount;
            return true;
        }
        if (Degrees == 0.0f)
        {
            Settings.MakeFixedAxis(Axis);
            ++Report.FixedAngularAxisCount;
            return true;
        }
        // Pinned Jolt SwingTwistConstraintPart::SetLimits changes these ranges
        // to locked/free internally. Refuse that loss instead of substituting
        // a nominal 179-degree limit or changing the authored motion mode.
        if (Degrees < 0.5f || Degrees > 179.5f)
        {
            ++Report.RejectedThresholdAxisCount;
            Error = FString::Printf(TEXT("%s Limited %.9g degrees enters Jolt's internal locked/free threshold; authored angle was not changed."), Label, Degrees);
            return false;
        }
        Settings.SetLimitedAxis(Axis, -JPH::DegreesToRadians(Degrees), JPH::DegreesToRadians(Degrees));
        ++Report.HardAngularAxisCount;
        return true;
    default:
        Error = FString::Printf(TEXT("%s has an unknown angular motion enum."), Label);
        return false;
    }
}

void DescribeDeferredProfile(const FConstraintProfileProperties& Profile, FHardJointConversionReport& Report)
{
    // These are explicit readiness gaps for the isolated limit fixture. They
    // must not be erased from the lossless descriptor or read as a no-op port.
    if (Profile.LinearDrive.IsPositionDriveEnabled() || Profile.LinearDrive.IsVelocityDriveEnabled())
        Report.DeferredProfileFeatures.Add(TEXT("Active linear motors are not implemented by the hard-limit fixture."));
    if (Profile.AngularDrive.IsOrientationDriveEnabled() || Profile.AngularDrive.IsVelocityDriveEnabled())
        Report.DeferredProfileFeatures.Add(TEXT("Active selected-mode angular motors are not implemented by the hard-limit fixture."));
    if (Profile.bEnableProjection)
        Report.DeferredProfileFeatures.Add(TEXT("Chaos projection, including teleport tolerances/alphas, is not implemented."));
    if (Profile.bEnableMassConditioning)
        Report.DeferredProfileFeatures.Add(TEXT("Chaos joint mass conditioning is not implemented."));
    if (Profile.bEnableShockPropagation)
        Report.DeferredProfileFeatures.Add(TEXT("Chaos shock propagation is not implemented."));
    if (Profile.bParentDominates)
        Report.DeferredProfileFeatures.Add(TEXT("Parent dominance is not implemented; stock two-body response remains active."));
    if (Profile.bLinearBreakable || Profile.bAngularBreakable)
        Report.DeferredProfileFeatures.Add(TEXT("Break thresholds/events are not implemented."));
    if (Profile.bLinearPlasticity || Profile.bAngularPlasticity)
        Report.DeferredProfileFeatures.Add(TEXT("Plasticity and target reset behavior are not implemented."));
    if (Profile.ContactTransferScale != 0.0f)
        Report.DeferredProfileFeatures.Add(TEXT("Chaos contact transfer scale is not implemented."));
    if (Profile.bUseLinearJointSolver)
        Report.DeferredProfileFeatures.Add(TEXT("Chaos linear joint solver selection is not reproduced by the stock Jolt solver."));
    if ((Profile.ConeLimit.Swing1Motion == ACM_Limited || Profile.ConeLimit.Swing2Motion == ACM_Limited)
        && (Profile.ConeLimit.Restitution != 0.0f || Profile.ConeLimit.ContactDistance != 0.0f))
        Report.DeferredProfileFeatures.Add(TEXT("Authored swing restitution/contact distance has no matching stock Jolt angular-limit setting."));
    if (Profile.TwistLimit.TwistMotion == ACM_Limited
        && (Profile.TwistLimit.Restitution != 0.0f || Profile.TwistLimit.ContactDistance != 0.0f))
        Report.DeferredProfileFeatures.Add(TEXT("Authored twist restitution/contact distance has no matching stock Jolt angular-limit setting."));
}

void SetFrame(const FTransform& Frame, const FTransform& COMToOrigin,
    JPH::RVec3& Position, JPH::Vec3& AxisX, JPH::Vec3& AxisY)
{
    Position = Conversions::ToJoltPosition(COMToOrigin.InverseTransformPosition(Frame.GetTranslation()));
    const FQuat Rotation = COMToOrigin.GetRotation().Inverse() * Frame.GetRotation();
    AxisX = Conversions::ToJoltDirection(Rotation.GetAxisX());
    AxisY = Conversions::ToJoltDirection(Rotation.GetAxisY());
}
}

bool BuildHardJointSettings(const FProphecyJoltRigJoint& Joint,
    const FTransform& Body1COMToBodyOrigin, const FTransform& Body2COMToBodyOrigin,
    JPH::SixDOFConstraintSettings& OutSettings, FHardJointConversionReport& OutReport, FString& OutError)
{
    OutError.Reset();
    OutReport = FHardJointConversionReport();
    OutReport.JoltBody1Index = Joint.Body2Index;
    OutReport.JoltBody2Index = Joint.Body1Index;
    const FConstraintProfileProperties& Profile = Joint.CurrentProfile;
    OutReport.bAuthoredSoftSwing = Profile.ConeLimit.bSoftConstraint;
    OutReport.bAuthoredSoftTwist = Profile.TwistLimit.bSoftConstraint;
    OutReport.bDisableCollision = Profile.bDisableCollision;
    DescribeDeferredProfile(Profile, OutReport);
    if (Joint.Body1Index < 0 || Joint.Body2Index < 0 || Joint.Body1Index == Joint.Body2Index)
    {
        OutError = TEXT("A rig joint requires two distinct captured body indices.");
        return false;
    }
    if (!IsRigidFrame(Joint.Frame1) || !IsRigidFrame(Joint.Frame2)
        || !IsRigidFrame(Body1COMToBodyOrigin) || !IsRigidFrame(Body2COMToBodyOrigin))
    {
        OutError = TEXT("Joint and COM frames must be finite rigid transforms with unit scale; bake scale before conversion.");
        return false;
    }
    if (!Body1COMToBodyOrigin.GetRotation().Equals(FQuat::Identity, 1.0e-6)
        || !Body2COMToBodyOrigin.GetRotation().Equals(FQuat::Identity, 1.0e-6))
    {
        OutError = TEXT("Jolt COM-to-origin frames must have identity rotation; principal inertia rotation belongs in the inertia tensor, not the joint frame.");
        return false;
    }
    if (Profile.AngularDrive.AngularDriveMode != EAngularDriveMode::SLERP
        && Profile.AngularDrive.AngularDriveMode != EAngularDriveMode::TwistAndSwing)
    {
        OutError = TEXT("Unknown authored angular drive mode.");
        return false;
    }

    JPH::SixDOFConstraintSettings Settings;
    Settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    // UE5.7 PBDJointContainerSolver GetJointParticle/GetJointFrame reverse
    // FConstraintInstance Body1/Body2. Jolt's relative rotation is
    // (Rparent*Cparent)^-1 * (Rchild*Cchild): retain that reference direction.
    SetFrame(Joint.Frame2, Body2COMToBodyOrigin, Settings.mPosition1, Settings.mAxisX1, Settings.mAxisY1);
    SetFrame(Joint.Frame1, Body1COMToBodyOrigin, Settings.mPosition2, Settings.mAxisX2, Settings.mAxisY2);

    // Stock Jolt cone is an ellipse in swing-quaternion (Y,Z), with semiaxes
    // sin(Swing2/2), sin(Swing1/2). Axis limits retain the authored angles;
    // combined-swing geometry and solver response are not Chaos parity claims.
    Settings.mSwingType = JPH::ESwingType::Cone;
    using EAxis = JPH::SixDOFConstraintSettings::EAxis;
    const ELinearConstraintMotion LinearMotions[] = { Profile.LinearLimit.XMotion, Profile.LinearLimit.YMotion, Profile.LinearLimit.ZMotion };
    int32 LimitedLinearAxes = 0;
    for (ELinearConstraintMotion Motion : LinearMotions)
        LimitedLinearAxes += Motion == LCM_Limited ? 1 : 0;
    if (LimitedLinearAxes > 1)
    {
        OutError = TEXT("Multiple UE Limited translation axes form a coupled circle/sphere; independent SixDOF ranges cannot preserve that geometry.");
        return false;
    }
    if (LimitedLinearAxes != 0)
    {
        OutError = TEXT("Limited translation is outside this first rig fixture: the lossless profile alone does not supply the live scaled-distance contract. Authored linear limits were not changed.");
        return false;
    }
    for (int32 Index = 0; Index < 3; ++Index)
    {
        const EAxis Axis = static_cast<EAxis>(Index);
        switch (LinearMotions[Index])
        {
        case LCM_Locked: Settings.MakeFixedAxis(Axis); break;
        case LCM_Free: Settings.MakeFreeAxis(Axis); break;
        default:
            OutError = TEXT("Unknown authored linear motion enum.");
            return false;
        }
    }
    if (!MapAngular(Profile.TwistLimit.TwistMotion, Profile.TwistLimit.TwistLimitDegrees, EAxis::RotationX, TEXT("Twist/X"), Settings, OutReport, OutError)
        || !MapAngular(Profile.ConeLimit.Swing2Motion, Profile.ConeLimit.Swing2LimitDegrees, EAxis::RotationY, TEXT("Swing2/Y"), Settings, OutReport, OutError)
        || !MapAngular(Profile.ConeLimit.Swing1Motion, Profile.ConeLimit.Swing1LimitDegrees, EAxis::RotationZ, TEXT("Swing1/Z"), Settings, OutReport, OutError))
        return false;
    OutSettings = Settings;
    return true;
}
}
