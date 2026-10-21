#pragma once
#include <array>
#include <cstdint>
#include <vector>
#include <algorithm>

// 2D greedy rectangle partition (Lysenko, 2012); independently implemented.
// Every output rectangle contains only occupied cells. Input is never modified.
namespace BloodRect
{
constexpr int Side = 32;
using Mask = std::array<uint32_t, Side>;
struct Rect
{
    int X, Y, W, H;
    bool operator==(const Rect& B) const { return X==B.X && Y==B.Y && W==B.W && H==B.H; }
};
inline uint32_t Bits(int X, int W)
{
    return (W == 32 ? UINT32_MAX : ((uint32_t(1) << W) - 1)) << X;
}
inline void Mesh(const Mask& Input, std::vector<Rect>& Output)
{
    Mask Rows=Input;
    Output.clear();
    for (int Y=0; Y<Side; ++Y)
    {
        while (Rows[Y])
        {
            int X=0;
            while (!(Rows[Y] & (uint32_t(1)<<X))) ++X;
            int W=1;
            while (X+W<Side && (Rows[Y] & (uint32_t(1)<<(X+W)))) ++W;
            const uint32_t Run=Bits(X,W);
            int H=1;
            while (Y+H<Side && (Rows[Y+H]&Run)==Run) ++H;
            for (int J=0; J<H; ++J) Rows[Y+J]&=~Run;
            Output.push_back({X,Y,W,H});
        }
    }
}
inline bool Exact(const Mask& Input, const std::vector<Rect>& Rects)
{
    Mask Seen{};
    for (const Rect& R:Rects)
    {
        if(R.X<0 || R.Y<0 || R.W<1 || R.H<1 || R.X+R.W>Side || R.Y+R.H>Side) return false;
        uint32_t Run=Bits(R.X,R.W);
        for(int Y=R.Y;Y<R.Y+R.H;++Y)
        {
            if(Seen[Y]&Run) return false;
            Seen[Y]|=Run;
        }
    }
    return Seen==Input;
}
}
