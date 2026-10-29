"""Keep Epic's volume bindings; crop the simulated density in world space."""
target=ROOT+'/M_GasSmoke'
m=unreal.load_asset(target)
if not m:
 source=unreal.load_asset('/NiagaraFluids/Materials/Grid3D/M_3DGas_Base')
 assert source,'Epic native gas material missing'
 m=unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset('M_GasSmoke',ROOT,source)
assert m

def crop_output(material_property,tag):
 original=LIB.get_material_property_input_node(m,material_property)
 assert original,'Missing Epic volume output '+str(material_property)
 if original.get_editor_property('desc')==tag:return
 output=LIB.get_material_property_input_node_output_name(m,material_property)
 position=node(m,unreal.MaterialExpressionWorldPosition)
 plane=node(m,unreal.MaterialExpressionVectorParameter,parameter_name='CropPlane',default_value=unreal.LinearColor(0,0,1,-300))
 feather=scalar(m,65,'CropFeather')
 gain=scalar(m,1,'SmokeRenderDensity')
 cropped=custom(m,'return D*Gain*smoothstep(0,max(1,Feather),dot(P,Plane.xyz)+Plane.a);',{'D':original,'P':position,'Plane':plane,'Feather':feather,'Gain':gain})
 cropped.set_editor_property('desc',tag)
 assert LIB.connect_material_expressions(original,output,cropped,'D')
 # Vector parameters default to RGB: use RGBA to retain the plane offset.
 assert LIB.connect_material_expressions(plane,'RGBA',cropped,'Plane')
 assert LIB.connect_material_property(cropped,'',material_property)

crop_output(unreal.MaterialProperty.MP_SUBSURFACE_COLOR,'ColdSmokeExtinctionCrop')
emission=LIB.get_material_property_input_node(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
if emission:crop_output(unreal.MaterialProperty.MP_EMISSIVE_COLOR,'ColdSmokeEmissionCrop')
save(m)
receipt=out/'smoke-system.json'
if receipt.exists():receipt.unlink()
unreal.SystemLibrary.execute_console_command(None,'Scene.FinalizeSmoke')
assert receipt.exists() and json.loads(receipt.read_text(encoding='utf-8-sig'))['saved'],'Cold smoke system preparation failed'
print('COLD_SMOKE_MATERIAL_AND_SYSTEM_READY')
