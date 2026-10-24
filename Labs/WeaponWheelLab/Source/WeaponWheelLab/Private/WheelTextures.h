#pragma once
#include "Engine/Texture2D.h"
#include "TextureResource.h"
#include "ImageUtils.h"
#include "ImageCore.h"
#include "UObject/StrongObjectPtr.h"

// Runtime texture filtering, not a second edited copy of the artwork. Slate's
// file-backed dynamic images have only mip 0, which aliases detailed engravings
// at UI sizes. Build the small mip chain once, then let the GPU filter it.
inline TStrongObjectPtr<UTexture2D> LoadWheelIconTexture(const FString& Path)
{
    FImage Source;
    if(!FImageUtils::LoadImage(*Path,Source)) return {};
    TStrongObjectPtr<UTexture2D> Texture(UTexture2D::CreateTransient(Source.SizeX,Source.SizeY,PF_B8G8R8A8));
    if(!Texture.IsValid()) return {};
    Texture->SRGB=true;
    Texture->NeverStream=true;
    Texture->Filter=TF_Trilinear;
    Texture->AddressX=TA_Clamp;
    Texture->AddressY=TA_Clamp;
    auto* Data=Texture->GetPlatformData();
    Data->Mips.Empty();
    for(;;)
    {
        FImage Bytes;
        Source.CopyTo(Bytes,ERawImageFormat::BGRA8,EGammaSpace::sRGB);
        auto* Mip=new FTexture2DMipMap();
        Mip->SizeX=Source.SizeX; Mip->SizeY=Source.SizeY; Mip->SizeZ=1;
        Mip->BulkData.Lock(LOCK_READ_WRITE);
        void* Dest=Mip->BulkData.Realloc(Bytes.RawData.Num());
        FMemory::Memcpy(Dest,Bytes.RawData.GetData(),Bytes.RawData.Num());
        Mip->BulkData.Unlock();
        Data->Mips.Add(Mip);
        if(Source.SizeX==1 && Source.SizeY==1) break;
        FImage Smaller;
        FImageCore::ResizeImageAllocDest(Source,Smaller,FMath::Max(1,Source.SizeX/2),FMath::Max(1,Source.SizeY/2),
            ERawImageFormat::RGBA32F,EGammaSpace::Linear,
            FImageCore::EResizeImageFilter::CubicMitchell | FImageCore::EResizeImageFilter::Flag_AlphaWeighted);
        Source=MoveTemp(Smaller);
    }
    Texture->UpdateResource();
    UE_LOG(LogTemp,Display,TEXT("WHEEL_ICON_TEXTURE %dx%d mips=%d filter=trilinear alpha-weighted"),Data->SizeX,Data->SizeY,Data->Mips.Num());
    return Texture;
}
