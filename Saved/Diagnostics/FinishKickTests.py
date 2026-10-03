from pathlib import Path
r=Path(__file__).resolve().parents[2]
p=r/'Source/GameAnimationSample3/Private/ProphecyLowerTemperingLibrary.cpp'
s=p.read_text(); a=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyKickTemperingTest'); b=s.index('#endif',a)
block=s[a:b];s=s[:a]+s[b:]; i=s.rindex('#endif');s=s[:i]+block+s[i:];p.write_text(s)
p=r/'Source/GameAnimationSample3/Private/ProphecyJoltSwordFixture.cpp'
s=p.read_text().replace('#include "ProphecySwordAttackCollision.h"','#include "ProphecySwordAttackCollision.h"\n#include "ProphecySwordComponent.h"',1)
s=s.replace('''            ProphecySwordAttackCollision::Begin(Agent,Family);Check(false);
            ProphecySwordAttackCollision::Armed(Agent);''','''            Agent->NotifySwordAttackState(true);
            ProphecySwordAttackCollision::Begin(Agent,Family);Check(false);
            auto* Controller=Agent->FindComponentByClass<UProphecySwordComponent>();
            if (!Controller) return false;
            Controller->RefreshOwnerCollision();
            FProphecyJoltWorldDiagnostics Suppressed;World->GetDiagnostics(Suppressed);
            TestTrue(TEXT("Before Hit sword suppresses owner body pairs"),Suppressed.SuppressedBodyPairCount>Before.SuppressedBodyPairCount);
            ProphecySwordAttackCollision::Armed(Agent);''',1)
s=s.replace('''            ProphecySwordAttackCollision::Hit(Agent);Check(true);
            ProphecySwordAttackCollision::Refresh(Agent);Check(true); // latched through recovery/rebind''','''            ProphecySwordAttackCollision::Hit(Agent);Check(true);
            FProphecyJoltWorldDiagnostics Restored;World->GetDiagnostics(Restored);
            TestEqual(TEXT("Hit restores native owner pairs to normal grip-only exclusions"),Restored.SuppressedBodyPairCount,Before.SuppressedBodyPairCount);
            TestTrue(TEXT("Hit does not end attack context"),Agent->IsSwordAttackActive());
            TestFalse(TEXT("Hit is latched for deferred grip/rebind"),ProphecySwordAttackCollision::SuppressesOwner(Agent));
            Controller->RefreshOwnerCollision();World->GetDiagnostics(Restored);
            TestEqual(TEXT("Refresh after Hit keeps owner collisions restored"),Restored.SuppressedBodyPairCount,Before.SuppressedBodyPairCount);
            ProphecySwordAttackCollision::Refresh(Agent);Check(true); // latched through recovery/rebind''',1)
s=s.replace('''            ProphecySwordAttackCollision::End(Agent);Check(true);
        }
        ProphecySwordAttackCollision::Begin(Agent,TEXT("pike"));Check(false);''','''            Agent->NotifySwordAttackState(false);Check(true);
        }
        ProphecySwordAttackCollision::Begin(Agent,TEXT("pike"));Check(false);''',1)
p.write_text(s)
