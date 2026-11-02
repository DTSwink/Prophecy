#pragma once
#include "CoreMinimal.h"

class FJsonObject;

enum class EProphecyFootIKNNWarmup : uint8 { All, Stream, Continuation };

// Frozen Foot IK Run181751 + Upper82500 recurrence. One object per serialized
// solver owner; no global manager mutation, Python process, or fixed worker.
// Prepare is serial-owner safe on either GT or the owning worker. Do not call
// Prepare concurrently with generation, cancellation or another preparation.
// Initialize/Generate run on the serial owning thread. Private
// engine-ORT CPU sessions use one thread/no spinning. No UObject is retained;
// destruction is safe on the retiring worker after inference ends.
// Native NN points/axes/roots remain lab metres/Y-up throughout this boundary.
class FProphecyFootIKNN
{
public:
    struct FGenerateTiming
    {
        double TotalSeconds=0,ParseSeconds=0,InitializeSeconds=0,TensorSeconds=0,OrtSeconds=0,PoseSeconds=0,SerializeSeconds=0;
        int32 Inferences=0;
    };
    FProphecyFootIKNN();
    ~FProphecyFootIKNN();
    FProphecyFootIKNN(const FProphecyFootIKNN&)=delete;
    FProphecyFootIKNN& operator=(const FProphecyFootIKNN&)=delete;
    bool Prepare(const FString& SettingsJson,FString& Error);
    // Create only the caller's graph sessions without running inference or
    // changing recurrent history. Other graphs remain available lazily.
    bool PrewarmSessions(FString& Error,EProphecyFootIKNNWarmup Mode=EProphecyFootIKNNWarmup::All);
    // Output is a K.decode-compatible source. Coupled surfaces need only the
    // five initial policy poses; offline stairs require their complete course.
    bool Initialize(FString& OutSourceJson,FString& Error);
    // frames=2: canonical surface_nn.Stream.step response. Initial/reset calls
    // encode BOTH seeds; ordinary calls retain current + previous policy state.
    // frames>2: independent /resume continuation for canonical Handoff.prepare,
    // returning a complete K.decode source with its exact supplied first pose.
    bool Generate(const FString& RequestJson,FString& OutResponseJson,FString& Error,FGenerateTiming* Timing=nullptr);
    // Native consumers can take the exact generated object without formatting
    // and reparsing its thousands of numeric values. Public JSON stays above.
    bool GenerateResult(const FString& RequestJson,TSharedPtr<FJsonObject>& OutResponse,FString& Error,FGenerateTiming* Timing=nullptr,const TFunction<bool()>& Superseded={});
    // Thread-safe, checked between warmup rows and immediately around RunSync.
    // A currently executing NNE call may finish; no following inference starts.
    void Cancel();
private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
