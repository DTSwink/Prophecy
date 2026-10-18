import unreal
folder='/Game/_mygame/BombGenerated/'
source=unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/Materials/Bomb')
chain=[source]
while isinstance(chain[-1],unreal.MaterialInstanceConstant):chain.append(chain[-1].get_editor_property('parent'))
assert isinstance(chain[-1],unreal.Material)
assert not unreal.EditorAssetLibrary.does_asset_exist(folder+'M_BombBurn'),'Prepared material already exists'
master=unreal.EditorAssetLibrary.duplicate_asset(chain[-1].get_path_name(),folder+'M_BombBurn')
master.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
master.set_editor_property('opacity_mask_clip_value',.333)
master.set_editor_property('two_sided',True)
lib=unreal.MaterialEditingLibrary
def make(cls,x,y):return lib.create_material_expression(master,cls,x,y)
colour=make(unreal.MaterialExpressionVertexColor,-800,800)
remaining=make(unreal.MaterialExpressionScalarParameter,-800,1000)
remaining.set_editor_property('parameter_name','FuseRemaining');remaining.set_editor_property('default_value',1.)
one=make(unreal.MaterialExpressionConstant,-800,1200);one.set_editor_property('r',1.)
zero=make(unreal.MaterialExpressionConstant,-800,1400);zero.set_editor_property('r',0.)
mask=make(unreal.MaterialExpressionIf,-400,800)
lib.connect_material_expressions(colour,'R',mask,'A');lib.connect_material_expressions(remaining,'',mask,'B')
lib.connect_material_expressions(zero,'',mask,'A > B');lib.connect_material_expressions(one,'',mask,'A == B');lib.connect_material_expressions(one,'',mask,'A < B')
assert lib.connect_material_property(mask,'',unreal.MaterialProperty.MP_OPACITY_MASK)
lib.connect_material_property(zero,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
lib.recompile_material(master)
unreal.EditorAssetLibrary.save_loaded_asset(master)
parent=master
for i,original in enumerate(reversed(chain[:-1])):
 name='MI_BombBurn' if original==source else 'MI_BombBurnParent_'+str(i)
 instance=unreal.EditorAssetLibrary.duplicate_asset(original.get_path_name(),folder+name)
instance_count=len(chain)-1
# Clone in order to retain every texture/switch override in the glTF parent chain.
parent=master
for i,original in enumerate(reversed(chain[:-1])):
 name='MI_BombBurn' if original==source else 'MI_BombBurnParent_'+str(i)
 instance=unreal.load_asset(folder+name)
 lib.set_material_instance_parent(instance,parent)
 lib.update_material_instance(instance);unreal.EditorAssetLibrary.save_loaded_asset(instance)
 parent=instance
print('Prepared fuse material preserving',instance_count,'instance override layers:',parent)
import pathlib
exec(pathlib.Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/BombFuse/VerifyMaterial.py').read_text(),{})
