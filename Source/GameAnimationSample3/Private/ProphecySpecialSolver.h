#pragma once
class AProphecyAgent;
namespace ProphecySpecialSolver
{
bool IsActive(const AProphecyAgent* Agent);
void AttackChanged(AProphecyAgent* Agent, bool Active);
void DefenseChanged(AProphecyAgent* Agent, bool Active);
void Remove(const AProphecyAgent* Agent);
}
