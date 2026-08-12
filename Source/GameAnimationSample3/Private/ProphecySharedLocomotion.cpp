// Compile the accepted mover implementation into the Unreal runtime module.
// Keeping one source implementation prevents the standalone and Unreal movers
// from silently diverging.
#include "../../../StandaloneSim/sim_core/src/locomotion.cpp"
