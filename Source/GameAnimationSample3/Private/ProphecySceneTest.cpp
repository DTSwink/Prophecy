#include "ProphecySceneTest.h"
#include "ProphecyJoltSkeletalPropComponent.h"
#include "ProphecyNoose.h"
#include "ProphecyPotenceRope.h"
#include "ProphecyJoltStaticMeshLibrary.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "PhysicsEngine/BodyInstance.h"
#include "RHI.h"
#include "RenderCore.h"
#include "ShaderCompiler.h"
#include "UnrealClient.h"

bool UProphecySceneTestSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	FString Script;
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld() && FParse::Value(FCommandLine::Get(), TEXT("SceneTest="), Script);
}

void UProphecySceneTestSubsystem::OnWorldBeginPlay(UWorld& World)
{
	Super::OnWorldBeginPlay(World);
	FString Script;
	if (!FParse::Value(FCommandLine::Get(), TEXT("SceneTest="), Script)) return;
	FActorSpawnParameters P;
	P.ObjectFlags |= RF_Transient;
	if (auto* D = World.SpawnActor<AProphecySceneTestDirector>(FVector::ZeroVector, FRotator::ZeroRotator, P)) D->ScriptPath = Script;
}

AProphecySceneTestDirector::AProphecySceneTestDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void AProphecySceneTestDirector::Log(const FString& Line)
{
	UE_LOG(LogTemp, Display, TEXT("SCENETEST %s"), *Line);
	Report += Line + TEXT("\n");
	FFileHelper::SaveStringToFile(Report, *(OutDir / TEXT("report.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void AProphecySceneTestDirector::OnShot(int32 W, int32 H, const TArray<FColor>& Colors)
{
	if (Colors.Num() != W * H) return;
	IImageWrapperModule& M = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	TSharedPtr<IImageWrapper> Img = M.CreateImageWrapper(EImageFormat::JPEG);
	if (!Img.IsValid()) return;
	TArray<FColor> Opaque = Colors;
	for (FColor& C : Opaque) C.A = 255;
	Img->SetRaw(Opaque.GetData(), Opaque.Num() * sizeof(FColor), W, H, ERGBFormat::BGRA, 8);
	const FString Name = PendingName.IsEmpty() ? FString::Printf(TEXT("frame_%05d.jpg"), FrameIndex++) : PendingName + TEXT(".jpg");
	FFileHelper::SaveArrayToFile(Img->GetCompressed(PendingName.IsEmpty() ? 90 : 95), *(OutDir / Name));
	PendingName.Reset();
}

void AProphecySceneTestDirector::BeginPlay()
{
	Super::BeginPlay();
	FString Out;
	OutDir = FParse::Value(FCommandLine::Get(), TEXT("SceneTestOut="), Out) ? Out : FPaths::ProjectSavedDir() / TEXT("SceneTest");
	IFileManager::Get().MakeDirectory(*OutDir, true);
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *ScriptPath)) { Log(FString::Printf(TEXT("cannot read script %s"), *ScriptPath)); return; }
	TArray<FString> Lines; Text.ParseIntoArrayLines(Lines);
	for (FString L : Lines)
	{
		L.TrimStartAndEndInline();
		if (L.IsEmpty() || L.StartsWith(TEXT("#"))) continue;
		TArray<FString> W; L.ParseIntoArrayWS(W);
		const FString Op = W[0].ToLower();
		auto Num = [&](int32 I, double Default = 0) { return W.IsValidIndex(I) ? FCString::Atod(*W[I]) : Default; };
		if (Op == TEXT("anchor") && W.Num() > 1) AnchorClass = W[1];
		else if (Op == TEXT("cam") && W.Num() >= 9)
		{
			FCamKey K; K.T = Num(1);
			K.Loc = FVector(Num(2), Num(3), Num(4)); K.Target = FVector(Num(5), Num(6), Num(7)); K.Fov = float(Num(8, 50));
			K.bCut = !(W.IsValidIndex(9) && W[9].ToLower() == TEXT("blend"));
			Cams.Add(K);
		}
		else if (Op == TEXT("orbit") && W.Num() >= 6)
		{
			FOrbit O; O.T0 = Num(1); O.T1 = Num(2); O.Radius = Num(3, 80); O.Elevation = Num(4, 15); O.Fov = Num(5, 45); O.Turns = Num(6, 1);
			Orbits.Add(O);
		}
		else if (Op == TEXT("record")) { RecordFrom = Num(1); RecordTo = Num(2); RecordEvery = FMath::Max(1, int32(Num(3, 2))); }
		else if (Op == TEXT("probe")) ProbeEvery = Num(1, .5);
		else if (Op == TEXT("hold") && W.Num() > 1) HoldLabels.Add(W[1]);
		else if (Op == TEXT("focus") && W.Num() > 1) FocusLabel = W[1];
		else if (Op == TEXT("ramp") && W.Num() >= 6) { FRamp R; R.T0 = Num(1); R.T1 = Num(2); R.Fn = W[3]; R.From = Num(4); R.To = Num(5); Ramps.Add(R); }
		else { FCmd C; C.Op = Op; C.T = Num(1); for (int32 I = 2; I < W.Num(); ++I) C.Args.Add(W[I]); Cmds.Add(C); }
	}
	Cams.Sort([](const FCamKey& A, const FCamKey& B) { return A.T < B.T; });
	FActorSpawnParameters P;
	Cam = GetWorld()->SpawnActor<ACameraActor>(FVector(0, 0, 300), FRotator::ZeroRotator, P);
	Cam->GetCameraComponent()->bConstrainAspectRatio = false;
	auto& PP = Cam->GetCameraComponent()->PostProcessSettings;
	PP.bOverride_AutoExposureSpeedUp = true; PP.AutoExposureSpeedUp = 6.f;
	PP.bOverride_AutoExposureSpeedDown = true; PP.AutoExposureSpeedDown = 6.f;
	PP.bOverride_MotionBlurAmount = true; PP.MotionBlurAmount = 0.f;
	ShotHandle = UGameViewportClient::OnScreenshotCaptured().AddUObject(this, &AProphecySceneTestDirector::OnShot);
	Log(FString::Printf(TEXT("script=%s out=%s commands=%d cams=%d"), *ScriptPath, *OutDir, Cmds.Num(), Cams.Num()));
}

void AProphecySceneTestDirector::EndPlay(const EEndPlayReason::Type Reason)
{
	if (ShotHandle.IsValid()) UGameViewportClient::OnScreenshotCaptured().Remove(ShotHandle);
	Super::EndPlay(Reason);
}

FTransform AProphecySceneTestDirector::Frame() const
{
	return Anchor ? FTransform(Anchor->GetActorQuat(), Anchor->GetActorLocation()) : FTransform::Identity;
}

USkeletalMeshComponent* AProphecySceneTestDirector::Rope() const
{
	return Anchor ? Anchor->FindComponentByClass<USkeletalMeshComponent>() : nullptr;
}

bool AProphecySceneTestDirector::BodyPose(USkeletalMeshComponent* Mesh, FName Bone, FVector& Pos, FVector& Vel) const
{
	if (!Mesh) return false;
	if (const auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Mesh); Prop && Prop->IsJoltStepClientActive())
	{
		FProphecyJoltBodyHandle H;
		const auto* Native = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
		FProphecyJoltBodyState S;
		if (!Native || !Prop->GetBodyHandle(Bone, H) || !Native->ReadBody(H, S).IsSuccess()) return false;
		Pos = S.PositionCm; Vel = S.CenterOfMassVelocityCmPerSecond; return true;
	}
	const FBodyInstance* B = Mesh->GetBodyInstance(Bone);
	if (!B || !B->IsValidBodyInstance()) return false;
	Pos = B->GetUnrealWorldTransform().GetLocation(); Vel = B->GetUnrealWorldVelocity(); return true;
}

AActor* AProphecySceneTestDirector::FindActor(const FString& Label) const
{
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
#if WITH_EDITOR
		if (It->GetActorLabel() == Label) return *It;
#endif
		if (It->GetName() == Label) return *It;
	}
	return nullptr;
}

