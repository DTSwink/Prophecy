from pathlib import Path
import hashlib,json,difflib,datetime
r=Path.cwd();d=r/'Saved/JoltMigration/ORTThreadingR6Draft'
paths=['Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp','Saved/JoltMigration/PackagedNNCrowdDraft/Run-NNCrowdPackage.ps1','Saved/JoltMigration/PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py']
old={p:(r/p).read_text(encoding='utf-8-sig') for p in paths};new=dict(old);cpp,ps,py=paths

def change(p,a,b):
 assert new[p].count(a)==1,(p,a[:90],new[p].count(a))
 new[p]=new[p].replace(a,b)

change(cpp,'#include "Misc/Parse.h"','#include "Misc/Parse.h"\n#include "Misc/ConfigCacheIni.h"\n#include "Modules/ModuleManager.h"\n#include "UObject/Class.h"\n#include "UObject/UObjectGlobals.h"\n#include "UObject/UnrealType.h"')
change(cpp,'struct FProphecyNNJoltBenchmarkState','''struct FProphecyNNOrtThreadingSnapshot
{
    bool bUseGlobalPool = false;
    int32 IntraOpThreads = 0, InterOpThreads = 0;
    uint8 ExecutionMode = 0;
    TSharedPtr<FJsonObject> Json;

    bool HasSameTypedSettings(const FProphecyNNOrtThreadingSnapshot& Other) const
    {
        return bUseGlobalPool == Other.bUseGlobalPool && IntraOpThreads == Other.IntraOpThreads
            && InterOpThreads == Other.InterOpThreads && ExecutionMode == Other.ExecutionMode;
    }
};

struct FProphecyNNJoltBenchmarkState''')
change(cpp,'    int32 PhysicalFeedbackMode = 0;','    int32 PhysicalFeedbackMode = 0;\n    TSharedPtr<FJsonObject> OrtThreadingBeforeModels, OrtThreadingAfterModels;')
helper=(r/'Saved/JoltMigration/ORTThreadingResearchDraft/CaptureOrtCpuThreadingSettings.cpp').read_text(encoding='utf-8-sig')
helper=helper[helper.index('bool CaptureOrtCpuThreadingSettings'):]
helper=helper.replace('!FModuleManager::Get().IsModuleLoaded(TEXT("NNERuntimeORT")))','!FModuleManager::Get().IsModuleLoaded(TEXT("NNERuntimeORT")) || !GConfig)')
helper=helper.replace('Capture requires the initialized ORT module on the game thread.','Capture requires the initialized ORT module and config cache on the game thread.')
helper=helper.replace('bool CaptureOrtCpuThreadingSettings(FJsonObject& Out, FString& Error)','bool CaptureOrtCpuThreadingSettings(FProphecyNNOrtThreadingSnapshot& Snapshot, FString& Error)')
helper=helper.replace('    Out.SetStringField(TEXT("settings_class"), SettingsClass->GetPathName());','''    Snapshot.bUseGlobalPool = Global->GetPropertyValue_InContainer(Values);
    Snapshot.IntraOpThreads = Intra->GetPropertyValue_InContainer(Values);
    Snapshot.InterOpThreads = Inter->GetPropertyValue_InContainer(Values);
    Snapshot.ExecutionMode = ExecutionValue;
    if (Snapshot.IntraOpThreads < 0 || Snapshot.InterOpThreads < 0)
    { Error = TEXT("Native ORT thread counts cannot be negative."); return false; }
    const FString ExecutionName = Execution->Enum->GetNameStringByValue(ExecutionValue);
    if (ExecutionName != (ExecutionValue == 0 ? TEXT("SEQUENTIAL") : TEXT("PARALLEL")))
    { Error = TEXT("Native ORT execution enum labels differ from reviewed UE 5.7."); return false; }
    Snapshot.Json = MakeShared<FJsonObject>();
    FJsonObject& Out = *Snapshot.Json;
    Out.SetStringField(TEXT("settings_class"), SettingsClass->GetPathName());''')
