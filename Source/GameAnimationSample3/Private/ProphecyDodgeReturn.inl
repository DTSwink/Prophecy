// Included inside ProphecyUpperBodyInertia. Only a configured dodge exit creates this cache.
bool HasDodgeReturn(const AProphecyAgent* A)
{ return !DodgePublications.IsEmpty() && DodgePublications.Contains(A); }

void BeginDodge(const AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TConstArrayView<FName> Core,TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current,
    const FTransform& PreviousCarrier,const FTransform& Carrier,double SourceTime,double Dt,uint32 PublishedAgeTicks)
{
    Cancel(A);
    if(!Configured(A) || Names.Num()!=Parents.Num() || Current.Num()!=Names.Num() || Previous.Num()!=Current.Num())return;
    TArray<FTransform,TInlineAllocator<32>> OldWorld,World;
    for(int32 I=0;I<Current.Num();++I){OldWorld.Add(Previous[I]*PreviousCarrier);World.Add(Current[I]*Carrier);}
    Begin(A,OldWorld,World,Names,Core,Dt,PreviousCarrier,Carrier);
    auto* R=Returns.Find(A);if(!R)return;
    R->Elapsed=double(PublishedAgeTicks)/60.;
    FDodgePublication Cache;Cache.Time=SourceTime;
    const int32 Spine=Names.IndexOfByKey(TEXT("spine_01"));
    for(int32 I=0;I<Current.Num();++I)
        for(int32 P=I;Parents.IsValidIndex(P);P=Parents[P])if(P==Spine)
        {
            const int32 Parent=Parents[I];if(!Parents.IsValidIndex(Parent)){Cancel(A);return;}
            Cache.Bones.Add({I,Parent,Core.Contains(Names[I]),Previous[I].GetRelativeTransform(Previous[Parent]),Current[I].GetRelativeTransform(Current[Parent])});
            break;
        }
    if(Cache.Bones.IsEmpty()){Cancel(A);return;}
    DodgePublications.Add(A,MoveTemp(Cache));
}

bool ApplyDodge(const AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TConstArrayView<FName> Core,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,
    TArrayView<FTransform> Local,const FTransform& Carrier,double SourceTime,double Dt,const FVector2D& ForearmLengths,bool& NewSample)
{
    NewSample=false;
    auto* C=DodgePublications.IsEmpty()?nullptr:DodgePublications.Find(A);if(!C)return false;
    if(SourceTime>C->Time)
    {
        C->PreviousComplete=C->Complete;C->Time=SourceTime;C->Sampled=false;
        for(auto& B:C->Bones)B.Previous=B.Current;
        Advance(A);C->Complete=!Active(A);
        if(!C->Complete)
        {
            // Preserve FK attachment offsets when inertial core rotations move the shoulders.
            for(auto& B:C->Bones)B.Current=Current[B.Index].GetRelativeTransform(Current[B.Parent]);
            Apply(A,Parents,Names,Core,Carrier,Current,Dt);
            for(const auto& B:C->Bones)if(!B.Core)Current[B.Index]=B.Current*Current[B.Parent];
            ApplyArms(A,Carrier,Current,Dt,ForearmLengths,Carrier);
        }
        for(auto& B:C->Bones)B.Current=Current[B.Index].GetRelativeTransform(Current[B.Parent]);
    }
    if(C->PreviousComplete){Cancel(A);return false;}
    // Repeated publication must restore accepted endpoints, never integrate a spring twice.
    for(const auto& B:C->Bones)
    {
        Previous[B.Index]=B.Previous*Previous[B.Parent];
        if(!C->Complete){Local[B.Index]=B.Current;Current[B.Index]=B.Current*Current[B.Parent];}
    }
    NewSample=!C->Sampled;C->Sampled=true;
    return true;
}
