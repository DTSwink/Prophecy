import pathlib,json,sys,numpy as np
p=pathlib.Path('Saved/Diagnostics');sys.path.insert(0,str(p.resolve()))
ns={};s=(p/'PrototypeBendCoordinate.py').read_text();exec(compile(s[:s.index('rows=[r for r in map')],str((p/'PrototypeBendCoordinate.py').resolve()),'exec'),dict(__file__=str((p/'PrototypeBendCoordinate.py').resolve())),ns) if False else None
import importlib.util,contextlib,io
spec=importlib.util.spec_from_file_location('bc',p/'PrototypeBendCoordinate.py');m=importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):spec.loader.exec_module(m)
r=next(r for r in map(json.loads,(p/'FootVibration-nn-pelvis159-baseline.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1') and round(r['time']*60)==157)
prev=np.array(r['previous_lower']);target=np.array(r['published_lower']);raw=m.clean(np.array(r['lower_input'][:41])+r['lower_delta'][:41]);g=m.evaluate(r,0)
def fl(v):
 t=format(float(v),'.9g');return t+('f' if '.' in t or 'e' in t else '.f')
def arr(v):return ','.join(fl(x) for x in v)
off=m.off;pole=np.array(m.w['ik_local_pole_axes'][0][0]);L2=g['length_cm']/100
snippet='''
#if WITH_EDITOR
static void CheckCapturedKneePlaneReturn(FAutomationTestBase& Test)
{
    // Recorded131->161 recovery: changing the plane becomes feasible at157.
    // These are frozen inputs; this check cannot pass merely by changing rollout.
    const float Previous[41]={PREV};
    const float NN[41]={RAW};
    const float Recorded[41]={TARGET};
    const float ExpectedRot[6]={EXPECTED};
    const ProphecyLowerTempering::FSettings S{SETTINGS};
    const FPelvisLegGeometry G{FVector3f(HIP),FVector3f(KNEE),FVector3f(POLE),CALF,FLOOR};
    const int32 SavedMode=CVarTemperingKneePlane.GetValueOnGameThread();
    float Legacy[41],Candidate[41];FMemory::Memcpy(Legacy,Recorded,sizeof(Legacy));FMemory::Memcpy(Candidate,Recorded,sizeof(Candidate));
    auto Solve=[&](float* Out){ResolveTemperedLeg(S,Previous,G,Out,9,FVector3f(TOE),FVector3f(1,0,0),.15f,true,NN);};
    CVarTemperingKneePlane->Set(1,ECVF_SetByCode);Solve(Legacy);
    CVarTemperingKneePlane->Set(3,ECVF_SetByCode);Solve(Candidate);
    const FQuat Prior=MatrixToQuat(MatrixFromRot6(Previous+18));
    const FQuat Old=MatrixToQuat(MatrixFromRot6(Legacy+18));
    const FQuat New=MatrixToQuat(MatrixFromRot6(Candidate+18));
    Test.TestTrue(TEXT("Recorded original reproduces the greater-than40-degree thigh step"),FMath::RadiansToDegrees(Prior.AngularDistance(Old))>40.);
    Test.TestTrue(TEXT("Same frozen inputs produce a thigh step below6 degrees"),FMath::RadiansToDegrees(Prior.AngularDistance(New))<6.);
    Test.TestTrue(TEXT("Independent double-precision bend-coordinate oracle"),FMath::RadiansToDegrees(New.AngularDistance(MatrixToQuat(MatrixFromRot6(ExpectedRot))))<.01);
    Test.TestEqual(TEXT("Recorded solve leaves pelvis unchanged"),FMemory::Memcmp(Recorded,Candidate,9*sizeof(float)),0);
    Test.TestTrue(TEXT("Recorded solve keeps the exact ankle endpoint"),ReadStateVec3(Recorded,9).Equals(ReadStateVec3(Candidate,9),2.e-6f));
    Test.TestEqual(TEXT("Recorded solve preserves foot rotation and toe"),FMemory::Memcmp(Recorded+12,Candidate+12,6*sizeof(float)),0);
    Test.TestEqual(TEXT("Recorded toe unchanged"),Recorded[24],Candidate[24]);
    const FVector3f Hip=ReadStateVec3(Candidate,0)+TransformRow(G.HipOffset,MatrixFromRot6(Candidate+3));
    const FVector3f Knee=Hip+TransformRow(G.KneeOffset,MatrixFromRot6(Candidate+18));
    Test.TestTrue(TEXT("Recorded calf remains connected"),FMath::Abs((ReadStateVec3(Candidate,9)-Knee).Size()-G.CalfLength)<2.e-6f);
    // Sweep the endpoint through the previous feasibility boundary using fixed
    // reference poses. This also covers an almost straight connected leg.
    FQuat Last;double MaxStep=0;
    for(int32 I=0;I<=1000;++I)
    {
        float P[41];FMemory::Memcpy(P,Recorded,sizeof(P));
        WriteStateVec3(P,9,ReadStateVec3(Recorded,9)+FVector3f(0,0,(float(I)/1000.f-.5f)*.08f));
        Solve(P);
        const FQuat Q=MatrixToQuat(MatrixFromRot6(P+18));
        if(I) MaxStep=FMath::Max(MaxStep,double(FMath::RadiansToDegrees(Last.AngularDistance(Q))));
        Last=Q;
        Test.TestTrue(TEXT("Endpoint sweep remains finite"),!Q.ContainsNaN());
    }
    Test.TestTrue(TEXT("No discrete knee turn across endpoint feasibility sweep"),MaxStep<1.);
    Test.AddInfo(FString::Printf(TEXT("Frozen recorded157: old %.6f, new %.6f degrees; sweep max %.6f degrees"),FMath::RadiansToDegrees(Prior.AngularDistance(Old)),FMath::RadiansToDegrees(Prior.AngularDistance(New)),MaxStep));
    CVarTemperingKneePlane->Set(SavedMode,ECVF_SetByCode);
}
#endif
'''
values={'PREV':arr(prev),'RAW':arr(raw),'TARGET':arr(target),'EXPECTED':arr(g['plane_thigh']),'SETTINGS':arr(r['tempering']),'HIP':arr(off[17]),'KNEE':arr(off[18]),'POLE':arr(pole),'CALF':fl(L2),'FLOOR':fl(m.minimum(target,0)),'TOE':arr(m.w['ik_toe_offsets_m'][0])}
for k,v in values.items():snippet=snippet.replace(k,v)
f=pathlib.Path('Source/GameAnimationSample3/Private/ProphecyLowerTempering.inl');src=f.read_text();needle='#if WITH_DEV_AUTOMATION_TESTS\nIMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingSupportSourceTest,';assert needle in src;src=src.replace(needle,'#if WITH_DEV_AUTOMATION_TESTS\n'+snippet+'\nIMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingSupportSourceTest,',1)
needle='bool FProphecyTemperingSupportSourceTest::RunTest(const FString&)\n{';assert needle in src;src=src.replace(needle,needle+'\n#if WITH_EDITOR\n    CheckCapturedKneePlaneReturn(*this);\n#endif',1);f.write_text(src)
