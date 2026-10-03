"""Validate an existing packaged crowd result; standard library only, no UE launches."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    def bad_constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")
    with open(path, encoding="utf-8-sig") as stream:
        return json.load(stream, parse_constant=bad_constant)


def digest(path):
    result = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest().upper()


def validate(args):
    feedback_mode = {"Original": 0, "PreparedSerial": 1, "PreparedParallel": 2}[args.feedback_mode]

    def validate_feedback_row(row, label):
        mode = row["physical_feedback_mode"]
        require(isinstance(mode, (int, float)) and not isinstance(mode, bool)
                and mode == feedback_mode, f"{label}: wrong physical feedback mode.")
        for key in ("prepared_physical_samples", "prepared_physical_batches"):
            value = row[key]
            require(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and value >= 0 and value == int(value), f"{label}: invalid {key}.")
            if feedback_mode == 0:
                require(value == 0, f"{label}: Original mode performed prepared feedback work.")

    package = load(args.package)
    require(package["success"] is True, "Package was not successfully built/staged.")
    require(package["configuration"] == args.configuration, "Package configuration mismatch.")
    snapshot = load(package["snapshot"])
    require(digest(package["snapshot"]) == package["snapshotSha256"], "Snapshot manifest changed.")
    controls = package["controlledQueryTests"]
    require(controls["success"] is True and controls["snapshotSha256"] == package["snapshotSha256"], "Query controls are not from this snapshot.")
    require(digest(controls["report"]) == controls["reportSha256"], "Query control report changed.")
    tests = {item["fullTestPath"]: item for item in load(controls["report"])["tests"]}
    for name in ("Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose",
                 "Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle"):
        require(name in tests and tests[name]["state"] == "Success" and tests[name]["errors"] == 0
                and tests[name]["warnings"] == 0, f"Required matching-source query control failed: {name}")
    report = load(args.result)
    require(report["error"] == "", f"Native benchmark failed: {report['error']}")
    require(report["mesh"] == "/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin", "Wrong mannequin identity.")
    require("failed_case_partial_measurements" not in report, "Partial failure report is not acceptance.")
    for key, expected in (("count", args.count), ("warmup_frames", args.warmup), ("sample_frames", args.samples)):
        require(report[key] == expected, f"Wrong {key}.")
    require(report["nullrhi"] is True and report["movement_only"] is True
            and report["substepping"] is False and report["async_physics"] is False, "Workload flags differ.")
    require(abs(report["fixed_dt"] - 1 / 60) < 1e-12, "World cadence differs.")
    build = report["game_module_build_profile"]
    require(build["profile"] == "DEFAULT" and build["editor_build"] is False
            and build["shipping_build"] is (args.configuration == "Shipping"), "Wrong loaded Game module/configuration.")
    padding = report["native_query_padding_control"]
    require(padding["requested"] is True and padding["applied"] is True and padding["restored"] is True
            and abs(padding["applied_value_cm"] - args.padding) < 1e-4
            and padding["restored_flags"] == padding["original_flags"]
            and abs(padding["restored_value_cm"] - padding["original_value_cm"]) < 1e-4,
            "Native padding application/restoration did not pass.")
    require(padding["world"] == "/Engine/Maps/Entry.Entry", "Snapshot did not start in the intended Entry world.")
    require(len(report["passes"]) == 1, "Expected one complete NN crowd pass.")
    case = report["passes"][0]
    require(case["mode"] == "NNJoltCrowd", "Synthetic/other case is not an actual NN comparison.")
    require(len(case["world_ms"]) == args.samples and all(math.isfinite(v) and v > 0 for v in case["world_ms"]), "Incomplete/nonfinite timed samples.")
    before = case["before"]
    scope = before["actual_nn_scope"]
    require(scope["synthetic_publication_after_adoption"] is False and scope["nn_hz"] == 30
            and scope["world_and_presentation_hz"] == 60 and scope["policy_bones"] == 25
            and scope["presented_skeleton_bones"] == 88 and scope["dynamic_bodies_per_character"] == 22,
            "Actual NN/pose scope changed.")
    capsule_policies = scope["root_capsule_policies"]
    require(len(capsule_policies) == args.count, "Root capsule policy count differs.")
    expected_responses = [2] + [0] * 31
    for policy in capsule_policies:
        responses = policy["responses_by_channel"]
        require(isinstance(responses, list) and len(responses) == 32
                and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                        and math.isfinite(v) and v in (0, 1, 2) for v in responses)
                and responses == expected_responses,
                "Root capsule must export exactly 32 stored channel responses (WorldStatic Block, others Ignore); no transient/sentinel extras.")
        require(policy["object_channel"] == 21 and policy["collision_enabled"] == 3
                and policy["radius_cm"] == 30 and policy["half_height_cm"] == 86,
                "Root capsule object/channel/geometry policy differs.")
    expected_models = set(snapshot["modelRelativePaths"])
    actual_models = {scope[key].replace("\\", "/") for key in
                     ("run_model", "walk_model", "upper_model", "run_contract", "walk_contract", "upper_contract")}
    require(actual_models == expected_models, "Native model/layout identities changed.")
    handoff = before["multi_jolt_handoff"]
    require("DuringPhysics" in handoff["automatic_tick_group"] and handoff["characters"] == args.count, "Coordinator group/count differs.")
    require(len(handoff["source_captures"]) == args.count, "Cooked rig capture count differs.")
    for capture in handoff["source_captures"]:
        require(capture["bodies"] == 22 and capture["joints"] == 21 and capture["disabled_pairs"] == 47,
                "Cooked PHAT topology/collision pairs differ.")
        require(capture["physics_asset"] == "/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin", "Wrong PHAT override.")
        require(capture["physical_component"].startswith("/Engine/Maps/Entry.Entry:PersistentLevel.")
                and capture["physical_component"].endswith(".PhysicalMesh"), "Captured receiver is not in the intended Entry world.")
    summary = case["multi_jolt_validation"]
    require(summary["success"] is True and summary["characters"] == args.count
            and summary["frames"] == args.samples and summary["bones_per_character"] == 88, "Incomplete character validation.")
    frames = case["multi_jolt_frames"]
    require(len(frames) == args.samples, "Missing frame records.")
    agent_records = body_checks = bone_checks = query_checks = 0
    initial_nn = before["actual_nn_initial"]
    validate_feedback_row(initial_nn, "Initial NN state")
    previous_nn = initial_nn
    for i, frame in enumerate(frames):
        require(frame["success"] is True and frame["sample_frame"] == i, f"Frame {i} failed or reordered.")
        native = frame["jolt"]
        require(native["initialized"] is True and native["faulted"] is False and native["update_error_bits"] == 0
                and native["bodies"] == args.count * 22 + 1 and native["constraints"] == args.count * 21
                and native["completed_steps"] == i + 1 and native["worker_threads"] == args.workers
                and native["no_lock_idle_body_reads"] is True and native["last_collision_steps"] == 1
                and abs(native["last_step_seconds"] - 1 / 60) < 1e-7, f"Frame {i} native cadence/topology differs.")
        require(frame["validated_dynamic_rig_bodies"] == args.count * 22
                and frame["validated_skeleton_bones"] == args.count * 88, "Frame body/bone coverage incomplete.")
        require(len(frame["agents"]) == args.count, f"Frame {i} lost a character.")
        for lane, agent in enumerate(frame["agents"]):
            require(agent["success"] is True and agent["agent_index"] == lane
                    and agent["completed_revision"] == i + 2 and agent["validated_dynamic_rig_bodies"] == 22
                    and agent["validated_skeleton_bones"] == 88, f"Frame {i} lane {lane} coverage/revision failed.")
            require(agent["max_feedback_render_position_cm"] <= summary["position_tolerance_cm"]
                    and agent["max_feedback_render_angle_degrees"] <= summary["angle_tolerance_degrees"]
                    and agent["max_feedback_render_scale_difference"] <= summary["scale_tolerance"], "Feedback/render mismatch.")
            query = agent["post_endphysics_queries"]
            require(query["success"] is True and query["validated_query_bodies"] == 22, "Native query pose coverage incomplete.")
            ray = query["center_ray"]
            # UE FName identity is case-insensitive; cooked builds may display "Head".
            require(ray["success"] is True and isinstance(ray["hit_bone"], str) and ray["hit_bone"].lower() == "head"
                    and ray["hit_component"].endswith(".PhysicalMesh"), "Head query receiver mismatch.")
            require(query["normal_unfiltered_head_visibility_exercised"] is True
                    or query["validation_only_ignored_own_capsule"] is True, "Head-ray coverage is not classified.")
            agent_records += 1
            body_checks += 22
            bone_checks += 88
            query_checks += query["validated_query_bodies"]
        nn = frame["actual_nn"]
        validate_feedback_row(nn, f"Frame {i}")
        for part in ("run", "walk", "upper"):
            require(nn[f"{part}_runtime"] == "NNERuntimeORTCpu" and nn[f"{part}_batch_size"] == 100, "NN runtime/batch identity changed.")
        steps = nn["completed_nn_steps"] - previous_nn["completed_nn_steps"]
        feedback = nn["completed_physical_samples"] - previous_nn["completed_physical_samples"]
        require(steps in (0, 1) and feedback == steps * args.count and nn["failed_physical_samples"] == 0, "Per-frame NN/feedback cadence failed.")
        prepared_samples = nn["prepared_physical_samples"] - previous_nn["prepared_physical_samples"]
        prepared_batches = nn["prepared_physical_batches"] - previous_nn["prepared_physical_batches"]
        require(prepared_samples == (steps * args.count if feedback_mode else 0)
                and prepared_batches == (steps if feedback_mode else 0),
                f"Frame {i}: prepared feedback did not complete exactly one join and Count items per NN step.")
        previous_nn = nn
    nn_summary = case["actual_nn_validation"]
    validate_feedback_row(nn_summary, "NN summary")
    expected_steps = args.samples // 2
    require(nn_summary["success"] is True and nn_summary["completed_nn_steps"] == expected_steps
            and nn_summary["completed_physical_samples"] == expected_steps * args.count
            and previous_nn["completed_nn_steps"] - initial_nn["completed_nn_steps"] == expected_steps
            and previous_nn["completed_physical_samples"] - initial_nn["completed_physical_samples"] == expected_steps * args.count,
            "Full actual NN/feedback sample totals failed.")
    expected_prepared_batches = expected_steps if feedback_mode else 0
    expected_prepared_samples = expected_prepared_batches * args.count
    require(nn_summary["prepared_physical_samples"] == expected_prepared_samples
            and nn_summary["prepared_physical_batches"] == expected_prepared_batches
            and previous_nn["prepared_physical_samples"] - initial_nn["prepared_physical_samples"] == expected_prepared_samples
            and previous_nn["prepared_physical_batches"] - initial_nn["prepared_physical_batches"] == expected_prepared_batches,
            "Full prepared feedback join/item totals failed.")
    require(summary["removed_during_bone_finalization"] is True and summary["returned_kinematic"] is True
            and summary["stale_handles_rejected"] == args.count * 22
            and summary["survivor_handles_preserved"] == (args.count - 1) * 22
            and summary["removed_handles_rejected"] == 22
            and summary["coordinator_characters_after_disable"] == 0
            and summary["chaos_dynamic_bodies_after_disable"] == 0
            and summary["after_disable"]["bodies"] == 1 and summary["after_disable"]["constraints"] == 0,
            "Native removal/disable/handle lifetime gates failed.")
    restore = summary.get("callback_kinematic_restore")
    require(isinstance(restore, dict), "Missing callback kinematic restoration evidence.")
    for key in ("success", "same_engine_frame", "native_ownership_removed_inside_callback",
                "class_change_waited_for_callback_return", "reentrant_modes_refused",
                "direct_component_cleanup_kinematic"):
        require(restore.get(key) is True, f"Callback kinematic restoration failed: {key}.")
    require(restore.get("restored_anim_class") == "/Script/GameAnimationSample3.ProphecyNNLocomotionAnimInstance",
            "Callback cleanup did not restore the exact native NN AnimInstance class.")
    probe_bone = restore.get("probe_bone")
    require(isinstance(probe_bone, str) and probe_bone.lower() == "head",
            "Callback kinematic restoration probe is not the head bone.")
    for key, expected in (("first_local_shift_cm", 17), ("second_local_shift_cm", 24)):
        value = restore.get(key)
        require(isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and math.isclose(value, expected, rel_tol=0, abs_tol=1e-5),
                f"Callback kinematic restoration has invalid {key}; expected {expected} cm within 1e-5 cm.")
    late = summary["late_admission_cancellation"]
    require(late["success"] is True and late["pending_token_cleared"] is True
            and late["completion_delegate_cleared"] is True and late["chaos_dynamic_bodies_after_cancellation"] == 0,
            "Pending enable cancellation failed.")
    if args.pclass:
        require(report["game_thread_processor_control"]["requested"] is True
                and report["game_thread_processor_control"]["restored"] is True, "GT affinity was not restored.")
    paused = report["paused_chaos_diagnostic"]
    if args.paused:
        require(paused["requested"] is True and paused["restored"] is True
                and paused["validated_positive_delta_frames"] == 2
                and paused["validated_zero_delta_frames"] == args.samples - 2
                and paused["validated_total_frames"] == args.samples, "Deferred pause sample coverage/restoration failed.")
    else:
        require(paused["requested"] is False, "An unrequested pause factor was applied.")
    return dict(success=True, configuration=args.configuration, count=args.count, samples=args.samples,
                agent_records=agent_records, body_checks=body_checks, bone_checks=bone_checks, query_body_checks=query_checks,
                actual_nn_steps=expected_steps, physical_feedback_samples=expected_steps * args.count,
                feedback_mode=args.feedback_mode, physical_feedback_mode=feedback_mode,
                prepared_physical_samples=expected_prepared_samples, prepared_physical_batches=expected_prepared_batches,
                world_tick=case["world_tick"], snapshotSha256=package["snapshotSha256"],
                scope="Complete native JSON and matching-source query controls. NullRHI elapsed world time, not rendered FPS, blood pixels or summed worker CPU.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for flag in ("package", "result", "output", "configuration"):
        parser.add_argument("--" + flag, required=True)
    for flag in ("count", "warmup", "samples", "workers"):
        parser.add_argument("--" + flag, type=int, required=True)
    parser.add_argument("--padding", type=float, required=True)
    parser.add_argument("--feedback-mode", choices=("Original", "PreparedSerial", "PreparedParallel"), default="Original")
    parser.add_argument("--paused", action="store_true")
    parser.add_argument("--pclass", action="store_true")
    arguments = parser.parse_args()
    try:
        output = validate(arguments)
    except Exception as error:
        output = dict(success=False, error=f"{type(error).__name__}: {error}")
    with open(arguments.output, "x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
    raise SystemExit(0 if output["success"] else 1)
