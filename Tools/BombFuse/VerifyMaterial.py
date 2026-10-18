"""Validate/fix only the derived fuse graph and its copied instance chain."""
import unreal
folder='/Game/_mygame/BombGenerated/'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
master=unreal.load_asset(folder+'M_BombBurn');lib=unreal.MaterialEditingLibrary
nodes=[o for o in unreal.ObjectIterator(unreal.MaterialExpression) if o.get_outer()==master]
def at(cls,x,y):return next(n for n in nodes if isinstance(n,cls) and n.get_editor_property('material_expression_editor_x')==x and n.get_editor_property('material_expression_editor_y')==y)
matches=[n for n in nodes if isinstance(n,unreal.MaterialExpressionComponentMask) and n.get_editor_property('desc')=='Fuse distance from UV1']
if matches:color=matches[0]
else:
 uv=lib.create_material_expression(master,unreal.MaterialExpressionTextureCoordinate,-1100,800)
 uv.set_editor_property('coordinate_index',1)
 color=lib.create_material_expression(master,unreal.MaterialExpressionComponentMask,-1000,800)
 color.set_editor_property('desc','Fuse distance from UV1');color.set_editor_property('r',True);color.set_editor_property('g',False)
 color.set_editor_property('b',False);color.set_editor_property('a',False)
 assert lib.connect_material_expressions(uv,'',color,'')
remaining=at(unreal.MaterialExpressionScalarParameter,-800,1000)
one=at(unreal.MaterialExpressionConstant,-800,1200);zero=at(unreal.MaterialExpressionConstant,-800,1400)
mask=at(unreal.MaterialExpressionIf,-400,800)
def link(src,pin,dst,target):
 names=list(lib.get_material_expression_input_names(dst))
 aliases={'AGreaterThanB':'A > B','AEqualsB':'A == B','ALessThanB':'A < B'}
 if target not in names and target in aliases:target=aliases[target]
 assert lib.connect_material_expressions(src,pin,dst,target),(target,names)
link(color,'',mask,'A');link(remaining,'',mask,'B')
for name,value in [('AGreaterThanB',zero),('AEqualsB',one),('ALessThanB',one)]:link(value,'',mask,name)
attributes=master.get_editor_property('use_material_attributes')
print('USE MATERIAL ATTRIBUTES',attributes)
if attributes:
 original=lib.get_material_property_input_node(master,unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
 original_pin=lib.get_material_property_input_node_output_name(master,unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
 existing=isinstance(original,unreal.MaterialExpressionSetMaterialAttributes) and original.get_editor_property('desc')=='Prophecy fuse mask'
 setter=original if existing else lib.create_material_expression(master,unreal.MaterialExpressionSetMaterialAttributes,200,800)
 setter.set_editor_property('desc','Prophecy fuse mask')
 setter.set_editor_property('attribute_set_types',[unreal.Guid(0x679FFB17,0x2BB5422C,0xAD520483,0x166E0C75),unreal.Guid(0xB769B54D,0xD08D4440,0xABC21BA6,0xCD27D0E2)])
 names=list(lib.get_material_expression_input_names(setter));print('ATTRIBUTE INPUTS',names)
 if not existing:link(original,original_pin,setter,names[0])
 link(mask,'',setter,names[1]);link(zero,'',setter,names[2])
 assert lib.connect_material_property(setter,'',unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
else:
 assert lib.connect_material_property(mask,'',unreal.MaterialProperty.MP_OPACITY_MASK)
 assert lib.connect_material_property(zero,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
# Remove only the obsolete experimental tip nodes from our derived material.
for node in nodes:
 x=node.get_editor_property('material_expression_editor_x');y=node.get_editor_property('material_expression_editor_y')
 if (x,y) in [(-400,1600),(-150,1600),(-600,1600),(-800,1800),(-800,2000),(-800,800)]:
  lib.delete_material_expression(master,node)
master.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
master.set_editor_property('opacity_mask_clip_value',.333)
lib.recompile_material(master);unreal.EditorAssetLibrary.save_loaded_asset(master)
instance=unreal.load_asset(folder+'MI_BombBurn')
while isinstance(instance,unreal.MaterialInstanceConstant):
 overrides=instance.get_editor_property('base_property_overrides')
 print(instance.get_name(),'OVERRIDES',overrides)
 overrides.set_editor_property('override_blend_mode',False)
 overrides.set_editor_property('override_opacity_mask_clip_value',False)
 instance.set_editor_property('base_property_overrides',overrides)
 lib.update_material_instance(instance);unreal.EditorAssetLibrary.save_loaded_asset(instance)
 instance=instance.get_editor_property('parent')
print('FUSE MATERIAL GRAPH VERIFIED')
