#pragma once

#include "CoreMinimal.h"

namespace ProphecyNNLegClamps
{
// Apply the same reach/radius controls to a decoded attack after it replaces locomotion.
// Rotations of the foot/toes, upper-leg pose, scales and raw model history are not authored here.
inline void Apply(const FVector& Hip, FTransform& Calf, FTransform& Foot, FTransform& Toe,
	const FVector& CalfLocalAxis, double UpperLength, bool bFoot, float FootMultiplier,
	bool bCalf, float CalfMultiplier, float FootLeewayCm = 0, float CalfLeewayCm = 0)
{
	if (!bFoot && !bCalf) return;
	const double LowerLength = CalfLocalAxis.Length();
	if (LowerLength <= UE_SMALL_NUMBER) return;
	auto Multiplier = [](float Value) { return FMath::IsFinite(Value) ? FMath::Max(0.f, Value) : 1.f; };
	const FVector Knee = Calf.GetTranslation();
	FVector End = Foot.GetTranslation();
	if (bFoot)
	{
		const double Maximum = (UpperLength + LowerLength) * Multiplier(FootMultiplier) + FMath::Max(0.f, FootLeewayCm);
		const FVector Delta = End - Hip;
		if (Maximum > 0 && Delta.SizeSquared() > Maximum * Maximum)
			End = Hip + Delta * (Maximum / Delta.Length());
	}
	const FVector CurrentAxis = Calf.GetRotation().RotateVector(CalfLocalAxis / LowerLength);
	FVector DesiredAxis = (End - Knee).GetSafeNormal(UE_SMALL_NUMBER, CurrentAxis);
	if (bCalf)
	{
		const double Length = LowerLength * Multiplier(CalfMultiplier);
		if (Length > 0)
		{
			const double Radius = (End-Knee).Length();
			const double Leeway = FMath::Max(0.f, CalfLeewayCm);
			const double Allowed = FMath::Clamp(Radius, FMath::Max(0., Length-Leeway), Length+Leeway);
			if (Allowed != Radius) End = Knee + DesiredAxis * Allowed;
		}
	}
	// Within the permitted band, leave the decoded pose untouched.
	if (End == Foot.GetTranslation() && (!bCalf || CalfLeewayCm > 0)) return;
	// Reach clipping may change the aim. Preserve the decoded roll using the shortest swing.
	Calf.SetRotation((FQuat::FindBetweenNormals(CurrentAxis, DesiredAxis) * Calf.GetRotation()).GetNormalized());
	const FVector Shift = End - Foot.GetTranslation();
	Foot.SetTranslation(End);
	Toe.AddToTranslation(Shift);
}
}
