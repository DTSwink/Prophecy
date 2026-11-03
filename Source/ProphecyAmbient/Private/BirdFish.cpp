#include "BirdFish.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

ABirdFish::ABirdFish()
{
	PrimaryActorTick.bCanEverTick = false;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Root->SetMobility(EComponentMobility::Movable);
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->bCastDynamicShadow = true;
	Tags.Add(TEXT("BirdFood"));
}

void ABirdFish::Init(UStaticMesh* InMesh, float LengthCm, float StruggleSeconds, int32 Seed)
{
	Rng.Initialize(Seed);
	Length = LengthCm;
	StruggleTime = FMath::Max(StruggleSeconds, 0.1f);
	Phase = Rng.FRandRange(0.f, 6.283f);
	if (!InMesh) return;
	Mesh->SetStaticMesh(InMesh);
	// canonical fish frame on the actor: X = length (longest mesh axis), Y = across the flat side (thinnest axis), Z = height
	const FBoxSphereBounds B = InMesh->GetBounds();
	const FVector E = B.BoxExtent;
	int32 LongA = 0, ThinA = 0;
	for (int32 i = 1; i < 3; ++i)
	{
		if (E[i] > E[LongA]) LongA = i;
		if (E[i] < E[ThinA]) ThinA = i;
	}
	if (ThinA == LongA) ThinA = (LongA + 1) % 3;
	const int32 HighA = 3 - LongA - ThinA;
	FVector Rows[3];
	Rows[LongA] = FVector::XAxisVector;
	Rows[ThinA] = FVector::YAxisVector;
	// right-handed: the remaining mesh axis is the cross product of the other two (in mesh axis order)
	if (HighA == 2) Rows[2] = FVector::CrossProduct(Rows[0], Rows[1]);
	else if (HighA == 0) Rows[0] = FVector::CrossProduct(Rows[1], Rows[2]);
	else Rows[1] = FVector::CrossProduct(Rows[2], Rows[0]);
	const FMatrix M(Rows[0], Rows[1], Rows[2], FVector::ZeroVector);
	const FQuat R(M);
	MeshScale = LengthCm / FMath::Max(2.f * E[LongA], 0.01f);
	MeshOffset = -R.RotateVector(B.Origin * MeshScale);
	HalfThick = E[ThinA] * MeshScale;
	Mesh->SetRelativeRotation(R);
	SetMeat(1.f);
}

void ABirdFish::SetMeat(float InMeat)
{
	Meat = FMath::Clamp(InMeat, 0.f, 1.f);
	// eaten from the middle out: the remains are shorter and thinner (placeholder for a real carcass mesh)
	const float K = 0.5f + 0.5f * Meat;
	Mesh->SetRelativeScale3D(FVector(MeshScale * K));
	Mesh->SetRelativeLocation(MeshOffset * K);
}

FQuat ABirdFish::Orientation(const FVector& Long, const FVector& Side)
{
	const FVector X = Long.GetSafeNormal();
	FVector Y = (Side - X * FVector::DotProduct(Side, X)).GetSafeNormal();
	if (Y.IsNearlyZero()) Y = FVector::CrossProduct(FVector::UpVector, X).GetSafeNormal();
	const FVector Z = FVector::CrossProduct(X, Y);
	return FQuat(FMatrix(X, Y, Z, FVector::ZeroVector));
}

FVector2D ABirdFish::UpdateStruggle(float Dt)
{
	Age += Dt;
	Struggle = FMath::Clamp(1.f - Age / StruggleTime, 0.f, 1.f);
	// fights hard for the first half, then tires: weaker, slower, shorter bursts and longer rests until it lies still
	const float Energy = FMath::Clamp(Struggle / 0.5f, 0.f, 1.f);
	const float Strength = FMath::Pow(Energy, 1.4f);
	NudgeAmp = FMath::Max(0.f, NudgeAmp - Dt * 60.f);
	float Swing = 0.f, Roll = 0.f;
	if (Strength > 0.f)
	{
		// thrashing comes in bursts (tail beats at 3-6 Hz) with pauses that grow longer as the fish tires
		if (BurstLeft > 0.f)
		{
			BurstLeft -= Dt;
			Phase += 2.f * PI * BurstHz * Dt;
			const float Env = FMath::Clamp(BurstLeft / 0.12f, 0.f, 1.f);		// full strength until the last beat
			Swing = BurstAmp * Strength * Env * FMath::Sin(Phase);
			Roll = 0.4f * BurstAmp * Strength * Env * FMath::Sin(Phase * 0.5f + 1.1f);
			if (BurstLeft <= 0.f) PauseLeft = Rng.FRandRange(0.06f, 0.3f) + FMath::Square(1.f - Energy) * Rng.FRandRange(0.6f, 2.2f);
		}
		else
		{
			PauseLeft -= Dt;
			Phase += 2.f * PI * 7.f * Dt;
			Swing = 6.f * Strength * FMath::Sin(Phase);		// quivers between bursts while it still has energy
			if (PauseLeft <= 0.f)
			{
				BurstLeft = Rng.FRandRange(1.f, 3.f) * (0.25f + 0.75f * Energy);
				BurstHz = Rng.FRandRange(6.f, 11.f) * (0.45f + 0.55f * Energy);
				BurstAmp = Rng.FRandRange(28.f, 45.f);
			}
		}
	}
	Swing += NudgeAmp * FMath::Sin(Age * 40.f);
	return FVector2D(Swing, Roll);
}
