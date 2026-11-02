#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <fstream>
#include <iostream>
int main(int argc,char** argv)
{
    if(argc!=2)return 2;
    JPH::RegisterDefaultAllocator();JPH::Factory::sInstance=new JPH::Factory;JPH::RegisterTypes();
    int count=0,failed=0;std::ifstream input(argv[1]);input>>count;
    for(int i=0;i<count;++i)
    {
        int n=0;input>>n;JPH::ConvexHullShapeSettings s;s.mHullTolerance=0;s.mMaxConvexRadius=0;
        for(int j=0;j<n;++j){float x,y,z;input>>x>>y>>z;s.mPoints.emplace_back(x,y,z);}
        auto result=s.Create();std::cout<<i<<" "<<(result.HasError()?result.GetError().c_str():"PASS")<<"\n";
        failed+=result.HasError();
    }
    JPH::UnregisterTypes();delete JPH::Factory::sInstance;JPH::Factory::sInstance=nullptr;
    return failed?1:0;
}