USkeletalMeshComponent* AProphecySceneTestDirector::MeshOf(const FString& Label) const
{
	AActor* A = FindActor(Label);
	return A ? A->FindComponentByClass<USkeletalMeshComponent>() : nullptr;
}

bool AProphecySceneTestDirector::TieArgs(const FCmd& C, USkeletalMeshComponent*& Mesh, FName& Body, FName& At, float& Clearance) const
{
	// <label> <body bone> <at bone|-> [clearance]
	if (C.Args.Num() < 3) return false;
	Mesh = MeshOf(C.Args[0]);
	Body = FName(*C.Args[1]);
	At = C.Args[2] == TEXT("-") ? NAME_None : FName(*C.Args[2]);
	Clearance = C.Args.IsValidIndex(3) ? FCString::Atof(*C.Args[3]) : .6f;
	return Mesh != nullptr;
}

bool AProphecySceneTestDirector::SetBodyVelocityDelta(USkeletalMeshComponent* Mesh, FName Bone, const FVector& Dv)
{
	const auto* Prop = Mesh ? UProphecyJoltSkeletalPropComponent::Find(Mesh) : nullptr;
	auto* Native = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
	FProphecyJoltBodyHandle H; FProphecyJoltBodyState S;
	return Prop && Prop->IsJoltStepClientActive() && Native && Prop->GetBodyHandle(Bone, H) && Native->ReadBody(H, S).IsSuccess()
		&& Native->SetBodyVelocity(H, S.CenterOfMassVelocityCmPerSecond + Dv, S.AngularVelocityRadiansPerSecond, true).IsSuccess();
}

