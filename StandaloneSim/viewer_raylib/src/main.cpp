#include "control_settings.h"
#include "locomotion_poses.h"
#include "rig.h"
#include "scenario.h"
#include "telemetry.h"
#include "window_placement.h"

#include "prophecy/sim/simulation.h"

#include "raygui.h"
#include "raylib.h"
#include "raymath.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>

namespace {

namespace sim = ::prophecy::sim;
namespace viewer = ::prophecy::viewer;

constexpr std::uint16_t kDefaultTelemetryPort = 17831;
constexpr float kPi = 3.14159265358979323846f;
constexpr Color kPanel{24, 29, 31, 245};
constexpr Color kPanelRaised{34, 41, 43, 255};
constexpr Color kText{238, 242, 240, 255};
constexpr Color kMuted{164, 175, 171, 255};
constexpr Color kAccent{63, 188, 211, 255};
constexpr Color kAzureSkeleton{48, 168, 232, 255};
constexpr Color kCrimsonSkeleton{235, 74, 83, 255};
constexpr Color kHead{226, 214, 190, 255};
constexpr Color kRootMarker{255, 205, 64, 255};
constexpr Color kSheath{48, 42, 38, 255};
constexpr Color kLeather{103, 66, 43, 255};
constexpr Color kSwordMetal{224, 232, 234, 255};
constexpr Color kSwordGuard{214, 164, 54, 255};
constexpr Color kSelection{244, 247, 246, 255};
constexpr float kInfoPanelHeight = 204.0f;
constexpr float kOptionsPanelY = 228.0f;

Vector3 CoreToWorld(const sim::Vec3& value) {
    return {value.x, value.z, value.y};
}

Vector3 AgentRenderRoot(const sim::AgentSnapshot& agent, float prediction_seconds) {
    return Vector3Add(CoreToWorld(agent.position),
        Vector3Scale(CoreToWorld(agent.root_velocity), prediction_seconds));
}

Vector3 Forward(float yaw, float pitch) {
    const float horizontal = std::cos(pitch);
    return Vector3Normalize({horizontal * std::cos(yaw), std::sin(pitch), horizontal * std::sin(yaw)});
}

Vector3 Right(float yaw) {
    return {-std::sin(yaw), 0.0f, std::cos(yaw)};
}

struct FlyingCamera {
    Camera3D camera{};
    float yaw = 0.0f;
    float pitch = 0.0f;
    float follow_distance = 5.0f;
    std::uint32_t followed_agent_id = 0;

    void Initialize(Vector3 focus, float distance, float initial_yaw, float initial_pitch) {
        yaw = initial_yaw;
        pitch = -std::fabs(initial_pitch);
        const Vector3 forward = Forward(yaw, pitch);
        camera.position = Vector3Subtract(focus, Vector3Scale(forward, distance));
        camera.target = focus;
        camera.up = {0.0f, 1.0f, 0.0f};
        camera.fovy = 55.0f;
        camera.projection = CAMERA_PERSPECTIVE;
    }

    void Follow(const sim::AgentSnapshot& agent, float prediction_seconds) {
        Vector3 focus = AgentRenderRoot(agent, prediction_seconds);
        focus.y += 0.9f;
        const Vector3 to_focus = Vector3Subtract(focus, camera.position);
        const float distance = Vector3Length(to_focus);
        if (distance > 0.001f) {
            const Vector3 direction = Vector3Scale(to_focus, 1.0f / distance);
            yaw = std::atan2(direction.z, direction.x);
            pitch = std::asin(std::clamp(direction.y, -1.0f, 1.0f));
        }
        follow_distance = std::clamp(distance, 2.5f, 7.0f);
        followed_agent_id = agent.id;
        camera.position = Vector3Subtract(focus, Vector3Scale(Forward(yaw, pitch), follow_distance));
        camera.target = focus;
    }

