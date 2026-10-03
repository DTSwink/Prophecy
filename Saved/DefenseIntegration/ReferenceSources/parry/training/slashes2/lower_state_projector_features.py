from __future__ import annotations


LOWER_STATE_DIM = 41
# The frozen locomotion policy still owns this historical feature width. Slash2
# v2 AEs do not consume it.
ROOT_LOOKAHEAD_DIM = 35
ATTACK_LABEL_DIM = 5
TARGET_HEIGHT_DIM = 1
STATE_CONDITIONED_AE1_DIM = LOWER_STATE_DIM * 3 + TARGET_HEIGHT_DIM
STATE_CONDITIONED_AE11_DIM = (
    LOWER_STATE_DIM * 3 + TARGET_HEIGHT_DIM + ATTACK_LABEL_DIM
)


def ae1_feature_schema() -> dict[str, object]:
    cursor = 0
    schema: dict[str, object] = {
        "kind": "slash2_lower_state_conditioned_transition_projector",
        "prior": "ae1",
        "label_agnostic": True,
        "target_agnostic": True,
        "proposed_delta": {
            "start": cursor,
            "end": cursor + LOWER_STATE_DIM,
            "reference": "held target-frame next lower state minus current state",
            "scored": True,
        },
    }
    cursor += LOWER_STATE_DIM
    schema["previous_lower_state"] = {
        "start": cursor,
        "end": cursor + LOWER_STATE_DIM,
        "reference": "previous lower state in one held target frame",
    }
    cursor += LOWER_STATE_DIM
    schema["current_lower_state"] = {
        "start": cursor,
        "end": cursor + LOWER_STATE_DIM,
        "reference": "current lower state in one held target frame",
    }
    cursor += LOWER_STATE_DIM
    schema["target_height"] = {
        "start": cursor,
        "end": cursor + TARGET_HEIGHT_DIM,
        "reference": "target world Y above the zero-height root/floor plane",
    }
    cursor += TARGET_HEIGHT_DIM
    schema.update(
        {
            "score_start": 0,
            "score_end": LOWER_STATE_DIM,
            "lower_state_dim": LOWER_STATE_DIM,
            "phase_or_frame_input": False,
            "total_dim": cursor,
        }
    )
    if cursor != STATE_CONDITIONED_AE1_DIM:
        raise RuntimeError(
            f"Lower state-conditioned AE1 schema {cursor} != {STATE_CONDITIONED_AE1_DIM}"
        )
    return schema


def feature_schema() -> dict[str, object]:
    cursor = 0
    schema: dict[str, object] = {
        "kind": "slash2_lower_state_conditioned_transition_projector",
        "proposed_delta": {
            "start": cursor,
            "end": cursor + LOWER_STATE_DIM,
            "reference": "held target-frame next lower state minus current state",
            "scored": True,
        },
    }
    cursor += LOWER_STATE_DIM
    schema["previous_lower_state"] = {
        "start": cursor,
        "end": cursor + LOWER_STATE_DIM,
        "reference": "previous lower state in one held target frame",
    }
    cursor += LOWER_STATE_DIM
    schema["current_lower_state"] = {
        "start": cursor,
        "end": cursor + LOWER_STATE_DIM,
        "reference": "current lower state in one held target frame",
    }
    cursor += LOWER_STATE_DIM
    schema["target_height"] = {
        "start": cursor,
        "end": cursor + TARGET_HEIGHT_DIM,
        "reference": "target world Y above the zero-height root/floor plane",
    }
    cursor += TARGET_HEIGHT_DIM
    schema["attack_labels"] = {
        "start": cursor,
        "end": cursor + ATTACK_LABEL_DIM,
        "names": ["attack_angle", "is_pike", "is_melee", "is_kick", "is_headbutt"],
        "scope": "once per transition sample",
    }
    cursor += ATTACK_LABEL_DIM
    schema.update(
        {
            "score_start": 0,
            "score_end": LOWER_STATE_DIM,
            "lower_state_dim": LOWER_STATE_DIM,
            "phase_or_frame_input": False,
            "total_dim": cursor,
        }
    )
    if cursor != STATE_CONDITIONED_AE11_DIM:
        raise RuntimeError(
            f"Lower state-conditioned schema {cursor} != {STATE_CONDITIONED_AE11_DIM}"
        )
    return schema
