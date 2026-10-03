import unreal

asset_path = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"
agent_class = unreal.EditorAssetLibrary.load_blueprint_class(asset_path)
defaults = unreal.get_default_object(agent_class)
print("MANUAL_API class={} names={}".format(
    agent_class,
    [name for name in dir(defaults) if "manual" in name.lower() or "future" in name.lower() or "kinematic" in name.lower()]))
print("MANUAL_API_DEFAULT manual={}".format(
    defaults.get_editor_property("manual_nn_pose_application")))