    void Update(const viewer::ControlSettings& settings, bool allow_mouse,
        const sim::SimulationSnapshot& snapshot, float prediction_seconds) {
        const float frame_seconds = std::min(GetFrameTime(), 0.1f);
        const float boost = IsKeyDown(KEY_LEFT_SHIFT) || IsKeyDown(KEY_RIGHT_SHIFT) ? 3.0f : 1.0f;
        const Vector3 forward = Forward(yaw, pitch);
        const Vector3 right = Right(yaw);
        Vector3 movement{};
#if defined(_WIN32)
        if (viewer::IsCharacterKeyDown('z')) movement = Vector3Add(movement, forward);
        if (viewer::IsCharacterKeyDown('s')) movement = Vector3Subtract(movement, forward);
        if (viewer::IsCharacterKeyDown('d')) movement = Vector3Add(movement, right);
        if (viewer::IsCharacterKeyDown('q')) movement = Vector3Subtract(movement, right);
#else
        if (IsKeyDown(KEY_Z)) movement = Vector3Add(movement, forward);
        if (IsKeyDown(KEY_S)) movement = Vector3Subtract(movement, forward);
        if (IsKeyDown(KEY_D)) movement = Vector3Add(movement, right);
        if (IsKeyDown(KEY_Q)) movement = Vector3Subtract(movement, right);
#endif
        const Vector2 mouse_delta = allow_mouse ? GetMouseDelta() : Vector2{};
        const bool left_drag = allow_mouse && IsMouseButtonDown(MOUSE_BUTTON_LEFT);
        const bool right_drag = allow_mouse && IsMouseButtonDown(MOUSE_BUTTON_RIGHT);
        const float wheel = allow_mouse ? GetMouseWheelMove() : 0.0f;

        if (followed_agent_id != 0 && (Vector3LengthSqr(movement) > 0.0f || right_drag)) {
            followed_agent_id = 0;
        }

        if (followed_agent_id != 0) {
            const auto followed = std::find_if(snapshot.agents.begin(), snapshot.agents.end(),
                [this](const sim::AgentSnapshot& agent) { return agent.id == followed_agent_id; });
            if (followed != snapshot.agents.end()) {
                if (left_drag) {
                    yaw += mouse_delta.x * settings.look_sensitivity;
                    pitch = std::clamp(pitch - mouse_delta.y * settings.look_sensitivity, -1.48f, 1.48f);
                }
                if (std::fabs(wheel) > 0.0f) {
                    follow_distance = std::clamp(
                        follow_distance - wheel * settings.zoom_sensitivity, 1.5f, 20.0f);
                }
                Vector3 focus = AgentRenderRoot(*followed, prediction_seconds);
                focus.y += 0.9f;
                camera.position = Vector3Subtract(focus, Vector3Scale(Forward(yaw, pitch), follow_distance));
                camera.target = focus;
                return;
            }
            followed_agent_id = 0;
        }

        if (Vector3LengthSqr(movement) > 0.0f) {
            movement = Vector3Scale(Vector3Normalize(movement), settings.flight_speed * boost * frame_seconds);
            camera.position = Vector3Add(camera.position, movement);
        }

        if (left_drag) {
            yaw += mouse_delta.x * settings.look_sensitivity;
            pitch = std::clamp(pitch - mouse_delta.y * settings.look_sensitivity, -1.48f, 1.48f);
        }
        if (right_drag) {
            const Vector3 up = Vector3Normalize(Vector3CrossProduct(right, Forward(yaw, pitch)));
            const Vector3 pan = Vector3Add(
                Vector3Scale(right, mouse_delta.x * settings.pan_sensitivity),
                Vector3Scale(up, -mouse_delta.y * settings.pan_sensitivity));
            camera.position = Vector3Add(camera.position, pan);
        }
        if (std::fabs(wheel) > 0.0f) {
            camera.position = Vector3Add(camera.position,
                Vector3Scale(Forward(yaw, pitch), wheel * settings.zoom_sensitivity));
        }
        camera.target = Vector3Add(camera.position, Forward(yaw, pitch));
    }
};

const sim::AgentSnapshot* PickAgent(const sim::SimulationSnapshot& snapshot,
    const Camera3D& camera, Vector2 screen_position, float prediction_seconds) {
    const Ray ray = GetScreenToWorldRay(screen_position, camera);
    const sim::AgentSnapshot* nearest = nullptr;
    float nearest_distance = 1.0e30f;
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        const Vector3 root = AgentRenderRoot(agent, prediction_seconds);
        const BoundingBox bounds{
            {root.x - 0.55f, root.y, root.z - 0.55f},
            {root.x + 0.55f, root.y + 1.9f, root.z + 0.55f},
        };
        const RayCollision collision = GetRayCollisionBox(ray, bounds);
        if (collision.hit && collision.distance < nearest_distance) {
            nearest = &agent;
            nearest_distance = collision.distance;
        }
    }
    return nearest;
}

const sim::AgentSnapshot* FindAgent(const sim::SimulationSnapshot& snapshot, sim::EntityId id) {
    const auto agent = std::find_if(snapshot.agents.begin(), snapshot.agents.end(),
        [id](const sim::AgentSnapshot& candidate) { return candidate.id == id; });
    return agent == snapshot.agents.end() ? nullptr : &*agent;
}

struct AgentDoubleClick {
    std::uint32_t agent_id = 0;
    double time_seconds = -1.0;
    Vector2 screen_position{};

    bool Register(const sim::AgentSnapshot& agent, Vector2 position) {
        constexpr double kMaximumInterval = 0.35;
        constexpr float kMaximumDrift = 12.0f;
        const double now = GetTime();
        const bool matched = agent_id == agent.id && time_seconds >= 0.0 &&
            now - time_seconds <= kMaximumInterval &&
            Vector2Distance(position, screen_position) <= kMaximumDrift;
        agent_id = matched ? 0U : agent.id;
        time_seconds = matched ? -1.0 : now;
        screen_position = position;
        return matched;
    }

    void Clear() noexcept {
        agent_id = 0;
        time_seconds = -1.0;
    }
};

struct EquipmentJoints {
    int pelvis = -1;
    int lowerarm_right = -1;
    int hand_right = -1;

    bool Valid() const noexcept {
        return pelvis >= 0 && lowerarm_right >= 0 && hand_right >= 0;
    }
};

EquipmentJoints ResolveEquipmentJoints(const viewer::LocomotionPoses& poses) {
    const auto find = [&poses](const char* name) {
        const auto joint = std::find(poses.joint_names.begin(), poses.joint_names.end(), name);
        return joint == poses.joint_names.end()
            ? -1 : static_cast<int>(std::distance(poses.joint_names.begin(), joint));
    };
    return {find("pelvis"), find("lowerarm_r"), find("hand_r")};
}

#if PROPHECY_ENABLE_REWIND
struct RewindController {
    sim::ReplayLog tape{};
    std::uint64_t head_tick = 0;
    bool active = false;

    void Clear() noexcept {
        tape = {};
        head_tick = 0;
        active = false;
    }

    bool Seek(sim::Simulation& simulation, std::uint64_t target_tick) {
        if (!active) {
            tape = simulation.RecordedReplay();
            head_tick = tape.end_tick;
            if (head_tick == 0) return target_tick == 0;
        }
        target_tick = std::min(target_tick, head_tick);
        if (!simulation.SeekReplay(tape, target_tick)) return false;
        active = target_tick < head_tick;
        if (!active) return simulation.ResumeRecordingFromReplay();
        return true;
    }

    bool SeekBackward(sim::Simulation& simulation, std::uint64_t ticks) {
        const std::uint64_t current = simulation.Snapshot().tick;
        return Seek(simulation, ticks > current ? 0U : current - ticks);
    }

    void Advanced(sim::Simulation& simulation) {
        if (active && simulation.Snapshot().tick >= head_tick) {
            if (simulation.ResumeRecordingFromReplay()) active = false;
        }
    }

    bool ReturnLive(sim::Simulation& simulation) {
        return !active || Seek(simulation, head_tick);
    }

    std::uint64_t DisplayHead(const sim::Simulation& simulation) const noexcept {
        return active ? head_tick : simulation.Snapshot().tick;
    }
};
#endif

struct BenchmarkResult {
    std::uint64_t ticks = 0;
    double seconds = 0.0;
    double ticks_per_second = 0.0;
    double realtime_factor = 0.0;
};

