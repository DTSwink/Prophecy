#include "ProphecyLimbColorLibrary.h"
#include "ProphecyLimbColorNames.h"
#include "ProphecyAgent.h"
#include "Components/SkinnedMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Texture2D.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/Float16Color.h"

UProphecyLimbColorState::UProphecyLimbColorState()
{
    PrimaryComponentTick.bCanEverTick=false;
    for(auto& C:Colors)C=FLinearColor::Transparent;
}
bool UProphecyLimbColorState::Bind(AProphecyAgent* Agent)
{
    using namespace ProphecyLimbColors;
    TInlineComponentArray<USkinnedMeshComponent*> Meshes(Agent);
    TArray<TPair<USkinnedMeshComponent*,UMaterialInterface*>,TInlineAllocator<2>> Pending;
    for(auto* Mesh:Meshes)
    {
        if(Mesh->GetFName()!=TEXT("Mesh") && Mesh->GetFName()!=TEXT("PhysicalMesh"))continue;
        if(!Mesh->GetSkinnedAsset() || Mesh->GetSkinnedAsset()->GetPathName()!=MeshPath)continue;
        if(Bindings.ContainsByPredicate([Mesh](const auto& B){return B.Mesh==Mesh && Mesh->GetMaterial(0)==B.Dynamic;}))continue;
        auto* Source=Mesh->GetMaterial(0);auto* Base=Source?Source->GetMaterial():nullptr;
        if(!Base)return false;
        const FString BasePath=Base->GetPathName();FString Target;
        if(BasePath==TEXT("/Game/Characters/UEFN_Mannequin/Materials/M_UEFN_Mannequin.M_UEFN_Mannequin"))
            Target=TEXT("/Game/_mygame/Materials/LimbColors/M_UEFN_LimbColors.M_UEFN_LimbColors");
        else if(BasePath==TEXT("/Game/Characters/UEFN_Mannequin/Materials/M_UEFN_Mannequin_Masked_Bicolor.M_UEFN_Mannequin_Masked_Bicolor"))
            Target=TEXT("/Game/_mygame/Materials/LimbColors/M_UEFN_Bicolor_LimbColors.M_UEFN_Bicolor_LimbColors");
        else return false;
        auto* Parent=LoadObject<UMaterialInterface>(nullptr,*Target);
        if(!Parent)return false;
        Pending.Emplace(Mesh,Parent);
    }
    if(Pending.IsEmpty())return !Bindings.IsEmpty();
    if(!Palette)
    {
        Palette=UTexture2D::CreateTransient(PaletteSize,1,PF_FloatRGBA);
        if(!Palette)return false;
        Palette->SRGB=false;Palette->Filter=TF_Nearest;
        Palette->AddressX=TA_Clamp;Palette->AddressY=TA_Clamp;
        auto& Mip=Palette->GetPlatformData()->Mips[0];
        auto* Data=static_cast<FFloat16Color*>(Mip.BulkData.Lock(LOCK_READ_WRITE));
        for(int32 I=0;I<PaletteSize;++I)Data[I]=FFloat16Color(Colors[I]);
        Mip.BulkData.Unlock();Palette->UpdateResource();
    }
    for(const auto& P:Pending)
    {
        auto* Original=P.Key->GetMaterial(0);
        auto* Dynamic=UMaterialInstanceDynamic::Create(P.Value,this);
        Dynamic->CopyMaterialUniformParameters(Original);
        Dynamic->SetTextureParameterValue(TEXT("ProphecyLimbPalette"),Palette);
        FProphecyLimbColorBinding B;B.Mesh=P.Key;B.Original=Original;B.Dynamic=Dynamic;Bindings.Add(B);
        P.Key->SetMaterial(0,Dynamic);
    }
    return true;
}
void UProphecyLimbColorState::Set(int32 Region,const FLinearColor& Color)
{
    if(Colors[Region]==Color)return;
    Colors[Region]=Color;
    auto* Data=new FFloat16Color[ProphecyLimbColors::PaletteSize];
    for(int32 I=0;I<ProphecyLimbColors::PaletteSize;++I)Data[I]=FFloat16Color(Colors[I]);
    auto* Rect=new FUpdateTextureRegion2D(0,0,0,0,ProphecyLimbColors::PaletteSize,1);
    Palette->UpdateTextureRegions(0,1,Rect,sizeof(FFloat16Color)*ProphecyLimbColors::PaletteSize,sizeof(FFloat16Color),reinterpret_cast<uint8*>(Data),
        [](uint8* Bytes,const FUpdateTextureRegion2D* Region){delete[] reinterpret_cast<FFloat16Color*>(Bytes);delete Region;});
}
void UProphecyLimbColorState::Restore()
{
    for(int32 I=Bindings.Num()-1;I>=0;--I)
    {
        auto& B=Bindings[I];if(auto* Mesh=B.Mesh.Get();Mesh && Mesh->GetMaterial(0)==B.Dynamic)Mesh->SetMaterial(0,B.Original);
    }
    Bindings.Reset();Palette=nullptr;
}
void UProphecyLimbColorState::OnComponentDestroyed(bool bDestroyingHierarchy)
{
    Restore();Super::OnComponentDestroyed(bDestroyingHierarchy);
}
bool UProphecyLimbColorLibrary::SetLimbColor(AProphecyAgent* Agent,FName BoneName,FLinearColor Color)
{
    const int32 Region=ProphecyLimbColors::Bones().Find(BoneName)+1;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || Region==0
        || !FMath::IsFinite(Color.R) || !FMath::IsFinite(Color.G) || !FMath::IsFinite(Color.B) || !FMath::IsFinite(Color.A))return false;
    Color.A=FMath::Clamp(Color.A,0.f,1.f);
    auto* State=Agent->FindComponentByClass<UProphecyLimbColorState>();
    if(Color.A==0.f && !State)return true;
    const bool Created=!State;
    if(Created){State=NewObject<UProphecyLimbColorState>(Agent);Agent->AddInstanceComponent(State);State->RegisterComponent();}
    if(!State->Bind(Agent)){if(Created)State->DestroyComponent();return false;}
    State->Set(Region,Color);
    return true;
}
bool UProphecyLimbColorLibrary::ResetLimbColor(AProphecyAgent* Agent,FName BoneName)
{
    if(!IsInGameThread() || !IsValid(Agent))return false;
    if(!BoneName.IsNone())return SetLimbColor(Agent,BoneName,FLinearColor::Transparent);
    if(auto* State=Agent->FindComponentByClass<UProphecyLimbColorState>())State->DestroyComponent();
    return true;
}
TArray<FName> UProphecyLimbColorLibrary::GetLimbColorBones(){return ProphecyLimbColors::Bones();}
