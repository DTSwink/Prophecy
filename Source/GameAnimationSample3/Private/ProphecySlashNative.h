// Included in the locomotion implementation's private maths namespace.
// Slash2 v3: unchanged float32 neural layers, native coordinate/pin/FK work.
class FSlashNative
{
public:
	int32 InputBatchSize = 1;
	bool Initialize(const FString& Directory, const TSharedPtr<FJsonObject>& Contract, bool bGpu = false, const FString& AuditGeometryPath = FString());
	bool SetBatch(int32 Count);
	bool Run(TArray<float>& Input, TArray<float>& Output);
	TArray<float> StartupExpected;
	// Kept here for opt-in numerical audits; production adds no trace collection.
	TArray<float> NetworkInputs[3], NetworkOutputs[3];
private:
	struct FPose { FVector3f P[25]; FMat3f R[25]; };
	struct FWork
	{
		FMat3f Heading;
		FVector3f Origin;
		float PrevLower[41], CurLower[41], PrevUpper[90], CurUpper[90];
		float Frozen[41], NextLower[41], NextUpper[90], BaseUpper[90];
		FPose FrozenPose;
		float Pins[2];
	};
	struct FLimb
	{
		int32 Start = 0, Mid = 0, End = 0, Toe = INDEX_NONE, StateOffset = 0;
		FVector3f Pole[2], ToeOffset, ToeAxis;
	};
	FPolicyModel Models[3];
	TStrongObjectPtr<UNNEModelData> ModelData[3];
	TArray<FWork> Work;
	FMat3f RootRotation;
	FVector3f RootPosition, FootHalf, ToeHalf;
	FVector3f LowerOffsets[25], FullOffsets[25], RestOffsets[25];
	int32 Parents[25], CoreSlots[25];
	FLimb Legs[2], Arms[2];
	float RootFeatures[35], DeltaScale = 1, SoleOffset = 0, Ground = 0, GateThreshold = 0.6f;

	static FVector3f Read(const float* V, int32 O = 0) { return FVector3f(V[O], V[O+1], V[O+2]); }
	static void Write(float* V, int32 O, const FVector3f& P) { V[O]=P.X; V[O+1]=P.Y; V[O+2]=P.Z; }
	static void Clean(float* V, bool bUpper)
	{
		if (bUpper)
		{
			for (int32 I=0; I<60; I+=6) WriteRot6(MatrixFromRot6(V+I), V+I);
			for (int32 I : {63,69,78,84}) WriteRot6(MatrixFromRot6(V+I), V+I);
		}
		else
		{
			for (int32 I : {3,12,18,28,34}) WriteRot6(MatrixFromRot6(V+I), V+I);
			V[24]=FMath::Clamp(V[24],-1.f,1.f); V[40]=FMath::Clamp(V[40],-1.f,1.f);
		}
	}
	static void Rebase(const float* In, float* Out, bool bUpper, const FVector3f& FromP,
		const FMat3f& FromR, const FVector3f& ToP, const FMat3f& ToR);
	FFootAxes Axes(int32 Leg, const FVector3f& P, const FMat3f& R, float Toe) const;
	float Lowest(int32 Leg, const FVector3f& P, const FMat3f& R, float Toe) const;
	void Pin(float* Candidate, const float* Current, const float* Pins) const;
	void FrozenUpper(const float* Lower, FPose& Pose, float* Upper) const;
	void SolveLimb(FPose& Pose, const FLimb& Limb, const FVector3f* Offsets, const float* State) const;
	void RawUpper(const float* Lower, const float* Upper, FPose& Pose) const;
	void Finish(FWork& W, const float* State, const float* NeuralUpper, float* Out) const;
};