BenchmarkResult RunHeadlessBenchmark(const sim::SimulationConfig& config, std::uint64_t seed,
    double target_seconds = 0.5) {
    sim::Simulation benchmark(config, seed);
    constexpr std::uint64_t batch_ticks = 4096;
    std::uint64_t ticks = 0;
    const auto start = std::chrono::steady_clock::now();
    double elapsed = 0.0;
    do {
        for (std::uint64_t tick = 0; tick < batch_ticks; ++tick) benchmark.Tick();
        ticks += batch_ticks;
        elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    } while (elapsed < target_seconds);
    return {ticks, elapsed, static_cast<double>(ticks) / elapsed,
        (static_cast<double>(ticks) / elapsed) / static_cast<double>(config.tick_rate_hz)};
}

void AdvanceTicks(sim::Simulation& simulation,
#if PROPHECY_ENABLE_REWIND
    RewindController& rewind,
#endif
    std::uint64_t count) {
    for (std::uint64_t tick = 0; tick < count; ++tick) {
        simulation.Tick();
#if PROPHECY_ENABLE_REWIND
        rewind.Advanced(simulation);
#endif
    }
}

Vector3 TransformJoint(const Vector3& local, const sim::AgentSnapshot& agent, float prediction_seconds) {
    const float cosine = std::cos(agent.facing_radians);
    const float sine = std::sin(agent.facing_radians);
    const Vector3 base = AgentRenderRoot(agent, prediction_seconds);
    return {
        base.x + local.x * cosine + local.z * sine,
        base.y + local.y,
        base.z - local.x * sine + local.z * cosine,
    };
}

void DrawRootMarker(const sim::AgentSnapshot& agent, float prediction_seconds) {
    Vector3 root = AgentRenderRoot(agent, prediction_seconds);
    root.y = 0.025f;
    const Vector3 forward{std::sin(agent.facing_radians), 0.0f, std::cos(agent.facing_radians)};
    const Vector3 shaft_start = Vector3Add(root, Vector3Scale(forward, 0.075f));
    const Vector3 shaft_end = Vector3Add(root, Vector3Scale(forward, 0.38f));
    const Vector3 arrow_tip = Vector3Add(root, Vector3Scale(forward, 0.52f));

    DrawSphere(root, 0.045f, kRootMarker);
    DrawCylinderEx(shaft_start, shaft_end, 0.014f, 0.014f, 6, kRootMarker);
    DrawCylinderEx(shaft_end, arrow_tip, 0.055f, 0.0f, 8, kRootMarker);
}

void DrawSelectionMarker(const sim::AgentSnapshot& agent, float prediction_seconds) {
    Vector3 root = AgentRenderRoot(agent, prediction_seconds);
    root.y = 0.018f;
    constexpr float half = 0.34f;
    constexpr float corner = 0.11f;
    const std::array<Vector3, 4> corners{{
        {root.x - half, root.y, root.z - half},
        {root.x + half, root.y, root.z - half},
        {root.x + half, root.y, root.z + half},
        {root.x - half, root.y, root.z + half},
    }};
    for (std::size_t index = 0; index < corners.size(); ++index) {
        const Vector3 current = corners[index];
        const Vector3 next = corners[(index + 1U) % corners.size()];
        const Vector3 previous = corners[(index + corners.size() - 1U) % corners.size()];
        DrawLine3D(current, Vector3Lerp(current, next, corner / (half * 2.0f)), kSelection);
        DrawLine3D(current, Vector3Lerp(current, previous, corner / (half * 2.0f)), kSelection);
    }
}

float RenderPosePhase(const sim::AgentSnapshot& agent, const viewer::LocomotionPoses& poses,
    float prediction_seconds) {
    const float cycle_distance = poses.Clip(agent.locomotion_mode).cycle_distance_m;
    return cycle_distance > 0.0f
        ? agent.pose_phase + agent.root_speed_mps * prediction_seconds / cycle_distance
        : agent.pose_phase;
}

void DrawEquipment(const sim::AgentSnapshot& agent, const viewer::LocomotionPoses& poses,
    const EquipmentJoints& joints, float render_phase, float prediction_seconds) {
    if (!agent.sword_equipped || !joints.Valid()) return;

    const Vector3 pelvis = viewer::SamplePoseJoint(poses, agent.locomotion_mode,
        render_phase, static_cast<std::size_t>(joints.pelvis));
    const Vector3 sheath_top_local = Vector3Add(pelvis, {0.22f, -0.04f, -0.03f});
    const Vector3 sheath_bottom_local = Vector3Add(pelvis, {0.33f, -0.64f, -0.11f});
    const Vector3 sheath_top = TransformJoint(sheath_top_local, agent, prediction_seconds);
    const Vector3 sheath_bottom = TransformJoint(sheath_bottom_local, agent, prediction_seconds);
    DrawCylinderEx(sheath_top, sheath_bottom, 0.038f, 0.030f, 7, kSheath);
    DrawSphere(sheath_top, 0.043f, kSwordGuard);

    if (agent.sword_state == sim::SwordState::Sheathed) {
        const Vector3 sheath_axis = Vector3Normalize(Vector3Subtract(sheath_top, sheath_bottom));
        const Vector3 grip_end = Vector3Add(sheath_top, Vector3Scale(sheath_axis, 0.18f));
        DrawCylinderEx(sheath_top, grip_end, 0.021f, 0.019f, 7, kLeather);
        return;
    }

    const Vector3 lowerarm = TransformJoint(viewer::SamplePoseJoint(poses, agent.locomotion_mode,
        render_phase, static_cast<std::size_t>(joints.lowerarm_right)), agent, prediction_seconds);
    const Vector3 hand = TransformJoint(viewer::SamplePoseJoint(poses, agent.locomotion_mode,
        render_phase, static_cast<std::size_t>(joints.hand_right)), agent, prediction_seconds);
    Vector3 sword_direction = Vector3Subtract(hand, lowerarm);
    if (Vector3LengthSqr(sword_direction) < 0.0001f) {
        sword_direction = {std::sin(agent.facing_radians), 0.0f, std::cos(agent.facing_radians)};
    } else {
        sword_direction = Vector3Normalize(sword_direction);
    }
    const Vector3 grip_start = Vector3Subtract(hand, Vector3Scale(sword_direction, 0.09f));
    const Vector3 blade_start = Vector3Add(hand, Vector3Scale(sword_direction, 0.12f));
    const Vector3 blade_tip = Vector3Add(hand, Vector3Scale(sword_direction, 0.82f));
    DrawCylinderEx(grip_start, blade_start, 0.022f, 0.019f, 7, kLeather);
    DrawCylinderEx(blade_start, blade_tip, 0.018f, 0.004f, 7, kSwordMetal);

    Vector3 guard_direction = Vector3CrossProduct(sword_direction, {0.0f, 1.0f, 0.0f});
    if (Vector3LengthSqr(guard_direction) < 0.0001f) {
        guard_direction = Vector3CrossProduct(sword_direction, {0.0f, 0.0f, 1.0f});
    }
    guard_direction = Vector3Normalize(guard_direction);
    DrawCylinderEx(Vector3Subtract(blade_start, Vector3Scale(guard_direction, 0.10f)),
        Vector3Add(blade_start, Vector3Scale(guard_direction, 0.10f)),
        0.014f, 0.014f, 6, kSwordGuard);
}

