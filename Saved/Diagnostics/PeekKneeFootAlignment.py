print('capture',knee_foot_alignment_capture.n,'done',knee_foot_alignment_capture.done,'info',knee_foot_alignment_capture.info)
print('actors',[(a.get_name(),bool(a.read_nn_future_world_pose())) for a in (knee_foot_alignment_capture.actors or [])])
