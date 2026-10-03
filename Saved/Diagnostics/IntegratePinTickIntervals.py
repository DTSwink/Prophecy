from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinning.h');s=p.read_text().replace('int32 PoseId=INDEX_NONE;','FVector WorldOffset[2]={FVector::ZeroVector,FVector::ZeroVector};\n    int32 PoseId=INDEX_NONE;');p.write_text(s)
p=Path('Source/GameAnimationSample3/Public/ProphecyNNLocomotionManager.h');s=p.read_text().replace('void UpdateWalkTickPinning();','void UpdateWalkTickPinning(float DeltaSeconds);\n    void CommitWalkTickPinning();');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp');s=p.read_text().replace('UpdateWalkTickPinning();','UpdateWalkTickPinning(DeltaSeconds);').replace('\tResamplePhysicalAgents();\n\tBuildInputBatch(StepSeconds);','    if(ProphecyWalkPinning::AnyTickPinning()) CommitWalkTickPinning();\n\tResamplePhysicalAgents();\n\tBuildInputBatch(StepSeconds);');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinningRuntime.inl');s=p.read_text().replace('void AProphecyNNLocomotionManager::UpdateWalkTickPinning()','void AProphecyNNLocomotionManager::UpdateWalkTickPinning(float DeltaSeconds)');s=s.replace('''        if(!T->Dirty && T->Last==Value)continue;
        T->Last=Value;T->Dirty=false;''','''        // Integrate this render interval only. Reweighting a whole 30 Hz endpoint
        // after half of it was already displayed would produce a catch-up jump.
        bool Moved=false;
        const float Fraction=FMath::Clamp(DeltaSeconds*NNUpdateHz*GetAgentTimeDilation(A->GetAgentHandle()),0.f,1.f);
        for(int32 I=0;I<2;++I)
        {
            const FVector Delta=LowerPointToWorld(T->Current.Shift(I,Value[I])*Fraction,Impl->SeedRootRot,FVector3f::ZeroVector,Agent.PublishedYaw);
            T->WorldOffset[I]+=Delta;Moved|=!Delta.IsNearlyZero(1.e-9);
        }
        if(!T->Dirty && T->Last==Value && !Moved)continue;
        T->Last=Value;T->Dirty=false;''');s=s.replace('''            const FVector3f Shift[]={Frame.Shift(0,Value.X),Frame.Shift(1,Value.Y)};''','''            const float Yaw=End?Agent.PublishedYaw:Agent.PreviousPublishedYaw;
            FVector3f Shift[2];
            for(int32 I=0;I<2;++I) Shift[I]=TransformRow(TransformRow(UnrealToTraining(T->WorldOffset[I]),YawMatrix(Yaw)),Transpose(Impl->SeedRootRot));''');s+='''
// Carry only the newly applied pin correction into the next real NN input.
// Do this before physical feedback so an actual simulation sample still wins.
void AProphecyNNLocomotionManager::CommitWalkTickPinning()
{
    const auto* Clock=ProphecyAgentTime::Context(this);
    for(int32 Index=0;Index<AgentActors.Num();++Index)
    {
        if(Clock && !Clock->Step->Due[Index])continue;
        const AProphecyAgent* A=AgentActors[Index];auto* T=ProphecyWalkPinning::FindTickPinning(A);
        if(!T || !T->HasBase)continue;
        const auto& Agent=Impl->Agents[Index];
        if(!A->bNNInferenceEnabled || Agent.Slash.bActive || Agent.DefensePose)continue;
        for(int32 I=0;I<2;++I)
        {
            if(T->WorldOffset[I].IsNearlyZero(1.e-9))continue;
            const FVector3f World=UnrealToTraining(T->WorldOffset[I]);
            const int32 O=9+16*I;
            auto Shift=[&](float* State,float Yaw)
            {
                const FVector3f D=TransformRow(TransformRow(World,YawMatrix(Yaw)),Transpose(Impl->SeedRootRot));
                WriteStateVec3(State,O,ReadStateVec3(State,O)+D);
            };
            Shift(StateSlice(Impl->CurStateBuffer,Index),Agent.CurRootYaw);
            Shift(StateSlice(Impl->PublishedStateBuffer,Index),Agent.PublishedYaw);
            T->WorldOffset[I]=FVector::ZeroVector;
        }
    }
}
''';p.write_text(s)
