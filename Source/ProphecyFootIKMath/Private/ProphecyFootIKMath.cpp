#include "ProphecyFootIKMath.h"
#include <cmath>
#include <limits>

// UE exposes Precise, not Strict, per-module FP semantics. These MSVC pragmas
// additionally preserve exception-sensitive evaluation and disable contraction,
// matching /fp:strict used by the standalone independent parity probe.
#if defined(_MSC_VER)
#pragma float_control(precise, on, push)
#pragma float_control(except, on)
#pragma fenv_access(on)
#pragma fp_contract(off)
#endif

// Exact V8 13.6 source, kept with its BSD/Sun notices in Tools/FootIK/v8-math.
#include "../../../Tools/FootIK/v8-math/src/base/ieee754.cc"

namespace ProphecyFootIKMath
{
// V8 13.6 src/numbers/ieee754.cc, its default use_std_math_pow path.
static double Pow(double X,double Y)
{
    if(std::isnan(Y)||(std::isinf(Y)&&(X==1||X==-1)))return std::numeric_limits<double>::quiet_NaN();
    if(std::isnan(X))X=std::numeric_limits<double>::quiet_NaN();
    if(Y==2)return X*X;
    if(Y==.5)return std::isinf(X)?std::numeric_limits<double>::infinity():std::sqrt(X+0.0);
    return std::pow(X,Y);
}
const FOperation* Operations(int& Count)
{
    namespace M=v8::base::ieee754;
    static const FOperation Values[]={
        {L"sin",M::sin,nullptr},{L"cos",M::cos,nullptr},{L"tan",M::tan,nullptr},
        {L"acos",M::acos,nullptr},{L"asin",M::asin,nullptr},{L"atan",M::atan,nullptr},
        {L"atan2",nullptr,M::atan2},{L"exp",M::exp,nullptr},{L"log",M::log,nullptr},{L"log1p",M::log1p,nullptr},
        {L"pow",nullptr,Pow}
    };
    Count=int(sizeof(Values)/sizeof(Values[0]));return Values;
}
}
#if defined(_MSC_VER)
#pragma float_control(pop)
#endif
