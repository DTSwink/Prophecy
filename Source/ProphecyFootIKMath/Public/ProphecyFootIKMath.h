#pragma once
#include "HAL/Platform.h"

namespace ProphecyFootIKMath
{
struct FOperation
{
    const wchar_t* Name;
    double (*Unary)(double);
    double (*Binary)(double,double);
};
// Same implementation/operation order as the lab's V8 13.6 math. The table and
// function pointers live for the module lifetime; a VM owns no math state.
PROPHECYFOOTIKMATH_API const FOperation* Operations(int& Count);
}
