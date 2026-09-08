namespace
{
bool FSlashNative::Initialize(const FString& Directory, const TSharedPtr<FJsonObject>& Contract, bool bGpu, const FString& AuditGeometryPath)
{
	FString Text;
	TSharedPtr<FJsonObject> C;
	if (!FFileHelper::LoadFileToString(Text, *(AuditGeometryPath.IsEmpty() ? Directory / TEXT("prophecy_slash_native.json") : AuditGeometryPath)) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), C) || !C.IsValid()) return false;
	// Fail closed if a future export changes a currently-pruned semantic branch.
	if (C->GetStringField(TEXT("checkpoint_sha256")) != Contract->GetStringField(TEXT("checkpoint_sha256")) ||
		C->GetBoolField(TEXT("clamp_reach")) || C->GetNumberField(TEXT("fake_gravity")) != 0 ||
		C->GetBoolField(TEXT("frozen_height_gate")) || C->GetIntegerField(TEXT("pin_up_axis")) != 2 ||
		C->GetIntegerField(TEXT("foot_roll_steps")) != 4 ||
		C->GetStringField(TEXT("frozen_pin_mode")) != TEXT("legacy_logit_selected")) return false;
	JsonFloatArray(C->GetArrayField(TEXT("startup_expected")), StartupExpected);
	JsonVec3(C->GetArrayField(TEXT("root_position")), RootPosition);
	for (int32 I=0; I<3; ++I) JsonVec3(C->GetArrayField(TEXT("root_rotation"))[I]->AsArray(), RootRotation.Rows[I]);
	JsonVec3(C->GetArrayField(TEXT("foot_half_dims")), FootHalf);
	JsonVec3(C->GetArrayField(TEXT("toe_half_dims")), ToeHalf);
	SoleOffset=C->GetNumberField(TEXT("sole_offset")); Ground=C->GetNumberField(TEXT("ground"));
	DeltaScale=C->GetNumberField(TEXT("pose_delta_scale")); GateThreshold=Contract->GetNumberField(TEXT("gate_threshold"));
	const auto& Features=C->GetArrayField(TEXT("root_features"));
	if (Features.Num()!=35 || StartupExpected.Num()!=437) return false;
	for (int32 I=0; I<35; ++I) RootFeatures[I]=Features[I]->AsNumber();
	const auto& Lower=C->GetObjectField(TEXT("lower_geometry"));
	const auto& Full=C->GetObjectField(TEXT("full_geometry"));
	const auto& Names=C->GetArrayField(TEXT("bone_names"));
	if (Names.Num()!=25) return false;
	for (int32 I=0; I<25; ++I)
	{
		Parents[I]=C->GetArrayField(TEXT("parents"))[I]->AsNumber(); CoreSlots[I]=INDEX_NONE;
		JsonVec3(Lower->GetArrayField(TEXT("local_offsets"))[I]->AsArray(), LowerOffsets[I]);
		JsonVec3(Full->GetArrayField(TEXT("local_offsets"))[I]->AsArray(), FullOffsets[I]);
		JsonVec3(Lower->GetArrayField(TEXT("slash_rest_offsets_from_pelvis"))[I]->AsArray(), RestOffsets[I]);
		const auto& Core=C->GetArrayField(TEXT("core_bones"));
		for (int32 J=0; J<Core.Num(); ++J) if (Core[J]->AsString()==Names[I]->AsString()) CoreSlots[I]=J;
	}
	auto LoadLimb=[](FLimb& L, const TSharedPtr<FJsonObject>& Spec, const TSharedPtr<FJsonObject>& G, int32 I)
	{
		L.Start=Spec->GetIntegerField(TEXT("start")); L.Mid=Spec->GetIntegerField(TEXT("mid")); L.End=Spec->GetIntegerField(TEXT("end"));
		L.Toe=Spec->Values.FindChecked(TEXT("toe"))->IsNull() ? INDEX_NONE : Spec->GetIntegerField(TEXT("toe"));
		for (int32 J=0; J<2; ++J) JsonVec3(G->GetArrayField(TEXT("ik_local_pole_axis"))[I]->AsArray()[J]->AsArray(), L.Pole[J]);
		JsonVec3(G->GetArrayField(TEXT("ik_toe_offsets"))[I]->AsArray(), L.ToeOffset);
		JsonVec3(G->GetArrayField(TEXT("ik_toe_axis"))[I]->AsArray(), L.ToeAxis);
	};
	for (int32 I=0; I<2; ++I)
	{
		LoadLimb(Legs[I], C->GetArrayField(TEXT("lower_limbs"))[I]->AsObject(), Lower, I); Legs[I].StateOffset=9+16*I;
		LoadLimb(Arms[I], C->GetArrayField(TEXT("full_limbs"))[I]->AsObject(), Full, I); Arms[I].StateOffset=60+15*I;
	}
	FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));
	const TCHAR* Keys[]={TEXT("frozen"),TEXT("lower"),TEXT("upper")};
	for (int32 I=0; I<3; ++I)
	{
		const auto& N=C->GetObjectField(TEXT("networks"))->GetObjectField(Keys[I]);
		TArray64<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *(Directory / N->GetStringField(TEXT("file"))))) return false;
		ModelData[I].Reset(NewObject<UNNEModelData>());
		ModelData[I]->Init(TEXT("onnx"), TConstArrayView64<uint8>(Bytes.GetData(), Bytes.Num()));
		Models[I].InputWidth=N->GetIntegerField(TEXT("input_dim")); Models[I].InputBatchSize=InputBatchSize;
		if (bGpu ? !Models[I].CreateGpu(ModelData[I].Get(), TEXT("NNERuntimeORTDml")) :
			!Models[I].CreateCpu(ModelData[I].Get(), TEXT("NNERuntimeORTCpu"))) return false;
	}
	return SetBatch(InputBatchSize);
}

