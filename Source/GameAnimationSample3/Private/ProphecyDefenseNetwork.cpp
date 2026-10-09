#include "ProphecyDefenseNetwork.h"
#include "NNE.h"
#include "NNEModelData.h"
#include "NNERuntimeCPU.h"
#include "Modules/ModuleManager.h"
#include "Misc/FileHelper.h"
#include "UObject/StrongObjectPtr.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

// Separate from retained network allocations so old Live Coding instances keep
// their old contract. New metadata is latched together with new model bytes.
static TMap<const FProphecyDefenseNetwork*,bool> ExactForearmModels;

struct FProphecyDefenseNetwork::FState
{
    TStrongObjectPtr<UNNEModelData> Data;
    TSharedPtr<UE::NNE::IModelInstanceCPU> Instance;
    int32 InputWidth=0, OutputWidth=0, Batch=0;
    bool bOutputShapeChecked=false;
    bool Shape(int32 Count)
    {
        if (Count<1 || Count>1024 || !Instance) return false;
        if (Batch==Count) return true;
        const uint32 Dimensions[]={uint32(Count),uint32(InputWidth)};
        const auto Shape=UE::NNE::FTensorShape::Make(MakeArrayView(Dimensions,2));
        if (Instance->SetInputTensorShapes(MakeArrayView(&Shape,1))!=UE::NNE::EResultStatus::Ok) return false;
        // ORT leaves a dynamic batch's output shape unresolved until RunSync.
        Batch=Count;bOutputShapeChecked=false;return true;
    }
};
FProphecyDefenseNetwork::FProphecyDefenseNetwork()=default;
FProphecyDefenseNetwork::~FProphecyDefenseNetwork(){ExactForearmModels.Remove(this);}
bool FProphecyDefenseNetwork::UsesExactForearms() const{return ExactForearmModels.Contains(this);}
void FProphecyDefenseNetwork::SwapWith(FProphecyDefenseNetwork& Other)
{
    if(this==&Other)return;
    const bool A=UsesExactForearms(),B=Other.UsesExactForearms();
    Swap(State,Other.State);
    if(B)ExactForearmModels.Add(this,true);else ExactForearmModels.Remove(this);
    if(A)ExactForearmModels.Add(&Other,true);else ExactForearmModels.Remove(&Other);
}
bool FProphecyDefenseNetwork::Initialize(const FString& Filename,int32 InputWidth,int32 OutputWidth,FString& Error)
{
    Error.Reset();
    if (!IsInGameThread() || InputWidth<=0 || OutputWidth<=0)
    { Error=TEXT("Defense model initialization requires valid dimensions and the game thread.");return false; }
    TArray64<uint8> Bytes;
    if (!FFileHelper::LoadFileToArray(Bytes,*Filename)) { Error=TEXT("Cannot read defense model: ")+Filename;return false; }
    bool ExactForearms=false;
    const FString Name=FPaths::GetCleanFilename(Filename);
    if(Name==TEXT("prophecy_parry_upper.onnx") || Name==TEXT("prophecy_dodge_upper.onnx"))
    {
        const FString Metadata=FPaths::GetPath(Filename)/(Name.Contains(TEXT("parry"))?TEXT("parry_checkpoint.json"):TEXT("dodge_checkpoint.json"));
        if(FPaths::FileExists(Metadata))
        {
            FString Text;TSharedPtr<FJsonObject> Document;
            if(!FFileHelper::LoadFileToString(Text,*Metadata) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Document) || !Document)
            {Error=TEXT("Invalid defense checkpoint metadata: ")+Metadata;return false;}
            Document->TryGetBoolField(TEXT("exact_forearms"),ExactForearms);
        }
    }
    FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));
    auto Runtime=UE::NNE::GetRuntime<INNERuntimeCPU>(TEXT("NNERuntimeORTCpu"));
    auto Next=MakeUnique<FState>();
    Next->Data.Reset(NewObject<UNNEModelData>());
    Next->Data->Init(TEXT("onnx"),TConstArrayView64<uint8>(Bytes.GetData(),Bytes.Num()));
    if (!Runtime.IsValid() || Runtime->CanCreateModelCPU(Next->Data.Get())!=UE::NNE::EResultStatus::Ok)
    { Error=TEXT("ORT CPU cannot create the saved defense model.");return false; }
    const auto Model=Runtime->CreateModelCPU(Next->Data.Get());
    Next->Instance=Model ? Model->CreateModelInstanceCPU() : nullptr;
    Next->InputWidth=InputWidth;Next->OutputWidth=OutputWidth;
    if (!Next->Instance) { Error=TEXT("Cannot create the defense model instance.");return false; }
    auto Matches=[](TConstArrayView<UE::NNE::FTensorDesc> Descs,int32 Width)
    {
        if (Descs.Num()!=1 || Descs[0].GetDataType()!=ENNETensorDataType::Float) return false;
        const auto Dims=Descs[0].GetShape().GetData();
        return Dims.Num()==2 && Dims[0]==-1 && Dims[1]==Width;
    };
    if (!Matches(Next->Instance->GetInputTensorDescs(),InputWidth) || !Matches(Next->Instance->GetOutputTensorDescs(),OutputWidth))
    { Error=TEXT("Defense model tensor descriptors do not match the float32 batch contract.");return false; }
    if (!Next->Shape(1)) { Error=TEXT("Defense model shape does not match its contract.");return false; }
    State=MoveTemp(Next);
    if(ExactForearms)ExactForearmModels.Add(this,true);else ExactForearmModels.Remove(this);
    return true;
}

#include "ProphecyDefenseCheckpoint.inl"
bool FProphecyDefenseNetwork::SetBatch(int32 Count) { return State && State->Shape(Count); }
bool FProphecyDefenseNetwork::Run(TConstArrayView<float> Input,TArrayView<float> Output)
{
    if (!State || State->Batch<=0 || Input.Num()!=State->Batch*State->InputWidth || Output.Num()!=State->Batch*State->OutputWidth) return false;
    const UE::NNE::FTensorBindingCPU In{const_cast<float*>(Input.GetData()),uint64(Input.Num())*sizeof(float)};
    const UE::NNE::FTensorBindingCPU Out{Output.GetData(),uint64(Output.Num())*sizeof(float)};
    if (State->Instance->RunSync(MakeArrayView(&In,1),MakeArrayView(&Out,1))!=UE::NNE::EResultStatus::Ok) return false;
    if (!State->bOutputShapeChecked)
    {
        const auto Shapes=State->Instance->GetOutputTensorShapes();
        if (Shapes.Num()!=1 || Shapes[0].Volume()!=uint64(State->Batch)*uint64(State->OutputWidth)) { State->Batch=0;return false; }
        State->bOutputShapeChecked=true;
    }
    return true;
}
