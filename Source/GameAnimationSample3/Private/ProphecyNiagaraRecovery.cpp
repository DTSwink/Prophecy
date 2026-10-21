// Explicit editor recovery command. Never invoked by gameplay.
#if WITH_EDITOR
#include "CoreMinimal.h"
#include "Factories.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "NiagaraSystem.h"
#include "UObject/Package.h"

namespace ProphecyNiagaraRecovery
{
class FFactory final : public FCustomizableTextObjectFactory
{
public:
    FFactory():FCustomizableTextObjectFactory(GWarn){}
    UNiagaraSystem* System=nullptr;
protected:
    virtual bool CanCreateClass(UClass* Class,bool& bOmitSubObjects) const override
    {bOmitSubObjects=true;return Class==UNiagaraSystem::StaticClass();}
    virtual void ProcessConstructedObject(UObject* Object) override
    {System=Cast<UNiagaraSystem>(Object);}
};
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.RecoverNiagaraText"),
    TEXT("Recover a Niagara text export into a new package: <file> <package>. Type indices must match this editor session. Does not save or overwrite packages."),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args)
    {
        if(Args.Num()!=2 || !Args[1].StartsWith(TEXT("/Game/_mygame/bomb/")) || !FPackageName::IsValidLongPackageName(Args[1]))return;
        if(FindPackage(nullptr,*Args[1]) || FPackageName::DoesPackageExist(Args[1]))
        {UE_LOG(LogTemp,Error,TEXT("Niagara recovery refuses to overwrite %s"),*Args[1]);return;}
        FString Text;if(!FFileHelper::LoadFileToString(Text,*Args[0]))return;
        if(!Text.StartsWith(TEXT("Begin Object Class=/Script/Niagara.NiagaraSystem ")))return;
        auto* Package=CreatePackage(*Args[1]);FFactory Factory;
        Factory.ProcessBuffer(Package,RF_Public|RF_Standalone|RF_Transactional,Text);
        if(!Factory.System){UE_LOG(LogTemp,Error,TEXT("Niagara recovery import failed"));return;}
        Factory.System->PostEditImport();Factory.System->PostEditChange();
        Factory.System->RequestCompile(true);Factory.System->MarkPackageDirty();
        UE_LOG(LogTemp,Display,TEXT("Niagara recovery imported %s; compilation requested, not saved"),*Factory.System->GetPathName());
    }));
static FAutoConsoleCommand Check(TEXT("Prophecy.Editor.CheckRecoveredNiagara"),TEXT("Check recovered system after shader compilation."),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args)
    {
        if(Args.Num()!=1)return;
        auto* System=FindObject<UNiagaraSystem>(nullptr,*Args[0]);if(!System)return;
        UE_LOG(LogTemp,Display,TEXT("Niagara recovery check: valid=%d ready=%d emitters=%d"),System->IsValid(),System->IsReadyToRun(),System->GetEmitterHandles().Num());
    }));
}
#endif
