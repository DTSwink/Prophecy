from pathlib import Path
import re
root=Path.cwd()
def edit(name, fn):
    p=root/name
    s=p.read_text(encoding='utf-8'); t=fn(s)
    if t!=s:p.write_text(t,encoding='utf-8')
base='Source/GameAnimationSample3/'
for p in (root/base).rglob('*'):
    if p.suffix not in ('.h','.cpp','.inl'):continue
    def common(s):
        s=s.replace('UENUM(BlueprintType)\nenum class EProphecyParryBlocker : uint8 { Blade, LeftArm, RightArm };\n\n','')
        s=s.replace('enum class EProphecyParryBlocker : uint8;\n','')
        s=s.replace('EProphecyParryBlocker Blocker,','').replace('    EProphecyParryBlocker Blocker;\n','')
        s=s.replace('Attacker,Blocker,MaximumDurationSeconds','Attacker,MaximumDurationSeconds')
        s=s.replace('bDodge, Blocker, MaximumSeconds','bDodge, MaximumSeconds')
        s=s.replace('Attacker, Pair.Value.Blocker, Pair.Value.MaximumSeconds','Attacker, Pair.Value.MaximumSeconds')
        s=s.replace('Attacker,false,Blocker,MaximumSeconds','Attacker,false,MaximumSeconds')
        s=s.replace('Attacker,true,EProphecyParryBlocker::RightArm,MaximumSeconds','Attacker,true,MaximumSeconds')
        s=s.replace('    UPROPERTY(BlueprintReadOnly,Category="Defense") bool Blocked=false;\n','')
        s=s.replace('    UPROPERTY(BlueprintReadOnly,Category="Defense") bool HarmfulContact=false;\n','')
        s=s.replace('FContactOrder','FFirstContact')
        return s
    edit(p.relative_to(root),common)
def runtime(s):
    s=s.replace('P.Order={};P.Status.Blocked=P.Status.HarmfulContact=false;','P.Order={};')
    s=re.sub(r'            TSet<FName> Blocking;\n.*?            auto Contacts=', '            auto Contacts=',s,flags=re.S)
    s=s.replace('Impl.BodyNames,Blocking,Error','Impl.BodyNames,Error')
    s=s.replace('        P.Status.Blocked=P.Order.bProtected;P.Status.HarmfulContact=P.Order.bHarmful;\n','')
    s=s.replace('P.Order.bProtected?P.Order.BlockCollider:P.Order.HarmCollider','P.Order.Collider')
    s=s.replace('(P.Order.bProtected?P.Order.BlockTime:P.Order.HarmTime)','P.Order.Time')
    s=re.sub(r'    if \(Blocker==EProphecyParryBlocker::Blade.*?return false; }\n','',s,flags=re.S)
    s=s.replace('AttackCollider==INDEX_NONE || (Blocker==EProphecyParryBlocker::Blade && !Drawn)','AttackCollider==INDEX_NONE')
    s=s.replace('Unsupported attack collider, or blade parry requested without a held sword.','Unsupported attack collider.')
    s=re.sub(r'^    P.BlockingMask=.*\n','',s,flags=re.M)
    return s
edit(base+'Private/ProphecyNNDefenseRuntime.inl',runtime)
edit(base+'Private/ProphecyNNDefenseRuntime.h',lambda s:s.replace('PresentMask=0,BlockingMask=0','PresentMask=0'))
for name in ['Private/ProphecyDefensePhysicalContacts.h','Private/ProphecyDefensePhysicalContacts.cpp']:
    edit(base+name,lambda s:s.replace('bBlade=false,bBlocking=false','bBlade=false').replace('const TSet<FName>& Blocking,','').replace(';B.bBlocking=Blocking.Contains(B.Name)','').replace('NAME_None,Blocking,Defender','NAME_None,Defender').replace('AttackBone,{},Attacker','AttackBone,Attacker').replace('Pair,I,D.bBlocking,Step','Pair,I,Step'))
