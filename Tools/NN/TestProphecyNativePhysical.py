"""Run through the editor bridge after NativePhysicalTest is ready in PIE.

Only touches the isolated fixture at runtime. No screenshots or asset saves.
Requires fresh baseline strength=1 because native per-body scales have no getter.
Cancel safely with cancel_native_physical_audit(); ending PIE also cancels safely.
"""
import json
import math
import time
import traceback
from pathlib import Path

import unreal


def _np_world():
    return (unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            or unreal.EditorLevelLibrary.get_game_world())


def _np_xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def _np_transform(transform):
    q = transform.rotation
    return {"p_cm": _np_xyz(transform.translation),
            "q_xyzw": [float(q.x), float(q.y), float(q.z), float(q.w)],
            "scale": _np_xyz(transform.scale3d)}


def _np_angle(first, second):
    a, b = first.rotation, second.rotation
    qa, qb = [a.x, a.y, a.z, a.w], [b.x, b.y, b.z, b.w]
    denominator = math.sqrt(sum(v*v for v in qa) * sum(v*v for v in qb))
    assert denominator > 0, "Zero-length quaternion"
    dot = abs(sum(x*y for x, y in zip(qa, qb)) / denominator)
    return math.degrees(2.0 * math.acos(min(1.0, dot)))


def _np_stats(values):
    values = sorted(values)
    if not values:
        return None
    return {"count": len(values), "mean": sum(values)/len(values),
            "rms": math.sqrt(sum(v*v for v in values)/len(values)),
            "p95": values[min(len(values)-1, int(0.95*(len(values)-1)))],
            "max": values[-1]}