bool FSlashNative::SetBatch(int32 Count)
{
	if (Count<1 || Count>100) return false;
	const int32 InWidths[]={152,92,217}, OutWidths[]={43,43,92};
	for (int32 I=0; I<3; ++I)
	{
		if (!Models[I].ResizeBatch(Count)) return false;
		NetworkInputs[I].SetNumUninitialized(Count*InWidths[I]);
		NetworkOutputs[I].SetNumUninitialized(Count*OutWidths[I]);
	}
	Work.SetNum(Count); InputBatchSize=Count;
	return true;
}

void FSlashNative::Rebase(const float* In, float* Out, bool bUpper, const FVector3f& FromP,
	const FMat3f& FromR, const FVector3f& ToP, const FMat3f& ToR)
{
	FMemory::Memcpy(Out,In,(bUpper?90:41)*sizeof(float)); Clean(Out,bUpper);
	const FMat3f Inv=Transpose(ToR);
	if (bUpper)
	{
		for (int32 I : {60,75})
		{
			Write(Out,I,TransformRow(TransformRow(Read(Out,I),FromR)+FromP-ToP,Inv));
			for (int32 J : {3,9}) WriteRot6(Multiply(Multiply(MatrixFromRot6(Out+I+J),FromR),Inv),Out+I+J);
		}
	}
	else
	{
		for (int32 I : {0,9,25}) Write(Out,I,TransformRow(TransformRow(Read(Out,I),FromR)+FromP-ToP,Inv));
		for (int32 I : {3,12,18,28,34}) WriteRot6(Multiply(Multiply(MatrixFromRot6(Out+I),FromR),Inv),Out+I);
		// The source codec cleans limb rotations again after the frame change.
		for (int32 I : {12,18,28,34}) WriteRot6(MatrixFromRot6(Out+I),Out+I);
	}
}

FFootAxes FSlashNative::Axes(int32 Leg, const FVector3f& P, const FMat3f& R, float Toe) const
{
	const FLimb& L=Legs[Leg];
	const FVector3f V=TransformRow(L.ToeOffset,R), TP=P+V;
	FVector3f U=R.Rows[0], F=R.Rows[1]; const FVector3f S=R.Rows[2];
	if (FVector3f::DotProduct(F,V)<0) F*=-1; if (U.Z<0) U*=-1;
	const FMat3f TR=Multiply(AxisAngleMatrix(L.ToeAxis,FMath::Clamp(Toe,-1.f,1.f)*ToeAlphaRadians),R);
	FVector3f TF=TR.Rows[0], TU=TR.Rows[1]; const FVector3f TS=TR.Rows[2];
	if (FVector3f::DotProduct(TF,V)<0) TF*=-1; if (TU.Z<0) TU*=-1;
	return {TP-F*FootHalf.X+U*SoleOffset,F,S,U,TP+TF*ToeHalf.X+TU*SoleOffset,TF,TS,TU};
}