helper=helper.replace('Global->GetPropertyValue_InContainer(Values));','Snapshot.bUseGlobalPool);').replace('Intra->GetPropertyValue_InContainer(Values));','Snapshot.IntraOpThreads);').replace('Inter->GetPropertyValue_InContainer(Values));','Snapshot.InterOpThreads);')
change(cpp,'constexpr double NNHz = 30.0, WorldHz = 60.0;','constexpr double NNHz = 30.0, WorldHz = 60.0;\n\n'+helper)
change(cpp,'    auto* Manager = GetWorld()->SpawnActorDeferred<AProphecyNNLocomotionManager>(' ,'''    // Read-only provenance outside timed samples. Module startup already selected the environment
    // pool options; capture the loaded CDO without recreating it or touching session settings.
    FProphecyNNOrtThreadingSnapshot OrtBeforeModels, OrtAfterModels;
    if (!ProphecySterileBench::NNJolt::CaptureOrtCpuThreadingSettings(OrtBeforeModels, Error)) return false;
    auto* Manager = GetWorld()->SpawnActorDeferred<AProphecyNNLocomotionManager>(''')
change(cpp,'    Manager->FinishSpawning(FTransform::Identity);\n    auto Pending = MakeShared<FProphecyNNJoltBenchmarkState>();','''    Manager->FinishSpawning(FTransform::Identity);
    if (!ProphecySterileBench::NNJolt::CaptureOrtCpuThreadingSettings(OrtAfterModels, Error)) return false;
    if (!OrtBeforeModels.HasSameTypedSettings(OrtAfterModels))
    { Error = TEXT("ORT threading settings changed while creating the actual NN models."); return false; }
    auto Pending = MakeShared<FProphecyNNJoltBenchmarkState>();
    Pending->OrtThreadingBeforeModels = MoveTemp(OrtBeforeModels.Json);
    Pending->OrtThreadingAfterModels = MoveTemp(OrtAfterModels.Json);''')
change(cpp,'    auto Scope = MakeShared<FJsonObject>();\n    Scope->SetNumberField(TEXT("nn_hz"), NN::NNHz);','''    if (!NNJoltState->OrtThreadingBeforeModels.IsValid() || !NNJoltState->OrtThreadingAfterModels.IsValid())
    { Error = TEXT("Actual NN scope lost its ORT threading initialization evidence."); return false; }
    auto Scope = MakeShared<FJsonObject>();
    Scope->SetObjectField(TEXT("ort_cpu_threading_before_models"), NNJoltState->OrtThreadingBeforeModels);
    Scope->SetObjectField(TEXT("ort_cpu_threading_after_models"), NNJoltState->OrtThreadingAfterModels);
    Scope->SetNumberField(TEXT("nn_hz"), NN::NNHz);''')
