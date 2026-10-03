from pathlib import Path
import shutil, hashlib, json

root = Path.cwd()
backup = root / 'Saved/Diagnostics/UpperCoreArms-20261002-comparison'
assert not backup.exists(), 'Do not overwrite the saved comparison version'
files = [
 'Source/GameAnimationSample3/Private/ProphecyUpperBodyInertiaLibrary.cpp',
 'Source/GameAnimationSample3/Private/ProphecyUpperBodyInertia.h',
 'Source/GameAnimationSample3/Private/ProphecyHandInertiaRuntime.inl',
 'Source/GameAnimationSample3/Public/ProphecyUpperBodyInertiaLibrary.h',
 'Source/GameAnimationSample3/Private/ProphecyUpperBodyInertiaSettingsTests.inl',
 'Source/ProphecyEditor/Private/ProphecyBlendNodeUpgrade.cpp',
 'Docs/UpperBodyInertia.md', 'ProjectJournal.md',
 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',
]
for name in files:
    dest = backup / 'split' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / name, dest)
(backup / 'manifest.json').write_text(json.dumps({n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files}, indent=2))

def edit(name, transform):
    path = root / name
    text = path.read_text(encoding='utf-8')
    text = transform(text)
    path.write_text(text, encoding='utf-8', newline='\r\n')

def replace(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)

def runtime(t):
    start=t.index('// Separate storage keeps retained Live Coding config/return layouts unchanged.')
    end=t.index('// Keep the fading rotation offset',start)
    t=t[:start]+t[end:]
    t=replace(t,'        Clean(ArmTimings);Clean(ArmTimingBaselines);Clean(ActiveArmTimings);\n','')
    t=replace(t,'bool CoreActive(const AProphecyAgent* A) { const auto* R=Returns.IsEmpty()?nullptr:Returns.Find(A);return R && !R->Joints.IsEmpty(); }\n','')
    for old in ['ActiveArmTimings.Remove(A);','ArmTimings.Remove(A);','ArmTimingBaselines.Remove(A);','ArmTimingBaselines.Add(A,ArmTimings.FindRef(A));','ArmTimings.Add(A,ArmTimingBaselines.FindRef(A));']:
        t=t.replace(old,'')
    start=t.index('void Advance(const AProphecyAgent* A)')
    end=t.index('void Begin(',start)
    t=t[:start]+t[end:]
    t=replace(t,'    FArmTiming ArmTiming=ResolvedArmTiming(A,*C);\n','')
    t=replace(t,'R.Config.Response=ArmTiming.Response=DebugResponse','R.Config.Response=DebugResponse')
    t=replace(t,'    const double CoreDuration=Duration(R.Config.Response,C->Hold,C->Blend);\n    const double ArmDuration=Duration(ArmTiming.Response,C->Hold,ArmTiming.Blend);\n    if(CoreDuration>0)for(FName N:Core)','    for(FName N:Core)')
    t=replace(t,'    Returns.Add(A,MoveTemp(R));\n    if(CoreActive(A))\n    {\n        Handoffs.Add(A).Append(World.GetData(),World.Num());\n        BlendOffsets.Add(A).Core.Init(FVector::ZeroVector,Core.Num());\n    }\n    if(ArmDuration>0)\n    {','    Returns.Add(A,MoveTemp(R));Handoffs.Add(A).Append(World.GetData(),World.Num());\n    BlendOffsets.Add(A).Core.Init(FVector::ZeroVector,Core.Num());')
    t=replace(t,'ActiveArmTimings.Add(A,ArmTiming);','')
    t=replace(t,'    }\n    if(!CoreActive(A) && !ArmsActive(A)){Cancel(A);return;}\n    ProphecyBlendClock::Start(A,K::UpperBodyInertia,FMath::Max(CoreActive(A)?CoreDuration:0.,ArmsActive(A)?ArmDuration:0.));','    ProphecyBlendClock::Start(A,K::UpperBodyInertia,double(C->Hold)+C->Blend);')
    t=replace(t,'static double BlendAlpha(const FReturn& R,float Blend)','static double BlendAlpha(const FReturn& R)')
    t=replace(t,'R.Elapsed<R.Config.Hold?0.:Blend>0?\n        FMath::Clamp((R.Elapsed-R.Config.Hold)/Blend,0.,1.):1.;','R.Elapsed<R.Config.Hold?0.:R.Config.Blend>0?\n        FMath::Clamp((R.Elapsed-R.Config.Hold)/R.Config.Blend,0.,1.):1.;')
    t=replace(t,'    const auto* Timing=ActiveArmTimings.Find(A);\n    const float Response=Timing?Timing->Response:R->Config.Response,Blend=Timing?Timing->Blend:R->Config.Blend;\n','')
    t=replace(t,'BlendAlpha(*R,Blend)','BlendAlpha(*R)')
    t=replace(t,'GetNormalized(),Response,Dt);','GetNormalized(),R->Config.Response,Dt);',3)
    t=replace(t,'    auto* R=Returns.IsEmpty()?nullptr:Returns.Find(A);if(!R || R->Joints.IsEmpty()) return;','    auto* R=Returns.IsEmpty()?nullptr:Returns.Find(A);if(!R) return;\n    const double Dt=ProphecyBlendClock::Consume(A,K::UpperBodyInertia);R->Elapsed+=Dt;\n    if(R->Elapsed+1.e-8>=double(R->Config.Hold)+R->Config.Blend) {Cancel(A);return;}')
    t=replace(t,'BlendAlpha(*R,R->Config.Blend)','BlendAlpha(*R)')
    t=replace(t,'PoseStepSeconds>=0?PoseStepSeconds:ProphecyBlendClock::TickSeconds','PoseStepSeconds>=0?PoseStepSeconds:Dt')
    t=replace(t,'float Alpha,float ArmsResponse,float ArmsBlend)','float Alpha)')
    t=replace(t,'    for(float V:{ArmsResponse,ArmsBlend})if(!FMath::IsFinite(V) || (V<0 && V!=-1.f))return false;\n','')
    t=replace(t,'    const FArmTiming NewTiming{ArmsResponse,ArmsBlend};\n    const float ArmResponse=ArmsResponse<0?Response:ArmsResponse,ArmBlend=ArmsBlend<0?Blend:ArmsBlend;\n    if(Enabled && Alpha>0 && (Duration(Response,Hold,Blend)>0 || Duration(ArmResponse,Hold,ArmBlend)>0))','    if(Enabled && Alpha>0 && Response>0 && (Hold>0 || Blend>0))')
    t=replace(t,'        const FArmTiming OldTiming=ArmTimings.FindRef(A);\n','')
    t=replace(t,' && OldTiming.Response==ArmsResponse && OldTiming.Blend==ArmsBlend','')
    t=replace(t,'ArmTimings.Add(A,NewTiming);','')
    t=replace(t,'Advance(A);Apply(', 'Apply(',7)
    t=replace(t,'#include "ProphecyUpperBodyInertiaSettingsTests.inl"\n','')
    assert not any(s in t for s in ['ArmTiming','CoreActive','ArmsResponse','void Advance'])
    return t

