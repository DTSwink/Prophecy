import unreal
import json

world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
agent=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)[0]
phat=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin')
print('PHAT', phat.get_path_name())
for template in unreal.ObjectIterator():
    if template.get_outer() != phat or template.get_class().get_name() != 'PhysicsConstraintTemplate':
        continue
    instance=template.get_editor_property('DefaultInstance')
    name=str(instance.get_editor_property('ConstraintBone1'))
    if name in ('hand_l','hand_r'):
        print(name, 'parent',instance.get_editor_property('ConstraintBone2'),'pos1',instance.get_editor_property('Pos1'),'pos2',instance.get_editor_property('Pos2'))