change(ps,"    [ValidateRange(0,32)][int]$JoltWorkerThreads=7,","    [ValidateRange(0,32)][int]$JoltWorkerThreads=7,\n    [ValidateSet(0,1,2)][int]$OrtIntraOpThreads=0, # 0 preserves packaged settings; 1/2 are Development startup factors.")
change(ps,"if($package.kind -ne 'ProphecyPackagedNNCrowd' -or $package.success -ne $true){throw 'Expected a successful packaged NN result.'}","if($package.kind -ne 'ProphecyPackagedNNCrowd' -or $package.success -ne $true){throw 'Expected a successful packaged NN result.'}\nif($OrtIntraOpThreads -ne 0 -and $package.configuration -ne 'Development'){throw 'ORT startup overrides are Development-only; Shipping Game compiles out -ini overrides.'}")
change(ps,"if($PauseChaos){$arguments+=' -PhysicsBenchPauseChaos'}","""if($PauseChaos){$arguments+=' -PhysicsBenchPauseChaos'}
$ortOverrideTuple=$null
if($OrtIntraOpThreads -ne 0){
    $ortOverrideTuple="(bUseGlobalThreadPool=False,IntraOpNumThreads=$OrtIntraOpThreads,InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)"
    $arguments+=' -ini:Engine:[/Script/NNERuntimeORT.NNERuntimeORTSettings]:GameThreadingOptions='+$ortOverrideTuple
}""")
change(ps,"'--padding',$padding,'--feedback-mode',$FeedbackMode)","'--padding',$padding,'--feedback-mode',$FeedbackMode,'--ort-intra-op-threads',\"$OrtIntraOpThreads\")")
change(ps,"    processId=$pidOwned;exitCode=$exitCode;timedOut=$timedOut;ownedKillIssued=$killIssued;timeoutSeconds=$TimeoutSeconds","    ortIntraOpThreadsOverride=$OrtIntraOpThreads;ortStartupTuple=$ortOverrideTuple\n    processId=$pidOwned;exitCode=$exitCode;timedOut=$timedOut;ownedKillIssued=$killIssued;timeoutSeconds=$TimeoutSeconds")
change(py,'    feedback_mode = {"Original": 0, "PreparedSerial": 1, "PreparedParallel": 2}[args.feedback_mode]','''    feedback_mode = {"Original": 0, "PreparedSerial": 1, "PreparedParallel": 2}[args.feedback_mode]
    ort_override = args.ort_intra_op_threads
    require(isinstance(ort_override, int) and not isinstance(ort_override, bool) and ort_override in (0, 1, 2),
            "ORT intra-op factor must be 0 (no override), 1 or 2.")
    require(ort_override == 0 or args.configuration == "Development",
            "ORT startup overrides are supported only by Development Game.")
    expected_ort_intra = ort_override or 1
''')
insert='''    ort_rows = []
    for phase in ("before_models", "after_models"):
        ort = scope.get("ort_cpu_threading_" + phase)
        require(isinstance(ort, dict), f"Missing ORT selected threading capture {phase}.")
        require(ort.get("settings_class") == "/Script/NNERuntimeORT.NNERuntimeORTSettings"
                and ort.get("selected_options") == "GameThreadingOptions",
                f"Wrong ORT settings identity/target {phase}.")
        require(ort.get("use_global_thread_pool") is False
                and ort.get("session_worker_execution_directly_observed") is False
                and ort.get("commandline_ini_overrides_enabled") is (args.configuration == "Development"),
                f"ORT pool/capture/build scope differs {phase}.")
        for key, expected in (("intra_op_num_threads", expected_ort_intra),
                              ("inter_op_num_threads", 1), ("execution_mode", 0)):
            value = ort.get(key)
            require(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and value == expected,
                    f"Unexpected ORT {key} {phase}.")
        require(ort.get("execution_mode_name") == "SEQUENTIAL", f"ORT graph mode changed {phase}.")
        present = ort.get("config_value_present")
        require(isinstance(present, bool)
                and ((present and isinstance(ort.get("config_value"), str))
                     or (not present and "config_value" not in ort)), f"Malformed ORT raw config capture {phase}.")
        if ort_override:
            expected_tuple = ("(bUseGlobalThreadPool=False,IntraOpNumThreads=" + str(ort_override)
                              + ",InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)")
            require(present and ort["config_value"] == expected_tuple,
                    f"ORT startup override was not captured exactly {phase}.")
        ort_rows.append(ort)
    for key in ("use_global_thread_pool", "intra_op_num_threads", "inter_op_num_threads", "execution_mode"):
        require(ort_rows[0][key] == ort_rows[1][key], f"ORT typed settings changed while creating models: {key}.")
'''
change(py,'    capsule_policies = scope["root_capsule_policies"]',insert+'    capsule_policies = scope["root_capsule_policies"]')
change(py,'                world_tick=case["world_tick"], snapshotSha256=package["snapshotSha256"],','''                ort_intra_op_threads_override=ort_override, ort_expected_intra_op_threads=expected_ort_intra,
                ort_cpu_threading_before_models=ort_rows[0], ort_cpu_threading_after_models=ort_rows[1],
                world_tick=case["world_tick"], snapshotSha256=package["snapshotSha256"],''')
change(py,'    parser.add_argument("--paused", action="store_true")','    parser.add_argument("--ort-intra-op-threads", type=int, choices=(0, 1, 2), default=0)\n    parser.add_argument("--paused", action="store_true")')
items=[];patch=[]
for path in paths:
 name=Path(path).name;dest=d/name;dest.write_text(new[path],encoding='utf-8',newline='\n')
 patch.extend(difflib.unified_diff(old[path].splitlines(keepends=True),new[path].splitlines(keepends=True),fromfile='a/'+path,tofile='b/'+path))
 items.append({'active':str(r/path),'draft':str(dest),'active_sha256':hashlib.sha256((r/path).read_bytes()).hexdigest(),'draft_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(d/'Proposed.patch').write_text(''.join(patch),encoding='utf-8')
(d/'Evidence.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'DRAFT_ONLY_NOT_COMPILED_OR_RUN_IN_UE','files':items},indent=2),encoding='utf-8')
print(json.dumps({'files':len(items),'patch_lines':len(''.join(patch).splitlines()),'draft':str(d)}))