void DrawSkeleton(const sim::AgentSnapshot& agent, const viewer::LocomotionPoses& poses,
    float prediction_seconds) {
    const Color skeleton_color = agent.team == sim::Team::Azure ? kAzureSkeleton : kCrimsonSkeleton;
    const float render_phase = RenderPosePhase(agent, poses, prediction_seconds);
    for (std::size_t joint = 0; joint < poses.joint_names.size(); ++joint) {
        const int parent = poses.parents[joint];
        if (parent < 0) continue;
        const Vector3 parent_position = viewer::SamplePoseJoint(poses, agent.locomotion_mode,
            render_phase, static_cast<std::size_t>(parent));
        const Vector3 joint_position = viewer::SamplePoseJoint(poses, agent.locomotion_mode,
            render_phase, joint);
        DrawCylinderEx(TransformJoint(parent_position, agent, prediction_seconds),
            TransformJoint(joint_position, agent, prediction_seconds),
            0.018f, 0.018f, 5, skeleton_color);
    }
    const auto head = std::find(poses.joint_names.begin(), poses.joint_names.end(), "head");
    if (head != poses.joint_names.end()) {
        const std::size_t head_index = static_cast<std::size_t>(std::distance(poses.joint_names.begin(), head));
        DrawSphere(TransformJoint(viewer::SamplePoseJoint(poses, agent.locomotion_mode,
            render_phase, head_index), agent, prediction_seconds), 0.095f, kHead);
    }
}

void DrawWorld(const viewer::Scenario& scenario, const sim::SimulationSnapshot& snapshot,
    const viewer::LocomotionPoses& poses, const EquipmentJoints& equipment_joints,
    sim::EntityId selected_agent_id, float prediction_seconds) {
    const float min_x = scenario.simulation.world_min.x;
    const float max_x = scenario.simulation.world_max.x;
    const float min_z = scenario.simulation.world_min.y;
    const float max_z = scenario.simulation.world_max.y;
    DrawPlane({(min_x + max_x) * 0.5f, 0.0f, (min_z + max_z) * 0.5f},
        {max_x - min_x, max_z - min_z}, scenario.ground_color);
    for (int x = static_cast<int>(std::ceil(min_x)); x <= static_cast<int>(std::floor(max_x)); x += 4) {
        DrawLine3D({static_cast<float>(x), 0.003f, min_z}, {static_cast<float>(x), 0.003f, max_z}, scenario.grid_color);
    }
    for (int z = static_cast<int>(std::ceil(min_z)); z <= static_cast<int>(std::floor(max_z)); z += 4) {
        DrawLine3D({min_x, 0.003f, static_cast<float>(z)}, {max_x, 0.003f, static_cast<float>(z)}, scenario.grid_color);
    }
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        if (agent.id == selected_agent_id) DrawSelectionMarker(agent, prediction_seconds);
        DrawRootMarker(agent, prediction_seconds);
        DrawSkeleton(agent, poses, prediction_seconds);
        DrawEquipment(agent, poses, equipment_joints,
            RenderPosePhase(agent, poses, prediction_seconds), prediction_seconds);
    }
}

struct Tooltip {
    const char* text = nullptr;
    Vector2 anchor{};
};

bool IconButton(Rectangle bounds, int icon, const char* tooltip, Tooltip& pending) {
    if (CheckCollisionPointRec(GetMousePosition(), bounds)) {
        pending.text = tooltip;
        pending.anchor = {bounds.x + bounds.width * 0.5f, bounds.y + bounds.height + 7.0f};
    }
    return GuiButton(bounds, GuiIconText(icon, nullptr)) != 0;
}

void DrawTooltip(const Tooltip& tooltip) {
    if (tooltip.text == nullptr) return;
    constexpr float font_size = 15.0f;
    constexpr float padding = 8.0f;
    const Vector2 measured = MeasureTextEx(GetFontDefault(), tooltip.text, font_size, 1.0f);
    Rectangle box{tooltip.anchor.x - measured.x * 0.5f - padding,
        tooltip.anchor.y, measured.x + padding * 2.0f, measured.y + padding * 2.0f};
    box.x = std::clamp(box.x, 4.0f, static_cast<float>(GetScreenWidth()) - box.width - 4.0f);
    if (box.y + box.height > static_cast<float>(GetScreenHeight()) - 4.0f) {
        box.y = tooltip.anchor.y - box.height - 46.0f;
    }
    DrawRectangleRec(box, {9, 12, 13, 248});
    DrawRectangleLinesEx(box, 1.0f, kAccent);
    DrawTextEx(GetFontDefault(), tooltip.text, {box.x + padding, box.y + padding}, font_size, 1.0f, kText);
}

std::string RateText(double ticks_per_second) {
    char text[64]{};
    if (ticks_per_second >= 1.0e6) {
        std::snprintf(text, sizeof(text), "Logic %.1fM ticks/s", ticks_per_second / 1.0e6);
    } else if (ticks_per_second >= 1.0e3) {
        std::snprintf(text, sizeof(text), "Logic %.1fk ticks/s", ticks_per_second / 1.0e3);
    } else {
        std::snprintf(text, sizeof(text), "Logic %.0f ticks/s", ticks_per_second);
    }
    return text;
}