float FSlashNative::Lowest(int32 Leg,const FVector3f& P,const FMat3f& R,float Toe) const
{
	const auto A=Axes(Leg,P,R,Toe); const float Blend=FMath::DegreesToRadians(8.f);
	return FMath::Min(BoxContact(A.FootCenter,A.FootForward,A.FootSide,A.FootUp,FootHalf,Blend).Z,
		BoxContact(A.ToeCenter,A.ToeForward,A.ToeSide,A.ToeUp,ToeHalf,Blend).Z);
}

void FSlashNative::Pin(float* Candidate,const float* Current,const float* Pins) const
{
	Clean(Candidate,false);
	for (int32 Leg=0; Leg<2; ++Leg)
	{
		const int32 O=9+16*Leg;
		FVector3f P=Read(Candidate,O); const FMat3f R=MatrixFromRot6(Candidate+O+3); const float Toe=Candidate[O+15];
		if (Pins[Leg]>0)
		{
			const FMat3f CR=MatrixFromRot6(Current+O+3); const float CT=FMath::Clamp(Current[O+15],-1.f,1.f);
			const FVector3f RV=RotationVectorBetween(CR,R); const float Angle=RV.Size(); const FVector3f Axis=SafeNormal(RV);
			FMat3f PrevR=CR; float PrevToe=CT; FVector3f Delta=FVector3f::ZeroVector;
			for (int32 Step=1; Step<=4; ++Step)
			{
				const float T=float(Step)*0.25f; const FMat3f SR=Multiply(AxisAngleMatrix(Axis,Angle*T),CR);
				const float ST=CT+(Toe-CT)*T; const auto N=Axes(Leg,FVector3f::ZeroVector,SR,ST);
				const auto B=Axes(Leg,FVector3f::ZeroVector,PrevR,PrevToe); FVector3f FS,TS;
				const auto FP=BoxContact(N.FootCenter,N.FootForward,N.FootSide,N.FootUp,FootHalf,FMath::DegreesToRadians(8.f),&FS);
				const auto TP=BoxContact(N.ToeCenter,N.ToeForward,N.ToeSide,N.ToeUp,ToeHalf,FMath::DegreesToRadians(8.f),&TS);
				Delta+=TP.Z<FP.Z ? BoxPointWithSupport(B.ToeCenter,B.ToeForward,B.ToeSide,B.ToeUp,TS)-TP :
					BoxPointWithSupport(B.FootCenter,B.FootForward,B.FootSide,B.FootUp,FS)-FP;
				PrevR=SR; PrevToe=ST;
			}
			const FVector3f CP=Read(Current,O);
			P+=Pins[Leg]*(FVector3f(CP.X+Delta.X,CP.Y+Delta.Y,P.Z)-P);
		}
		P.Z+=FMath::Max(0.f,Ground-Lowest(Leg,P,R,Toe)); Write(Candidate,O,P);
	}
}

void FSlashNative::FrozenUpper(const float* Lower,FPose& Pose,float* Upper) const
{
	const FMat3f PR=Multiply(MatrixFromRot6(Lower+3),RootRotation);
	const FVector3f PP=TransformRow(Read(Lower),RootRotation)+RootPosition;
	for (int32 I=0; I<25; ++I) { Pose.P[I]=TransformRow(RestOffsets[I],PR)+PP; Pose.R[I]=PR; }
	for (int32 I=0; I<25; ++I) if (CoreSlots[I]!=INDEX_NONE)
		WriteRot6(Multiply(Pose.R[I],Transpose(Pose.R[Parents[I]])),Upper+CoreSlots[I]*6);
	for (int32 I=0; I<2; ++I)
	{
		const auto& A=Arms[I]; const int32 O=A.StateOffset;
		Write(Upper,O,TransformRow(Pose.P[A.End]-RootPosition,Transpose(RootRotation)));
		WriteRot6(Multiply(Pose.R[A.End],Transpose(RootRotation)),Upper+O+3);
		WriteRot6(Multiply(Pose.R[A.Start],Transpose(RootRotation)),Upper+O+9);
	}
	Clean(Upper,true);
}

