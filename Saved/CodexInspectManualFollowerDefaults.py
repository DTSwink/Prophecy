import unreal


asset = unreal.EditorAssetLibrary.load_asset(
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent")
generated = asset.generated_class()
cdo = unreal.get_default_object(generated)
print("MANUAL_FOLLOW_CDO_CLASS", generated.get_name())
for property_name in (
        "physical_bones", "physical bones", "manual_nn_pose_application",
        "primary_actor_tick", "physical_drive_settings"):
    try:
        print("MANUAL_FOLLOW_CDO", property_name, cdo.get_editor_property(property_name))
    except Exception as error:
        print("MANUAL_FOLLOW_CDO_ERROR", property_name, error)