struct UiActions {
    bool toggle_pause = false;
    bool rewind_second = false;
    bool previous_tick = false;
    bool next_tick = false;
    bool next_second = false;
    bool return_live = false;
    bool reset = false;
    bool new_seed = false;
    bool benchmark = false;
    bool reset_settings = false;
    bool save_settings = false;
};

UiActions DrawUi(const viewer::Scenario& scenario, const sim::Simulation& simulation,
    bool paused, float& time_scale, bool rewind_active, std::uint64_t rewind_head,
    bool& options_open, viewer::ControlSettings& settings, const BenchmarkResult& benchmark,
    const std::string& settings_status, sim::EntityId selected_agent_id, Tooltip& tooltip) {
    UiActions actions{};
#if !PROPHECY_ENABLE_REWIND
    (void)rewind_active;
#endif
    const sim::SimulationSnapshot& snapshot = simulation.Snapshot();
    const Rectangle transport{12.0f, 12.0f, 480.0f, 104.0f};
    DrawRectangleRec(transport, kPanel);
    DrawRectangleLinesEx(transport, 1.0f, {73, 86, 88, 255});
    DrawText("SIMULATION", 23, 20, 13, kMuted);
    DrawText(TextFormat("tick %llu / %llu", static_cast<unsigned long long>(snapshot.tick),
        static_cast<unsigned long long>(rewind_head)), 296, 19, 15, kText);

    constexpr float button = 34.0f;
    float x = 22.0f;
    const float y = 42.0f;
    actions.toggle_pause = IconButton({x, y, button, button}, paused ? ICON_PLAYER_PLAY : ICON_PLAYER_PAUSE,
        paused ? "Play (Space)" : "Pause (Space)", tooltip); x += 39.0f;
#if PROPHECY_ENABLE_REWIND
    actions.rewind_second = IconButton({x, y, button, button}, ICON_PLAYER_PREVIOUS,
        "Rewind one second", tooltip); x += 39.0f;
    actions.previous_tick = IconButton({x, y, button, button}, ICON_PLAYER_PLAY_BACK,
        "Previous tick (Left)", tooltip); x += 39.0f;
#endif
    actions.next_tick = IconButton({x, y, button, button}, ICON_PLAYER_NEXT,
        "Next tick (Right)", tooltip); x += 39.0f;
    actions.next_second = IconButton({x, y, button, button}, ICON_PLAYER_JUMP,
        "Advance one second", tooltip); x += 39.0f;
#if PROPHECY_ENABLE_REWIND
    actions.return_live = IconButton({x, y, button, button}, ICON_PLAYER_RECORD,
        rewind_active ? "Return to live tick" : "Already at live tick", tooltip); x += 39.0f;
#endif
    actions.reset = IconButton({x, y, button, button}, ICON_RESTART,
        "Reset this seed to tick zero", tooltip); x += 39.0f;
    actions.new_seed = IconButton({x, y, button, button}, ICON_SHUFFLE,
        "Create a new seed", tooltip); x += 39.0f;
    actions.benchmark = IconButton({x, y, button, button}, ICON_CPU,
        "Benchmark raw logic headlessly", tooltip); x += 39.0f;
    if (IconButton({x, y, button, button}, ICON_GEAR, "Camera options", tooltip)) options_open = !options_open;

    DrawText("Speed", 22, 84, 14, kMuted);
    constexpr std::array<float, 6> speeds{0.1f, 0.25f, 0.5f, 1.0f, 2.0f, 5.0f};
    constexpr std::array<const char*, 6> speed_labels{"0.1x", "0.25x", "0.5x", "1x", "2x", "5x"};
    for (std::size_t index = 0; index < speeds.size(); ++index) {
        const Rectangle segment{70.0f + static_cast<float>(index) * 56.0f, 81.0f, 52.0f, 25.0f};
        if (std::fabs(time_scale - speeds[index]) < 0.01f) {
            DrawRectangleRec(segment, {36, 117, 133, 255});
        }
        if (GuiButton(segment, speed_labels[index])) time_scale = speeds[index];
    }
    DrawText(TextFormat("FPS %i", GetFPS()), 414, 84, 14, kText);

    const float info_x = static_cast<float>(GetScreenWidth()) - 342.0f;
    const Rectangle info{info_x, 12.0f, 330.0f, kInfoPanelHeight};
    DrawRectangleRec(info, kPanel);
    DrawRectangleLinesEx(info, 1.0f, {73, 86, 88, 255});
    DrawText(scenario.name.c_str(), static_cast<int>(info.x + 12.0f), 22, 18, kText);
    DrawText(TextFormat("%u locomotion agents  |  SIM %.0f Hz", static_cast<unsigned int>(snapshot.agents.size()),
        simulation.Config().tick_rate_hz), static_cast<int>(info.x + 12.0f), 50, 14, kMuted);
    DrawText(TextFormat("seed %llu  |  %.2fs", static_cast<unsigned long long>(snapshot.seed), snapshot.time_seconds),
        static_cast<int>(info.x + 12.0f), 72, 14, kMuted);
    int agent_y = 96;
    const sim::AgentSnapshot* selected = FindAgent(snapshot, selected_agent_id);
    if (selected != nullptr) {
        const Color color = selected->team == sim::Team::Azure ? kAzureSkeleton : kCrimsonSkeleton;
        DrawText(TextFormat("SELECTED  %s %u", sim::ToString(selected->team), selected->id),
            static_cast<int>(info.x + 12.0f), agent_y, 14, color);
        DrawText(TextFormat("%s  %.2f m/s  response %s", sim::ToString(selected->locomotion_mode),
            selected->root_speed_mps, sim::ToString(selected->locomotion_response)),
            static_cast<int>(info.x + 12.0f), agent_y + 22, 13, kText);
        DrawText(TextFormat("move %.0f deg @ %.2f  facing %.0f deg",
            selected->speed_stick_direction_radians * 180.0f / kPi, selected->speed_stick_amplitude,
            selected->facing_radians * 180.0f / kPi),
            static_cast<int>(info.x + 12.0f), agent_y + 42, 13, kText);
        DrawText(TextFormat("sword %s  |  equipped %s", sim::ToString(selected->sword_state),
            selected->sword_equipped ? "yes" : "no"),
            static_cast<int>(info.x + 12.0f), agent_y + 62, 13, kText);
        agent_y += 82;
    } else {
        for (const sim::AgentSnapshot& agent : snapshot.agents) {
            const Color color = agent.team == sim::Team::Azure ? kAzureSkeleton : kCrimsonSkeleton;
            DrawText(TextFormat("%s %u  %s  %.1fm/s  %s  %s", sim::ToString(agent.team), agent.id,
                sim::ToString(agent.locomotion_mode), agent.root_speed_mps,
                sim::ToString(agent.locomotion_response), sim::ToString(agent.sword_state)),
                static_cast<int>(info.x + 12.0f), agent_y, 13, color);
            agent_y += 20;
        }
    }
    if (benchmark.ticks > 0) {
        DrawText(RateText(benchmark.ticks_per_second).c_str(), static_cast<int>(info.x + 12.0f), agent_y + 2, 14, kAccent);
    }

    if (options_open) {
        const Rectangle panel{static_cast<float>(GetScreenWidth()) - 332.0f, kOptionsPanelY, 320.0f, 330.0f};
        DrawRectangleRec(panel, kPanel);
        DrawRectangleLinesEx(panel, 1.0f, {73, 86, 88, 255});
        DrawText("CAMERA", static_cast<int>(panel.x + 16.0f), static_cast<int>(panel.y + 14.0f), 14, kMuted);
        struct SliderRow { const char* label; float* value; float minimum; float maximum; };
        std::array<SliderRow, 4> rows{{
            {"Look", &settings.look_sensitivity, viewer::kMinLookSensitivity, viewer::kMaxLookSensitivity},
            {"Pan", &settings.pan_sensitivity, viewer::kMinPanSensitivity, viewer::kMaxPanSensitivity},
            {"Flight", &settings.flight_speed, viewer::kMinFlightSpeed, viewer::kMaxFlightSpeed},
            {"Dolly", &settings.zoom_sensitivity, viewer::kMinZoomSensitivity, viewer::kMaxZoomSensitivity},
        }};
        float row_y = panel.y + 51.0f;
        for (const SliderRow& row : rows) {
            DrawText(row.label, static_cast<int>(panel.x + 16.0f), static_cast<int>(row_y), 15, kText);
            DrawText(TextFormat(row.maximum <= 0.1f ? "%.3f" : "%.2f", *row.value),
                static_cast<int>(panel.x + 248.0f), static_cast<int>(row_y), 15, kMuted);
            GuiSliderBar({panel.x + 16.0f, row_y + 23.0f, 288.0f, 18.0f}, nullptr, nullptr,
                row.value, row.minimum, row.maximum);
            row_y += 55.0f;
        }
        const Rectangle reset_button{panel.x + 16.0f, panel.y + 275.0f, 42.0f, 38.0f};
        const Rectangle save_button{panel.x + 64.0f, panel.y + 275.0f, 42.0f, 38.0f};
        actions.reset_settings = IconButton(reset_button, ICON_RESTART, "Reset camera defaults", tooltip);
        actions.save_settings = IconButton(save_button, ICON_FILE_SAVE, "Save camera settings", tooltip);
        if (!settings_status.empty()) {
            DrawText(settings_status.c_str(), static_cast<int>(panel.x + 120.0f),
                static_cast<int>(panel.y + 287.0f), 13, kMuted);
        }
    }
    return actions;
}

