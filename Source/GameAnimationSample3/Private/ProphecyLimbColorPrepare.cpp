#if WITH_EDITOR
#include "ProphecyLimbColorNames.h"
#include "Engine/SkeletalMesh.h"
#include "SkeletalMeshTypes.h"
#include "SkeletalMeshAttributes.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Animation/BoneReference.h"
#include "Editor.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpressionTextureCoordinate.h"
#include "Materials/MaterialExpressionTextureSampleParameter2D.h"
#include "Materials/MaterialExpressionVertexInterpolator.h"
#include "Materials/MaterialExpressionComponentMask.h"
#include "Materials/MaterialExpressionLinearInterpolate.h"
#include "Engine/Texture2D.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace ProphecyLimbColorPrepare
{
uint32 Digest(FMeshDescription& D)
{
    FSkeletalMeshAttributes A(D);const auto Pos=A.GetVertexPositions();const auto W=A.GetVertexSkinWeights();
    uint32 Hash=0;
    for(const auto V:D.Vertices().GetElementIDs())
    {
        const auto P=Pos[V];Hash=FCrc::MemCrc32(&P,sizeof(P),Hash);
        for(const auto B:W.Get(V)){const auto Packed=B.ToInt32();Hash=FCrc::MemCrc32(&Packed,sizeof(Packed),Hash);}
    }
    for(const auto T:D.Triangles().GetElementIDs())for(const auto V:D.GetTriangleVertices(T))
    {const int32 Id=V.GetValue();Hash=FCrc::MemCrc32(&Id,sizeof(Id),Hash);}
    const auto UV=A.GetVertexInstanceUVs();
    for(const auto V:D.VertexInstances().GetElementIDs())for(int32 I=0;I<FMath::Min(UV.GetNumChannels(),ProphecyLimbColors::UVChannel);++I)
    {const auto P=UV.Get(V,I);Hash=FCrc::MemCrc32(&P,sizeof(P),Hash);}
    return Hash;
}
template<class T>T* Add(UMaterial* M)
{return CastChecked<T>(UMaterialEditingLibrary::CreateMaterialExpression(M,T::StaticClass(),-200,0));}
bool Material(const TCHAR* Source,const TCHAR* Name,UTexture2D* Palette)
{
    const FString Folder=TEXT("/Game/_mygame/Materials/LimbColors");
    const FString AssetPath=(Folder/FString(Name))+TEXT(".")+Name;
    if(LoadObject<UMaterial>(nullptr,*AssetPath))return true;
    auto* Original=LoadObject<UMaterial>(nullptr,Source);if(!Original || Original->bUseMaterialAttributes)return false;
    auto* M=Cast<UMaterial>(FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools")).Get().DuplicateAsset(Name,Folder,Original));
    if(!M)return false;
    auto* UV=Add<UMaterialExpressionTextureCoordinate>(M);UV->CoordinateIndex=ProphecyLimbColors::UVChannel;
    auto* Sample=Add<UMaterialExpressionTextureSampleParameter2D>(M);
    Sample->ParameterName=TEXT("ProphecyLimbPalette");Sample->Texture=Palette;Sample->SamplerType=SAMPLERTYPE_LinearColor;
    Sample->MipValueMode=TMVM_MipLevel;Sample->ConstMipValue=0;Sample->Coordinates.Connect(0,UV);
    auto* VS=Add<UMaterialExpressionVertexInterpolator>(M);VS->Input.Connect(0,Sample);
    // Texture output0 is RGB; use a separate alpha interpolator for unmodified limbs.
    auto* Alpha=Add<UMaterialExpressionVertexInterpolator>(M);Alpha->Input.Connect(4,Sample);
    auto* Blend=Add<UMaterialExpressionLinearInterpolate>(M);
    Blend->A=static_cast<const FExpressionInput&>(M->GetEditorOnlyData()->BaseColor);
    Blend->B.Connect(0,VS);Blend->Alpha.Connect(0,Alpha);
    M->GetEditorOnlyData()->BaseColor.Connect(0,Blend);
    M->PostEditChange();M->MarkPackageDirty();
    return true;
}
void Run(const TArray<FString>& Args)
{
    using namespace ProphecyLimbColors;
    if(!GEditor || GEditor->PlayWorld || Args.Num()!=1)return;
    const bool Apply=Args[0]==TEXT("Apply");
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,MeshPath);if(!Mesh)return;
    FString Report=FString::Printf(TEXT("mesh=%s lods=%d materials=%d apply=%d\n"),MeshPath,Mesh->GetLODNum(),Mesh->GetMaterials().Num(),Apply);
    for(int32 L=0;L<Mesh->GetLODNum();++L)
    {
        auto* D=Mesh->GetMeshDescription(L);
        if(!D){Report+=FString::Printf(TEXT("lod%d generated/no source description\n"),L);continue;}
        FSkeletalMeshAttributes A(*D);auto UV=A.GetVertexInstanceUVs();auto Weights=A.GetVertexSkinWeights();
        Report+=FString::Printf(TEXT("lod%d vertices=%d triangles=%d uv=%d hash=%u\n"),L,D->Vertices().Num(),D->Triangles().Num(),UV.GetNumChannels(),Digest(*D));
        if(!Weights.IsValid() || UV.GetNumChannels()>UVChannel){
            Report+=TEXT("Existing extra UV channel; refusing to overwrite.\n");
            FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/LimbMaterials20261006/prepare.txt")));return;
        }
    }
    if(Apply)
    {
        auto* Palette=LoadObject<UTexture2D>(nullptr,TEXT("/Game/_mygame/Materials/LimbColors/T_LimbPalette.T_LimbPalette"));
        if(!Palette){UE_LOG(LogTemp,Error,TEXT("Create the neutral limb palette first"));return;}
        Mesh->Modify();
        {
            FScopedSkeletalMeshPostEditChange Edit(Mesh);
            for(int32 L=0;L<Mesh->GetLODNum();++L)
            {
                auto* D=Mesh->GetMeshDescription(L);if(!D)continue;
                FSkeletalMeshAttributes A(*D);auto UV=A.GetVertexInstanceUVs();auto Weights=A.GetVertexSkinWeights();
                // Pad an unused pre-existing channel with zero, making the digest comparable.
                if(UV.GetNumChannels()<UVChannel)UV.SetNumChannels(UVChannel);
                const uint32 Before=Digest(*D);UV.SetNumChannels(UVChannel+1);
                int32 Counts[PaletteSize]={};
                for(const auto VI:D->VertexInstances().GetElementIDs())
                {
                    float Totals[PaletteSize]={};
                    for(const auto W:Weights.Get(D->GetVertexInstanceVertex(VI)))Totals[Region(Mesh->GetRefSkeleton(),W.GetBoneIndex())]+=W.GetWeight();
                    int32 Best=0;for(int32 I=1;I<PaletteSize;++I)if(Totals[I]>Totals[Best])Best=I;
                    UV.Set(VI,UVChannel,FVector2f((float(Best)+.5f)/PaletteSize,.5f));++Counts[Best];
                }
                const uint32 After=Digest(*D);
                Report+=FString::Printf(TEXT("lod%d before=%u after=%u unchanged_geometry_weights_original_uv=%d regions:"),L,Before,After,Before==After);
                for(int32 I=0;I<PaletteSize;++I)if(Counts[I])Report+=FString::Printf(TEXT(" %d=%d"),I,Counts[I]);
                Report+=TEXT("\n");check(Before==After);Mesh->CommitMeshDescription(L);
            }
        }
        Mesh->MarkPackageDirty();
        const bool A=Material(TEXT("/Game/Characters/UEFN_Mannequin/Materials/M_UEFN_Mannequin.M_UEFN_Mannequin"),TEXT("M_UEFN_LimbColors"),Palette);
        const bool B=Material(TEXT("/Game/Characters/UEFN_Mannequin/Materials/M_UEFN_Mannequin_Masked_Bicolor.M_UEFN_Mannequin_Masked_Bicolor"),TEXT("M_UEFN_Bicolor_LimbColors"),Palette);
        Report+=FString::Printf(TEXT("materials_ready=%d assets_saved=0\n"),A&&B);
    }
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/LimbMaterials20261006/prepare.txt")));
    UE_LOG(LogTemp,Display,TEXT("Limb colors: %s"),*Report);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Editor.PrepareLimbColors"),TEXT("Audit|Apply UEFN limb-color UV and material preparation. Leaves assets unsaved."),FConsoleCommandWithArgsDelegate::CreateStatic(&Run));
}
#endif
