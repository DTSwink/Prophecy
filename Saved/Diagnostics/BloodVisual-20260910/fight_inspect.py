import unreal,builtins,json
s=builtins._blood_visual;w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor);r=[]
for a in actors:
 item={'actor':a.get_path_name(),'class':a.get_class().get_path_name()}
 if isinstance(a,unreal.ProphecyAgent):
  item['jolt']=a.is_jolt_physical_animation_enabled()
  item['meshes']=[{'path':c.get_path_name(),'visible':c.is_visible(),'sim':c.is_simulating_physics(),'collision':str(c.get_collision_enabled())} for c in a.get_components_by_class(unreal.SkeletalMeshComponent)]
 if isinstance(a,unreal.ProphecyBloodTexturePaintManager):item['pairs']=[{'clean':str(p.clean_material),'blood':str(p.blood_material)} for p in a.blood_enabled_material_pairs]
 if 'DecalManager' in a.get_class().get_name():
  for p in ('paint manager','paint_manager','floor'):
   try:item[p]=str(a.get_editor_property(p))
   except:pass
 r.append(item)
(s['out']/'fight-ownership.json').write_text(json.dumps(r,indent=2));print('FIGHT_OWNERS',w.get_path_name(),json.dumps(r))
