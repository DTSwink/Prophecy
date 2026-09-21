import unreal
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
cdo=unreal.get_default_object(bp.generated_class())
for name in ['attack_list','melee_list','slash_list','AttackList','MeleeList','SlashList','attack list','melee list','slash list']:
    try: print('FOUND', name, list(cdo.get_editor_property(name)))
    except Exception: pass