def header(s):
    s=s.replace('    // Eligibility is supplied by gameplay, never appended to the NN input.\n    uint32 BlockingMask(int32 TrainingLabel,bool bDrawn) const;\n','')
    s=s.replace('// Strict conservative advancement: exhausted searches may be harmful, but\n// never certify a block. Time is a fraction of this completed policy interval.','// Conservative advancement: exhausted searches do not confirm a contact.\n// Time is a fraction of this completed policy interval.')
    start=s.index('struct FFirstContact')
    return s[:start]+'''// Earliest confirmed contact, without gameplay success/damage classification.
struct FFirstContact
{
    double Time=std::numeric_limits<double>::infinity();
    int32 Collider=INDEX_NONE,Unresolved=0;
    void Include(const FContactPair& Pair,int32 Body,double Start,double End);
};
}
'''
edit(base+'Private/ProphecyDefenseContacts.h',header)
def cpp(s):
    start=s.index('uint32 FContactGeometry::BlockingMask'); end=s.index('float BoxGap',start)
    s=s[:start]+s[end:]
    start=s.index('void FFirstContact::Include')
    return s[:start]+'''void FFirstContact::Include(const FContactPair& Pair,int32 Body,double Start,double End)
{
    if (!Pair.bResolved) ++Unresolved;
    const double Candidate=Start+Pair.Fraction*(End-Start);
    if (Pair.bConfirmed && Candidate<Time) { Time=Candidate;Collider=Body; }
}
}
'''
edit(base+'Private/ProphecyDefenseContacts.cpp',cpp)
def contacts_test(s):
    s=s.replace('const uint32 Blocking=G.BlockingMask(16,true),Present=G.PresentMask(true);','const uint32 Present=G.PresentMask(true);')
    s=s.replace('Contact,I,(Blocking&(1u<<I))!=0,PreviousTime','Contact,I,PreviousTime')
    s=s.replace('TestEqual(TEXT("Saved successful block"),Order.bProtected,Doc->GetNumberField(TEXT("expected_protected"))!=0);','TestTrue(TEXT("Saved trajectory has a confirmed contact"),Order.Collider!=INDEX_NONE);')
    s=s.replace(';Report->SetBoolField(TEXT("protected"),Order.bProtected)','')
    s=s.replace('Order.BlockTime','Order.Time').replace('block_time','contact_time')
    s=s.replace('Exhaustion cannot grant a block','Exhaustion cannot confirm a contact')
    start=s.index('    FFirstContact Tie;'); end=s.index('    AddInfo(',start)
    s=s[:start]+'''    FFirstContact First;First.Include(Exhausted,2,0,1);
    TestEqual(TEXT("Unconfirmed contact is ignored"),First.Collider,INDEX_NONE);
    First.Include(Fast,0,1,2);First.Include(Fast,1,0,1);
    TestEqual(TEXT("Earliest contact wins regardless of body"),First.Collider,1);
    TestTrue(TEXT("Earliest fractional time"),FMath::IsNearlyEqual(First.Time,double(Fast.Fraction)));
'''+s[end:]
    return s
edit(base+'Private/ProphecyDefenseContactTests.cpp',contacts_test)
def parry_test(s):
    s=s.replace('Pair,I,(ContactGeometry.BlockingMask(16,true)&(1u<<I))!=0,PreviousTime','Pair,I,PreviousTime')
    s=re.sub(r'^    Candidate->SetNumberField\(TEXT\("contact/protected"\).*\n','',s,flags=re.M)
    s=s.replace('ContactOrder.BlockTime','ContactOrder.Time').replace('contact/first_block_time','contact/first_contact_time')
    s=s.replace('TestTrue(TEXT("Native inferred pose blocks the attack"),ContactOrder.bProtected);','TestTrue(TEXT("Native inferred pose contacts the attack"),ContactOrder.Collider!=INDEX_NONE);')
    s=s.replace('native block %.9f','native contact %.9f')
    return s
edit(base+'Private/ProphecyParryRuntimeTests.cpp',parry_test)
edit('Source/ProphecyEditor/Private/ProphecyCombatDemoSetup.cpp',lambda s:s.replace(';G.Default(Parry,TEXT("Blocker"),TEXT("RightArm"))',''))
print('Removed blocker selection and contact classification; retained earliest confirmed contact.')
