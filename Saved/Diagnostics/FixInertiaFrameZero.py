from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp');s=p.read_text(encoding='utf-8');s=s.replace('Output=E->Frame==0?E->Output:Step(E->Output,Authored,E->Delta,E->AngularDelta,L,R);','''if(E->Frame==0)
            {
                if(L!=0)Output.SetLocation(E->Output.GetLocation());
                if(R!=0)Output.SetRotation(E->Output.GetRotation());
            }
            else Output=Step(E->Output,Authored,E->Delta,E->AngularDelta,L,R);''');p.write_text(s,encoding='utf-8')
