#pragma once
#include <Jolt/Jolt.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/Body/BodyLockMulti.h>
#include <type_traits>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/Shape/Shape.h>
#include <algorithm>
#include <cmath>

namespace ProphecyExplosion
{
// x is squared normalised distance. Default exponent keeps the original arithmetic/pow-free path.
inline double Weight(double x, double Exponent)
{
    if (!(x >= 0.0 && x < 1.0)) return 0.0;
    const double edge = 1.0 - x;
    const double Base = 1.0 + 25.0 * x;
    if (Exponent == 2.0) return edge * edge / Base;
    if (Exponent == 0.0) return edge * edge;
    // Reciprocal base avoids overflow for large positive exponents; tiny tails can underflow to zero.
    return edge * edge * std::pow(1.0 / Base, Exponent * 0.5);
}
struct FResult { int Candidates = 0, Affected = 0; };
struct FIgnoreImpact { void operator()(const JPH::Body&, JPH::Vec3Arg, JPH::RVec3Arg) const {} };
struct FImpact
{
    JPH::BodyID Body;
    JPH::Vec3 Impulse;
    double ArrivalSeconds = 0;
    uint64_t Generation = 0;
};
struct FWave
{
    JPH::RVec3 Origin;
    double StartSeconds = 0, EndSeconds = 0;
    float RadiusMetres = 0, VelocityMetresPerSecond = 0;
    JPH::Array<FImpact> Impacts;
    size_t Next = 0;
    double RadiusAt(double Seconds) const
    { return std::clamp((Seconds-StartSeconds)*VelocityMetresPerSecond,0.0,double(RadiusMetres)); }
};
struct FScheduler
{
    JPH::Array<FWave> Waves;
    void Add(FWave&& Wave)
    {
        Waves.push_back(std::move(Wave));
    }
    // One cursor check per active wave, then only the impacts that are due. No repeated body query.
    template<class TGeneration, class TImpact = FIgnoreImpact>
    int Advance(JPH::PhysicsSystem& Physics,double Now,TGeneration&& Generation, TImpact Notify = {})
    {
        if(Waves.empty()) return 0;
        JPH::BodyIDVector Wake;
        int Applied=0;
        JPH::BodyIDVector Due;
        for(auto& Wave:Waves)
        {
            size_t End=Wave.Next;
            while(End<Wave.Impacts.size() && Wave.Impacts[End].ArrivalSeconds<=Now) ++End;
            if(End==Wave.Next) continue;
            Due.clear();Due.reserve(End-Wave.Next);
            for(size_t I=Wave.Next;I<End;++I) Due.push_back(Wave.Impacts[I].Body);
            // Take each shared mutex once for this due batch, preserving impact order.
            JPH::BodyLockMultiWrite Locks(Physics.GetBodyLockInterface(),Due.data(),int(Due.size()));
            for(int I=0;Wave.Next<End;++I)
            {
                const auto& Hit=Wave.Impacts[Wave.Next++];
                auto* Ptr=Locks.GetBody(I);
                if(!Ptr || !Ptr->IsInBroadPhase()) continue;
                auto& Body=*Ptr;
                if(!Body.IsDynamic() || Generation(Body)!=Hit.Generation) continue;
                const auto Velocity=Body.GetLinearVelocity()+Hit.Impulse*Body.GetMotionProperties()->GetInverseMass();
                if(!std::isfinite(Velocity.LengthSq())) continue;
                Body.AddImpulse(Hit.Impulse);
                Notify(Body,Hit.Impulse,Wave.Origin);
                if(!Body.IsActive()) Wake.push_back(Hit.Body);
                ++Applied;
            }
        }
        // Different concurrent waves may wake the same body; keep a single activation per ID.
        if(Waves.size()>1 && Wake.size()>1)
        {
            std::sort(Wake.begin(),Wake.end(),[](auto A,auto B){return A.GetIndexAndSequenceNumber()<B.GetIndexAndSequenceNumber();});
            Wake.erase(std::unique(Wake.begin(),Wake.end()),Wake.end());
        }
        if(!Wake.empty()) Physics.GetBodyInterface().ActivateBodies(Wake.data(),int(Wake.size()));
        Waves.erase(std::remove_if(Waves.begin(),Waves.end(),[Now](const FWave& Wave){return Now>=Wave.EndSeconds;}),Waves.end());
        if(Waves.empty()) JPH::Array<FWave>().swap(Waves);
        return Applied;
    }
};

// Query first, then mutate: never activate bodies while a broadphase collector holds its tree lock.
// The caller owns an idle world; locks also make this safe for concurrent read-only users.
template<class TAccept, class TImpact = FIgnoreImpact>
FResult Apply(JPH::PhysicsSystem& Physics, JPH::RVec3Arg Origin, float RadiusMetres,
    float PressureImpulse, float FalloffExponent, TAccept&& Accept, const JPH::BroadPhaseLayerFilter& LayerFilter = {}, FWave* Scheduled=nullptr, TImpact Notify = {})
{
    FResult Result;
    if (!(std::isfinite(RadiusMetres) && RadiusMetres > 0 && std::isfinite(PressureImpulse) && PressureImpulse > 0)
        || !std::isfinite(FalloffExponent) || FalloffExponent < 0
        || !std::isfinite(Origin.GetX()) || !std::isfinite(Origin.GetY()) || !std::isfinite(Origin.GetZ())
        || !std::isfinite(JPH::Vec3(Origin).LengthSq())) return Result;
    JPH::AllHitCollisionCollector<JPH::CollideShapeBodyCollector> Hits;
    Physics.GetBroadPhaseQuery().CollideSphere(JPH::Vec3(Origin), RadiusMetres, Hits, LayerFilter);
    // Immediate mutation/wake order stays stable. Scheduled snapshots need only the
    // final deadline/ID ordering below, avoiding a second sort of the same recipients.
    auto End=Hits.mHits.end();
    if(!Scheduled)
    {
        std::sort(Hits.mHits.begin(),End,[](auto A,auto B){return A.GetIndexAndSequenceNumber()<B.GetIndexAndSequenceNumber();});
        End=std::unique(Hits.mHits.begin(),End);
    }
    JPH::BodyIDVector Wake;
    const double RadiusSquared = double(RadiusMetres) * RadiusMetres;
    const int Count=int(End-Hits.mHits.begin());
    if(Scheduled) Scheduled->Impacts.reserve(Count);
    auto Process=[&](auto& Locks)
    {
    for (int I=0;I<Count;++I)
    {
        ++Result.Candidates;
        auto* Ptr=Locks.GetBody(I);
        if (!Ptr || !Ptr->IsInBroadPhase()) continue;
        auto& Body=*Ptr;
        if (!Body.IsDynamic()) continue;
        const uint64_t Generation=Accept(Body);
        if (!Generation) continue;
        const auto Delta=Body.GetCenterOfMassPosition()-Origin;
        const double D2=Delta.LengthSq();
        if (!(D2 > 1.e-16 && D2 < RadiusSquared)) continue;
        const double Distance=std::sqrt(D2);
        const JPH::Vec3 Direction(Delta / Distance);
        const auto LocalDirection=Body.GetRotation().Conjugated()*Direction;
        const auto Size=Body.GetShape()->GetLocalBounds().GetSize();
        // Projected oriented collision-bounds area, m^2; compounds are counted once.
        const double Area=std::abs(double(LocalDirection.GetX()))*Size.GetY()*Size.GetZ()
            +std::abs(double(LocalDirection.GetY()))*Size.GetX()*Size.GetZ()
            +std::abs(double(LocalDirection.GetZ()))*Size.GetX()*Size.GetY();
        const double Magnitude=double(PressureImpulse)*Weight(D2/RadiusSquared,FalloffExponent)*Area;
        const auto Impulse=Direction*float(Magnitude);
        const auto Velocity=Body.GetLinearVelocity()+Impulse*Body.GetMotionProperties()->GetInverseMass();
        if (!(Magnitude>0 && std::isfinite(Magnitude) && std::isfinite(Impulse.LengthSq()) && std::isfinite(Velocity.LengthSq()))) continue;
        if constexpr(std::is_const_v<std::remove_reference_t<decltype(Body)>>)
            Scheduled->Impacts.push_back({Hits.mHits[I],Impulse,Scheduled->StartSeconds+Distance/Scheduled->VelocityMetresPerSecond,Generation});
        else
        {
            Body.AddImpulse(Impulse);
            Notify(Body,Impulse,Origin);
            if (!Body.IsActive()) Wake.push_back(Hits.mHits[I]);
        }
        ++Result.Affected;
    }
    };
    // Read-only snapshots can share locks; immediate impulses require exclusive locks.
    // Release both before activation (which takes its own locks).
    if(Scheduled)
    {
        JPH::BodyLockMultiRead Locks(Physics.GetBodyLockInterface(),Hits.mHits.data(),Count);
        Process(Locks);
    }
    else
    {
        JPH::BodyLockMultiWrite Locks(Physics.GetBodyLockInterface(),Hits.mHits.data(),Count);
        Process(Locks);
    }
    if(Scheduled)
    {
        auto& Impacts=Scheduled->Impacts;
        std::sort(Impacts.begin(),Impacts.end(),[](const FImpact& A,const FImpact& B)
        {
            return A.ArrivalSeconds!=B.ArrivalSeconds ? A.ArrivalSeconds<B.ArrivalSeconds
                : A.Body.GetIndexAndSequenceNumber()<B.Body.GetIndexAndSequenceNumber();
        });
        // Snapshot values are identical for duplicate leaves in the caller-owned idle world.
        Impacts.erase(std::unique(Impacts.begin(),Impacts.end(),[](const FImpact& A,const FImpact& B)
            {return A.Body==B.Body;}),Impacts.end());
        Result.Affected=int(Impacts.size());
    }
    if (!Wake.empty()) Physics.GetBodyInterface().ActivateBodies(Wake.data(), int(Wake.size()));
    return Result;
}
}
