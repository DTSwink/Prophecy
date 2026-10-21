"""Union blade-depth coverage with the existing sword blood-paint mask."""
import pathlib,shutil,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
path='/Game/Prophecy/BloodTexturePainting/Generated/_mygame_sword_geometry_M_Sword_BloodPaint'
m=unreal.load_asset(path);lib=unreal.MaterialEditingLibrary
assert m
assert 'BladeBloodDepth' not in [str(n) for n in lib.get_scalar_parameter_names(m)],'Already upgraded; inspect first'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth'
source=pathlib.Path(unreal.Paths.project_content_dir())/(path.removeprefix('/Game/')+'.uasset')
backup=out/'paint-material.before.uasset'
if not backup.exists():shutil.copy2(source,backup)
matches=[]
for n in unreal.ObjectIterator(unreal.MaterialExpressionSaturate):
    if n.get_outer()!=m:continue
    inputs=lib.get_inputs_for_material_expression(m,n)
    if len(inputs)!=1 or not isinstance(inputs[0],unreal.MaterialExpressionMultiply):continue
    parent=inputs[0]
    upstream=lib.get_inputs_for_material_expression(m,parent)
    if any(isinstance(x,unreal.MaterialExpressionTextureSampleParameter2D) and str(x.get_editor_property('parameter_name'))=='BloodMaskRT' for x in upstream):matches.append((n,parent))
assert len(matches)==1,('Expected blood-mask multiply/saturate',matches)
sat,paint=matches[0]
def expr(cls,x,y):return lib.create_material_expression(m,cls,x,y)
def scalar(name,value,y):
    n=expr(unreal.MaterialExpressionScalarParameter,-1800,y)
    n.set_editor_property('parameter_name',name);n.set_editor_property('default_value',value);n.set_editor_property('group','Blade Blood')
    return n
position=expr(unreal.MaterialExpressionPreSkinnedPosition,-1800,1000)
vertex=expr(unreal.MaterialExpressionVertexInterpolator,-1600,1000)
assert lib.connect_material_expressions(position,'',vertex,'')
depth=scalar('BladeBloodDepth',0,1200);base=scalar('BladeBaseLocalZ',0,1400);length=scalar('BladeLengthLocal',1,1600)
mask=expr(unreal.MaterialExpressionCustom,-1300,1000)
mask.set_editor_property('description','Additive blade-depth coverage')
mask.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT1)
inputs=[]
for name in ['LocalPosition','Depth','BaseZ','BladeLength']:
    item=unreal.CustomInput();item.set_editor_property('input_name',name);inputs.append(item)
mask.set_editor_property('inputs',inputs)
mask.set_editor_property('code','float d = saturate(Depth); float t = (LocalPosition.z - BaseZ) / max(abs(BladeLength), 0.0001); return (d > 0 && t >= 0 && t >= 1-d) ? 1.0 : 0.0;')
for n,name in [(vertex,'LocalPosition'),(depth,'Depth'),(base,'BaseZ'),(length,'BladeLength')]:assert lib.connect_material_expressions(n,'',mask,name)
union=expr(unreal.MaterialExpressionMax,-800,700)
union.set_editor_property('desc','Union existing painted blood with accumulated blade depth')
assert lib.connect_material_expressions(paint,'',union,'A')
assert lib.connect_material_expressions(mask,'',union,'B')
assert lib.connect_material_expressions(union,'',sat,'')
lib.recompile_material(m)
assert unreal.EditorAssetLibrary.save_loaded_asset(m,only_if_is_dirty=False)
print('Saved depth/paint union on existing sword blood material; original paint inputs retained')
