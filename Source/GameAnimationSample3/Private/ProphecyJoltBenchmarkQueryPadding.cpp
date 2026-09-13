#include "ProphecyJoltBenchmarkQueryPadding.h"

#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/DefaultValueHelper.h"
#include "Misc/Parse.h"
#include "UObject/ObjectKey.h"

namespace ProphecyJolt::BenchmarkQueryPadding
{
namespace
{
constexpr const TCHAR* Name = TEXT("p.aabbtree.DynamicTreeBoundingBoxPadding");
struct FControl
{
    FObjectKey Owner;
    TWeakObjectPtr<UWorld> World;
    IConsoleVariable* Variable = nullptr;
    EConsoleVariableFlags OriginalFlags = ECVF_Default;
    IConsoleVariable::FResolvedContext SetContext{ECVF_SetByConstructor, NAME_None};
    float Original = 0, Applied = 0;
    bool bOwned = false;
    TSharedPtr<FJsonObject> Report;
};
FControl Control;
bool Fail(FString& OutError, const FString& Message)
{
    OutError = Message;
    if (Control.Report) Control.Report->SetStringField(TEXT("error"), Message);
    return false;
}
}

bool Begin(const UObject& Owner, UWorld& World, FString& OutError)
{
    OutError.Reset();
    if (!FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchApplyNativeQueryPadding"))) return true;
    if (!IsInGameThread() || World.WorldType != EWorldType::Game || World.bIsTearingDown)
        return Fail(OutError, TEXT("Native query padding requires the benchmark's live Game world and game thread."));
    if (Control.bOwned)
        return Control.Owner == FObjectKey(&Owner) && Control.World.Get() == &World
            ? true : Fail(OutError, TEXT("Native query padding already belongs to another benchmark world."));
    Control.Report = MakeShared<FJsonObject>();
    Control.Report->SetBoolField(TEXT("requested"), true);
    Control.Report->SetBoolField(TEXT("applied"), false);
    Control.Report->SetBoolField(TEXT("restored"), false);
    Control.Report->SetStringField(TEXT("owner"), Owner.GetPathName());
    Control.Report->SetStringField(TEXT("world"), World.GetPathName());
    Control.Report->SetStringField(TEXT("scope"), TEXT("Explicit NNJoltCrowd-only native broadphase-padding application before fixture loads; no geometry/filter/cadence change. Public explicit-priority CVar setter preserves the original priority and tag; original value and flags restored for the exact owner. This works without Shipping console/ExecCmds support."));
    FString Methods, Requested;
    float Value = 0;
    if (!FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchMethods="), Methods, false)
        || Methods != TEXT("NNJoltCrowd")
        || !FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchQueryTreePaddingCm="), Requested)
        || !FDefaultValueHelper::ParseFloat(Requested, Value) || !FMath::IsFinite(Value) || Value < 0 || Value > 1000)
        return Fail(OutError, TEXT("Native padding requires sole NNJoltCrowd and a finite explicit PhysicsBenchQueryTreePaddingCm in [0,1000]."));
    IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name);
    if (!Variable || Variable->TestFlags(ECVF_ReadOnly))
        return Fail(OutError, TEXT("Native padding CVar is missing or read-only."));
    Control.Owner = FObjectKey(&Owner);
    Control.World = &World;
    Control.Variable = Variable;
    Control.Original = Variable->GetFloat();
    if (!FMath::IsFinite(Control.Original))
        return Fail(OutError, TEXT("Native padding's original value is nonfinite; no value was changed."));
    Control.OriginalFlags = Variable->GetFlags();
    // UE5.7 refuses implicit replacement of the constructor-priority value. Resolve a tagged
    // current setting once, but use the explicitly supported constructor priority for defaults.
    const EConsoleVariableFlags Priority = EConsoleVariableFlags(Control.OriginalFlags & ECVF_SetByMask);
    IConsoleVariable::FSetContext Context(Priority, NAME_None);
    if (Priority != ECVF_SetByConstructor)
    {
        Context.PriorityMode = IConsoleVariable::FSetContext::EPriorityMode::ReplaceCurrent;
        Context.TagMode = IConsoleVariable::FSetContext::ETagMode::ReplaceCurrent;
    }
    Control.SetContext = Variable->ResolveContext(Context);
    if ((Control.SetContext.Flags & ECVF_SetByMask) != Priority)
        return Fail(OutError, TEXT("Native query padding could not resolve the original setting priority; no value was changed."));
    Control.Applied = Value;
    Control.Report->SetNumberField(TEXT("original_value_cm"), Control.Original);
    Control.Report->SetNumberField(TEXT("original_flags"), uint32(Control.OriginalFlags));
    Control.bOwned = true; // Ensure a failed setter/readback still reaches exact restoration.
    Variable->Set(*FString::Printf(TEXT("%.9g"), double(Value)), Control.SetContext);
    Control.Report->SetNumberField(TEXT("applied_value_cm"), Variable->GetFloat());
    Control.Report->SetNumberField(TEXT("applied_flags"), uint32(Variable->GetFlags()));
    if (!FMath::IsNearlyEqual(Variable->GetFloat(), Value, 1.e-4f) || Variable->GetFlags() != Control.OriginalFlags)
        return Fail(OutError, TEXT("Native query padding application/readback did not preserve the current priority and flags."));
    Control.Report->SetBoolField(TEXT("applied"), true);
    return true;
}

bool Restore(const UObject& Owner, FString& OutError)
{
    OutError.Reset();
    if (!Control.bOwned || Control.Owner != FObjectKey(&Owner)) return true;
    if (!IsInGameThread()) return Fail(OutError, TEXT("Native query padding restoration requires its owning game thread."));
    IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name);
    if (!Variable || Variable != Control.Variable)
        return Fail(OutError, TEXT("Owned padding CVar identity changed; no unrelated variable was modified."));
    const bool bUnchanged = !Control.Report->GetBoolField(TEXT("applied"))
        || (FMath::IsNearlyEqual(Variable->GetFloat(), Control.Applied, 1.e-4f)
            && Variable->GetFlags() == Control.OriginalFlags);
    Control.Report->SetNumberField(TEXT("before_restore_value_cm"), Variable->GetFloat());
    Control.Report->SetNumberField(TEXT("before_restore_flags"), uint32(Variable->GetFlags()));
    Variable->SetFlags(Control.OriginalFlags);
    Variable->Set(*FString::Printf(TEXT("%.9g"), double(Control.Original)), Control.SetContext);
    const bool bRestored = FMath::IsNearlyEqual(Variable->GetFloat(), Control.Original, 1.e-4f)
        && Variable->GetFlags() == Control.OriginalFlags;
    Control.Report->SetNumberField(TEXT("restored_value_cm"), Variable->GetFloat());
    Control.Report->SetNumberField(TEXT("restored_flags"), uint32(Variable->GetFlags()));
    Control.Report->SetBoolField(TEXT("restored"), bRestored);
    Control.bOwned = !bRestored;
    if (!bRestored) return Fail(OutError, TEXT("Native padding failed to restore its original value/flags."));
    if (!bUnchanged) return Fail(OutError, TEXT("Owned padding changed externally before restoration; original value/flags restored."));
    return true;
}

TSharedPtr<FJsonObject> ToJson()
{
    if (Control.Report) return Control.Report;
    auto Value = MakeShared<FJsonObject>();
    Value->SetBoolField(TEXT("requested"), false);
    Value->SetBoolField(TEXT("applied"), false);
    return Value;
}
}
