#pragma once
class AProphecyAgent;
namespace ProphecyRootFacing
{
// An impulse owns an unwrapped stopping heading until explicit facing supersedes it.
void Impulse(const AProphecyAgent* Agent);
void Explicit(const AProphecyAgent* Agent);
bool IsImpulseOwned(const AProphecyAgent* Agent);
}
