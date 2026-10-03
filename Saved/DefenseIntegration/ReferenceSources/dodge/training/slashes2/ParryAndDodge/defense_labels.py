"""Training-label merges; raw labels retain the actual blocking side."""
RAW_TO_TYPE = {
    0: 'dodge_regular', 1: 'dodge_idle_safe',
    16: 'parry_weapon', 17: 'parry_weapon',
    18: 'block_standard', 19: 'block_standard',
    20: 'block_alt1', 21: 'block_alt2',
    22: 'block_leg', 23: 'block_leg',
}
PARRY_TYPES = ('parry_weapon', 'block_standard', 'block_alt1', 'block_alt2', 'block_leg')
BLOCKING_CHAIN = {
    16: ('blade',), 17: ('blade',),
    18: ('upperarm_l', 'lowerarm_l', 'hand_l'),
    19: ('upperarm_r', 'lowerarm_r', 'hand_r'),
    20: ('upperarm_l', 'lowerarm_l', 'hand_l'),
    21: ('upperarm_r', 'lowerarm_r', 'hand_r'),
    22: ('thigh_l', 'calf_l', 'foot_l', 'ball_l'),
    23: ('thigh_r', 'calf_r', 'foot_r', 'ball_r'),
}
SWORDLESS_RAW_TYPES = frozenset((19, 21))


def collision_masks(raw_kind, collider_names):
    """Names here are anatomical; the legacy hand_r weapon must be named blade.

    Never replace the missing sword with an anatomical-hand-sized weapon or
    silently count the legacy 86-cm blade as a hand.
    """
    if raw_kind not in RAW_TO_TYPE:
        raise ValueError(f'Unknown defense label {raw_kind}')
    allowed = BLOCKING_CHAIN.get(raw_kind, ())
    present = [name != 'blade' or raw_kind not in SWORDLESS_RAW_TYPES
               for name in collider_names]
    blocking = [exists and name in allowed for name, exists in zip(collider_names, present)]
    harmful = [exists and not block for exists, block in zip(present, blocking)]
    return present, blocking, harmful
