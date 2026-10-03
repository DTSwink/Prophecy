import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics');root=p.parents[1]
rows=json.loads((p/'KneeHistoricalBaseline-capture.json').read_text())['rows'];actor=rows[0]['actor']
r=next(n for n in map(json.loads,(p/'KneeHistoricalBaseline-nn.jsonl').read_text(encoding='utf-8').splitlines()) if n['actor']==actor and round(n['time']*60)==175)
c=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text());off=np.array(json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())['local_offsets_m'])
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def rot(s,o):
 a=unit(s[o:o+3]);b=unit(s[o+3:o+6]-a*(s[o+3:o+6]@a));return np.array([a,b,np.cross(a,b)])
raw=np.array(r['lower_input'][:41])+r['lower_delta'][:41]
for o in (3,12,18,28,34):raw[o:o+6]=rot(raw,o)[:2].ravel()
raw[[24,40]]=np.clip(raw[[24,40]],-1,1)
target=np.array(r['published_lower']);hip=target[:3]+off[21]@rot(target,3);ko=off[22]
L2=np.linalg.norm(target[25:28]-hip-ko@rot(target,34))
def f(x):
 s=format(float(x),'.10g');return s+('f' if '.' in s or 'e' in s else '.f')
def ar(a):return ','.join(map(f,a))
text='''// Frozen current-scene recovery input at tick175; no replay timing dependency.
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCleanRecoverySourceTest,
    "Prophecy.NN.LowerTempering.CleanRecoverySource",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCleanRecoverySourceTest::RunTest(const FString&)
{
'''
text+=f'    const float Raw[41]={{{ar(raw)}}};\n    const float Pinned[41]={{{ar(target)}}};\n'
text+=f'    const FPelvisLegGeometry G{{FVector3f({ar(off[21])}),FVector3f({ar(ko)}),FVector3f({ar(c["ik_local_pole_axes"][1][0])}),{f(L2)},0.f}};\n'
text+='''    float Clean[41],Corrupted[41];FMemory::Memcpy(Clean,Pinned,sizeof(Clean));FMemory::Memcpy(Corrupted,Pinned,sizeof(Corrupted));
    FMemory::Memcpy(Corrupted+34,Raw+34,6*sizeof(float));
    const FVector3f P=ReadStateVec3(Pinned,0);const FMat3f R=MatrixFromRot6(Pinned+3);
    FVector3f CleanPole,OldPole;
    ResolvePelvisLeg(ReadStateVec3(Raw,0),MatrixFromRot6(Raw+3),P,R,G,Clean,25,Raw,false,&CleanPole);
    ResolvePelvisLeg(P,R,P,R,G,Corrupted,25,nullptr,false,&OldPole);
    const FVector3f H=P+TransformRow(G.HipOffset,R),Axis=SafeNormal(ReadStateVec3(Clean,25)-H);
    const FVector3f SourceH=ReadStateVec3(Raw,0)+TransformRow(G.HipOffset,MatrixFromRot6(Raw+3));
    const FVector3f SourceAxis=SafeNormal(ReadStateVec3(Raw,25)-SourceH);
    const FVector3f SourcePole=ProjectToPlane(TransformRow(G.KneeOffset,MatrixFromRot6(Raw+34)),SourceAxis);
    const FVector3f Expected=ProjectToPlane(SourcePole-(SourceAxis+Axis)*(FVector3f::DotProduct(SourcePole,Axis)/(1.f+FVector3f::DotProduct(SourceAxis,Axis))),Axis);
    TestTrue(TEXT("Unmodified NN hinge transports to the pinned endpoint"),FVector3f::DotProduct(CleanPole,Expected)>.99999f);
    const float Difference=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector3f::DotProduct(CleanPole,OldPole),-1.f,1.f)));
    TestTrue(TEXT("Recorded post-pin source mixes incompatible frames"),Difference>20.f);
    TestTrue(TEXT("Pin position is preserved"),ReadStateVec3(Clean,25).Equals(ReadStateVec3(Pinned,25),1.e-5f));
    TestEqual(TEXT("Pelvis unchanged"),FMemory::Memcmp(Clean,Pinned,9*sizeof(float)),0);
    TestEqual(TEXT("Foot rotation unchanged"),FMemory::Memcmp(Clean+28,Pinned+28,6*sizeof(float)),0);
    TestEqual(TEXT("Other leg unchanged"),FMemory::Memcmp(Clean+9,Pinned+9,16*sizeof(float)),0);
    const FVector3f K=H+TransformRow(G.KneeOffset,MatrixFromRot6(Clean+34));
    TestTrue(TEXT("Calf remains connected"),FMath::Abs((ReadStateVec3(Clean,25)-K).Size()-G.CalfLength)<2.e-6f);
    AddInfo(FString::Printf(TEXT("Same endpoints: incompatible source changes knee pole by %.6f degrees"),Difference));
    return !HasAnyErrors();
}
#endif
'''
(root/'Source/GameAnimationSample3/Private/ProphecyRecoverySourceTests.inl').write_text(text,encoding='utf-8')
