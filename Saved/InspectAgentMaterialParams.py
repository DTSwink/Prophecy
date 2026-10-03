import unreal
m=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Materials/M_UEFN_Mannequin.M_UEFN_Mannequin')
print('V',unreal.MaterialEditingLibrary.get_vector_parameter_names(m))
print('S',unreal.MaterialEditingLibrary.get_scalar_parameter_names(m))
