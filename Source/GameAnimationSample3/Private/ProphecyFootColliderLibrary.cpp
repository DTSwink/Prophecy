#include "ProphecyFootColliderLibrary.h"
#include "ProphecyFootColliderTrim.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "Engine/World.h"

namespace ProphecyFootColliderTrim
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Settings;
static FDelegateHandle Cleanup;
float Get(const AProphecyAgent* A) { const float* V=Settings.Find(A); return V ? *V : 0.0f; }
}
bool UProphecyFootColliderLibrary::SetFootColliderFrontTrim(AProphecyAgent* Agent,FString& OutError,float TrimCm)
{
    using namespace ProphecyFootColliderTrim;
    OutError.Reset();
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || Agent->GetWorld()->bIsTearingDown || !FMath::IsFinite(TrimCm) || TrimCm<0.0f)
    { OutError=TEXT("A live agent and a finite, nonnegative trim are required."); return false; }
    auto* Component=Agent->GetJoltCharacterComponent();
    if (!Component || !Component->SetFootColliderFrontTrim(TrimCm,OutError)) return false;
    if (TrimCm==0.0f) Settings.Remove(Agent); else Settings.Add(Agent,TrimCm);
    if (!Cleanup.IsValid() && !Settings.IsEmpty())
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Settings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        });
    return true;
}
