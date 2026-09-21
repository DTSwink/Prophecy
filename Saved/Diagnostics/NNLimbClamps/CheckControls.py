import unreal

# Verify reflection on the native CDO, restoring values without touching scene assets.
actor = unreal.get_default_object(unreal.ProphecyNNLocomotionManager)
names = ('clamp_hand', 'clamp_foot', 'clamp_calf', 'hand_clamp_length_multiplier', 'foot_clamp_length_multiplier', 'calf_clamp_length_multiplier')
original = {name: actor.get_editor_property(name) for name in names}
try:
    assert actor.get_editor_property('clamp_hand') is True
    assert actor.get_editor_property('hand_clamp_length_multiplier') == 1.0
    for name in ('clamp_hand', 'clamp_foot', 'clamp_calf'):
        actor.set_editor_property(name, False)
        assert actor.get_editor_property(name) is False
        actor.set_editor_property(name, True)
        assert actor.get_editor_property(name) is True
    for name in ('hand_clamp_length_multiplier', 'foot_clamp_length_multiplier', 'calf_clamp_length_multiplier'):
        actor.set_editor_property(name, 1.25)
        assert actor.get_editor_property(name) == 1.25
    print('NN_LIMB_CLAMP_CONTROLS_PASS')
finally:
    for name, value in original.items():
        actor.set_editor_property(name, value)
