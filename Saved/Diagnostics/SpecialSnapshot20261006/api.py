import unreal
for cls,names in [(unreal.ProphecyAgent,['get_body_magnetization_settings','get_physical_feedback_tolerance','set_body_magnetization','set_physical_feedback_tolerance','set_locomotion_foot_clamp']),(unreal.ProphecyJointDampingLibrary,['set_jolt_joint_angular_damping','get_jolt_joint_angular_damping'])]:
 for name in names:
  print(name,getattr(cls,name).__doc__)