void FSlashNative::SolveLimb(FPose& Pose,const FLimb& L,const FVector3f* Offsets,const float* State) const
{
	const int32 O=L.StateOffset;
	const FMat3f SR=Multiply(MatrixFromRot6(State+O+9),RootRotation);
	const FMat3f ER=MatrixFromRot6(State+O+3);
	const FVector3f EndRoot=Read(State,O);
	Pose.R[L.Start]=SR; Pose.P[L.Mid]=Pose.P[L.Start]+TransformRow(Offsets[L.Mid],SR);
	Pose.P[L.End]=TransformRow(EndRoot,RootRotation)+RootPosition;
	FVector3f Axis=Pose.P[L.End]-Pose.P[L.Mid];
	if (Axis.SizeSquared()<=1.e-16f) Axis=TransformRow(Offsets[L.End],SR);
	// ik_core's modified Gram-Schmidt basis (do not change the unrelated
	// locomotion decoder while porting the accepted Slash decoder).
	auto Normalize=[](const FVector3f& V) { return V/FMath::Max(V.Size(),1.e-8f); };
	auto Plane=[&](const FVector3f& V,const FVector3f& N) { const auto Unit=Normalize(N); return Normalize(V-Unit*FVector3f::DotProduct(V,Unit)); };
	auto Basis=[&](const FVector3f& Main,const FVector3f& Pole)
	{
		const FVector3f Side=Plane(Pole,Main); FVector3f Up=FVector3f::CrossProduct(Main,Side);
		if (Up.SizeSquared()<=1.e-16f) Up=FVector3f::CrossProduct(Main,StablePerpendicular(Main));
		Up=Normalize(Up); FMat3f B; B.Rows[0]=Main; B.Rows[1]=Normalize(FVector3f::CrossProduct(Up,Main)); B.Rows[2]=Up; return B;
	};
	Pose.R[L.Mid]=Multiply(Transpose(Basis(Normalize(Offsets[L.End]),L.Pole[1])),Basis(Normalize(Axis),TransformRow(L.Pole[0],SR)));
	// Frozen lower FK uses ik_core's calf hemisphere rule. Full decoder leg
	// deltas cancel, so its unchanged final legs are this exact frozen result.
	if (L.Toe!=INDEX_NONE && FVector3f::DotProduct(Pose.R[L.Mid].Rows[2],SR.Rows[2])<0)
	{
		const FVector3f Unit=Normalize(Axis), Calf=Plane(Pose.R[L.Mid].Rows[2],Unit), Thigh=Plane(SR.Rows[2],Unit);
		const float Twist=FMath::Atan2(FVector3f::DotProduct(FVector3f::CrossProduct(Calf,Thigh),Unit),FVector3f::DotProduct(Calf,Thigh));
		for (auto& Row:Pose.R[L.Mid].Rows) Row=RotateAroundAxis(Row,Unit,Twist);
	}
	Pose.R[L.End]=Multiply(ER,RootRotation);
	if (L.Toe!=INDEX_NONE)
	{
		Pose.P[L.Toe]=TransformRow(EndRoot+TransformRow(L.ToeOffset,ER),RootRotation)+RootPosition;
		Pose.R[L.Toe]=Multiply(Multiply(AxisAngleMatrix(L.ToeAxis,FMath::Clamp(State[O+15],-1.f,1.f)*ToeAlphaRadians),ER),RootRotation);
	}
}