edit(files[0],runtime)
edit(files[1],lambda t:replace(t,'bool CoreActive(const AProphecyAgent* Agent);\nvoid Advance(const AProphecyAgent* Agent);\n',''))
def caller(t):
    t=replace(t,'    ProphecyUpperBodyInertia::Advance(Actor);\n    const bool CoreInertia=ProphecyUpperBodyInertia::CoreActive(Actor);','    const bool CoreInertia=ProphecyUpperBodyInertia::Active(Actor);')
    t=replace(t,'if(!ProphecyUpperBodyInertia::ArmsActive(Actor))return;','if(!CoreInertia || !ProphecyUpperBodyInertia::ArmsActive(Actor))return;')
    t=replace(t,'    }\n    // Completed core channels and unrelated hand solvers do no recurring work.\n    if(!Recovery && !Temper && !ProphecySlashReturn::Active(Actor) && !ProphecyHandInertia::IsActive(Actor,Agent.PublishedWalkWeight,false)) {FinishInertia();return;}','        // Do not run a hand solve when only core tempering was requested.\n        if(!Recovery && !Temper && !ProphecySlashReturn::Active(Actor) && !ProphecyHandInertia::IsActive(Actor,Agent.PublishedWalkWeight,false)) {FinishInertia();return;}\n    }')
    return t
edit(files[2],caller)
def header(t):
    t=replace(t,'     * ArmsResponseTimeSeconds and ArmsBlendToNormalDurationSeconds apply equally\n     * to both arms; -1 inherits the corresponding core value. Hold is shared.\n     * Zero response or hold plus blend zero bypasses that region only. */','     * Zero response or hold plus blend zero disables inertia. */')
    t=replace(t,'UPARAM(DisplayName="Core Response Time Seconds") ','')
    t=replace(t,'UPARAM(DisplayName="Core Blend To Normal Duration Seconds") ','')
    t=replace(t,'float Alpha=1.f,\n        UPARAM(meta=(ClampMin="-1")) float ArmsResponseTimeSeconds=-1.f,\n        UPARAM(meta=(ClampMin="-1")) float ArmsBlendToNormalDurationSeconds=-1.f);','float Alpha=1.f);')
    return t
edit(files[3],header)
for name in files[:4]:
    dest=backup/'shared'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/name,dest)
print('SPLIT_BACKUP',backup)
print('Restored shared response/blend, original clock consumption, retirement and caller ordering.')
