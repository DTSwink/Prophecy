// On-demand lab checkpoint export; no retained state or runtime polling.
static void ExportReachCheckpoint(UWorld* World)
{
    using namespace ProphecyReach;
    auto Numbers=[](std::initializer_list<double> Values){TArray<TSharedPtr<FJsonValue>> A;for(double V:Values)A.Add(MakeShared<FJsonValueNumber>(V));return A;};
    auto V=[&](FVector P){return Numbers({P.X,P.Y,P.Z});};
    auto Q=[&](FQuat R){return Numbers({R.X,R.Y,R.Z,R.W});};
    auto T=[&](FTransform X){const auto P=X.GetLocation();const auto R=X.GetRotation();return Numbers({P.X,P.Y,P.Z,R.X,R.Y,R.Z,R.W});};
    for(const auto& Entry:States)
    {
        const auto* A=Entry.Key.Get();if(!A||A->GetWorld()!=World||!A->IsPlayerControlled())continue;
        const auto& S=*Entry.Value;if(S.Pose.Num()!=26)continue;
        auto Out=MakeShared<FJsonObject>();const auto Space=A->GetAgentMesh()->GetComponentTransform();
        Out->SetArrayField(TEXT("space"),T(Space));
        for(const auto& Pair:{TPair<FString,const TArray<FTransform>*>(TEXT("base"),&S.Ordered),{TEXT("pose"),&S.Pose}})
        {TArray<TSharedPtr<FJsonValue>> P;for(auto X:*Pair.Value)P.Add(MakeShared<FJsonValueArray>(T(X)));Out->SetArrayField(Pair.Key,P);}
        TArray<TSharedPtr<FJsonValue>> State;for(double B:S.Solver.Body)State.Add(MakeShared<FJsonValueNumber>(B));
        for(auto P:S.Solver.Targets)State.Append(V(P));for(auto P:S.Solver.Elbows)State.Append(V(P));for(bool B:S.Solver.Active)State.Add(MakeShared<FJsonValueNumber>(B?1:0));
        Out->SetArrayField(TEXT("state"),State);const auto Angles=GrabAngles(A),Tuning=ReachTuning(A);
        Out->SetArrayField(TEXT("angles"),Numbers({Angles.X,Angles.Y}));Out->SetArrayField(TEXT("tuning"),Numbers({Tuning.X,Tuning.Y}));
        TArray<TSharedPtr<FJsonValue>> Hands;
        for(int K=0;K<2;++K)
        {
            const auto& H=S.Hands[K];auto J=MakeShared<FJsonObject>();const auto Frame=TargetFrame(H);
            J->SetBoolField(TEXT("enabled"),H.Enabled);J->SetBoolField(TEXT("grab"),H.Grab);J->SetBoolField(TEXT("gripped"),H.Gripped);J->SetBoolField(TEXT("physical"),H.Physical);
            J->SetNumberField(TEXT("speed"),H.Speed);J->SetNumberField(TEXT("rotationSpeed"),H.RotationSpeed);J->SetNumberField(TEXT("close"),H.Close);J->SetNumberField(TEXT("distance"),H.Distance);J->SetNumberField(TEXT("contacts"),H.Contacts);
            J->SetArrayField(TEXT("target"),T(H.Target.GetRelativeTransform(Space)));J->SetArrayField(TEXT("ball"),T(Frame.GetRelativeTransform(Space)));
            J->SetArrayField(TEXT("surface"),V(Space.InverseTransformPosition(Frame.TransformPosition(H.Point))));J->SetArrayField(TEXT("normal"),V(Space.InverseTransformVectorNoScale(Frame.TransformVectorNoScale(H.Normal).GetSafeNormal())));
            J->SetArrayField(TEXT("palm"),V(H.Palm));TArray<TSharedPtr<FJsonValue>> C;for(const auto& F:H.Fingers)C.Add(MakeShared<FJsonValueNumber>(F.Curl));J->SetArrayField(TEXT("curl"),C);
            if(const auto* W=WristConstraint(A,K))
            {auto P=MakeShared<FJsonObject>();const auto& B=W->ProfileInstance;P->SetBoolField(TEXT("handFirst"),W->ConstraintBone1==HandName(K));P->SetArrayField(TEXT("frame1"),Q(W->GetRefFrame(EConstraintFrame::Frame1).GetRotation()));P->SetArrayField(TEXT("frame2"),Q(W->GetRefFrame(EConstraintFrame::Frame2).GetRotation()));P->SetArrayField(TEXT("modes"),Numbers({double(B.TwistLimit.TwistMotion),double(B.ConeLimit.Swing2Motion),double(B.ConeLimit.Swing1Motion)}));P->SetArrayField(TEXT("limits"),Numbers({B.TwistLimit.TwistLimitDegrees,B.ConeLimit.Swing2LimitDegrees,B.ConeLimit.Swing1LimitDegrees}));J->SetObjectField(TEXT("joint"),P);}
            const auto& P=H.ArmPlan;auto Plan=MakeShared<FJsonObject>();Plan->SetBoolField(TEXT("valid"),P.Valid);Plan->SetNumberField(TEXT("reserve"),P.Reserve);Plan->SetArrayField(TEXT("target"),V(P.Target));Plan->SetArrayField(TEXT("shoulder"),V(P.Shoulder));Plan->SetArrayField(TEXT("forearm"),Q(P.Solution.Forearm));Plan->SetNumberField(TEXT("cos"),P.Solution.Cos);Plan->SetNumberField(TEXT("evaluations"),P.Solution.Evaluations);J->SetObjectField(TEXT("plan"),Plan);
            Hands.Add(MakeShared<FJsonValueObject>(J));
        }
        Out->SetArrayField(TEXT("hands"),Hands);FString Text;FJsonSerializer::Serialize(Out,TJsonWriterFactory<>::Create(&Text));
        FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachElbowHitch20261016/checkpoint.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);return;
    }
}
