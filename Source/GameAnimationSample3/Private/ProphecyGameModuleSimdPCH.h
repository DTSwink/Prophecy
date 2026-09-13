#pragma once

// Explicit ISA experiments use a module-private PCH. UE 5.7 shared-PCH reuse
// does not include MinCpuArchX64 in its compatibility key.
#include "CoreMinimal.h"
