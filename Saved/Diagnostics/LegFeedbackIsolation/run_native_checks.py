import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.NN.PhysicalFeedback+Prophecy.NN.AgentReset.MotionAndWindow')
print('Requested isolated native feedback tests; no PIE or authored asset changes.')
