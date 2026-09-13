#include "ProphecyJoltPoseBatch.h"

#include "Async/ParallelFor.h"

namespace ProphecyJolt::Pose
{
void ComposeBatch(TArrayView<FComposeBatchItem> Items, bool bForceSingleThread)
{
    ParallelFor(TEXT("ProphecyJolt.ComposeCompletedPoses"), Items.Num(), 1, [Items](int32 Index)
    {
        FComposeBatchItem& Item = Items[Index];
        check(Item.Layout && Item.Output);
        Item.bSucceeded = Item.Layout->Compose(Item.BaseLocal, Item.BodyWorld,
            Item.ComponentWorld, *Item.Output, Item.Error);
    }, bForceSingleThread ? EParallelForFlags::ForceSingleThread : EParallelForFlags::None);
}
}