void AProphecySceneTestDirector::Probe(double T)
{
	USkeletalMeshComponent* M = Rope();
	if (!M) return;
	const FTransform F = Frame();
	double Length = 0; FVector Prev, V, Tip, TipV, Root;
	bool Ok = BodyPose(M, TEXT("joint"), Prev, V); Root = Prev;
	for (int32 I = 1; I <= 27 && Ok; ++I)
	{
		FVector P;
		Ok = BodyPose(M, FName(*FString::Printf(TEXT("joint%d"), I)), P, V);
		Length += FVector::Dist(P, Prev); Prev = P; Tip = P; TipV = V;
	}
	if (!Ok) { Log(FString::Printf(TEXT("PROBE {\"t\":%.2f,\"error\":\"no rope bodies\"}"), T)); return; }
	{
		float Lin = -1, Ang = -1;
		const bool Tied = UProphecyNooseLibrary::GetNooseTieError(M, Lin, Ang);
		FVector PelvisAt = FVector::ZeroVector, PelvisV = FVector::ZeroVector;
		const bool Focus = !FocusLabel.IsEmpty() && BodyPose(MeshOf(FocusLabel), TEXT("pelvis"), PelvisAt, PelvisV);
		if (Tied || Focus)
			Log(FString::Printf(TEXT("HANG {\"t\":%.2f,\"tied\":%d,\"tie_err_cm\":%.3f,\"tie_err_deg\":%.3f,\"pelvis_local\":\"%s\",\"pelvis_speed\":%.1f,\"reel\":%.3f}"),
				T, Tied, Lin, Ang, *Frame().InverseTransformPosition(PelvisAt).ToString(), PelvisV.Size(), ProphecyPotenceRope::GetAmount(M)));
	}
	if (RestLength < 0) RestLength = Length;
	const auto* Prop = UProphecyJoltSkeletalPropComponent::Find(M);
	const UStaticMeshComponent* Noose = nullptr;
	TInlineComponentArray<UStaticMeshComponent*> Statics(Anchor);
	for (auto* S : Statics) if (S->GetName() == TEXT("Noose")) Noose = S;
	const FVector NooseAt = Noose ? Noose->GetComponentLocation() : FVector::ZeroVector;
	Log(FString::Printf(TEXT("PROBE {\"t\":%.2f,\"owner\":\"%s\",\"root_local\":\"%s\",\"tip_local\":\"%s\",\"tip_speed\":%.1f,\"chain_cm\":%.2f,\"stretch\":%.4f,")
		TEXT("\"noose_to_tip_cm\":%.2f,\"noose_to_socket_cm\":%.2f,\"noose_sim\":%d,\"gpu_ms\":%.2f,\"game_ms\":%.2f}"),
		T, Prop && Prop->IsJoltStepClientActive() ? TEXT("jolt") : (M->IsSimulatingPhysics(TEXT("joint27")) ? TEXT("chaos") : TEXT("none")),
		*F.InverseTransformPosition(Root).ToString(), *F.InverseTransformPosition(Tip).ToString(), TipV.Size(), Length, Length / FMath::Max(RestLength, 1.0),
		Noose ? FVector::Dist(NooseAt, Tip) : -1.0, Noose ? FVector::Dist(NooseAt, M->GetSocketLocation(TEXT("joint27"))) : -1.0,
		Noose && Noose->IsSimulatingPhysics(), FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles()), FPlatformTime::ToMilliseconds(GGameThreadTime)));
}

