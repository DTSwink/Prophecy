#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyClampEase
{
enum class EChannel : uint8 { Foot, Calf, PhysicalCalf, PhysicalFoot, Wrist, Count };
constexpr double Duration = .25; // 15 unpaused authored ticks; opening is immediate.
struct FReduction
{
    float Target=-1,Value=-1,Start=0;
    double Elapsed=0;
    bool Active=false;
    void Request(float Next,float Observed=-1)
    {
        if(Next==Target)return;
        if(Next<0){*this=FReduction{};return;}
        const float From=Value<0?FMath::Max(Next,Observed):Value;
        Target=Next;
        if(Next>=From){Value=Next;Active=false;return;}
        if(Active)
        {
            // Blueprint snapshot blends may supply a new, lower limit every tick.
            // Keep this window's deadline; restarting would stall the tightening.
            const double T=Elapsed/Duration,S=T*T*(3.-2.*T);
            Start=float((Value-Next*S)/(1.-S));
            return;
        }
        // Unlimited / very large ranges start at the actual outgoing deviation,
        // not an arbitrary 1000 cm sentinel that postpones all visible tightening.
        Start=Observed>=0?FMath::Min(From,FMath::Max(Next,Observed)):From;
        Value=Start;Elapsed=0;Active=Start>Next;
    }
    void Advance(double Dt)
    {
        if(!Active)return;
        Elapsed+=Dt;
        if(Elapsed+1.e-8>=Duration){Value=Target;Active=false;return;}
        const double T=Elapsed/Duration;
        Value=FMath::Lerp(Start,Target,float(T*T*(3-2*T)));
    }
};
// Negative means unconstrained. Read pose/physics only when NeedsObservation is true.
bool NeedsObservation(const AProphecyAgent* Agent,EChannel Channel,float Target);
float Resolve(const AProphecyAgent* Agent,EChannel Channel,float Target,float Observed=-1);
float Current(const AProphecyAgent* Agent,EChannel Channel,float Fallback);
void Remove(const AProphecyAgent* Agent);
}
