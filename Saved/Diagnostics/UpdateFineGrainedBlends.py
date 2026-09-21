from pathlib import Path
root=Path(__file__).resolve().parents[2]
def edit(name,old,new):
    p=root/name
    s=p.read_text(encoding='utf-8-sig')
    assert old in s,(name,old)
    p.write_text(s.replace(old,new),encoding='utf-8')
p='Source/GameAnimationSample3/Private/ProphecyLowerTemperingLibrary.cpp'
edit(p,'FMath::Lerp(Initial.PelvisTranslation,1.f,Alpha),FMath::Lerp(Initial.PelvisRotation,1.f,Alpha)};',
       'FMath::Lerp(Initial.PelvisTranslation,1.f,Alpha),FMath::Lerp(Initial.PelvisRotation,1.f,Alpha),\n            FMath::Lerp(Initial.FeetTranslationZ,1.f,Alpha),FMath::Lerp(Initial.PelvisTranslationZ,1.f,Alpha)};')
for part in ['Feet','Pelvis']:
    edit(p,f'Value->{part}Translation=Sample.{part}Translation;',f'Value->{part}Translation=Sample.{part}Translation;Value->{part}TranslationZ=Sample.{part}TranslationZ;')
    edit(p,f'Value->{part}Translation==1 &&',f'Value->{part}Translation==1 && Value->{part}TranslationZ==1 &&')
    edit(p,f'Initial.{part}Translation==1 &&',f'Initial.{part}Translation==1 && Initial.{part}TranslationZ==1 &&')
    edit(p,f'Shared->Initial.{part}Translation=Shared->Initial.{part}Rotation=1;',f'Shared->Initial.{part}Translation=Shared->Initial.{part}TranslationZ=Shared->Initial.{part}Rotation=1;')
    edit(p,f'Value.{part}Translation=Value.{part}Rotation=1;',f'Value.{part}Translation=Value.{part}TranslationZ=Value.{part}Rotation=1;')
edit(p,'float FeetTranslation, float FeetRotation, float PelvisTranslation, float PelvisRotation)',
       'float FeetTranslation, float FeetRotation, float PelvisTranslation, float PelvisRotation,\n    float FeetTranslationZ, float PelvisTranslationZ)')
edit(p,'{FeetTranslation, FeetRotation, PelvisTranslation, PelvisRotation}',
       '{FeetTranslation, FeetRotation, PelvisTranslation, PelvisRotation, FeetTranslationZ, PelvisTranslationZ}')
edit('Source/GameAnimationSample3/Private/ProphecyAgentResetPhysics.cpp',
     'T.FeetTranslation,T.FeetRotation,T.PelvisTranslation,T.PelvisRotation);',
     'T.FeetTranslation,T.FeetRotation,T.PelvisTranslation,T.PelvisRotation,T.FeetTranslationZ,T.PelvisTranslationZ);')
edit('Source/GameAnimationSample3/Private/ProphecyNNInputDebug.inl',
     'S->FeetTranslation,S->FeetRotation,S->PelvisTranslation,S->PelvisRotation}',
     'S->FeetTranslation,S->FeetRotation,S->PelvisTranslation,S->PelvisRotation,S->FeetTranslationZ,S->PelvisTranslationZ}')
