"""Editor-facing names without renaming serialized native function references."""
import unreal


def apply():
    function = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyAgent:GetPoseReferenceMesh')
    if function is None:
        unreal.log_warning('Physical mesh node label: native getter is not loaded')
        return False
    for key, value in {
        'DisplayName': 'Get Physical Mesh',
        'ToolTip': 'Returns the skeletal mesh used for this agent\'s physical body. In manual pose mode this is PhysicalMesh; otherwise it is the inherited agent mesh.',
    }.items():
        if unreal.EditorAssetLibrary.get_metadata_tag(function, key) != value:
            unreal.EditorAssetLibrary.set_metadata_tag(function, key, value)
    return unreal.EditorAssetLibrary.get_metadata_tag(function, 'DisplayName') == 'Get Physical Mesh'