std::uint64_t NewSeed() {
    return static_cast<std::uint64_t>(
        std::chrono::high_resolution_clock::now().time_since_epoch().count());
}

std::string ControlSettingsPath() {
#if defined(_WIN32)
    char* local_app_data = nullptr;
    std::size_t length = 0;
    if (_dupenv_s(&local_app_data, &length, "LOCALAPPDATA") == 0 && local_app_data != nullptr) {
        const std::string path = (std::filesystem::path(local_app_data) /
            "ProphecyStandaloneSim" / "camera_settings.json").string();
        std::free(local_app_data);
        return path;
    }
#else
    if (const char* local_app_data = std::getenv("LOCALAPPDATA")) {
        return (std::filesystem::path(local_app_data) / "ProphecyStandaloneSim" / "camera_settings.json").string();
    }
#endif
    return (std::filesystem::current_path() / "camera_settings.json").string();
}

struct Arguments {
    std::string scenario_path{};
    std::string rig_path{};
    std::string locomotion_poses_path{};
    std::string capture_path{};
    bool capture_options = false;
    bool headless_benchmark = false;
    bool background_reload = false;
    bool telemetry = true;
    std::uint16_t telemetry_port = kDefaultTelemetryPort;
    std::uint64_t capture_tick = 0;
    std::uint32_t capture_follow_agent = 0;
    std::uintptr_t restore_foreground = 0;
};

Arguments ParseArguments(int argc, char** argv) {
    Arguments arguments{};
    const std::filesystem::path executable_data =
        std::filesystem::path(argc > 0 ? argv[0] : "").parent_path() / "data";
    const std::filesystem::path data_directory = std::filesystem::exists(executable_data / "scenario.json")
        ? executable_data : std::filesystem::path(PROPHECY_DATA_DIR);
    arguments.scenario_path = (data_directory / "scenario.json").string();
    arguments.rig_path = (data_directory / "rig.json").string();
    arguments.locomotion_poses_path = (data_directory / "locomotion_poses.json").string();
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--scenario" && index + 1 < argc) arguments.scenario_path = argv[++index];
        else if (argument == "--rig" && index + 1 < argc) arguments.rig_path = argv[++index];
        else if (argument == "--locomotion-poses" && index + 1 < argc) arguments.locomotion_poses_path = argv[++index];
        else if (argument == "--capture" && index + 1 < argc) arguments.capture_path = argv[++index];
        else if (argument == "--capture-options") arguments.capture_options = true;
        else if (argument == "--capture-tick" && index + 1 < argc) arguments.capture_tick = std::strtoull(argv[++index], nullptr, 10);
        else if (argument == "--capture-follow-agent" && index + 1 < argc) {
            arguments.capture_follow_agent = static_cast<std::uint32_t>(std::strtoul(argv[++index], nullptr, 10));
        }
        else if (argument == "--headless-benchmark") arguments.headless_benchmark = true;
        else if (argument == "--no-telemetry") arguments.telemetry = false;
        else if (argument == "--telemetry-port" && index + 1 < argc) {
            const int port = std::atoi(argv[++index]);
            if (port > 0 && port <= 65535) arguments.telemetry_port = static_cast<std::uint16_t>(port);
        }
        else if (argument == "--background-reload") arguments.background_reload = true;
        else if (argument == "--restore-foreground" && index + 1 < argc) {
            arguments.restore_foreground = static_cast<std::uintptr_t>(std::strtoull(argv[++index], nullptr, 10));
        }
    }
    return arguments;
}

