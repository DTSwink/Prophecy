#include "../Source/BloodDecalLab/RectangleMesher.h"
#include <cstdio>

int main()
{
    std::vector<BloodRect::Rect> Rects;
    Rects.reserve(512);
    int Cases=0, Failures=0;
    // Exhaust every 4x4 occupancy pattern, including the top bit/right/bottom edges.
    for(int Offset : {0,14,28})
        for(uint32_t Pattern=0;Pattern<65536;++Pattern)
        {
            BloodRect::Mask M{};
            for(int Y=0;Y<4;++Y)
                M[Y+Offset]=((Pattern>>(4*Y))&15u)<<Offset;
            const auto Original=M;
            BloodRect::Mesh(M,Rects);
            Failures+=!BloodRect::Exact(M,Rects) || M!=Original;
            ++Cases;
        }
    BloodRect::Mask Full{};
    Full.fill(UINT32_MAX);
    BloodRect::Mesh(Full,Rects);
    Failures+=!BloodRect::Exact(Full,Rects) || Rects.size()!=1;
    ++Cases;
    BloodRect::Mask Checker{};
    for(int Y=0;Y<32;++Y) Checker[Y]=(Y&1)?0xaaaaaaaa:0x55555555;
    BloodRect::Mesh(Checker,Rects);
    Failures+=!BloodRect::Exact(Checker,Rects) || Rects.size()!=512;
    ++Cases;
    std::printf("{\"cases\":%d,\"failures\":%d,\"scope\":\"native production-lab header; exhaustive 4x4 masks at three offsets, full region and checkerboard\"}\n",Cases,Failures);
    return Failures?1:0;
}