void FSlashNative::RawUpper(const float* Lower,const float* Upper,FPose& Pose) const
{
	Pose.P[0]=TransformRow(Read(Lower),RootRotation)+RootPosition;
	Pose.R[0]=Multiply(MatrixFromRot6(Lower+3),RootRotation);
	for (int32 I=1; I<17; ++I)
	{
		if (CoreSlots[I]==INDEX_NONE) continue;
		const int32 P=Parents[I]; Pose.P[I]=Pose.P[P]+TransformRow(FullOffsets[I],Pose.R[P]);
		Pose.R[I]=Multiply(MatrixFromRot6(Upper+CoreSlots[I]*6),Pose.R[P]);
	}
	for (const auto& A:Arms)
	{
		const int32 P=Parents[A.Start]; Pose.P[A.Start]=Pose.P[P]+TransformRow(FullOffsets[A.Start],Pose.R[P]);
		SolveLimb(Pose,A,FullOffsets,Upper);
	}
}

void FSlashNative::Finish(FWork& W,const float* State,const float* NeuralUpper,float* Out) const
{
	for (int32 I=0; I<90; ++I) W.NextUpper[I]+=NeuralUpper[I]; Clean(W.NextUpper,true);
	Rebase(W.NextLower,Out,false,W.Origin,W.Heading,RootPosition,RootRotation);
	Rebase(W.NextUpper,Out+41,true,W.Origin,W.Heading,RootPosition,RootRotation);
	// Only upper FK differs between the decoder baseline and candidate. Solve
	// the legs once, not in all three full-skeleton FK passes of the oracle.
	for (const auto& L:Legs) SolveLimb(W.FrozenPose,L,LowerOffsets,Out);
	FPose Base,Candidate; RawUpper(Out,W.BaseUpper,Base); RawUpper(Out,Out+41,Candidate);
	for (int32 I=0; I<25; ++I)
	{
		const FVector3f P=I<17 ? W.FrozenPose.P[I]+(Candidate.P[I]-Base.P[I]) : W.FrozenPose.P[I];
		const FMat3f R=I<17 ? Multiply(Multiply(Candidate.R[I],Transpose(Base.R[I])),W.FrozenPose.R[I]) : W.FrozenPose.R[I];
		Write(Out,131+I*3,P); for (int32 Row=0; Row<3; ++Row) Write(Out,206+I*9+Row*3,R.Rows[Row]);
	}
	// Match advance_phase_latches: a hit request while unarmed arms this
	// frame. It may become a hit only on a later step whose input was armed.
	const bool bHitRequest=NeuralUpper[91]>=GateThreshold;
	Out[432]=State[271]>=0.5f || (State[270]>=0.5f && bHitRequest) ? 1.f:0.f;
	Out[431]=State[270]>=0.5f || Out[432]>=0.5f || NeuralUpper[90]>=GateThreshold || bHitRequest ? 1.f:0.f;
	Out[433]=NeuralUpper[90]; Out[434]=NeuralUpper[91]; Out[435]=W.Pins[0]; Out[436]=W.Pins[1];
}