void ConfigureGui() {
    GuiSetStyle(DEFAULT, TEXT_SIZE, 15);
    GuiSetStyle(DEFAULT, TEXT_COLOR_NORMAL, 0xf0f4f2ff);
    GuiSetStyle(DEFAULT, TEXT_COLOR_FOCUSED, 0xffffffff);
    GuiSetStyle(DEFAULT, TEXT_COLOR_PRESSED, 0xffffffff);
    GuiSetStyle(DEFAULT, BASE_COLOR_NORMAL, 0x333b3dff);
    GuiSetStyle(DEFAULT, BASE_COLOR_FOCUSED, 0x3e555aff);
    GuiSetStyle(DEFAULT, BASE_COLOR_PRESSED, 0x287d8eff);
    GuiSetStyle(DEFAULT, BORDER_COLOR_NORMAL, 0x596669ff);
    GuiSetStyle(DEFAULT, BORDER_COLOR_FOCUSED, 0x51c9dfff);
    GuiSetStyle(DEFAULT, BORDER_COLOR_PRESSED, 0x74dff1ff);
    GuiSetStyle(BUTTON, BORDER_WIDTH, 1);
}

}  // namespace

int main(int argc, char** argv) {
    const Arguments arguments = ParseArguments(argc, argv);
    viewer::Scenario scenario = viewer::MakeFallbackScenario();
    std::string error;
    if (!viewer::LoadScenario(arguments.scenario_path, scenario, error)) {
        std::fprintf(stderr, "%s\nUsing the neutral fallback scenario.\n", error.c_str());
    }
    if (arguments.headless_benchmark) {
        const BenchmarkResult benchmark = RunHeadlessBenchmark(scenario.simulation, scenario.seed, 1.0);
        std::printf("ticks=%llu elapsed_seconds=%.6f ticks_per_second=%.3f realtime_factor=%.3f agents=%u\n",
            static_cast<unsigned long long>(benchmark.ticks), benchmark.seconds,
            benchmark.ticks_per_second, benchmark.realtime_factor, scenario.simulation.agent_count);
        return benchmark.ticks > 0 && benchmark.seconds > 0.0 ? 0 : 3;
    }

    viewer::Rig rig{};
    if (!viewer::LoadRig(arguments.rig_path, rig, error)) {
        std::fprintf(stderr, "%s\n", error.c_str());
        return 2;
    }
    viewer::LocomotionPoses locomotion_poses{};
    if (!viewer::LoadLocomotionPoses(arguments.locomotion_poses_path, locomotion_poses, error)) {
        std::fprintf(stderr, "%s\n", error.c_str());
        return 2;
    }
    const EquipmentJoints equipment_joints = ResolveEquipmentJoints(locomotion_poses);
    viewer::ControlSettings settings = viewer::DefaultControlSettings();
    std::string settings_status;
    if (!viewer::LoadControlSettings(ControlSettingsPath(), settings, error)) settings_status = "Defaults active";

    unsigned int flags = FLAG_WINDOW_RESIZABLE | FLAG_MSAA_4X_HINT | FLAG_VSYNC_HINT;
    if (arguments.background_reload) flags |= FLAG_WINDOW_UNFOCUSED | FLAG_WINDOW_HIDDEN;
    SetConfigFlags(flags);
    SetTraceLogLevel(LOG_WARNING);
    InitWindow(1500, 900, "Prophecy Standalone Simulation");
    if (arguments.background_reload) viewer::ShowWindowAtBottom(GetWindowHandle(), arguments.restore_foreground);
    SetWindowMinSize(1000, 650);
    SetTargetFPS(60);
    ConfigureGui();

    FlyingCamera flying_camera{};
    flying_camera.Initialize(CoreToWorld(scenario.camera_focus), scenario.camera_distance,
        scenario.camera_yaw, scenario.camera_pitch);
    sim::Simulation simulation(scenario.simulation, scenario.seed);
    if (arguments.capture_tick > 0) {
        for (std::uint64_t tick = 0; tick < arguments.capture_tick; ++tick) simulation.Tick();
    }
    if (arguments.capture_follow_agent != 0) {
        const auto followed = std::find_if(simulation.Snapshot().agents.begin(), simulation.Snapshot().agents.end(),
            [&arguments](const sim::AgentSnapshot& agent) { return agent.id == arguments.capture_follow_agent; });
        if (followed != simulation.Snapshot().agents.end()) flying_camera.Follow(*followed, 0.0f);
    }
#if PROPHECY_ENABLE_REWIND
    RewindController rewind{};
#endif
    viewer::TelemetryServer telemetry{};
    if (arguments.telemetry && !telemetry.Start(arguments.telemetry_port, error)) {
        std::fprintf(stderr, "%s\n", error.c_str());
    }

    bool paused = !arguments.capture_path.empty();
    bool options_open = arguments.capture_options;
    float time_scale = 1.0f;
    double tick_accumulator = 0.0;
    BenchmarkResult benchmark{};
    int capture_frames = 0;
    AgentDoubleClick agent_double_click{};
    sim::EntityId selected_agent_id = arguments.capture_follow_agent;

    while (!WindowShouldClose()) {
        const Rectangle transport{12.0f, 12.0f, 480.0f, 104.0f};
        const Rectangle info{static_cast<float>(GetScreenWidth()) - 342.0f, 12.0f, 330.0f, kInfoPanelHeight};
        const Rectangle options{static_cast<float>(GetScreenWidth()) - 332.0f, kOptionsPanelY, 320.0f, 330.0f};
        const Vector2 mouse = GetMousePosition();
        const bool ui_hovered = CheckCollisionPointRec(mouse, transport) || CheckCollisionPointRec(mouse, info) ||
            (options_open && CheckCollisionPointRec(mouse, options));
        if (IsKeyPressed(KEY_SPACE)) paused = !paused;
#if PROPHECY_ENABLE_REWIND
        if (IsKeyPressed(KEY_LEFT)) {
            paused = true;
            (void)rewind.SeekBackward(simulation, 1U);
            tick_accumulator = 0.0;
        }
#endif
        if (IsKeyPressed(KEY_RIGHT)) {
            paused = true;
            AdvanceTicks(simulation,
#if PROPHECY_ENABLE_REWIND
                rewind,
#endif
                1U);
            tick_accumulator = 0.0;
        }

        if (!paused) {
            tick_accumulator += static_cast<double>(GetFrameTime()) * static_cast<double>(time_scale);
            const double tick_seconds = simulation.TickSeconds();
            std::uint64_t due_ticks = static_cast<std::uint64_t>(tick_accumulator / tick_seconds);
            due_ticks = std::min<std::uint64_t>(due_ticks, 400U);
            if (due_ticks > 0) {
                AdvanceTicks(simulation,
#if PROPHECY_ENABLE_REWIND
                    rewind,
#endif
                    due_ticks);
                tick_accumulator -= static_cast<double>(due_ticks) * tick_seconds;
            }
        }

        const float render_prediction_seconds = paused ? 0.0f : static_cast<float>(
            std::clamp(tick_accumulator, 0.0, simulation.TickSeconds()));

        if (!ui_hovered && IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            const sim::AgentSnapshot* picked = PickAgent(
                simulation.Snapshot(), flying_camera.camera, mouse, render_prediction_seconds);
            if (picked != nullptr) {
                selected_agent_id = picked->id;
                if (agent_double_click.Register(*picked, mouse)) {
                    flying_camera.Follow(*picked, render_prediction_seconds);
                }
            } else {
                selected_agent_id = sim::kInvalidEntityId;
                agent_double_click.Clear();
            }
        }
        if ((IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_KP_ENTER)) &&
            selected_agent_id != sim::kInvalidEntityId) {
            const sim::AgentSnapshot* selected = FindAgent(simulation.Snapshot(), selected_agent_id);
            if (selected != nullptr) flying_camera.Follow(*selected, render_prediction_seconds);
        }
        flying_camera.Update(settings, !ui_hovered, simulation.Snapshot(), render_prediction_seconds);

        if (telemetry.SnapshotRequested()) {
            viewer::TelemetryViewState view{};
            view.paused = paused;
            view.time_scale = time_scale;
            view.render_fps = GetFPS();
            view.replaying = simulation.IsReplaying();
            view.selected_agent_id = selected_agent_id;
#if PROPHECY_ENABLE_REWIND
            view.rewind_active = rewind.active;
            view.rewind_head_tick = rewind.DisplayHead(simulation);
#else
            view.rewind_head_tick = simulation.Snapshot().tick;
#endif
            telemetry.FulfillSnapshot(scenario.name, simulation.Snapshot(), simulation.Config(), view);
        }

        BeginDrawing();
        ClearBackground(scenario.sky_color);
        BeginMode3D(flying_camera.camera);
        DrawWorld(scenario, simulation.Snapshot(), locomotion_poses,
            equipment_joints, selected_agent_id, render_prediction_seconds);
        EndMode3D();

        Tooltip tooltip{};
        const UiActions actions = DrawUi(scenario, simulation, paused, time_scale,
#if PROPHECY_ENABLE_REWIND
            rewind.active, rewind.DisplayHead(simulation),
#else
            false, simulation.Snapshot().tick,
#endif
            options_open, settings, benchmark, settings_status, selected_agent_id, tooltip);
        DrawTooltip(tooltip);
        EndDrawing();

        if (actions.toggle_pause) paused = !paused;
#if PROPHECY_ENABLE_REWIND
        if (actions.rewind_second) {
            paused = true;
            (void)rewind.SeekBackward(simulation, static_cast<std::uint64_t>(simulation.Config().tick_rate_hz));
        }
        if (actions.previous_tick) {
            paused = true;
            (void)rewind.SeekBackward(simulation, 1U);
        }
        if (actions.return_live) {
            paused = true;
            (void)rewind.ReturnLive(simulation);
        }
#endif
        if (actions.next_tick) {
            paused = true;
            AdvanceTicks(simulation,
#if PROPHECY_ENABLE_REWIND
                rewind,
#endif
                1U);
        }
        if (actions.next_second) {
            paused = true;
            AdvanceTicks(simulation,
#if PROPHECY_ENABLE_REWIND
                rewind,
#endif
                static_cast<std::uint64_t>(simulation.Config().tick_rate_hz));
        }
        if (actions.reset) {
            simulation.Reset(simulation.Seed());
#if PROPHECY_ENABLE_REWIND
            rewind.Clear();
#endif
            tick_accumulator = 0.0;
        }
        if (actions.new_seed) {
            simulation.Reset(NewSeed());
#if PROPHECY_ENABLE_REWIND
            rewind.Clear();
#endif
            tick_accumulator = 0.0;
        }
        if (actions.benchmark) benchmark = RunHeadlessBenchmark(simulation.Config(), simulation.Seed());
        if (actions.reset_settings) {
            settings = viewer::DefaultControlSettings();
            settings_status = "Defaults restored";
        }
        if (actions.save_settings) {
            settings_status = viewer::SaveControlSettings(ControlSettingsPath(), settings, error)
                ? "Saved" : "Save failed";
        }

        if (!arguments.capture_path.empty() && ++capture_frames >= 8) {
            TakeScreenshot(arguments.capture_path.c_str());
            break;
        }
    }

    telemetry.Stop();
    CloseWindow();
    return 0;
}
