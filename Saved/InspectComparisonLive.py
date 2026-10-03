import unreal
world=unreal.EditorLevelLibrary.get_game_world()
agents=unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for a in agents:
    mesh=a.get_agent_mesh()
    mats=[]
    for i in range(mesh.get_num_materials()):
        m=mesh.get_material(i)
        mats.append(m.get_path_name() if m else 'None')
    print('TEST_AGENT name={} mode={} mats={}'.format(a.get_name(), a.get_simulation_mode(), mats))