bool FSlashNative::Run(TArray<float>& Input,TArray<float>& Output)
{
	if (Input.Num()!=InputBatchSize*272) return false;
	Output.SetNumUninitialized(InputBatchSize*437);
	for (int32 Lane=0; Lane<InputBatchSize; ++Lane)
	{
		const float* S=Input.GetData()+272*Lane; auto& W=Work[Lane];
		const FVector3f Target=Read(S,262), Pelvis=TransformRow(Read(S,41),RootRotation)+RootPosition;
		const FVector3f D=Target-Pelvis;
		if (D.X*D.X+D.Z*D.Z<=1.e-10f) return false;
		W.Heading=YawMatrix(-FMath::Atan2(D.X,D.Z)); W.Origin=FVector3f(Target.X,0,Target.Z);
		Rebase(S,W.PrevLower,false,RootPosition,RootRotation,W.Origin,W.Heading);
		Rebase(S+41,W.CurLower,false,RootPosition,RootRotation,W.Origin,W.Heading);
		Rebase(S+82,W.PrevUpper,true,RootPosition,RootRotation,W.Origin,W.Heading);
		Rebase(S+172,W.CurUpper,true,RootPosition,RootRotation,W.Origin,W.Heading);
		float* N=NetworkInputs[0].GetData()+152*Lane;
		FMemory::Memcpy(N,S+41,41*sizeof(float)); FMemory::Memcpy(N+41,S,41*sizeof(float));
		for (int32 I=0; I<3; ++I) N[82+I]=(S[41+I]-S[I])/DeltaScale;
		for (int32 I=9; I<41; ++I) N[85+I-9]=(S[41+I]-S[I])/DeltaScale;
		FMemory::Memcpy(N+117,RootFeatures,35*sizeof(float));
	}
	if (!Models[0].Run(NetworkInputs[0],NetworkOutputs[0])) return false;
	for (int32 Lane=0; Lane<InputBatchSize; ++Lane)
	{
		const float* S=Input.GetData()+272*Lane; auto& W=Work[Lane];
		const float* R=NetworkOutputs[0].GetData()+43*Lane;
		for (int32 I=0; I<41; ++I) W.Frozen[I]=S[41+I]+R[I];
		const bool Both=R[41]<0 && R[42]<0;
		const float Pins[]={Both||R[41]<=R[42]?1.f:0.f,Both||R[42]<R[41]?1.f:0.f};
		Pin(W.Frozen,S+41,Pins);
		float* N=NetworkInputs[1].GetData()+92*Lane;
		FMemory::Memcpy(N,W.CurLower,41*sizeof(float));
		Rebase(W.Frozen,N+41,false,RootPosition,RootRotation,W.Origin,W.Heading);
		FMemory::Memcpy(N+82,S+265,5*sizeof(float)); N[87]=N[88]=N[90]=N[91]=0; N[89]=S[263];
	}
	if (!Models[1].Run(NetworkInputs[1],NetworkOutputs[1])) return false;
	for (int32 Lane=0; Lane<InputBatchSize; ++Lane)
	{
		const float* S=Input.GetData()+272*Lane; auto& W=Work[Lane];
		const float* R=NetworkOutputs[1].GetData()+43*Lane;
		const float* FrozenHeld=NetworkInputs[1].GetData()+92*Lane+41;
		float Candidate[41],Root[41];
		for (int32 I=0; I<41; ++I) Candidate[I]=FrozenHeld[I]+R[I];
		Rebase(Candidate,Root,false,W.Origin,W.Heading,RootPosition,RootRotation);
		for (int32 I=0; I<2; ++I) W.Pins[I]=FMath::Clamp(2.f/(1.f+FMath::Exp(-R[41+I]))-1.f,0.f,1.f);
		Pin(Root,S+41,W.Pins);
		Rebase(Root,W.NextLower,false,RootPosition,RootRotation,W.Origin,W.Heading);
		float CurrentBase[90],CurrentHeld[90],NextHeld[90]; FPose CurrentPose;
		FrozenUpper(S+41,CurrentPose,CurrentBase); FrozenUpper(Root,W.FrozenPose,W.BaseUpper);
		Rebase(CurrentBase,CurrentHeld,true,RootPosition,RootRotation,W.Origin,W.Heading);
		Rebase(W.BaseUpper,NextHeld,true,RootPosition,RootRotation,W.Origin,W.Heading);
		for (int32 I=0; I<90; ++I) W.NextUpper[I]=NextHeld[I]+(W.CurUpper[I]-CurrentHeld[I]); Clean(W.NextUpper,true);
		float* N=NetworkInputs[2].GetData()+217*Lane;
		FMemory::Memcpy(N,W.PrevUpper,90*sizeof(float)); FMemory::Memcpy(N+90,W.NextUpper,90*sizeof(float));
		N[180]=S[263]; FMemory::Memcpy(N+181,S+265,5*sizeof(float));
		FMemory::Memcpy(N+186,W.PrevLower,9*sizeof(float)); FMemory::Memcpy(N+195,W.CurLower,9*sizeof(float));
		FMemory::Memcpy(N+204,W.NextLower,9*sizeof(float)); N[213]=S[270]; N[214]=S[271]; N[215]=N[216]=0;
	}
	if (!Models[2].Run(NetworkInputs[2],NetworkOutputs[2])) return false;
	for (int32 Lane=0; Lane<InputBatchSize; ++Lane)
		Finish(Work[Lane],Input.GetData()+272*Lane,NetworkOutputs[2].GetData()+92*Lane,Output.GetData()+437*Lane);
	return true;
}
}
