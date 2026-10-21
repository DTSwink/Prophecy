"""Fix logical-tip tolerance on the new companion material only."""
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve active Play'
m=unreal.load_asset('/Game/_mygame/sword/geometry/M_Sword_BloodDepth')
nodes=[n for n in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if n.get_outer()==m]
assert len(nodes)==1
position=[n for n in unreal.ObjectIterator(unreal.MaterialExpressionPreSkinnedPosition) if n.get_outer()==m]
assert len(position)==1
interpolators=[n for n in unreal.ObjectIterator(unreal.MaterialExpressionVertexInterpolator) if n.get_outer()==m]
assert len(interpolators)<=1
interpolator=interpolators[0] if interpolators else unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionVertexInterpolator,220,1200)
assert unreal.MaterialEditingLibrary.connect_material_expressions(position[0],'',interpolator,'')
assert unreal.MaterialEditingLibrary.connect_material_expressions(interpolator,'',nodes[0],'LocalPosition')
nodes[0].set_editor_property('code','float d = saturate(Depth); float t = (LocalPosition.z - BaseZ) / max(abs(BladeLength), 0.0001); return (d > 0 && t >= 0 && t >= 1-d) ? 1.0 : 0.0;')
unreal.MaterialEditingLibrary.recompile_material(m)
assert unreal.EditorAssetLibrary.save_loaded_asset(m,only_if_is_dirty=False)
print('Blade-depth material finalized; logical tip tolerance removed')