class _NativePhysicalAudit:
    # Wall durations are intentional: record game delta and observed frame rate
    # rather than assuming t.MaxFPS fixes either the simulation dt or NN cadence.
    WARM_SECONDS = 1.25
    SAMPLE_SECONDS = 3.0
    ARM_RECOVERY_SECONDS = 2.0
    ARM_SAMPLE_SECONDS = 1.5

    def __init__(self):
        self.handle = None
        self.finished = False
        self.world = _np_world()
        assert self.world, "Start the isolated PIE fixture first"
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.ProphecyAgent)
        candidates = [a for a in actors if a.get_name() == "NativePhysicalTest"]
        assert len(candidates) == 1, "Expected exactly one actor named NativePhysicalTest"
        self.actor = candidates[0]
        assert "ProphecyNativePhysicalAgent" in self.actor.get_class().get_name(), self.actor.get_class().get_name()
        self.mesh = self.actor.get_agent_mesh()
        self.original_fps = unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")
        self.original_input = self.actor.get_locomotion_input()
        self.original_input_override = self.actor.get_editor_property("use_blueprint_locomotion_input")
        self.original_inference = self.actor.is_nn_inference_enabled()
        # Live Coding can expose the new reflected class through the old Python
        # wrapper; exact C++ names work before snake-case aliases are generated.
        self.original_contacts = self.actor.get_editor_property("bNativeContacts")
        self.original_gravity = self.actor.get_editor_property("bNativeGravity")
        self.original_feedback = {
            str(name): [float(settings.linear_tolerance_cm), float(settings.angular_tolerance_degrees)]
            for name, settings in self.actor.get_editor_property("physical_feedback_tolerances").items()}
        label = globals().get("NATIVE_PHYSICAL_AUDIT_LABEL", "results")
        self.output = Path(unreal.Paths.project_saved_dir()).resolve() / f"NativePhysical/{label}.json"
        self.started_wall = time.monotonic()
        self.last_game_time = None
        self.stage = "prepare"
        self.deadline = self.started_wall + 0.75
        self.case_index = -1
        self.case_samples = []
        self.case_summaries = []
        self.samples = []
        self.events = []
        self.failures = []
        self.cleanup_errors = []
        self.expected_bodies = None
        self.total_unique_frames = 0
        self.impulse = unreal.Vector(0.0, 0.0, 200.0)
        self.cases = []
        for contacts in (False, True):
            for fps in (60, 30, 5):
                for run in (False, True):
                    self.cases.append({"kind": "locomotion", "fps": fps, "run": run,
                                       "contacts": contacts, "gravity": contacts})
        for scale in (1.0, 0.5, 0.0, 1.0):
            self.cases.append({"kind": "arm_impulse", "fps": 60, "scale": scale,
                               "contacts": False, "gravity": False})

    def call(self, function, *args):
        return self.actor.call_method(function, args=args)

    def command(self, command):
        world = _np_world()
        if world is None:
            world = (unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
                     or unreal.EditorLevelLibrary.get_editor_world())
        if world is None:
            raise RuntimeError("No world available for console restoration")
        unreal.SystemLibrary.execute_console_command(world, command)

    def check_structure(self):
        meshes = list(self.actor.get_components_by_class(unreal.SkeletalMeshComponent))
        assert len(meshes) == 1, f"Expected one skeletal component, found {len(meshes)}"
        assert meshes[0] == self.mesh
        animation = self.mesh.get_anim_instance()
        assert animation and "ProphecyNNLocomotionAnimInstance" in animation.get_class().get_name(), "NN anim instance missing"
        assert not self.actor.get_editor_property("manual_nn_pose_application"), "Manual follower enabled"
        assert not self.actor.get_editor_property("auto_publish_manual_follower_substep_targets"), "Custom substep follower enabled"
        assert not self.actor.get_editor_property("auto_apply_world_magnetization"), "Custom magnetization enabled"
        assert self.actor.has_valid_agent_handle(), "No NN lane"

    def read(self, game_time, game_dt, wall_time):
        self.check_structure()
        pose = self.actor.read_nn_future_world_pose()
        assert pose is not None, "No independent authored pose data"
        names, future, presented, alpha = pose
        source = {str(name): value for name, value in zip(names, presented)}
        next_source = {str(name): value for name, value in zip(names, future)}
        simulated_names = [str(name) for name in names if self.mesh.is_simulating_physics(name)]
        if self.expected_bodies is None:
            required = {"pelvis", "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r",
                        "upperarm_r", "lowerarm_r", "hand_r"}
            assert required.issubset(simulated_names), f"Required bodies not simulated: {required-set(simulated_names)}"
            self.expected_bodies = sorted(simulated_names)
        assert sorted(simulated_names) == self.expected_bodies, "Simulated body set changed"
        bodies = {}
        for name in self.expected_bodies:
            native = self.call("GetNativeBodySample", unreal.Name(name))
            assert native is not None and len(native) == 6, f"Native sample unavailable: {name}"
            target, actual, velocity, omega, mass, blend = native
            assert mass > 0 and math.isfinite(mass), (name, "invalid mass", mass)
            assert abs(blend-1.0) <= 1e-6, (name, "not full physical rendering", blend)
            position_error = actual.translation-target.translation
            target_error = target.translation-source[name].translation
            row = {"native_target": _np_transform(target), "actual": _np_transform(actual),
                   "source_presented": _np_transform(source[name]), "source_future": _np_transform(next_source[name]),
                   "actual_minus_native_cm": _np_xyz(position_error),
                   "native_minus_source_cm": _np_xyz(target_error),
                   "tracking_linear_cm": math.sqrt(sum(v*v for v in _np_xyz(position_error))),
                   "tracking_angular_deg": _np_angle(actual, target),
                   "source_linear_cm": math.sqrt(sum(v*v for v in _np_xyz(target_error))),
                   "source_angular_deg": _np_angle(target, source[name]),
                   "linear_velocity_cm_s": _np_xyz(velocity), "angular_velocity_rad_s": _np_xyz(omega),
                   "mass_kg": float(mass), "physics_blend_weight": float(blend), "simulating": True}
            numeric = [v for key in ("native_target", "actual", "source_presented", "source_future")
                       for field in row[key].values() for v in field]
            numeric += row["linear_velocity_cm_s"] + row["angular_velocity_rad_s"]
            assert all(math.isfinite(v) for v in numeric), f"Non-finite body sample: {name}"
            bodies[name] = row
        return {"case": self.case_index, "stage": self.stage, "game_time": game_time,
                "game_dt": game_dt, "wall_elapsed": wall_time-self.started_wall,
                "root_cm": _np_xyz(self.actor.get_root_low_point()), "source_alpha": float(alpha), "bodies": bodies}

    def begin_case(self, now):
        self.case_index += 1
        if self.case_index == len(self.cases):
            self.finish()
            return
        case = self.cases[self.case_index]
        self.case_samples = []
        self.command(f"t.MaxFPS {case['fps']}")
        self.call("SetNativeContactsAndGravity", case["contacts"], case["gravity"])
        changed = self.call("SetNativeBodyStrengthBelow", unreal.Name("upperarm_r"), 1.0, 1.0, True)
        assert changed >= 3, f"Right-arm subtree only changed {changed} bodies"
        if case["kind"] == "locomotion":
            self.actor.set_nn_inference_enabled(True)
            # Reverse every walk/run pair to avoid steadily leaving the fixture floor.
            sign = 1.0 if (self.case_index//2) % 2 == 0 else -1.0
            direction = unreal.Vector(sign, 0.0, 0.0)
            self.actor.set_locomotion_input(direction, case["run"], direction, 1.0, 1.0)
            self.stage = "warm"
            self.deadline = now + self.WARM_SECONDS
        else:
            self.actor.stop_locomotion_input()
            # The first trial brakes before freezing; later trials keep exactly
            # the same authored target and recover naturally at strength1.
            self.stage = "arm_recover"
            self.deadline = now + self.ARM_RECOVERY_SECONDS
        self.events.append({"event": "case_begin", "case": self.case_index, "settings": case,
                            "wall_elapsed": now-self.started_wall})

    def summarize_case(self):
        case = self.cases[self.case_index]
        assert self.case_samples, f"No samples for case {self.case_index}"
        fields = ("tracking_linear_cm", "tracking_angular_deg", "source_linear_cm", "source_angular_deg")
        summary = {"case": self.case_index, "settings": case, "sample_count": len(self.case_samples),
                   "game_dt": _np_stats([s["game_dt"] for s in self.case_samples]), "per_body": {}}
        for name in self.expected_bodies:
            summary["per_body"][name] = {
                field: _np_stats([s["bodies"][name][field] for s in self.case_samples]) for field in fields}
            first = self.case_samples[0]["bodies"][name]["source_presented"]["p_cm"]
            summary["per_body"][name]["source_position_travel_cm"] = max(
                math.dist(first, s["bodies"][name]["source_presented"]["p_cm"]) for s in self.case_samples)
        if case["kind"] == "locomotion":
            root_travel = math.dist(self.case_samples[0]["root_cm"], self.case_samples[-1]["root_cm"])
            summary["root_net_travel_cm"] = root_travel
            assert root_travel > 0.01, f"Locomotion root did not move in case {self.case_index}"
        else:
            summary["impulse_kg_cm_s"] = _np_xyz(self.impulse)
            summary["initial_body_state"] = self.arm_initial
            summary["baseline_to_peak_hand_deviation_cm"] = max(
                s["bodies"]["hand_r"]["tracking_linear_cm"] for s in self.case_samples
            ) - self.arm_initial["tracking_linear_cm"]
        self.case_summaries.append(summary)
        self.write_report("running")

    def tick(self, _delta):
        try:
            now = time.monotonic()
            assert _np_world() == self.world, "PIE world ended or changed"
            assert now-self.started_wall < 180, "Audit exceeded its 180-second watchdog"
            game_time = float(unreal.GameplayStatics.get_time_seconds(self.world))
            if self.last_game_time is not None and game_time == self.last_game_time:
                return  # Slate can tick repeatedly without a new physics frame.
            game_dt = game_time-self.last_game_time if self.last_game_time is not None else 0.0
            self.last_game_time = game_time
            self.total_unique_frames += 1
            if self.stage == "prepare":
                if now < self.deadline:
                    return
                self.check_structure()
                self.actor.set_all_physical_feedback_tolerances(1000000.0, 360.0)
                self.begin_case(now)
                return
            row = self.read(game_time, game_dt, now)
            self.samples.append(row)
            if self.stage in ("sample", "arm_sample"):
                self.case_samples.append(row)
            if now < self.deadline:
                return
            if self.stage == "warm":
                self.stage = "sample"
                self.deadline = now+self.SAMPLE_SECONDS
            elif self.stage == "arm_recover":
                self.actor.set_nn_inference_enabled(False)
                scale = self.cases[self.case_index]["scale"]
                changed = self.call("SetNativeBodyStrengthBelow", unreal.Name("upperarm_r"), scale, scale, True)
                assert changed >= 3
                self.stage = "arm_gain_ready"
                self.deadline = now+0.2  # Allow native deferred settings update before the impulse.
            elif self.stage == "arm_gain_ready":
                self.arm_initial = row["bodies"]["hand_r"]
                self.mesh.add_impulse(self.impulse, unreal.Name("hand_r"), False)
                self.events.append({"event": "hand_impulse", "case": self.case_index,
                                    "impulse_kg_cm_s": _np_xyz(self.impulse), "game_time": game_time})
                self.stage = "arm_sample"
                self.deadline = now+self.ARM_SAMPLE_SECONDS
            elif self.stage in ("sample", "arm_sample"):
                self.summarize_case()
                self.begin_case(now)
        except Exception:
            self.failures.append(traceback.format_exc())
            self.finish("failed")

    def write_report(self, status):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        report = {"status": status, "actor": "NativePhysicalTest",
                  "invariants_passed": status == "completed" and not self.failures and not self.cleanup_errors,
                  "tracking_quality_accepted": None,
                  "acceptance_note": "Structural assertions do not establish tracking quality. Inspect numerical error distributions. Contact response proof is a separate fixture test.",
                  "single_mesh_required": True, "open_loop_tolerances": {"cm": 1000000.0, "degrees": 360.0},
                  "strength_restore": "Baseline1 on upperarm_r subtree; fixture must be pristine at start.",
                  "sample_phase": "Slate post tick; one row per distinct game time, after completed game physics.",
                  "elapsed_wall_seconds": time.monotonic()-self.started_wall,
                  "total_unique_frames": self.total_unique_frames, "expected_bodies": self.expected_bodies,
                  "cases": self.case_summaries, "events": self.events, "failures": self.failures,
                  "cleanup_errors": self.cleanup_errors, "samples": self.samples}
        self.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    def finish(self, status="completed"):
        if self.finished:
            return
        self.finished = True
        if self.handle is not None:
            try:
                unreal.unregister_slate_post_tick_callback(self.handle)
            except Exception:
                self.cleanup_errors.append(traceback.format_exc())
            self.handle = None
        cleanup = [lambda: self.command(f"t.MaxFPS {self.original_fps}")]
        if _np_world() == self.world:
            cleanup += [
                lambda: self.call("SetNativeBodyStrengthBelow", unreal.Name("upperarm_r"), 1.0, 1.0, True),
                lambda: self.call("SetNativeContactsAndGravity", self.original_contacts, self.original_gravity),
                lambda: self.actor.set_nn_inference_enabled(self.original_inference),
                lambda: self.actor.set_locomotion_input(self.original_input.world_move_input,
                    self.original_input.run, self.original_input.facing_world_direction,
                    self.original_input.speed_scale, self.original_input.turn_scale),
                lambda: self.actor.set_editor_property("use_blueprint_locomotion_input", self.original_input_override),
                lambda: self.actor.set_all_physical_feedback_tolerances(0.0, 0.0)]
            for name, values in self.original_feedback.items():
                cleanup.append(lambda name=name, values=values: self.actor.set_physical_feedback_tolerance(
                    unreal.Name(name), values[0], values[1]))
        for restore in cleanup:
            try:
                restore()
            except Exception:
                self.cleanup_errors.append(traceback.format_exc())
        try:
            self.write_report(status)
        finally:
            unreal.log(f"Native physical audit {status}: {self.output}; failures={len(self.failures)} cleanup_errors={len(self.cleanup_errors)}")


def cancel_native_physical_audit():
    audit = globals().get("native_physical_audit")
    if audit and not audit.finished:
        audit.finish("cancelled")


cancel_native_physical_audit()
native_physical_audit = _NativePhysicalAudit()
native_physical_audit.handle = unreal.register_slate_post_tick_callback(native_physical_audit.tick)
print("Native physical numerical audit started: 12 walk/run/FPS/contact cases and 4 arm impulses; no screenshots or asset saves.")
