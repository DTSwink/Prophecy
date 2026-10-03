from pathlib import Path
base=Path('Source/GameAnimationSample3/Private')
def edit(name, fn):
    p=base/name;s=p.read_text();n=fn(s);assert n!=s,name;p.write_text(n)
def cut(s,a,b):
    i=s.index(a);j=s.index(b,i);return s[:i]+s[j:]
def pose(s):
    s=cut(s,'\tstruct FKickFootExtension','\tstruct FPresentationSample')
    s=cut(s,'void ProphecyNNPresentation::SetKickFootExtension','float ProphecyNNPresentation::Resolve')
    s='\n'.join(x for x in s.split('\n') if 'GKickFootExtensions.' not in x and 'GKickFootReturns.' not in x)
    i=s.index('void FProphecyNNPoseStore::ApplyRigidCalves')
    j=s.index('\n\tstatic const FName Feet[]',i)
    begin=s.index('\n{',i)+2
    s=s[:begin]+'\n\t{\n\t\tFReadScopeLock Lock(GProphecyNNPoseLock);\n\t\tif (!GProphecyNNRigidCalves.Contains(AgentId)) return;\n\t}\n'+s[j:]
    return s
edit('ProphecyNNPoseTypes.cpp',pose)
edit('ProphecyNNPresentation.h',lambda s:'\n'.join(l for l in s.split('\n') if not any(n in l for n in ['void SetKickFootExtension','void SetKickFootReturn','bool ApplyKickFootExtension'])))
def lib(s):
    s=s.replace('#include "ProphecyNNPresentation.h"\n','')
    s=cut(s,'// Separate sidecar:','static FDelegateHandle')
    s=cut(s,'float ReturningExtension','static bool Apply')
    s=cut(s,'    int32 PoseId=INDEX_NONE;','    auto* Mesh=Agent->GetPoseReferenceMesh();')
    s=s.replace('    auto* Mesh=Agent->GetPoseReferenceMesh();','    if (!HasRig) return true;\n    auto* Mesh=Agent->GetPoseReferenceMesh();',1)
    s=cut(s,'    auto PublishNN=','    auto* Class=FindObject<UClass>')
    s=s.replace('    if (P.Result) PublishNN();\n','')
    s=s.replace(' ReturnExtensions.Remove(Agent);','').replace('    ReturnExtensions.Remove(Agent);\n','')
    s=cut(s,'    FVector2D Extension=FVector2D::ZeroVector;','    State->Returning=true;')
    s=cut(s,'    int32 PoseId; float Interval; bool Interpolate;','    Refresh();\n}',)
    s=s.replace('ReturnExtensions.Remove(It.Key()); ','')
    s=cut(s,'    ReturnExtensions.Add(Agent,FVector2D(2,6));','    Tick(World,LEVELTICK_All,1.f/120);')
    s='\n'.join(l for l in s.split('\n') if 'ReturningExtension(' not in l and 'ReturnExtensions.Contains' not in l)
    # The removed target rule is no longer part of the physical allowance.
    s=cut(s,'    const FVector Axis=','    FActive A;')
    return s
edit('ProphecyKickFootLeewayLibrary.cpp',lib)
edit('ProphecyKickFootLeeway.h',lambda s:s[:s.index('// Actual outgoing extension')]+ '}\n')
def manager(s):
    s=s.replace('+.01f*ProphecyKickFootLeeway::ReturningExtension(Controls,I)','').replace('+.01f*ProphecyKickFootLeeway::ReturningExtension(InertiaActor,I)','')
    s=cut(s,'\tif (bKickFootExtension)\n\t{\n\t\tProphecyNNPresentation::ApplyKickFootExtension','\tif (bTemperCalves || bKickFootExtension || bDefensePose')
    s=s.replace('if (bTemperCalves || bKickFootExtension || bDefensePose','if (bTemperCalves || bDefensePose')
    return s
edit('ProphecyNNLocomotionManager.cpp',manager)
edit('ProphecyNNDefenseRuntime.inl',lambda s:'\n'.join(l for l in s.split('\n') if 'ProphecyNNPresentation::ApplyKickFootExtension' not in l))
def physical(s):
    s=s.replace('if (Side!=INDEX_NONE)\n','if (Side!=INDEX_NONE && KickFootLeeway<=0)\n')
    s=cut(s,'                if (KickFootLeeway>0) Target=','                BodyWorld.SetLocation(Target);')
    return s
edit('ProphecyJoltCharacterComponent.cpp',physical)
def tests(s):
    return s[:s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyKickNNLeewayTest')]+ '#endif\n'
edit('ProphecyNNLegClampTests.cpp',tests)
