from pathlib import Path
p=Path('Saved/Diagnostics/ArmedSpineHitch/capture_after.py');s=p.read_text(encoding='utf-8').replace("tag='armed_spine_after'","tag='armed_forearm_after'")
pos=s.index("exec(compile(src,")
s=s[:pos]+'''src=src.replace("   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):", "   sword=a.call_method('GetHeldSword')\\n   sm=sword.get_component_by_class(unreal.StaticMeshComponent) if sword else None\\n   if sm:r['sword']=tr(sm.get_world_transform())\\n   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):")
'''+s[pos:]
Path('Saved/Diagnostics/ArmedSpineHitch/capture_forearm_after.py').write_text(s,encoding='utf-8')