void AProphecySceneTestDirector::Call(const FString& Function, double Value, bool bLog)
{
	UFunction* Fn = Anchor ? Anchor->FindFunction(FName(*Function)) : nullptr;
	if (!Fn) { if (bLog) Log(FString::Printf(TEXT("call %s: no such function"), *Function)); return; }
	uint8* Params = (uint8*)FMemory_Alloca(FMath::Max<int32>(Fn->ParmsSize, 1));
	FMemory::Memzero(Params, Fn->ParmsSize);
	for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It) It->InitializeValue_InContainer(Params);
	for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
	{
		if (It->HasAnyPropertyFlags(CPF_OutParm | CPF_ReturnParm)) continue;
		if (auto* Fp = CastField<FFloatProperty>(*It)) { Fp->SetPropertyValue_InContainer(Params, float(Value)); break; }
		if (auto* Dp = CastField<FDoubleProperty>(*It)) { Dp->SetPropertyValue_InContainer(Params, Value); break; }
	}
	Anchor->ProcessEvent(Fn, Params);
	if (Function == TEXT("ShrinkRope")) Amount = Value;
	for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It) It->DestroyValue_InContainer(Params);
	if (bLog) Log(FString::Printf(TEXT("call %s(%g)"), *Function, Value));
}

void AProphecySceneTestDirector::Run(FCmd& C)
{
	C.bDone = true;
	const FTransform F = Frame();
	if (C.Op == TEXT("call") && C.Args.Num() >= 1 && Anchor)
		Call(C.Args[0], C.Args.IsValidIndex(1) ? FCString::Atod(*C.Args[1]) : 0, true);
	else if (C.Op == TEXT("poke") && C.Args.Num() >= 5 && Anchor)
	{
		UPrimitiveComponent* Target = nullptr;
		TInlineComponentArray<UPrimitiveComponent*> Prims(Anchor);
		for (auto* P : Prims) if (P->GetName() == C.Args[0]) Target = P;
		const FName Bone = C.Args[1] == TEXT("-") ? NAME_None : FName(*C.Args[1]);
		const FVector Dv = F.TransformVector(FVector(FCString::Atod(*C.Args[2]), FCString::Atod(*C.Args[3]), FCString::Atod(*C.Args[4])));
		bool Done = false;
		if (auto* Mesh = Cast<USkeletalMeshComponent>(Target))
			if (const auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Mesh); Prop && Prop->IsJoltStepClientActive())
			{
				FProphecyJoltBodyHandle H; FProphecyJoltBodyState S;
				auto* Native = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
				Done = Native && Prop->GetBodyHandle(Bone, H) && Native->ReadBody(H, S).IsSuccess()
					&& Native->SetBodyVelocity(H, S.CenterOfMassVelocityCmPerSecond + Dv, S.AngularVelocityRadiansPerSecond, true).IsSuccess();
			}
		if (!Done && Target && Target->IsSimulatingPhysics(Bone)) { Target->AddImpulse(Dv, Bone, true); Done = true; }
		Log(FString::Printf(TEXT("poke %s.%s dv=%s %s"), *C.Args[0], *C.Args[1], *Dv.ToString(), Done ? TEXT("ok") : TEXT("FAILED")));
	}
	else if (C.Op == TEXT("release") && C.Args.Num() >= 1)
	{
		USkeletalMeshComponent* M = MeshOf(C.Args[0]);
		auto* Prop = M ? UProphecyJoltSkeletalPropComponent::Find(M) : nullptr;
		FString E;
		const bool Ok = Prop && Prop->SetSimulationEnabled(true, E);
		Log(FString::Printf(TEXT("release %s %s %s"), *C.Args[0], Ok ? TEXT("ok") : TEXT("FAILED"), *E));
	}
	else if (C.Op == TEXT("place") && C.Args.Num() >= 7)
	{
		// <label> x y z pitch yaw roll, in the anchor's frame (held props follow their actor)
		AActor* A = FindActor(C.Args[0]);
		const FVector L(FCString::Atod(*C.Args[1]), FCString::Atod(*C.Args[2]), FCString::Atod(*C.Args[3]));
		const FRotator R(FCString::Atod(*C.Args[4]), FCString::Atod(*C.Args[5]), FCString::Atod(*C.Args[6]));
		if (A) A->SetActorLocationAndRotation(F.TransformPosition(L), F.GetRotation() * R.Quaternion(), false, nullptr, ETeleportType::None);
		Log(FString::Printf(TEXT("place %s %s"), *C.Args[0], A ? *A->GetActorLocation().ToString() : TEXT("MISSING")));
	}
	else if ((C.Op == TEXT("align") || C.Op == TEXT("tie")) && Anchor)
	{
		USkeletalMeshComponent* M = nullptr; FName Body, At; float Clear = .6f;
		FString E; FVector Want = FVector::ZeroVector, Tip = FVector::ZeroVector, V;
		if (!TieArgs(C, M, Body, At, Clear)) { Log(FString::Printf(TEXT("%s: bad arguments or missing actor"), *C.Op)); return; }
		if (C.Op == TEXT("align"))
		{
			// Test helper: slide the held actor horizontally so its tie spot sits under the hanging noose.
			const bool Ok = UProphecyNooseLibrary::GetNooseTieTarget(Rope(), M, Body, At, Want, E, Clear) && BodyPose(Rope(), TEXT("joint27"), Tip, V);
			if (Ok) M->GetOwner()->AddActorWorldOffset(FVector(Tip.X - Want.X, Tip.Y - Want.Y, 0), false, nullptr, ETeleportType::None);
			Log(FString::Printf(TEXT("align %s.%s %s dz=%.1f %s"), *C.Args[0], *Body.ToString(), Ok ? TEXT("ok") : TEXT("FAILED"), Ok ? Want.Z - Tip.Z : 0.0, *E));
		}
		else
		{
			const bool Ok = UProphecyNooseLibrary::TieNoose(Rope(), M, Body, At, E, Clear);
			Log(FString::Printf(TEXT("tie %s.%s at %s: %s %s"), *C.Args[0], *Body.ToString(), *At.ToString(), Ok ? TEXT("ok") : TEXT("FAILED"), *E));
		}
	}
	else if (C.Op == TEXT("untie")) Log(FString::Printf(TEXT("untie %d"), UProphecyNooseLibrary::UntieNoose(Rope())));
	else if (C.Op == TEXT("reelto") && C.Args.Num() >= 5 && Anchor)
	{
		// <t1> <label> <body> <at|-> [clearance]: ramp the reel so the rope end reaches the tie height at t1
		FCmd Sub = C; Sub.Args.RemoveAt(0);
		USkeletalMeshComponent* M = nullptr; FName Body, At; float Clear = .6f;
		FString E; FVector Want = FVector::ZeroVector, Tip = FVector::ZeroVector, V; FTransform Anchor0; FVector Dir; float Len = 0;
		const bool Ok = TieArgs(Sub, M, Body, At, Clear) && UProphecyNooseLibrary::GetNooseTieTarget(Rope(), M, Body, At, Want, E, Clear)
			&& BodyPose(Rope(), TEXT("joint27"), Tip, V) && ProphecyPotenceRope::GetReelGeometry(Rope(), Anchor0, Dir, Len) && Len > 1;
		if (Ok)
		{
			FRamp R; R.T0 = C.T; R.T1 = FCString::Atod(*C.Args[0]); R.Fn = TEXT("ShrinkRope"); R.From = Amount;
			R.To = FMath::Clamp(Amount + (Want.Z - Tip.Z) / Len, 0.0, 0.95);
			Ramps.Add(R);
			Log(FString::Printf(TEXT("reelto %.3f -> %.3f (rope end %.1f cm %s)"), R.From, R.To, Want.Z - Tip.Z, Want.Z > Tip.Z ? TEXT("up") : TEXT("down")));
		}
		else Log(FString::Printf(TEXT("reelto FAILED %s"), *E));
	}
	else if (C.Op == TEXT("reelby") && C.Args.Num() >= 2)
	{
		// <t1> <delta>: ramp the reel from its current amount
		FRamp R; R.T0 = C.T; R.T1 = FCString::Atod(*C.Args[0]); R.Fn = TEXT("ShrinkRope"); R.From = Amount;
		R.To = FMath::Clamp(Amount + FCString::Atod(*C.Args[1]), 0.0, 0.95);
		Ramps.Add(R);
		Log(FString::Printf(TEXT("reelby %.3f -> %.3f"), R.From, R.To));
	}
	else if (C.Op == TEXT("pokeactor") && C.Args.Num() >= 5)
	{
		const FVector Dv = F.TransformVector(FVector(FCString::Atod(*C.Args[2]), FCString::Atod(*C.Args[3]), FCString::Atod(*C.Args[4])));
		const bool Ok = SetBodyVelocityDelta(MeshOf(C.Args[0]), FName(*C.Args[1]), Dv);
		Log(FString::Printf(TEXT("pokeactor %s.%s dv=%s %s"), *C.Args[0], *C.Args[1], *Dv.ToString(), Ok ? TEXT("ok") : TEXT("FAILED")));
	}
	else if (C.Op == TEXT("shot") && C.Args.Num() >= 1) { PendingName = C.Args[0]; FScreenshotRequest::RequestScreenshot(false); Log(FString::Printf(TEXT("shot %s t=%.2f"), *C.Args[0], C.T)); }
	else if (C.Op == TEXT("status"))
	{
		USkeletalMeshComponent* M = Rope();
		const auto* Prop = M ? UProphecyJoltSkeletalPropComponent::Find(M) : nullptr;
		UStaticMeshComponent* Noose = nullptr;
		TInlineComponentArray<UStaticMeshComponent*> Statics(Anchor);
		for (auto* S : Statics) if (S->GetName() == TEXT("Noose")) Noose = S;
		Log(FString::Printf(TEXT("status rope=%s class=%s jolt_binding=%d jolt_active=%d chaos_sim=%d root_dynamic=%d noose_sim=%d noose_jolt=%d noose_parent=%s.%s noose_collision=%d"),
			*GetNameSafe(M), M ? *M->GetClass()->GetName() : TEXT("-"), Prop != nullptr, Prop && Prop->IsJoltStepClientActive(),
			M && M->IsSimulatingPhysics(TEXT("joint27")), Prop && Prop->IsBodyDynamic(TEXT("joint")),
			Noose && Noose->IsSimulatingPhysics(), Noose && UProphecyJoltStaticMeshLibrary::IsJoltStaticMeshPhysicsEnabled(Noose),
			Noose ? *GetNameSafe(Noose->GetAttachParent()) : TEXT("-"), Noose ? *Noose->GetAttachSocketName().ToString() : TEXT("-"),
			Noose ? int32(Noose->GetCollisionEnabled()) : -1));
	}
	else if (C.Op == TEXT("exit")) { Log(FString::Printf(TEXT("exit t=%.2f frames=%d"), C.T, FrameIndex)); FGenericPlatformMisc::RequestExit(false, TEXT("SceneTest")); }
	else Log(FString::Printf(TEXT("unknown command %s"), *C.Op));
}

void AProphecySceneTestDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (GetWorld()->IsPaused() || !Cam) return;
	++Tick60;
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (PC && PC->GetViewTarget() != Cam) PC->SetViewTarget(Cam);
	for (int32 I = HoldLabels.Num() - 1; I >= 0; --I)
	{
		// Freeze a placed ragdoll as soon as Jolt admits it: its bodies become kinematic and follow the actor.
		USkeletalMeshComponent* M = MeshOf(HoldLabels[I]);
		auto* Prop = M ? UProphecyJoltSkeletalPropComponent::Find(M) : nullptr;
		if (!Prop || !Prop->IsJoltStepClientActive()) continue;
		FString E;
		const bool Ok = Prop->SetSimulationEnabled(false, E);
		Log(FString::Printf(TEXT("hold %s at tick %lld %s %s"), *HoldLabels[I], Tick60, Ok ? TEXT("ok") : TEXT("FAILED"), *E));
		HoldLabels.RemoveAt(I);
	}
	if (!bStarted)
	{
		const int32 Jobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		if (Jobs > 0 && Tick60 < 60 * 600) { if (Tick60 % 600 == 0) Log(FString::Printf(TEXT("waiting for %d shader jobs"), Jobs)); return; }
		if (Tick60 < 60 * 3) return;
		for (TActorIterator<AActor> It(GetWorld()); It; ++It)
			if (It->GetClass()->GetName().Contains(AnchorClass)) { Anchor = *It; break; }
		if (!Anchor) { Log(FString::Printf(TEXT("no anchor %s - abort"), *AnchorClass)); FGenericPlatformMisc::RequestExit(false, TEXT("SceneTest")); Cam = nullptr; return; }
		Log(FString::Printf(TEXT("anchor %s at %s rot %s"), *Anchor->GetName(), *Anchor->GetActorLocation().ToString(), *Anchor->GetActorRotation().ToString()));
		bStarted = true; StartTick = Tick60;
	}
	const double T = (Tick60 - StartTick) / 60.0;
	if (Cams.Num())
	{
		int32 K = 0;
		while (K + 1 < Cams.Num() && Cams[K + 1].T <= T) ++K;
		FVector L = Cams[K].Loc, Tg = Cams[K].Target; float Fov = Cams[K].Fov;
		if (K + 1 < Cams.Num() && !Cams[K + 1].bCut && Cams[K].T <= T)
		{
			const double A = FMath::Clamp((T - Cams[K].T) / FMath::Max(Cams[K + 1].T - Cams[K].T, 1e-3), 0.0, 1.0);
			const double S = A * A * (3 - 2 * A);
			L = FMath::Lerp(L, Cams[K + 1].Loc, S); Tg = FMath::Lerp(Tg, Cams[K + 1].Target, S); Fov = FMath::Lerp(Fov, Cams[K + 1].Fov, float(S));
		}
		const FTransform F = Frame();
		const FVector WL = F.TransformPosition(L), WT = F.TransformPosition(Tg);
		Cam->SetActorLocationAndRotation(WL, (WT - WL).Rotation());
		Cam->GetCameraComponent()->SetFieldOfView(Fov);
	}
	for (const FOrbit& O : Orbits)
	{
		if (T < O.T0 || T > O.T1 || !Anchor) continue;
		TInlineComponentArray<UProphecyNooseComponent*> Nooses(Anchor);
		if (Nooses.IsEmpty() || !Nooses[0]->IsRegistered()) break;
		const FVector Target = Nooses[0]->Bounds.Origin;
		const double A = 2. * PI * O.Turns * (T - O.T0) / FMath::Max(O.T1 - O.T0, 1e-3) - .5 * PI;
		const double El = FMath::DegreesToRadians(O.Elevation);
		const FVector Ring = Frame().GetRotation().RotateVector(FVector(FMath::Cos(A) * FMath::Cos(El), FMath::Sin(A) * FMath::Cos(El), FMath::Sin(El)));
		const FVector L = Target + Ring * O.Radius;
		Cam->SetActorLocationAndRotation(L, (Target - L).Rotation());
		Cam->GetCameraComponent()->SetFieldOfView(float(O.Fov));
		break;
	}
	for (FCmd& C : Cmds) if (!C.bDone && C.T <= T) Run(C);
	for (const FRamp& R : Ramps)
		if (T >= R.T0 && T <= R.T1 + 1.0 / 60)
		{
			const double A = FMath::Clamp((T - R.T0) / FMath::Max(R.T1 - R.T0, 1e-3), 0.0, 1.0);
			Call(R.Fn, FMath::Lerp(R.From, R.To, A), false);
		}
	if (ProbeEvery > 0 && T >= NextProbe) { Probe(T); NextProbe = T + ProbeEvery; }
	if (RecordFrom >= 0 && T >= RecordFrom && T <= RecordTo && (Tick60 % RecordEvery) == 0 && PendingName.IsEmpty())
		FScreenshotRequest::RequestScreenshot(false);
}
