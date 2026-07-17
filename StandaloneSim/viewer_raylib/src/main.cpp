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
#include "rlgl.h"

#include <algorithm>
#include <array>
#include <bitset>
#include <cerrno>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <iterator>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <system_error>
#include <vector>

namespace {

namespace sim = ::prophecy::sim;
namespace viewer = ::prophecy::viewer;

constexpr std::uint16_t kDefaultTelemetryPort = 17831;
constexpr float kPi = 3.14159265358979323846f;
constexpr KeyboardKey kAzertyLabelAKey = KEY_Q;
constexpr KeyboardKey kAzertyLabelQKey = KEY_A;
constexpr KeyboardKey kAzertyLabelZKey = KEY_W;
constexpr Color kPanel{24, 29, 31, 245};
constexpr Color kPanelRaised{34, 41, 43, 255};
constexpr Color kText{238, 242, 240, 255};
constexpr Color kMuted{164, 175, 171, 255};
constexpr Color kAccent{63, 188, 211, 255};
constexpr Color kHeroSkeleton{48, 168, 232, 255};
constexpr Color kVillainSkeleton{235, 74, 83, 255};
constexpr Color kHead{226, 214, 190, 255};
constexpr Color kCapCrown{47, 54, 57, 255};
constexpr Color kCapBrim{31, 36, 38, 255};
constexpr Color kWoundWarning{255, 222, 96, 255};
constexpr Color kInjuredLimb{255, 148, 40, 255};
constexpr Color kInjuredCritical{240, 70, 45, 255};
constexpr Color kBadlyInjuredLimb{255, 67, 196, 255};
constexpr Color kBadlyInjuredCritical{154, 36, 190, 255};
constexpr Color kDeadLimb{66, 70, 72, 255};
constexpr Color kRootMarker{255, 205, 64, 255};
constexpr Color kSheath{48, 42, 38, 255};
constexpr Color kLeather{103, 66, 43, 255};
constexpr Color kSwordMetal{224, 232, 234, 255};
constexpr Color kSwordGuard{214, 164, 54, 255};
constexpr Color kTrainingStick{151, 101, 54, 255};
constexpr Color kSelection{244, 247, 246, 255};
constexpr Color kSoundRing{185, 235, 202, 210};
constexpr Color kTacticalCone{112, 224, 168, 185};
constexpr Color kTacticalMove{67, 204, 232, 255};
constexpr float kInfoPanelHeight = 400.0f;
constexpr float kOptionsPanelY = 424.0f;
constexpr float kOptionsPanelHeight = 464.0f;
constexpr std::size_t kMaximumRenderedJoints = 64U;
constexpr int kSoundRingSegments = 20;
constexpr int kMaximumOverviewAgentRows = 13;
constexpr std::size_t kLineBatchCapacity = 24'000U;
constexpr std::size_t kSolidVertexCapacity = 1'300'002U;

struct RenderLine {
    Vector3 start{};
    Vector3 end{};
    Color color{};
};

struct LineBatch {
    std::array<RenderLine, kLineBatchCapacity> lines{};
    std::size_t count = 0;

    void Clear() noexcept { count = 0; }

    void Add(Vector3 start, Vector3 end, Color color) noexcept {
        if (count < lines.size()) lines[count++] = {start, end, color};
    }

    void Draw() const noexcept {
        if (count == 0U) return;
        rlBegin(RL_LINES);
        for (std::size_t index = 0; index < count; ++index) {
            const RenderLine& line = lines[index];
            rlColor4ub(line.color.r, line.color.g, line.color.b, line.color.a);
            rlVertex3f(line.start.x, line.start.y, line.start.z);
            rlVertex3f(line.end.x, line.end.y, line.end.z);
        }
        rlEnd();
    }
};

struct SphereTemplate {
    std::array<Vector3, 1'632U> vertices{};
    std::size_t count = 0;
};

struct SolidBatch {
    Mesh mesh{};
    Material material{};
    std::array<std::array<Vector2, 13U>, 13U> unit_circles{};
    SphereTemplate sphere_8{};
    SphereTemplate sphere_16{};
    std::size_t count = 0;

    static SphereTemplate BuildSphereTemplate(int rings, int slices) {
        SphereTemplate result{};
        const float ring_angle = kPi / static_cast<float>(rings + 1);
        const float slice_angle = 2.0f * kPi / static_cast<float>(slices);
        const float cosine_ring = std::cos(ring_angle);
        const float sine_ring = std::sin(ring_angle);
        const float cosine_slice = std::cos(slice_angle);
        const float sine_slice = std::sin(slice_angle);
        std::array<Vector3, 4U> face{};
        face[2] = {0.0f, 1.0f, 0.0f};
        face[3] = {sine_ring, cosine_ring, 0.0f};
        const auto append = [&result](Vector3 value) {
            if (result.count < result.vertices.size()) result.vertices[result.count++] = value;
        };
        for (int ring = 0; ring < rings + 1; ++ring) {
            for (int slice = 0; slice < slices; ++slice) {
                face[0] = face[2];
                face[1] = face[3];
                face[2] = {cosine_slice * face[2].x - sine_slice * face[2].z, face[2].y,
                    sine_slice * face[2].x + cosine_slice * face[2].z};
                face[3] = {cosine_slice * face[3].x - sine_slice * face[3].z, face[3].y,
                    sine_slice * face[3].x + cosine_slice * face[3].z};
                append(face[0]);
                append(face[3]);
                append(face[1]);
                append(face[0]);
                append(face[2]);
                append(face[3]);
            }
            face[2] = face[3];
            face[3] = {cosine_ring * face[3].x + sine_ring * face[3].y,
                -sine_ring * face[3].x + cosine_ring * face[3].y, face[3].z};
        }
        return result;
    }

    void Initialize() {
        for (int sides = 3; sides <= 12; ++sides) {
            const float angle = 2.0f * kPi / static_cast<float>(sides);
            for (int index = 0; index <= sides; ++index) {
                unit_circles[static_cast<std::size_t>(sides)][static_cast<std::size_t>(index)] = {
                    std::sin(angle * static_cast<float>(index)),
                    std::cos(angle * static_cast<float>(index))};
            }
        }
        sphere_8 = BuildSphereTemplate(8, 8);
        sphere_16 = BuildSphereTemplate(16, 16);
        mesh.vertexCount = static_cast<int>(kSolidVertexCapacity);
        mesh.triangleCount = mesh.vertexCount / 3;
        mesh.vertices = static_cast<float*>(MemAlloc(kSolidVertexCapacity * 3U * sizeof(float)));
        mesh.colors = static_cast<unsigned char*>(MemAlloc(kSolidVertexCapacity * 4U));
        std::fill_n(mesh.vertices, kSolidVertexCapacity * 3U, 0.0f);
        std::fill_n(mesh.colors, kSolidVertexCapacity * 4U, static_cast<unsigned char>(255));
        UploadMesh(&mesh, true);
        material = LoadMaterialDefault();
    }

    void Shutdown() {
        if (mesh.vaoId != 0U) UnloadMesh(mesh);
        if (material.maps != nullptr) UnloadMaterial(material);
        mesh = {};
        material = {};
    }

    void Clear() noexcept { count = 0; }

    void AddVertex(Vector3 position, Color color) noexcept {
        if (count >= kSolidVertexCapacity) return;
        const std::size_t position_index = count * 3U;
        mesh.vertices[position_index] = position.x;
        mesh.vertices[position_index + 1U] = position.y;
        mesh.vertices[position_index + 2U] = position.z;
        const std::size_t color_index = count * 4U;
        mesh.colors[color_index] = color.r;
        mesh.colors[color_index + 1U] = color.g;
        mesh.colors[color_index + 2U] = color.b;
        mesh.colors[color_index + 3U] = color.a;
        ++count;
    }

    void AddTriangle(Vector3 first, Vector3 second, Vector3 third, Color color) noexcept {
        AddVertex(first, color);
        AddVertex(second, color);
        AddVertex(third, color);
    }

    void AddCylinder(Vector3 start, Vector3 end, float start_radius, float end_radius,
        int sides, Color color) noexcept {
        sides = std::clamp(sides, 3, 12);
        const Vector3 direction = Vector3Subtract(end, start);
        if (Vector3LengthSqr(direction) <= 0.0f) return;
        const Vector3 first_axis = Vector3Normalize(Vector3Perpendicular(direction));
        const Vector3 second_axis = Vector3Normalize(Vector3CrossProduct(first_axis, direction));
        const auto& circle = unit_circles[static_cast<std::size_t>(sides)];
        for (int side = 0; side < sides; ++side) {
            const Vector2 first = circle[static_cast<std::size_t>(side)];
            const Vector2 second = circle[static_cast<std::size_t>(side + 1)];
            const float start_first_x = first.x * start_radius;
            const float start_first_y = first.y * start_radius;
            const float start_second_x = second.x * start_radius;
            const float start_second_y = second.y * start_radius;
            const float end_first_x = first.x * end_radius;
            const float end_first_y = first.y * end_radius;
            const float end_second_x = second.x * end_radius;
            const float end_second_y = second.y * end_radius;
            const Vector3 start_first{
                start.x + start_first_x * first_axis.x + start_first_y * second_axis.x,
                start.y + start_first_x * first_axis.y + start_first_y * second_axis.y,
                start.z + start_first_x * first_axis.z + start_first_y * second_axis.z};
            const Vector3 start_second{
                start.x + start_second_x * first_axis.x + start_second_y * second_axis.x,
                start.y + start_second_x * first_axis.y + start_second_y * second_axis.y,
                start.z + start_second_x * first_axis.z + start_second_y * second_axis.z};
            const Vector3 end_first{
                end.x + end_first_x * first_axis.x + end_first_y * second_axis.x,
                end.y + end_first_x * first_axis.y + end_first_y * second_axis.y,
                end.z + end_first_x * first_axis.z + end_first_y * second_axis.z};
            const Vector3 end_second{
                end.x + end_second_x * first_axis.x + end_second_y * second_axis.x,
                end.y + end_second_x * first_axis.y + end_second_y * second_axis.y,
                end.z + end_second_x * first_axis.z + end_second_y * second_axis.z};
            if (start_radius > 0.0f) AddTriangle(start, start_second, start_first, color);
            AddTriangle(start_first, start_second, end_first, color);
            AddTriangle(start_second, end_second, end_first, color);
            if (end_radius > 0.0f) AddTriangle(end, end_first, end_second, color);
        }
    }

    void AddSphere(Vector3 center, float radius, int rings, int slices, Color color) noexcept {
        const SphereTemplate& sphere = (rings == 8 && slices == 8) ? sphere_8 : sphere_16;
        for (std::size_t index = 0; index < sphere.count; ++index) {
            AddVertex(Vector3Add(center, Vector3Scale(sphere.vertices[index], radius)), color);
        }
    }

    void Draw() {
        if (count == 0U) return;
        UpdateMeshBuffer(mesh, RL_DEFAULT_SHADER_ATTRIB_LOCATION_POSITION, mesh.vertices,
            static_cast<int>(count * 3U * sizeof(float)), 0);
        UpdateMeshBuffer(mesh, RL_DEFAULT_SHADER_ATTRIB_LOCATION_COLOR, mesh.colors,
            static_cast<int>(count * 4U), 0);
        const int capacity = mesh.vertexCount;
        mesh.vertexCount = static_cast<int>(count);
        mesh.triangleCount = mesh.vertexCount / 3;
        DrawMesh(mesh, material, MatrixIdentity());
        mesh.vertexCount = capacity;
        mesh.triangleCount = capacity / 3;
    }
};

float OptionsPanelTop() {
    return std::min(kOptionsPanelY,
        std::max(12.0f, static_cast<float>(GetScreenHeight()) - kOptionsPanelHeight - 12.0f));
}

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
        if (IsKeyDown(kAzertyLabelZKey)) movement = Vector3Add(movement, forward);
        if (IsKeyDown(KEY_S)) movement = Vector3Subtract(movement, forward);
        if (IsKeyDown(KEY_D)) movement = Vector3Add(movement, right);
        if (IsKeyDown(kAzertyLabelQKey)) movement = Vector3Subtract(movement, right);
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

using AgentSelection = std::bitset<sim::kMaxSimulationAgentCount>;

const sim::AgentSnapshot* PickAgent(const sim::SimulationSnapshot& snapshot,
    const Camera3D& camera, Vector2 screen_position, float prediction_seconds,
    const AgentSelection* eligible_agents = nullptr) {
    const Ray ray = GetScreenToWorldRay(screen_position, camera);
    const sim::AgentSnapshot* nearest = nullptr;
    float nearest_distance = 1.0e30f;
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        if (eligible_agents != nullptr &&
            (agent.id == sim::kInvalidEntityId || agent.id > sim::kMaxSimulationAgentCount ||
                !eligible_agents->test(static_cast<std::size_t>(agent.id - 1U)))) continue;
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

bool IsAgentSelected(const AgentSelection& selection, sim::EntityId id) noexcept {
    return id != sim::kInvalidEntityId && id <= sim::kMaxSimulationAgentCount &&
        selection.test(static_cast<std::size_t>(id - 1U));
}

void SelectOnlyAgent(AgentSelection& selection, sim::EntityId id) noexcept {
    selection.reset();
    if (id != sim::kInvalidEntityId && id <= sim::kMaxSimulationAgentCount) {
        selection.set(static_cast<std::size_t>(id - 1U));
    }
}

void SelectAgentTeam(const sim::SimulationSnapshot& snapshot, sim::EntityId selected_agent_id,
    AgentSelection& selection) noexcept {
    const sim::AgentSnapshot* selected = FindAgent(snapshot, selected_agent_id);
    if (selected == nullptr) return;
    selection.reset();
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        if (agent.team == selected->team && agent.id <= sim::kMaxSimulationAgentCount) {
            selection.set(static_cast<std::size_t>(agent.id - 1U));
        }
    }
}

bool GroundPointFromMouse(const Camera3D& camera, Vector2 screen_position, Vector3& point) {
    const Ray ray = GetScreenToWorldRay(screen_position, camera);
    if (std::fabs(ray.direction.y) < 1.0e-5f) return false;
    const float distance = -ray.position.y / ray.direction.y;
    if (distance < 0.0f) return false;
    point = Vector3Add(ray.position, Vector3Scale(ray.direction, distance));
    point.y = 0.0f;
    return true;
}

bool ControlKeyDown() noexcept {
    return IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL);
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

struct AgentTransformDrag {
    struct Member {
        sim::EntityId id = sim::kInvalidEntityId;
        sim::Vec3 position{};
        float facing_radians = 0.0f;
    };

    std::array<Member, sim::kMaxSimulationAgentCount> members{};
    std::size_t member_count = 0;
    sim::EntityId anchor_id = sim::kInvalidEntityId;
    Vector2 start_mouse{};
    Vector2 start_ground{};
    bool editing = false;
    bool mode_initialized = false;
    bool rotating = false;

    void Begin(const sim::SimulationSnapshot& snapshot, const sim::AgentSnapshot& anchor,
        const AgentSelection& selection, Vector2 mouse, Vector3 ground_point) noexcept {
        anchor_id = anchor.id;
        start_mouse = mouse;
        start_ground = {ground_point.x, ground_point.z};
        member_count = 0;
        for (const sim::AgentSnapshot& agent : snapshot.agents) {
            if (!IsAgentSelected(selection, agent.id) || member_count >= members.size()) continue;
            members[member_count++] = {agent.id, agent.position, agent.facing_radians};
        }
        if (member_count == 0) {
            members[0] = {anchor.id, anchor.position, anchor.facing_radians};
            member_count = 1;
        }
        editing = false;
        mode_initialized = false;
        rotating = false;
    }

    void RebaseForMode(const sim::SimulationSnapshot& snapshot, Vector3 ground_point,
        bool rotate) noexcept {
        if (!mode_initialized) {
            mode_initialized = true;
            rotating = rotate;
            return;
        }
        if (rotating == rotate) return;

        for (std::size_t index = 0; index < member_count; ++index) {
            const sim::AgentSnapshot* agent = FindAgent(snapshot, members[index].id);
            if (agent == nullptr) continue;
            members[index].position = agent->position;
            members[index].facing_radians = agent->facing_radians;
        }
        start_ground = {ground_point.x, ground_point.z};
        rotating = rotate;
    }

    static void KeepRigidGroupInWorld(const sim::SimulationConfig& config,
        std::vector<sim::AgentTransform>& transforms) {
        if (transforms.empty()) return;
        float minimum_x = transforms.front().position.x;
        float maximum_x = minimum_x;
        float minimum_z = transforms.front().position.y;
        float maximum_z = minimum_z;
        for (const sim::AgentTransform& transform : transforms) {
            minimum_x = std::min(minimum_x, transform.position.x);
            maximum_x = std::max(maximum_x, transform.position.x);
            minimum_z = std::min(minimum_z, transform.position.y);
            maximum_z = std::max(maximum_z, transform.position.y);
        }
        float correction_x = 0.0f;
        float correction_z = 0.0f;
        if (minimum_x < config.world_min.x) correction_x = config.world_min.x - minimum_x;
        else if (maximum_x > config.world_max.x) correction_x = config.world_max.x - maximum_x;
        if (minimum_z < config.world_min.y) correction_z = config.world_min.y - minimum_z;
        else if (maximum_z > config.world_max.y) correction_z = config.world_max.y - maximum_z;
        for (sim::AgentTransform& transform : transforms) {
            transform.position.x += correction_x;
            transform.position.y += correction_z;
        }
    }

    bool BuildTransforms(Vector3 ground_point, bool rotate,
        const sim::SimulationConfig& config,
        std::vector<sim::AgentTransform>& transforms) const {
        transforms.clear();
        if (member_count == 0) return false;
        transforms.reserve(sim::kMaxSimulationAgentCount);

        if (!rotate) {
            const Vector2 delta{ground_point.x - start_ground.x, ground_point.z - start_ground.y};
            for (std::size_t index = 0; index < member_count; ++index) {
                const Member& member = members[index];
                transforms.push_back({member.id,
                    {member.position.x + delta.x, member.position.y + delta.y, 0.0f},
                    member.facing_radians});
            }
            KeepRigidGroupInWorld(config, transforms);
            return true;
        }

        for (std::size_t index = 0; index < member_count; ++index) {
            const Member& member = members[index];
            const float delta_x = ground_point.x - member.position.x;
            const float delta_z = ground_point.z - member.position.y;
            if (delta_x * delta_x + delta_z * delta_z <= 1.0e-6f) {
                transforms.push_back({member.id, member.position, member.facing_radians});
            } else {
                transforms.push_back(
                    {member.id, member.position, std::atan2(delta_x, delta_z)});
            }
        }
        return true;
    }

    bool CapturesMouse() const noexcept { return anchor_id != sim::kInvalidEntityId; }

    void Clear() noexcept {
        anchor_id = sim::kInvalidEntityId;
        member_count = 0;
        editing = false;
        mode_initialized = false;
        rotating = false;
    }
};

std::vector<sim::AgentTransform> BuildSquareFormation(
    const sim::SimulationSnapshot& snapshot, const sim::SimulationConfig& config) {
    constexpr float kSpacingMeters = 1.25f;
    std::vector<sim::AgentTransform> transforms;
    transforms.reserve(snapshot.agents.size());

    for (const sim::Team team : {sim::Team::Hero, sim::Team::Villain}) {
        std::array<const sim::AgentSnapshot*, sim::kMaxSimulationAgentCount> team_agents{};
        std::size_t count = 0;
        Vector2 mean{};
        for (const sim::AgentSnapshot& agent : snapshot.agents) {
            if (agent.team != team || count >= team_agents.size()) continue;
            team_agents[count++] = &agent;
            mean.x += agent.position.x;
            mean.y += agent.position.y;
        }
        if (count == 0) continue;
        mean = Vector2Scale(mean, 1.0f / static_cast<float>(count));

        const std::size_t columns = static_cast<std::size_t>(
            std::ceil(std::sqrt(static_cast<float>(count))));
        const std::size_t rows = (count + columns - 1U) / columns;
        std::array<Vector2, sim::kMaxSimulationAgentCount> offsets{};
        Vector2 offset_mean{};
        for (std::size_t index = 0; index < count; ++index) {
            const std::size_t row = index / columns;
            const std::size_t column = index % columns;
            const std::size_t row_count = std::min(columns, count - row * columns);
            offsets[index] = {
                (static_cast<float>(column) - 0.5f * static_cast<float>(row_count - 1U)) * kSpacingMeters,
                (static_cast<float>(row) - 0.5f * static_cast<float>(rows - 1U)) * kSpacingMeters,
            };
            offset_mean = Vector2Add(offset_mean, offsets[index]);
        }
        offset_mean = Vector2Scale(offset_mean, 1.0f / static_cast<float>(count));

        Vector2 minimum_offset{0.0f, 0.0f};
        Vector2 maximum_offset{0.0f, 0.0f};
        for (std::size_t index = 0; index < count; ++index) {
            offsets[index] = Vector2Subtract(offsets[index], offset_mean);
            minimum_offset.x = std::min(minimum_offset.x, offsets[index].x);
            minimum_offset.y = std::min(minimum_offset.y, offsets[index].y);
            maximum_offset.x = std::max(maximum_offset.x, offsets[index].x);
            maximum_offset.y = std::max(maximum_offset.y, offsets[index].y);
        }
        mean.x = std::clamp(mean.x, config.world_min.x - minimum_offset.x,
            config.world_max.x - maximum_offset.x);
        mean.y = std::clamp(mean.y, config.world_min.y - minimum_offset.y,
            config.world_max.y - maximum_offset.y);
        for (std::size_t index = 0; index < count; ++index) {
            const sim::AgentSnapshot& agent = *team_agents[index];
            transforms.push_back({agent.id,
                {mean.x + offsets[index].x, mean.y + offsets[index].y, 0.0f},
                agent.facing_radians});
        }
    }
    return transforms;
}

sim::Limb JointLimb(const std::string& name);

struct EquipmentJoints {
    int pelvis = -1;
    int upperarm_left = -1;
    int lowerarm_left = -1;
    int hand_left = -1;
    int upperarm_right = -1;
    int lowerarm_right = -1;
    int hand_right = -1;
    int head = -1;
    std::size_t joint_count = 0;
    std::array<sim::Limb, kMaximumRenderedJoints> limbs{};

    bool EquipmentValid() const noexcept {
        return pelvis >= 0 && lowerarm_right >= 0 && hand_right >= 0;
    }

    bool LeftArmValid() const noexcept {
        return upperarm_left >= 0 && lowerarm_left >= 0 && hand_left >= 0;
    }

    bool RightArmValid() const noexcept {
        return upperarm_right >= 0 && lowerarm_right >= 0 && hand_right >= 0;
    }
};

EquipmentJoints ResolveEquipmentJoints(const viewer::LocomotionPoses& poses) {
    const auto find = [&poses](const char* name) {
        const auto joint = std::find(poses.joint_names.begin(), poses.joint_names.end(), name);
        return joint == poses.joint_names.end()
            ? -1 : static_cast<int>(std::distance(poses.joint_names.begin(), joint));
    };
    EquipmentJoints result{};
    result.pelvis = find("pelvis");
    result.upperarm_left = find("upperarm_l");
    result.lowerarm_left = find("lowerarm_l");
    result.hand_left = find("hand_l");
    result.upperarm_right = find("upperarm_r");
    result.lowerarm_right = find("lowerarm_r");
    result.hand_right = find("hand_r");
    result.head = find("head");
    result.joint_count = std::min(poses.joint_names.size(), kMaximumRenderedJoints);
    for (std::size_t index = 0; index < result.joint_count; ++index) {
        result.limbs[index] = JointLimb(poses.joint_names[index]);
    }
    return result;
}

#if PROPHECY_ENABLE_REWIND
struct RewindController {
    static constexpr std::uint64_t kCheckpointIntervalTicks = 30U;

    sim::ReplayLog tape{};
    std::map<std::uint64_t, std::unique_ptr<sim::Simulation>> checkpoints{};
    std::uint64_t head_tick = 0;
    bool active = false;

    void Clear() noexcept {
        tape = {};
        checkpoints.clear();
        head_tick = 0;
        active = false;
    }

    void Capture(const sim::Simulation& simulation, bool force = false) {
        if (active || simulation.HasTransientAgents()) return;
        const std::uint64_t current_tick = simulation.Snapshot().tick;
        if (!force && current_tick % kCheckpointIntervalTicks != 0U) return;
        checkpoints[current_tick] = simulation.CreateRewindCheckpoint();
    }

    void Reset(const sim::Simulation& simulation) {
        Clear();
        Capture(simulation, true);
    }

    void RefreshCurrent(const sim::Simulation& simulation) {
        if (active || simulation.HasTransientAgents()) return;
        const auto checkpoint = checkpoints.find(simulation.Snapshot().tick);
        if (checkpoint != checkpoints.end()) checkpoint->second = simulation.CreateRewindCheckpoint();
    }

    bool PrepareTransformEdit(sim::Simulation& simulation) {
        if (!active) return true;
        if (!simulation.BranchRecordingFromReplay()) return false;
        const std::uint64_t current_tick = simulation.Snapshot().tick;
        checkpoints.erase(checkpoints.upper_bound(current_tick), checkpoints.end());
        tape = {};
        head_tick = current_tick;
        active = false;
        return true;
    }

    void CommitTransformEdit(const sim::Simulation& simulation) {
        if (active || simulation.HasTransientAgents()) return;
        const std::uint64_t current_tick = simulation.Snapshot().tick;
        checkpoints.erase(checkpoints.upper_bound(current_tick), checkpoints.end());
        checkpoints[current_tick] = simulation.CreateRewindCheckpoint();
    }

    bool Seek(sim::Simulation& simulation, std::uint64_t target_tick) {
        const bool discard_transient_state = simulation.HasTransientAgents();
        if (!active) {
            tape = simulation.RecordedReplay();
            head_tick = tape.end_tick;
            Capture(simulation, true);
            if (head_tick == 0 && !discard_transient_state) return target_tick == 0;
        }
        target_tick = std::min(target_tick, head_tick);
        const std::uint64_t current_tick = simulation.Snapshot().tick;
        if (target_tick != current_tick || discard_transient_state) {
            const bool short_forward_seek = !discard_transient_state && simulation.IsReplaying() &&
                target_tick > current_tick &&
                target_tick - current_tick <= kCheckpointIntervalTicks;
            if (short_forward_seek) {
                while (simulation.Snapshot().tick < target_tick) simulation.Tick();
            } else {
                const auto after_target = checkpoints.upper_bound(target_tick);
                if (after_target == checkpoints.begin()) {
                    if (!simulation.SeekReplay(tape, target_tick)) return false;
                } else {
                    const auto checkpoint = std::prev(after_target);
                    if (!simulation.RestoreRewindCheckpoint(*checkpoint->second, tape)) return false;
                    while (simulation.Snapshot().tick < target_tick) simulation.Tick();
                }
            }
        }
        active = target_tick < head_tick;
        if (!active && simulation.IsReplaying()) return simulation.ResumeRecordingFromReplay();
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
        if (!active) Capture(simulation);
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

Vector3 ApplyStatePose(Vector3 local, sim::AgentState state) {
    const float height = local.y;
    if (state == sim::AgentState::Agonising) {
        local.y = 0.10f + height * 0.28f;
        local.z += (height - 0.80f) * 0.55f;
    } else if (state == sim::AgentState::PassedOut) {
        local.y = 0.09f + std::max(0.0f, std::fabs(local.x) - 0.18f) * 0.04f;
        local.z += (height - 0.80f) * 0.90f;
    } else if (state == sim::AgentState::Crawling) {
        local.y = 0.10f + height * 0.32f;
        local.z += (height - 0.80f) * 0.62f;
    } else if (state == sim::AgentState::Dead) {
        local.y = 0.055f + std::max(0.0f, std::fabs(local.x) - 0.18f) * 0.025f;
        local.z += (height - 0.80f) * 0.94f;
    }
    return local;
}

Color BlendColor(Color healthy, Color injured, float injury) {
    injury = std::clamp(injury, 0.0f, 1.0f);
    const auto channel = [injury](unsigned char from, unsigned char to) {
        return static_cast<unsigned char>(std::lround(
            static_cast<float>(from) + (static_cast<float>(to) - static_cast<float>(from)) * injury));
    };
    return {channel(healthy.r, injured.r), channel(healthy.g, injured.g),
        channel(healthy.b, injured.b), 255};
}

sim::Limb JointLimb(const std::string& name) {
    if (name == "neck_01" || name == "neck_02" || name == "head") return sim::Limb::Head;
    if (name.find("arm_l") != std::string::npos || name == "hand_l") return sim::Limb::LeftArm;
    if (name.find("arm_r") != std::string::npos || name == "hand_r") return sim::Limb::RightArm;
    if (name == "thigh_l" || name == "calf_l" || name == "foot_l" || name == "ball_l") {
        return sim::Limb::LeftLeg;
    }
    if (name == "thigh_r" || name == "calf_r" || name == "foot_r" || name == "ball_r") {
        return sim::Limb::RightLeg;
    }
    return sim::Limb::Torso;
}

Color LimbColor(const sim::AgentSnapshot& agent, sim::Limb limb, Color healthy) {
    if (agent.state == sim::AgentState::Dead) return kDeadLimb;
    const sim::LimbWoundSnapshot& wound = agent.wounds[static_cast<std::size_t>(limb)];
    const float gauge = wound.gauge_percent / 100.0f;
    if (wound.condition == sim::LimbCondition::BadlyInjured) {
        return BlendColor(kBadlyInjuredLimb, kBadlyInjuredCritical, gauge);
    }
    if (wound.condition == sim::LimbCondition::Injured) {
        return BlendColor(kInjuredLimb, kInjuredCritical, gauge);
    }
    return BlendColor(healthy, kWoundWarning, gauge);
}

const char* WoundStageShort(sim::LimbCondition condition) {
    if (condition == sim::LimbCondition::BadlyInjured) return "badly";
    if (condition == sim::LimbCondition::Injured) return "injured";
    return "normal";
}

void DrawRootMarker(const sim::AgentSnapshot& agent, float prediction_seconds, SolidBatch& solids) {
    Vector3 root = AgentRenderRoot(agent, prediction_seconds);
    root.y = 0.025f;
    const Vector3 forward{std::sin(agent.facing_radians), 0.0f, std::cos(agent.facing_radians)};
    const Vector3 shaft_start = Vector3Add(root, Vector3Scale(forward, 0.075f));
    const Vector3 shaft_end = Vector3Add(root, Vector3Scale(forward, 0.38f));
    const Vector3 arrow_tip = Vector3Add(root, Vector3Scale(forward, 0.52f));

    solids.AddSphere(root, 0.045f, 16, 16, kRootMarker);
    solids.AddCylinder(shaft_start, shaft_end, 0.014f, 0.014f, 6, kRootMarker);
    solids.AddCylinder(shaft_end, arrow_tip, 0.055f, 0.0f, 8, kRootMarker);
}

void DrawTacticalDiagnostics(const sim::AgentSnapshot& agent, float prediction_seconds) {
    Vector3 root = AgentRenderRoot(agent, prediction_seconds);
    root.y = 0.022f;
    if (agent.tactical_steering == sim::TacticalSteeringMode::OutnumberedView) {
        constexpr int segments = 18;
        constexpr float radius = 2.25f;
        const float half_cone = 0.5f * sim::kOutnumberedViewConeRadians;
        Vector3 previous = root;
        for (int index = 0; index <= segments; ++index) {
            const float alpha = static_cast<float>(index) / static_cast<float>(segments);
            const float yaw = agent.tactical_view_center_yaw_radians - half_cone +
                alpha * sim::kOutnumberedViewConeRadians;
            const Vector3 edge = Vector3Add(root,
                {radius * std::sin(yaw), 0.0f, radius * std::cos(yaw)});
            if (index == 0 || index == segments) DrawLine3D(root, edge, kTacticalCone);
            if (index > 0) DrawLine3D(previous, edge, kTacticalCone);
            previous = edge;
        }
    }
    if (agent.tactical_steering == sim::TacticalSteeringMode::Direct ||
        agent.speed_stick_amplitude <= 0.001f) return;
    const Vector3 direction{std::sin(agent.tactical_move_yaw_radians), 0.0f,
        std::cos(agent.tactical_move_yaw_radians)};
    const Vector3 shaft_start = Vector3Add(root, Vector3Scale(direction, 0.58f));
    const Vector3 shaft_end = Vector3Add(root, Vector3Scale(direction, 1.18f));
    const Vector3 arrow_tip = Vector3Add(root, Vector3Scale(direction, 1.42f));
    DrawCylinderEx(shaft_start, shaft_end, 0.018f, 0.018f, 6, kTacticalMove);
    DrawCylinderEx(shaft_end, arrow_tip, 0.075f, 0.0f, 8, kTacticalMove);
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

bool UsesIdlePose(const sim::AgentSnapshot& agent) {
    return agent.speed_stick_amplitude <= 0.001f && agent.root_speed_mps <= 0.01f;
}

float RenderPosePhase(const sim::AgentSnapshot& agent, const viewer::LocomotionPoses& poses,
    double simulation_time_seconds, float prediction_seconds) {
    if (agent.state == sim::AgentState::Dead) return 0.0f;
    if (UsesIdlePose(agent)) {
        const float cycle_frames = static_cast<float>(std::max<std::size_t>(
            1U, poses.idle.frame_count - 1U));
        const double render_time = simulation_time_seconds + prediction_seconds;
        return static_cast<float>(render_time * poses.idle.fps / cycle_frames);
    }
    const float cycle_distance = poses.Clip(agent.locomotion_mode).cycle_distance_m;
    return cycle_distance > 0.0f
        ? agent.pose_phase + agent.root_speed_mps * prediction_seconds / cycle_distance
        : agent.pose_phase;
}

Vector3 SampleLocomotionPoseJoint(const viewer::LocomotionPoses& poses,
    const sim::AgentSnapshot& agent, float render_phase, std::size_t joint) {
    return UsesIdlePose(agent)
        ? viewer::SampleIdlePoseJoint(poses, render_phase, joint)
        : viewer::SamplePoseJoint(poses, agent.locomotion_mode, render_phase, joint);
}

float RenderActionProgress(const sim::AgentSnapshot& agent, float prediction_seconds) {
    if (agent.action.kind == sim::ActionKind::None || agent.action.duration_seconds <= 0.0f ||
        agent.action.phase == sim::ActionPhase::AwaitingValidation) return agent.action.progress;
    return std::clamp((agent.action.elapsed_seconds + prediction_seconds) /
        agent.action.duration_seconds, 0.0f, 1.0f);
}

float SmoothStep(float value);

float RenderReactionProgress(const sim::AgentSnapshot& agent, float prediction_seconds) {
    if (agent.reaction.kind == sim::ReactionKind::None || agent.reaction.duration_seconds <= 0.0f) {
        return agent.reaction.progress;
    }
    return std::clamp((agent.reaction.elapsed_seconds + prediction_seconds) /
        agent.reaction.duration_seconds, 0.0f, 1.0f);
}

float ReactionWeight(float progress) {
    const float enter = SmoothStep(std::clamp(progress / 0.20f, 0.0f, 1.0f));
    const float leave = SmoothStep(std::clamp((1.0f - progress) / 0.20f, 0.0f, 1.0f));
    return std::min(enter, leave);
}

Vector3 SampleBasePoseJoint(const viewer::LocomotionPoses& poses, const sim::AgentSnapshot& agent,
    float render_phase, float action_progress, float reaction_progress, std::size_t joint) {
    Vector3 result{};
    if (agent.action.kind == sim::ActionKind::SwordAttack ||
        agent.action.kind == sim::ActionKind::MeleeAttack) {
        result = viewer::SampleActionPoseJoint(poses, agent.action.kind,
            agent.action.animation_index, action_progress, joint);
    } else {
        result = SampleLocomotionPoseJoint(poses, agent, render_phase, joint);
    }
    if (agent.reaction.kind == sim::ReactionKind::Dodge) {
        const float weight = ReactionWeight(reaction_progress);
        const float height = std::clamp(result.y / 1.7f, 0.0f, 1.0f);
        result.x += (0.10f + 0.22f * height) * weight;
        result.y -= 0.08f * height * weight;
    }
    return result;
}

struct ProceduralReachPose {
    bool left_active = false;
    bool right_active = false;
    Vector3 left_elbow{};
    Vector3 left_hand{};
    Vector3 right_elbow{};
    Vector3 right_hand{};
};

float SmoothStep(float value) {
    value = std::clamp(value, 0.0f, 1.0f);
    return value * value * (3.0f - 2.0f * value);
}

bool SolveArmReach(Vector3 shoulder, Vector3 original_elbow, Vector3 original_hand,
    Vector3 target, float weight, Vector3& solved_elbow, Vector3& solved_hand) {
    constexpr float kMinimumLength = 0.001f;
    const float upper_length = Vector3Distance(shoulder, original_elbow);
    const float lower_length = Vector3Distance(original_elbow, original_hand);
    Vector3 shoulder_to_target = Vector3Subtract(target, shoulder);
    const float target_distance = Vector3Length(shoulder_to_target);
    if (upper_length < kMinimumLength || lower_length < kMinimumLength || target_distance < kMinimumLength) {
        return false;
    }

    const Vector3 direction = Vector3Scale(shoulder_to_target, 1.0f / target_distance);
    const float minimum_reach = std::fabs(upper_length - lower_length) + kMinimumLength;
    const float maximum_reach = upper_length + lower_length - kMinimumLength;
    const float distance = std::clamp(target_distance, minimum_reach, maximum_reach);
    const Vector3 reachable_target = Vector3Add(shoulder, Vector3Scale(direction, distance));
    const float along = (upper_length * upper_length - lower_length * lower_length + distance * distance) /
        (2.0f * distance);
    const float bend_height = std::sqrt(std::max(0.0f, upper_length * upper_length - along * along));

    const Vector3 authored_offset = Vector3Subtract(original_elbow, shoulder);
    Vector3 bend_direction = Vector3Subtract(authored_offset,
        Vector3Scale(direction, Vector3DotProduct(authored_offset, direction)));
    if (Vector3LengthSqr(bend_direction) < 0.000001f) {
        bend_direction = Vector3CrossProduct(direction, {0.0f, 1.0f, 0.0f});
        if (Vector3LengthSqr(bend_direction) < 0.000001f) {
            bend_direction = Vector3CrossProduct(direction, {0.0f, 0.0f, 1.0f});
        }
    }
    bend_direction = Vector3Normalize(bend_direction);
    const Vector3 full_elbow = Vector3Add(shoulder,
        Vector3Add(Vector3Scale(direction, along), Vector3Scale(bend_direction, bend_height)));
    solved_elbow = Vector3Lerp(original_elbow, full_elbow, weight);
    solved_hand = Vector3Lerp(original_hand, reachable_target, weight);
    return true;
}

Vector3 ReachTarget(const sim::AgentSnapshot& agent, const viewer::LocomotionPoses& poses,
    const EquipmentJoints& joints, float render_phase, bool left_hand) {
    if ((agent.action.kind == sim::ActionKind::SheatheSword ||
            agent.action.kind == sim::ActionKind::UnsheatheSword) && joints.pelvis >= 0) {
        const Vector3 pelvis = SampleLocomotionPoseJoint(
            poses, agent, render_phase, static_cast<std::size_t>(joints.pelvis));
        return Vector3Add(pelvis, {0.22f, 0.14f, -0.03f});
    }
    if (agent.action.kind == sim::ActionKind::PickUpStick ||
        agent.action.kind == sim::ActionKind::DropStick) {
        const Vector3 world_target = CoreToWorld(agent.action.target_position);
        const Vector3 root = CoreToWorld(agent.position);
        const Vector3 delta = Vector3Subtract(world_target, root);
        const float cosine = std::cos(agent.facing_radians);
        const float sine = std::sin(agent.facing_radians);
        return {delta.x * cosine - delta.z * sine, 0.08f,
            delta.x * sine + delta.z * cosine};
    }
    return {left_hand ? 0.28f : -0.28f, 1.08f, 0.48f};
}

ProceduralReachPose BuildProceduralReachPose(const sim::AgentSnapshot& agent,
    const viewer::LocomotionPoses& poses, const EquipmentJoints& joints,
    float render_phase, float action_progress, float reaction_progress) {
    ProceduralReachPose result{};
    if (agent.reaction.kind == sim::ReactionKind::Dodge) return result;

    const bool reaching_action = agent.action.kind == sim::ActionKind::Reach ||
        agent.action.kind == sim::ActionKind::Hold ||
        agent.action.kind == sim::ActionKind::SheatheSword ||
        agent.action.kind == sim::ActionKind::UnsheatheSword ||
        agent.action.kind == sim::ActionKind::PickUpStick ||
        agent.action.kind == sim::ActionKind::DropStick;
    const bool parrying = agent.reaction.kind == sim::ReactionKind::Parry;
    if ((!reaching_action || agent.action.phase == sim::ActionPhase::Idle) && !parrying) return result;

    const float weight = parrying
        ? ReactionWeight(reaction_progress)
        : SmoothStep(agent.action.reach_alpha);
    const auto solve = [&](int upperarm, int lowerarm, int hand, Vector3 target,
                           bool& active, Vector3& elbow_result, Vector3& hand_result) {
        if (upperarm < 0 || lowerarm < 0 || hand < 0) return;
        const Vector3 shoulder = SampleBasePoseJoint(poses, agent, render_phase,
            action_progress, reaction_progress, static_cast<std::size_t>(upperarm));
        const Vector3 elbow = SampleBasePoseJoint(poses, agent, render_phase,
            action_progress, reaction_progress, static_cast<std::size_t>(lowerarm));
        const Vector3 authored_hand = SampleBasePoseJoint(poses, agent, render_phase,
            action_progress, reaction_progress, static_cast<std::size_t>(hand));
        active = SolveArmReach(shoulder, elbow, authored_hand, target, weight,
            elbow_result, hand_result);
    };

    if (parrying) {
        solve(joints.upperarm_right, joints.lowerarm_right, joints.hand_right,
            {0.28f, 1.18f, 0.10f}, result.right_active, result.right_elbow, result.right_hand);
        return result;
    }

    if (agent.action.hands == sim::HandUsage::Left || agent.action.hands == sim::HandUsage::Both) {
        solve(joints.upperarm_left, joints.lowerarm_left, joints.hand_left,
            ReachTarget(agent, poses, joints, render_phase, true),
            result.left_active, result.left_elbow, result.left_hand);
    }
    if (agent.action.hands == sim::HandUsage::Right || agent.action.hands == sim::HandUsage::Both) {
        solve(joints.upperarm_right, joints.lowerarm_right, joints.hand_right,
            ReachTarget(agent, poses, joints, render_phase, false),
            result.right_active, result.right_elbow, result.right_hand);
    }
    return result;
}

Vector3 SampleRenderedJoint(const viewer::LocomotionPoses& poses, const sim::AgentSnapshot& agent,
    const EquipmentJoints& joints, const ProceduralReachPose& reach, float render_phase,
    float action_progress, float reaction_progress, std::size_t joint) {
    Vector3 result{};
    if (reach.left_active && static_cast<int>(joint) == joints.lowerarm_left) result = reach.left_elbow;
    else if (reach.left_active && static_cast<int>(joint) == joints.hand_left) result = reach.left_hand;
    else if (reach.right_active && static_cast<int>(joint) == joints.lowerarm_right) result = reach.right_elbow;
    else if (reach.right_active && static_cast<int>(joint) == joints.hand_right) result = reach.right_hand;
    else result = SampleBasePoseJoint(poses, agent, render_phase, action_progress, reaction_progress, joint);
    return ApplyStatePose(result, agent.state);
}

struct RenderedAgentPose {
    std::size_t joint_count = 0;
    std::array<Vector3, kMaximumRenderedJoints> local{};
    std::array<Vector3, kMaximumRenderedJoints> world{};
};

RenderedAgentPose BuildRenderedAgentPose(const viewer::LocomotionPoses& poses,
    const sim::AgentSnapshot& agent, const EquipmentJoints& joints,
    const ProceduralReachPose& reach, float render_phase, float action_progress,
    float reaction_progress, float prediction_seconds) {
    RenderedAgentPose result{};
    result.joint_count = joints.joint_count;
    const float cosine = std::cos(agent.facing_radians);
    const float sine = std::sin(agent.facing_radians);
    const Vector3 base = AgentRenderRoot(agent, prediction_seconds);
    for (std::size_t joint = 0; joint < result.joint_count; ++joint) {
        const Vector3 local = SampleRenderedJoint(poses, agent, joints, reach,
            render_phase, action_progress, reaction_progress, joint);
        result.local[joint] = local;
        result.world[joint] = {
            base.x + local.x * cosine + local.z * sine,
            base.y + local.y,
            base.z - local.x * sine + local.z * cosine,
        };
    }
    return result;
}

void DrawEquipment(const sim::AgentSnapshot& agent, const RenderedAgentPose& pose,
    const EquipmentJoints& joints, float prediction_seconds, SolidBatch& solids) {
    if (!agent.sword_equipped || !joints.EquipmentValid()) return;

    const auto segment = [&solids](Vector3 start, Vector3 end,
                             float start_radius, float end_radius, int sides, Color color) {
        solids.AddCylinder(start, end, start_radius, end_radius, sides, color);
    };
    const Vector3 pelvis = pose.local[static_cast<std::size_t>(joints.pelvis)];
    const bool grounded = agent.state == sim::AgentState::Agonising ||
        agent.state == sim::AgentState::PassedOut || agent.state == sim::AgentState::Crawling ||
        agent.state == sim::AgentState::Dead;
    const Vector3 sheath_top_local = Vector3Add(pelvis,
        grounded ? Vector3{0.18f, 0.02f, -0.08f} : Vector3{0.22f, -0.04f, -0.03f});
    const Vector3 sheath_bottom_local = Vector3Add(pelvis,
        grounded ? Vector3{0.54f, 0.02f, -0.16f} : Vector3{0.33f, -0.64f, -0.11f});
    const Vector3 sheath_top = TransformJoint(sheath_top_local, agent, prediction_seconds);
    const Vector3 sheath_bottom = TransformJoint(sheath_bottom_local, agent, prediction_seconds);
    segment(sheath_top, sheath_bottom, 0.038f, 0.030f, 7, kSheath);
    solids.AddSphere(sheath_top, 0.043f, 16, 16, kSwordGuard);

    if (agent.sword_state == sim::SwordState::Sheathed) {
        const Vector3 sheath_axis = Vector3Normalize(Vector3Subtract(sheath_top, sheath_bottom));
        const Vector3 grip_end = Vector3Add(sheath_top, Vector3Scale(sheath_axis, 0.18f));
        segment(sheath_top, grip_end, 0.021f, 0.019f, 7, kLeather);
        if (agent.held_weapon != sim::WeaponKind::Stick) return;
    }
    if (agent.sword_state == sim::SwordState::Dropped) {
        Vector3 drop = CoreToWorld(agent.dropped_sword_position);
        drop.y = 0.035f;
        const Vector3 direction{std::sin(agent.dropped_sword_yaw_radians), 0.0f,
            std::cos(agent.dropped_sword_yaw_radians)};
        const Vector3 right{direction.z, 0.0f, -direction.x};
        const Vector3 grip_start = Vector3Add(drop, Vector3Scale(right, -0.18f));
        const Vector3 blade_start = Vector3Add(drop, Vector3Scale(right, 0.03f));
        const Vector3 blade_tip = Vector3Add(drop, Vector3Scale(right, 0.73f));
        segment(grip_start, blade_start, 0.022f, 0.019f, 7, kLeather);
        segment(blade_start, blade_tip, 0.018f, 0.004f, 7, kSwordMetal);
        segment(Vector3Add(blade_start, Vector3Scale(direction, -0.10f)),
            Vector3Add(blade_start, Vector3Scale(direction, 0.10f)),
            0.014f, 0.014f, 6, kSwordGuard);
        return;
    }

    const Vector3 lowerarm = pose.world[static_cast<std::size_t>(joints.lowerarm_right)];
    const Vector3 hand = pose.world[static_cast<std::size_t>(joints.hand_right)];
    Vector3 sword_direction = Vector3Subtract(hand, lowerarm);
    if (Vector3LengthSqr(sword_direction) < 0.0001f) {
        sword_direction = {std::sin(agent.facing_radians), 0.0f, std::cos(agent.facing_radians)};
    } else {
        sword_direction = Vector3Normalize(sword_direction);
    }
    if (agent.held_weapon == sim::WeaponKind::Stick) {
        const Vector3 stick_start = Vector3Subtract(hand, Vector3Scale(sword_direction, 0.28f));
        const Vector3 stick_end = Vector3Add(hand, Vector3Scale(sword_direction, 0.78f));
        segment(stick_start, stick_end, 0.022f, 0.018f, 7, kTrainingStick);
        return;
    }
    const Vector3 grip_start = Vector3Subtract(hand, Vector3Scale(sword_direction, 0.09f));
    const Vector3 blade_start = Vector3Add(hand, Vector3Scale(sword_direction, 0.12f));
    const Vector3 blade_tip = Vector3Add(hand, Vector3Scale(sword_direction, 0.82f));
    segment(grip_start, blade_start, 0.022f, 0.019f, 7, kLeather);
    segment(blade_start, blade_tip, 0.018f, 0.004f, 7, kSwordMetal);

    Vector3 guard_direction = Vector3CrossProduct(sword_direction, {0.0f, 1.0f, 0.0f});
    if (Vector3LengthSqr(guard_direction) < 0.0001f) {
        guard_direction = Vector3CrossProduct(sword_direction, {0.0f, 0.0f, 1.0f});
    }
    guard_direction = Vector3Normalize(guard_direction);
    segment(Vector3Subtract(blade_start, Vector3Scale(guard_direction, 0.10f)),
        Vector3Add(blade_start, Vector3Scale(guard_direction, 0.10f)),
        0.014f, 0.014f, 6, kSwordGuard);
}

void DrawGroundSticks(const sim::SimulationSnapshot& snapshot, SolidBatch& solids) {
    for (const sim::StickSnapshot& stick : snapshot.sticks) {
        if (stick.holder_id != sim::kInvalidEntityId) continue;
        Vector3 center = CoreToWorld(stick.position);
        center.y = 0.025f;
        const Vector3 direction{std::sin(stick.facing_radians), 0.0f,
            std::cos(stick.facing_radians)};
        solids.AddCylinder(Vector3Add(center, Vector3Scale(direction, -0.52f)),
            Vector3Add(center, Vector3Scale(direction, 0.52f)),
            0.022f, 0.018f, 7, kTrainingStick);
    }
}

void DrawBaseballCap(const sim::AgentSnapshot& agent, Vector3 head, SolidBatch& solids) {
    const float horizontal = std::cos(agent.head_pitch_radians);
    const Vector3 forward = Vector3Normalize({
        horizontal * std::sin(agent.head_yaw_radians),
        std::sin(agent.head_pitch_radians),
        horizontal * std::cos(agent.head_yaw_radians),
    });
    const Vector3 right{
        std::cos(agent.head_yaw_radians), 0.0f, -std::sin(agent.head_yaw_radians)};
    const Vector3 up = Vector3Normalize(Vector3CrossProduct(forward, right));

    const Vector3 crown_bottom = Vector3Add(head, Vector3Scale(up, 0.045f));
    const Vector3 crown_top = Vector3Add(head, Vector3Scale(up, 0.125f));
    solids.AddCylinder(crown_bottom, crown_top, 0.102f, 0.072f, 12, kCapCrown);

    const Vector3 brim_back = Vector3Add(crown_bottom, Vector3Scale(forward, 0.025f));
    const Vector3 brim_front = Vector3Add(crown_bottom, Vector3Scale(forward, 0.185f));
    const Vector3 back_left = Vector3Subtract(brim_back, Vector3Scale(right, 0.095f));
    const Vector3 back_right = Vector3Add(brim_back, Vector3Scale(right, 0.095f));
    const Vector3 front_left = Vector3Subtract(brim_front, Vector3Scale(right, 0.072f));
    const Vector3 front_right = Vector3Add(brim_front, Vector3Scale(right, 0.072f));
    solids.AddTriangle(back_left, front_left, front_right, kCapBrim);
    solids.AddTriangle(back_left, front_right, back_right, kCapBrim);
    solids.AddTriangle(back_left, front_right, front_left, kCapBrim);
    solids.AddTriangle(back_left, back_right, front_right, kCapBrim);
}

void DrawSkeleton(const sim::AgentSnapshot& agent, const viewer::LocomotionPoses& poses,
    const EquipmentJoints& joints, const RenderedAgentPose& pose, SolidBatch& solids) {
    const Color skeleton_color = agent.team == sim::Team::Hero ? kHeroSkeleton : kVillainSkeleton;
    for (std::size_t joint = 0; joint < pose.joint_count; ++joint) {
        const int parent = poses.parents[joint];
        if (parent < 0) continue;
        if (static_cast<std::size_t>(parent) >= pose.joint_count) continue;
        const Color color = LimbColor(agent, joints.limbs[joint], skeleton_color);
        solids.AddCylinder(pose.world[static_cast<std::size_t>(parent)], pose.world[joint],
            0.018f, 0.018f, 5, color);
    }
    if (joints.head >= 0 && static_cast<std::size_t>(joints.head) < pose.joint_count) {
        const Vector3 head_position = pose.world[static_cast<std::size_t>(joints.head)];
        const Color head_color = LimbColor(agent, sim::Limb::Head, kHead);
        solids.AddSphere(head_position, 0.095f, 8, 8, head_color);
        DrawBaseballCap(agent, head_position, solids);
    }
}

void DrawSoundRings(const viewer::Scenario& scenario, const sim::SimulationSnapshot& snapshot,
    float prediction_seconds, LineBatch& line_batch) {
    static const std::array<Vector2, kSoundRingSegments + 1> unit_circle = [] {
        std::array<Vector2, kSoundRingSegments + 1> points{};
        for (int index = 0; index <= kSoundRingSegments; ++index) {
            const float angle = 2.0f * kPi * static_cast<float>(index) /
                static_cast<float>(kSoundRingSegments);
            points[static_cast<std::size_t>(index)] = {std::cos(angle), std::sin(angle)};
        }
        return points;
    }();
    const double visible_time = snapshot.time_seconds + static_cast<double>(prediction_seconds);
    const double tick_rate = static_cast<double>(scenario.simulation.tick_rate_hz);
    for (std::size_t index = 0; index < snapshot.sound_event_count; ++index) {
        const sim::SoundEventSnapshot& event = snapshot.sound_events[index];
        if (event.maximum_range_m <= 0.0f) continue;
        const double emitted_time = static_cast<double>(event.emitted_tick) / tick_rate;
        const float age_seconds = static_cast<float>(visible_time - emitted_time);
        const float lifetime_seconds = event.maximum_range_m /
            sim::kSoundPropagationMetersPerSecond;
        if (age_seconds < 0.0f || age_seconds >= lifetime_seconds) continue;
        const float progress = age_seconds / lifetime_seconds;
        Vector3 center = CoreToWorld(event.position);
        center.y = 0.015f;
        Color color = kSoundRing;
        color.a = static_cast<unsigned char>(static_cast<float>(color.a) * (1.0f - progress));
        const float radius = age_seconds * sim::kSoundPropagationMetersPerSecond;
        for (int segment = 0; segment < kSoundRingSegments; ++segment) {
            const Vector2 first = unit_circle[static_cast<std::size_t>(segment)];
            const Vector2 second = unit_circle[static_cast<std::size_t>(segment + 1)];
            line_batch.Add({center.x + first.x * radius, center.y, center.z + first.y * radius},
                {center.x + second.x * radius, center.y, center.z + second.y * radius}, color);
        }
    }
}

void DrawWorld(const viewer::Scenario& scenario, const sim::SimulationSnapshot& snapshot,
    const viewer::LocomotionPoses& poses, const EquipmentJoints& equipment_joints,
    sim::EntityId selected_agent_id, const AgentSelection& selected_agents,
    float prediction_seconds, bool sound_visualization, const Camera3D& camera,
    SolidBatch& solids) {
    const float min_x = scenario.simulation.world_min.x;
    const float max_x = scenario.simulation.world_max.x;
    const float min_z = scenario.simulation.world_min.y;
    const float max_z = scenario.simulation.world_max.y;
    static LineBatch line_batch{};
    line_batch.Clear();
    solids.Clear();
    DrawPlane({(min_x + max_x) * 0.5f, 0.0f, (min_z + max_z) * 0.5f},
        {max_x - min_x, max_z - min_z}, scenario.ground_color);
    for (int x = static_cast<int>(std::ceil(min_x)); x <= static_cast<int>(std::floor(max_x)); x += 4) {
        DrawLine3D({static_cast<float>(x), 0.003f, min_z}, {static_cast<float>(x), 0.003f, max_z}, scenario.grid_color);
    }
    for (int z = static_cast<int>(std::ceil(min_z)); z <= static_cast<int>(std::floor(max_z)); z += 4) {
        DrawLine3D({min_x, 0.003f, static_cast<float>(z)}, {max_x, 0.003f, static_cast<float>(z)}, scenario.grid_color);
    }
    DrawGroundSticks(snapshot, solids);
    if (sound_visualization) DrawSoundRings(
        scenario, snapshot, prediction_seconds, line_batch);
    const Vector3 camera_forward = Vector3Normalize(Vector3Subtract(camera.target, camera.position));
    const float screen_width = static_cast<float>(GetScreenWidth());
    const float screen_height = static_cast<float>(GetScreenHeight());
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        const Vector3 render_root = AgentRenderRoot(agent, prediction_seconds);
        const Vector3 to_agent = Vector3Subtract(render_root, camera.position);
        if (Vector3DotProduct(to_agent, camera_forward) <= 0.0f) continue;
        const Vector2 root_screen = GetWorldToScreen(render_root, camera);
        if (root_screen.x < -120.0f || root_screen.x > screen_width + 120.0f ||
            root_screen.y < -180.0f || root_screen.y > screen_height + 120.0f) continue;
        if (IsAgentSelected(selected_agents, agent.id)) {
            DrawSelectionMarker(agent, prediction_seconds);
        }
        if (agent.id == selected_agent_id) {
            DrawTacticalDiagnostics(agent, prediction_seconds);
        }
        DrawRootMarker(agent, prediction_seconds, solids);
        const float render_phase = RenderPosePhase(
            agent, poses, snapshot.time_seconds, prediction_seconds);
        const float action_progress = RenderActionProgress(agent, prediction_seconds);
        const float reaction_progress = RenderReactionProgress(agent, prediction_seconds);
        const ProceduralReachPose reach = BuildProceduralReachPose(
            agent, poses, equipment_joints, render_phase, action_progress, reaction_progress);
        const RenderedAgentPose pose = BuildRenderedAgentPose(poses, agent, equipment_joints,
            reach, render_phase, action_progress, reaction_progress, prediction_seconds);
        DrawSkeleton(agent, poses, equipment_joints, pose, solids);
        DrawEquipment(agent, pose, equipment_joints, prediction_seconds, solids);
    }
    solids.Draw();
    line_batch.Draw();
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

bool PrimaryIconButton(Rectangle bounds, int icon, const char* tooltip, Tooltip& pending) {
    const int normal = GuiGetStyle(BUTTON, BASE_COLOR_NORMAL);
    const int focused = GuiGetStyle(BUTTON, BASE_COLOR_FOCUSED);
    const int pressed = GuiGetStyle(BUTTON, BASE_COLOR_PRESSED);
    GuiSetStyle(BUTTON, BASE_COLOR_NORMAL, 0x247585ff);
    GuiSetStyle(BUTTON, BASE_COLOR_FOCUSED, 0x3097aaff);
    GuiSetStyle(BUTTON, BASE_COLOR_PRESSED, 0x1b5d69ff);
    const bool clicked = IconButton(bounds, icon, tooltip, pending);
    GuiSetStyle(BUTTON, BASE_COLOR_NORMAL, normal);
    GuiSetStyle(BUTTON, BASE_COLOR_FOCUSED, focused);
    GuiSetStyle(BUTTON, BASE_COLOR_PRESSED, pressed);
    return clicked;
}

struct TickKeyRepeater {
    int direction = 0;
    double tick_remainder = 0.0;

    std::int64_t Consume(bool left_down, bool right_down, float frame_seconds,
        float ticks_per_second) noexcept {
        const int requested_direction = left_down == right_down ? 0 : (left_down ? -1 : 1);
        if (requested_direction == 0) {
            direction = 0;
            tick_remainder = 0.0;
            return 0;
        }
        if (requested_direction != direction) {
            direction = requested_direction;
            tick_remainder = 0.0;
            return direction;
        }
        tick_remainder += static_cast<double>(std::min(frame_seconds, 0.1f)) *
            static_cast<double>(ticks_per_second);
        const std::uint64_t ticks = static_cast<std::uint64_t>(tick_remainder);
        tick_remainder -= static_cast<double>(ticks);
        return static_cast<std::int64_t>(ticks) * direction;
    }
};

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
    bool stop_reset = false;
    bool toggle_pause = false;
    bool rewind_second = false;
    bool previous_tick = false;
    bool next_tick = false;
    bool next_second = false;
    bool return_live = false;
    bool reset = false;
    bool new_seed = false;
    bool set_seed = false;
    std::uint64_t seed = 0;
    bool benchmark = false;
    bool screenshot = false;
    bool square_formation = false;
    bool save_opening_layout = false;
    bool set_autonomous = false;
    bool set_paired = false;
    bool validate_success = false;
    bool validate_failure = false;
    bool restore_saved_settings = false;
    bool save_settings = false;
    bool combat_settings_changed = false;
    bool tactics_settings_changed = false;
    bool wound_settings_changed = false;
    bool look_settings_changed = false;
    bool perception_settings_changed = false;
    bool team_counts_changed = false;
};

struct SeedInputState {
    std::array<char, 21> text{};
    bool editing = false;

    void Set(std::uint64_t seed) {
        std::snprintf(text.data(), text.size(), "%llu", static_cast<unsigned long long>(seed));
    }

    bool Read(std::uint64_t& seed) const {
        const std::string value(text.data());
        if (value.empty()) return false;
        const auto result = std::from_chars(value.data(), value.data() + value.size(), seed);
        return result.ec == std::errc{} && result.ptr == value.data() + value.size();
    }
};

float& SelectedAttackStun(viewer::ControlSettings& settings, int selected) noexcept {
    if (selected < static_cast<int>(sim::kSwordAttackClipCount)) {
        return settings.sword_attack_stun_seconds[static_cast<std::size_t>(selected)];
    }
    return settings.melee_attack_stun_seconds[
        static_cast<std::size_t>(selected) - sim::kSwordAttackClipCount];
}

struct AttackStunEditorState {
    std::array<char, 32> text{};
    std::string choices{};
    int selected = 0;
    bool editing = false;
    bool dropdown_open = false;

    void Initialize(const viewer::LocomotionPoses& poses, const viewer::ControlSettings& settings) {
        choices.clear();
        const auto append = [this](const char* category, const std::string& name) {
            if (!choices.empty()) choices.push_back(';');
            choices += category;
            choices.push_back(' ');
            choices += name;
        };
        for (const viewer::ActionPoseClip& clip : poses.sword_attacks) append("Sword", clip.name);
        for (const viewer::ActionPoseClip& clip : poses.melee_attacks) append("Melee", clip.name);
        Sync(settings);
    }

    void Sync(const viewer::ControlSettings& settings) {
        const int maximum = static_cast<int>(sim::kAttackClipCount) - 1;
        selected = std::clamp(selected, 0, maximum);
        const float seconds = selected < static_cast<int>(sim::kSwordAttackClipCount)
            ? settings.sword_attack_stun_seconds[static_cast<std::size_t>(selected)]
            : settings.melee_attack_stun_seconds[
                static_cast<std::size_t>(selected) - sim::kSwordAttackClipCount];
        std::snprintf(text.data(), text.size(), "%.3f", seconds);
    }

    bool Commit(viewer::ControlSettings& settings) {
        char* end = nullptr;
        errno = 0;
        const float seconds = std::strtof(text.data(), &end);
        if (end == text.data() || *end != '\0' || errno == ERANGE ||
            !std::isfinite(seconds) || seconds < 0.0f) {
            Sync(settings);
            return false;
        }
        float& current = SelectedAttackStun(settings, selected);
        const bool changed = current != seconds;
        current = seconds;
        Sync(settings);
        return changed;
    }
};

struct HeadTurnEditorState {
    std::array<char, 32> text{};
    bool editing = false;

    void Sync(const viewer::ControlSettings& settings) {
        std::snprintf(text.data(), text.size(), "%.1f",
            settings.head_turn_speed_degrees_per_second);
    }

    bool Commit(viewer::ControlSettings& settings) {
        char* end = nullptr;
        errno = 0;
        const float speed = std::strtof(text.data(), &end);
        if (end == text.data() || *end != '\0' || errno == ERANGE ||
            !std::isfinite(speed) || speed < 0.0f) {
            Sync(settings);
            return false;
        }
        const bool changed = settings.head_turn_speed_degrees_per_second != speed;
        settings.head_turn_speed_degrees_per_second = speed;
        Sync(settings);
        return changed;
    }
};

struct TeamCountEditorState {
    std::array<char, 4> hero_text{};
    std::array<char, 4> villain_text{};
    bool hero_editing = false;
    bool villain_editing = false;
    bool hero_select_all = false;
    bool villain_select_all = false;

    void Sync(const viewer::ControlSettings& settings) {
        std::snprintf(hero_text.data(), hero_text.size(), "%u", settings.hero_agent_count);
        std::snprintf(villain_text.data(), villain_text.size(), "%u", settings.villain_agent_count);
    }

    bool Commit(std::array<char, 4>& text, std::uint32_t& value,
        const viewer::ControlSettings& settings) {
        std::uint32_t parsed = 0;
        const std::string input(text.data());
        const auto result = std::from_chars(input.data(), input.data() + input.size(), parsed);
        if (result.ec != std::errc{} || result.ptr != input.data() + input.size()) {
            Sync(settings);
            return false;
        }
        parsed = std::clamp(parsed, viewer::kMinTeamAgentCount, viewer::kMaxTeamAgentCount);
        const bool changed = value != parsed;
        value = parsed;
        std::snprintf(text.data(), text.size(), "%u", value);
        return changed;
    }

    static void HandleSelectedInput(std::array<char, 4>& text, bool& select_all) {
        const bool control_down = IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL);
        if (control_down && IsKeyPressed(kAzertyLabelAKey)) {
            while (GetCharPressed() != 0) {}
            select_all = true;
            return;
        }
        if (!select_all) return;

        if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            select_all = false;
            return;
        }
        if (IsKeyPressed(KEY_BACKSPACE) || IsKeyPressed(KEY_DELETE)) {
            text.fill('\0');
            select_all = false;
            return;
        }

        std::array<char, 4> replacement{};
        std::size_t length = 0;
        for (int codepoint = GetCharPressed(); codepoint != 0; codepoint = GetCharPressed()) {
            if (codepoint >= '0' && codepoint <= '9' && length + 1U < replacement.size()) {
                replacement[length++] = static_cast<char>(codepoint);
            }
        }
        if (length > 0U) {
            text = replacement;
            select_all = false;
        }
    }

    static void DrawSelection(Rectangle bounds, const std::array<char, 4>& text, bool select_all) {
        if (!select_all || text[0] == '\0') return;

        const Font font = GuiGetFont();
        const float font_size = static_cast<float>(GuiGetStyle(DEFAULT, TEXT_SIZE));
        const float spacing = static_cast<float>(GuiGetStyle(DEFAULT, TEXT_SPACING));
        const float padding = static_cast<float>(GuiGetStyle(TEXTBOX, TEXT_PADDING));
        const Vector2 size = MeasureTextEx(font, text.data(), font_size, spacing);
        const Vector2 position{bounds.x + padding, bounds.y + (bounds.height - size.y) * 0.5f};
        const float maximum_width = std::max(0.0f, bounds.width - padding * 2.0f);
        const Rectangle selection{position.x - 1.0f, position.y - 1.0f,
            std::min(size.x + 3.0f, maximum_width + 2.0f), size.y + 2.0f};
        DrawRectangleRec(selection, {40, 125, 143, 255});
        DrawTextEx(font, text.data(), position, font_size, spacing, WHITE);
    }
};

enum class OptionsTab : std::uint8_t {
    Camera,
    Combat,
    Tactics,
    Wounds,
    Look,
    Sense,
    Sound,
};

UiActions DrawUi(const viewer::Scenario& scenario, const sim::Simulation& simulation,
    bool paused, float& time_scale, bool rewind_active, std::uint64_t rewind_head,
    bool& options_open, OptionsTab& options_tab, viewer::ControlSettings& settings,
    const viewer::LocomotionPoses& poses, const BenchmarkResult& benchmark,
    const std::string& settings_status, SeedInputState& seed_input,
    AttackStunEditorState& attack_stun_editor, HeadTurnEditorState& head_turn_editor,
    TeamCountEditorState& team_count_editor, sim::EntityId selected_agent_id,
    const AgentSelection& selected_agents, Tooltip& tooltip) {
    UiActions actions{};
#if !PROPHECY_ENABLE_REWIND
    (void)rewind_active;
#endif
    const sim::SimulationSnapshot& snapshot = simulation.Snapshot();
    const Rectangle transport{12.0f, 12.0f, 640.0f, 104.0f};
    DrawRectangleRec(transport, kPanel);
    DrawRectangleLinesEx(transport, 1.0f, {73, 86, 88, 255});
    DrawText("SIMULATION", 23, 20, 13, kMuted);
    DrawText("SEED", 112, 20, 13, kMuted);
    const Rectangle seed_box{149.0f, 16.0f, 135.0f, 22.0f};
    DrawRectangleRec(seed_box, kPanelRaised);
    if (GuiTextBox(seed_box, seed_input.text.data(), static_cast<int>(seed_input.text.size()),
            seed_input.editing) != 0) {
        if (seed_input.editing) {
            std::uint64_t seed = 0;
            if (seed_input.Read(seed)) {
                actions.set_seed = seed != simulation.Seed();
                actions.seed = seed;
            } else {
                seed_input.Set(simulation.Seed());
            }
        }
        seed_input.editing = !seed_input.editing;
    }
    DrawText("HEROES", 294, 20, 13, kHeroSkeleton);
    const Rectangle hero_count_input{344.0f, 16.0f, 38.0f, 22.0f};
    DrawRectangleRec(hero_count_input, kPanelRaised);
    if (team_count_editor.hero_editing) {
        TeamCountEditorState::HandleSelectedInput(
            team_count_editor.hero_text, team_count_editor.hero_select_all);
    }
    if (GuiTextBox(hero_count_input, team_count_editor.hero_text.data(),
            static_cast<int>(team_count_editor.hero_text.size()),
            team_count_editor.hero_editing) != 0) {
        if (team_count_editor.hero_editing) {
            actions.team_counts_changed |= team_count_editor.Commit(
                team_count_editor.hero_text, settings.hero_agent_count, settings);
        }
        team_count_editor.hero_editing = !team_count_editor.hero_editing;
        team_count_editor.hero_select_all = team_count_editor.hero_editing;
    }
    TeamCountEditorState::DrawSelection(hero_count_input,
        team_count_editor.hero_text, team_count_editor.hero_select_all);
    DrawText("VILLAINS", 391, 20, 13, kVillainSkeleton);
    const Rectangle villain_count_input{451.0f, 16.0f, 38.0f, 22.0f};
    DrawRectangleRec(villain_count_input, kPanelRaised);
    if (team_count_editor.villain_editing) {
        TeamCountEditorState::HandleSelectedInput(
            team_count_editor.villain_text, team_count_editor.villain_select_all);
    }
    if (GuiTextBox(villain_count_input, team_count_editor.villain_text.data(),
            static_cast<int>(team_count_editor.villain_text.size()),
            team_count_editor.villain_editing) != 0) {
        if (team_count_editor.villain_editing) {
            actions.team_counts_changed |= team_count_editor.Commit(
                team_count_editor.villain_text, settings.villain_agent_count, settings);
        }
        team_count_editor.villain_editing = !team_count_editor.villain_editing;
        team_count_editor.villain_select_all = team_count_editor.villain_editing;
    }
    TeamCountEditorState::DrawSelection(villain_count_input,
        team_count_editor.villain_text, team_count_editor.villain_select_all);
    DrawText(TextFormat("tick %llu / %llu", static_cast<unsigned long long>(snapshot.tick),
        static_cast<unsigned long long>(rewind_head)), 501, 19, 15, kText);

    constexpr float button = 34.0f;
    float x = 22.0f;
    const float y = 42.0f;
    actions.toggle_pause = PrimaryIconButton({x, y, button, button},
        paused ? ICON_PLAYER_PLAY : ICON_PLAYER_PAUSE,
        paused ? "Play (Space)" : "Pause (Space)", tooltip); x += 39.0f;
    actions.stop_reset = IconButton({x, y, button, button}, ICON_PLAYER_STOP,
        "Return to tick zero and pause", tooltip); x += 39.0f;
#if PROPHECY_ENABLE_REWIND
    actions.rewind_second = IconButton({x, y, button, button}, ICON_PLAYER_PREVIOUS,
        "Rewind one second", tooltip); x += 39.0f;
    actions.previous_tick = IconButton({x, y, button, button}, ICON_ARROW_LEFT,
        "Previous tick (Left)", tooltip); x += 39.0f;
#endif
    actions.next_tick = IconButton({x, y, button, button}, ICON_ARROW_RIGHT,
        "Next tick (Right)", tooltip); x += 39.0f;
    actions.next_second = IconButton({x, y, button, button}, ICON_PLAYER_NEXT,
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
    actions.screenshot = IconButton({x, y, button, button}, ICON_CAMERA,
        "Capture current simulation window", tooltip); x += 39.0f;
    const bool square_formation_clicked = IconButton({x, y, button, button}, ICON_BOX_GRID,
        paused ? "Arrange each team in a square around its mean" : "Pause to arrange teams",
        tooltip); x += 39.0f;
    actions.square_formation = paused && square_formation_clicked;
    const bool save_opening_layout_clicked = IconButton(
        {x, y, button, button}, ICON_FILE_SAVE,
        paused ? "Save current agent transforms as opening layout" : "Pause to save agent transforms",
        tooltip); x += 39.0f;
    actions.save_opening_layout = paused && save_opening_layout_clicked;
    if (IconButton({x, y, button, button}, ICON_GEAR, "Options", tooltip)) options_open = !options_open;

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
    DrawText("Mode", static_cast<int>(info.x + 12.0f), 97, 14, kMuted);
    const Rectangle autonomous_button{info.x + 58.0f, 90.0f, 92.0f, 27.0f};
    const Rectangle paired_button{info.x + 156.0f, 90.0f, 92.0f, 27.0f};
    if (simulation.Config().mode == sim::SimulationMode::Autonomous) {
        DrawRectangleRec(autonomous_button, {36, 117, 133, 255});
    } else {
        DrawRectangleRec(paired_button, {36, 117, 133, 255});
    }
    actions.set_autonomous = GuiButton(autonomous_button, "Auto") != 0;
    actions.set_paired = GuiButton(paired_button, "Paired") != 0;
    DrawRectangleLinesEx(simulation.Config().mode == sim::SimulationMode::Autonomous
            ? autonomous_button : paired_button,
        2.0f, kAccent);

    int agent_y = 128;
    const sim::AgentSnapshot* selected = FindAgent(snapshot, selected_agent_id);
    if (selected != nullptr) {
        const Color color = selected->team == sim::Team::Hero ? kHeroSkeleton : kVillainSkeleton;
        if (selected_agents.count() > 1U) {
            DrawText(TextFormat("TEAM %s  %u", sim::ToString(selected->team),
                static_cast<unsigned int>(selected_agents.count())),
                static_cast<int>(info.x + 12.0f), agent_y, 14, color);
        } else {
            DrawText(TextFormat("SELECTED  %s %u", sim::ToString(selected->team), selected->id),
                static_cast<int>(info.x + 12.0f), agent_y, 14, color);
        }
        DrawText(TextFormat("known %u  active %u  finish %u",
            selected->perception.recognized_threat_count,
            selected->perception.active_threat_count,
            selected->perception.finishing_target_count),
            static_cast<int>(info.x + 140.0f), agent_y, 12, kMuted);
        const sim::EntityId behavior_target_id = selected->behavior_mode == sim::BehaviorMode::Follow
            ? selected->follow_target_id
            : selected->attack_target_id;
        DrawText(TextFormat("%s -> %u  |  %.2fm  |  attacks %u", sim::ToString(selected->behavior_mode),
            behavior_target_id, selected->target_distance_m, selected->completed_attacks),
            static_cast<int>(info.x + 12.0f), agent_y + 22, 13, kText);
        DrawText(TextFormat("%s %.2fm/s %s  |  move %.2f", sim::ToString(selected->locomotion_mode),
            selected->root_speed_mps, sim::ToString(selected->locomotion_response),
            selected->speed_stick_amplitude),
            static_cast<int>(info.x + 12.0f), agent_y + 42, 13, kText);
        if (selected->tactical_steering == sim::TacticalSteeringMode::OutnumberedView) {
            DrawText(TextFormat("tactic contain %u  |  arc %.0f  |  move %.0f deg",
                selected->tactical_threat_count,
                selected->tactical_threat_arc_radians * 180.0f / kPi,
                selected->tactical_move_yaw_radians * 180.0f / kPi),
                static_cast<int>(info.x + 12.0f), agent_y + 62, 13, kText);
        } else if (selected->tactical_steering == sim::TacticalSteeringMode::ApproachSector) {
            DrawText(TextFormat("tactic sector %u  |  err %.0f  |  move %.0f deg",
                static_cast<unsigned int>(selected->tactical_sector_index) + 1U,
                selected->tactical_sector_error_radians * 180.0f / kPi,
                selected->tactical_move_yaw_radians * 180.0f / kPi),
                static_cast<int>(info.x + 12.0f), agent_y + 62, 13, kText);
        } else if (selected->tactical_steering == sim::TacticalSteeringMode::AttackerSpacing) {
            DrawText(TextFormat("tactic spacing  |  gap %.0f deg  |  move %.0f deg",
                selected->tactical_nearest_peer_separation_radians * 180.0f / kPi,
                selected->tactical_move_yaw_radians * 180.0f / kPi),
                static_cast<int>(info.x + 12.0f), agent_y + 62, 13, kText);
        } else {
            DrawText(TextFormat("stick %.0f deg  |  facing %.0f deg",
                selected->speed_stick_direction_radians * 180.0f / kPi,
                selected->facing_radians * 180.0f / kPi),
                static_cast<int>(info.x + 12.0f), agent_y + 62, 13, kText);
        }
        DrawText(TextFormat("weapon %s  |  sword %s", sim::ToString(selected->held_weapon),
            sim::ToString(selected->sword_state)),
            static_cast<int>(info.x + 12.0f), agent_y + 82, 13, kText);
        DrawText(TextFormat("action %s%s  |  %s", sim::ToString(selected->action.kind),
            selected->action.parried ? " (parried)" : "", sim::ToString(selected->action.phase)),
            static_cast<int>(info.x + 12.0f), agent_y + 102, 13, kText);
        if (selected->action.kind != sim::ActionKind::None) {
            const char* clip = viewer::ActionClipName(poses, selected->action.kind,
                selected->action.animation_index);
            DrawText(TextFormat("%s  |  hand %s  |  %.2f / %.2fs",
                clip[0] == '\0' ? "timed" : clip, sim::ToString(selected->action.hands),
                selected->action.elapsed_seconds, selected->action.duration_seconds),
                static_cast<int>(info.x + 12.0f), agent_y + 122, 13, kText);
        }
        DrawText(TextFormat("reaction %s  |  %.2f / %.2fs", sim::ToString(selected->reaction.kind),
            selected->reaction.elapsed_seconds, selected->reaction.duration_seconds),
            static_cast<int>(info.x + 12.0f), agent_y + 142, 13, kText);
        const char* state_text = selected->state_seconds_remaining > 0.0f
            ? TextFormat("state %s  |  %.1fs", sim::ToString(selected->state),
                selected->state_seconds_remaining)
            : TextFormat("state %s", sim::ToString(selected->state));
        DrawText(state_text, static_cast<int>(info.x + 12.0f), agent_y + 162, 13, kText);
        const auto wound = [selected](sim::Limb limb) -> const sim::LimbWoundSnapshot& {
            return selected->wounds[static_cast<std::size_t>(limb)];
        };
        const sim::LimbWoundSnapshot& head = wound(sim::Limb::Head);
        const sim::LimbWoundSnapshot& torso = wound(sim::Limb::Torso);
        DrawText(TextFormat("head %s %.0f%%  |  torso %s %.0f%%",
            WoundStageShort(head.condition), head.gauge_percent,
            WoundStageShort(torso.condition), torso.gauge_percent),
            static_cast<int>(info.x + 12.0f), agent_y + 182, 13, kText);
        const sim::LimbWoundSnapshot& left_arm = wound(sim::Limb::LeftArm);
        const sim::LimbWoundSnapshot& right_arm = wound(sim::Limb::RightArm);
        DrawText(TextFormat("arms  L %s %.0f%%  |  R %s %.0f%%",
            WoundStageShort(left_arm.condition), left_arm.gauge_percent,
            WoundStageShort(right_arm.condition), right_arm.gauge_percent),
            static_cast<int>(info.x + 12.0f), agent_y + 202, 13, kText);
        const sim::LimbWoundSnapshot& left_leg = wound(sim::Limb::LeftLeg);
        const sim::LimbWoundSnapshot& right_leg = wound(sim::Limb::RightLeg);
        DrawText(TextFormat("legs  L %s %.0f%%  |  R %s %.0f%%",
            WoundStageShort(left_leg.condition), left_leg.gauge_percent,
            WoundStageShort(right_leg.condition), right_leg.gauge_percent),
            static_cast<int>(info.x + 12.0f), agent_y + 222, 13, kText);
        if (selected->action.phase == sim::ActionPhase::AwaitingValidation) {
            DrawText("Unreal validation", static_cast<int>(info.x + 12.0f), agent_y + 251, 13, kAccent);
            actions.validate_success = IconButton({info.x + 132.0f, static_cast<float>(agent_y + 244), 32.0f, 30.0f},
                ICON_OK_TICK, "Accept paired action", tooltip);
            actions.validate_failure = IconButton({info.x + 170.0f, static_cast<float>(agent_y + 244), 32.0f, 30.0f},
                ICON_CROSS, "Fail paired action", tooltip);
            agent_y += 278;
        } else {
            agent_y += 246;
        }
    } else {
        int visible_rows = 0;
        for (const sim::AgentSnapshot& agent : snapshot.agents) {
            if (visible_rows >= kMaximumOverviewAgentRows) break;
            const Color color = agent.team == sim::Team::Hero ? kHeroSkeleton : kVillainSkeleton;
            DrawText(TextFormat("%s %u  %s  %s  %.1fm/s  attacks %u", sim::ToString(agent.team), agent.id,
                sim::ToString(agent.state), sim::ToString(agent.locomotion_mode), agent.root_speed_mps,
                agent.completed_attacks),
                static_cast<int>(info.x + 12.0f), agent_y, 13, color);
            agent_y += 20;
            ++visible_rows;
        }
    }
    if (benchmark.ticks > 0) {
        DrawText(RateText(benchmark.ticks_per_second).c_str(), static_cast<int>(info.x + 12.0f), agent_y + 2, 14, kAccent);
    }

    if (options_open) {
        const Rectangle panel{static_cast<float>(GetScreenWidth()) - 332.0f,
            OptionsPanelTop(), 320.0f, kOptionsPanelHeight};
        DrawRectangleRec(panel, kPanel);
        DrawRectangleLinesEx(panel, 1.0f, {73, 86, 88, 255});
        const Rectangle camera_tab{panel.x + 12.0f, panel.y + 14.0f, 41.0f, 28.0f};
        const Rectangle combat_tab{panel.x + 55.0f, panel.y + 14.0f, 41.0f, 28.0f};
        const Rectangle tactics_tab{panel.x + 98.0f, panel.y + 14.0f, 41.0f, 28.0f};
        const Rectangle wounds_tab{panel.x + 141.0f, panel.y + 14.0f, 41.0f, 28.0f};
        const Rectangle look_tab{panel.x + 184.0f, panel.y + 14.0f, 41.0f, 28.0f};
        const Rectangle sense_tab{panel.x + 227.0f, panel.y + 14.0f, 41.0f, 28.0f};
        const Rectangle sound_tab{panel.x + 270.0f, panel.y + 14.0f, 38.0f, 28.0f};
        const std::array<Rectangle, 7> option_tabs{
            camera_tab, combat_tab, tactics_tab, wounds_tab, look_tab, sense_tab, sound_tab};
        const Rectangle active_tab = option_tabs[static_cast<std::size_t>(options_tab)];
        DrawRectangleRec(active_tab, {36, 117, 133, 255});
        const OptionsTab previous_tab = options_tab;
        if (GuiButton(camera_tab, "Cam")) options_tab = OptionsTab::Camera;
        if (GuiButton(combat_tab, "Fight")) options_tab = OptionsTab::Combat;
        if (GuiButton(tactics_tab, "Tact")) options_tab = OptionsTab::Tactics;
        if (GuiButton(wounds_tab, "Wnd")) options_tab = OptionsTab::Wounds;
        if (GuiButton(look_tab, "Look")) options_tab = OptionsTab::Look;
        if (GuiButton(sense_tab, "Sens")) options_tab = OptionsTab::Sense;
        if (GuiButton(sound_tab, "Snd")) options_tab = OptionsTab::Sound;
        if (options_tab != previous_tab) {
            if (attack_stun_editor.editing) {
                actions.combat_settings_changed |= attack_stun_editor.Commit(settings);
                attack_stun_editor.editing = false;
            }
            if (head_turn_editor.editing) {
                actions.look_settings_changed |= head_turn_editor.Commit(settings);
                head_turn_editor.editing = false;
            }
            if (team_count_editor.hero_editing) {
                actions.team_counts_changed |= team_count_editor.Commit(
                    team_count_editor.hero_text, settings.hero_agent_count, settings);
                team_count_editor.hero_editing = false;
            }
            if (team_count_editor.villain_editing) {
                actions.team_counts_changed |= team_count_editor.Commit(
                    team_count_editor.villain_text, settings.villain_agent_count, settings);
                team_count_editor.villain_editing = false;
            }
            attack_stun_editor.dropdown_open = false;
        }

        struct SliderRow { const char* label; float* value; float minimum; float maximum; };
        bool draw_attack_dropdown = false;
        Rectangle attack_dropdown{};
        if (options_tab == OptionsTab::Camera) {
            std::array<SliderRow, 5> rows{{
                {"Look", &settings.look_sensitivity, viewer::kMinLookSensitivity, viewer::kMaxLookSensitivity},
                {"Pan", &settings.pan_sensitivity, viewer::kMinPanSensitivity, viewer::kMaxPanSensitivity},
                {"Flight", &settings.flight_speed, viewer::kMinFlightSpeed, viewer::kMaxFlightSpeed},
                {"Dolly", &settings.zoom_sensitivity, viewer::kMinZoomSensitivity, viewer::kMaxZoomSensitivity},
                {"Arrow rate", &settings.arrow_repeat_ticks_per_second,
                    viewer::kMinArrowRepeatRate, viewer::kMaxArrowRepeatRate},
            }};
            float row_y = panel.y + 58.0f;
            for (std::size_t index = 0; index < rows.size(); ++index) {
                const SliderRow& row = rows[index];
                DrawText(row.label, static_cast<int>(panel.x + 16.0f), static_cast<int>(row_y), 15, kText);
                DrawText(index == rows.size() - 1U
                        ? TextFormat("%.0f t/s", *row.value)
                        : TextFormat(row.maximum <= 0.1f ? "%.3f" : "%.2f", *row.value),
                    static_cast<int>(panel.x + 248.0f), static_cast<int>(row_y), 15, kMuted);
                (void)GuiSliderBar({panel.x + 16.0f, row_y + 23.0f, 288.0f, 18.0f}, nullptr, nullptr,
                    row.value, row.minimum, row.maximum);
                row_y += 51.0f;
            }
        } else if (options_tab == OptionsTab::Combat) {
            const bool controls_locked = attack_stun_editor.dropdown_open;
            if (controls_locked) GuiLock();
            std::array<SliderRow, 3> rows{{
                {"Cooldown", &settings.attack_cooldown_seconds,
                    viewer::kMinAttackCooldown, viewer::kMaxAttackCooldown},
                {"Parried", &settings.parried_attack_cooldown_seconds,
                    viewer::kMinAttackCooldown, viewer::kMaxAttackCooldown},
                {"Parry split", &settings.parry_probability,
                    viewer::kMinParryProbability, viewer::kMaxParryProbability},
            }};
            DrawText("Attack clip", static_cast<int>(panel.x + 16.0f),
                static_cast<int>(panel.y + 58.0f), 15, kText);
            attack_dropdown = {panel.x + 16.0f, panel.y + 80.0f, 288.0f, 20.0f};
            draw_attack_dropdown = true;

            float row_y = panel.y + 154.0f;
            for (std::size_t index = 0; index < rows.size(); ++index) {
                const SliderRow& row = rows[index];
                DrawText(row.label, static_cast<int>(panel.x + 16.0f), static_cast<int>(row_y), 15, kText);
                DrawText(index < 2U ? TextFormat("%.2fs", *row.value) : TextFormat("%.0f%%", *row.value * 100.0f),
                    static_cast<int>(panel.x + 248.0f), static_cast<int>(row_y), 15, kMuted);
                if (GuiSliderBar({panel.x + 16.0f, row_y + 23.0f, 288.0f, 18.0f}, nullptr, nullptr,
                    row.value, row.minimum, row.maximum)) actions.combat_settings_changed = true;
                row_y += 58.0f;
            }
            DrawText("Stun duration", static_cast<int>(panel.x + 16.0f),
                static_cast<int>(panel.y + 118.0f), 15, kText);
            const Rectangle stun_input{panel.x + 204.0f, panel.y + 110.0f, 80.0f, 30.0f};
            DrawRectangleRec(stun_input, kPanelRaised);
            if (GuiTextBox(stun_input, attack_stun_editor.text.data(),
                    static_cast<int>(attack_stun_editor.text.size()), attack_stun_editor.editing) != 0) {
                if (attack_stun_editor.editing) {
                    actions.combat_settings_changed |= attack_stun_editor.Commit(settings);
                }
                attack_stun_editor.editing = !attack_stun_editor.editing;
            }
            DrawText("s", static_cast<int>(panel.x + 291.0f),
                static_cast<int>(panel.y + 118.0f), 15, kMuted);
            if (controls_locked) GuiUnlock();
        } else if (options_tab == OptionsTab::Tactics) {
            std::array<SliderRow, 5> rows{{
                {"Commit", &settings.target_commitment_seconds,
                    viewer::kMinTargetCommitmentSeconds, viewer::kMaxTargetCommitmentSeconds},
                {"Flank near", &settings.sector_influence_distance_m,
                    viewer::kMinSectorInfluenceDistance, viewer::kMaxSectorInfluenceDistance},
                {"Angle jitter", &settings.sector_angle_variation_degrees,
                    viewer::kMinSectorAngleVariationDegrees,
                    viewer::kMaxSectorAngleVariationDegrees},
                {"Radius jitter", &settings.sector_radius_variation_m,
                    viewer::kMinSectorRadiusVariation, viewer::kMaxSectorRadiusVariation},
                {"Ally space", &settings.ally_spacing_distance_m,
                    viewer::kMinAllySpacingDistance, viewer::kMaxAllySpacingDistance},
            }};
            float row_y = panel.y + 58.0f;
            for (std::size_t index = 0; index < rows.size(); ++index) {
                const SliderRow& row = rows[index];
                DrawText(row.label, static_cast<int>(panel.x + 16.0f),
                    static_cast<int>(row_y), 15, kText);
                const char* value = index == 0U
                    ? TextFormat("%.2fs", *row.value)
                    : (index == 2U ? TextFormat("%.0f deg", *row.value)
                        : TextFormat("%.2fm", *row.value));
                DrawText(value, static_cast<int>(panel.x + 248.0f),
                    static_cast<int>(row_y), 15, kMuted);
                if (GuiSliderBar({panel.x + 16.0f, row_y + 23.0f, 288.0f, 18.0f},
                        nullptr, nullptr, row.value, row.minimum, row.maximum)) {
                    actions.tactics_settings_changed = true;
                }
                row_y += 58.0f;
            }
        } else if (options_tab == OptionsTab::Wounds) {
            std::array<SliderRow, 6> rows{{
                {"Melee gain", &settings.melee_wound_gain,
                    viewer::kMinMeleeWoundGain, viewer::kMaxMeleeWoundGain},
                {"Threshold", &settings.wound_threshold,
                    viewer::kMinWoundThreshold, viewer::kMaxWoundThreshold},
                {"Decay / sec", &settings.wound_decay_per_second,
                    viewer::kMinWoundDecay, viewer::kMaxWoundDecay},
                {"Leg agony", &settings.leg_agonising_seconds,
                    viewer::kMinWoundStateSeconds, viewer::kMaxWoundStateSeconds},
                {"Torso agony", &settings.torso_agonising_seconds,
                    viewer::kMinWoundStateSeconds, viewer::kMaxWoundStateSeconds},
                {"Head out", &settings.head_passed_out_seconds,
                    viewer::kMinWoundStateSeconds, viewer::kMaxWoundStateSeconds},
            }};
            float row_y = panel.y + 58.0f;
            for (std::size_t index = 0; index < rows.size(); ++index) {
                const SliderRow& row = rows[index];
                DrawText(row.label, static_cast<int>(panel.x + 16.0f), static_cast<int>(row_y), 15, kText);
                const bool percentage = index < 3U;
                DrawText(percentage ? TextFormat("%.1f%%", *row.value) : TextFormat("%.1fs", *row.value),
                    static_cast<int>(panel.x + 248.0f), static_cast<int>(row_y), 15, kMuted);
                if (GuiSliderBar({panel.x + 16.0f, row_y + 21.0f, 288.0f, 16.0f}, nullptr, nullptr,
                    row.value, row.minimum, row.maximum)) actions.wound_settings_changed = true;
                row_y += 55.0f;
            }
        } else if (options_tab == OptionsTab::Look) {
            DrawText("Turn speed", static_cast<int>(panel.x + 16.0f),
                static_cast<int>(panel.y + 66.0f), 15, kText);
            const Rectangle speed_input{panel.x + 168.0f, panel.y + 58.0f, 92.0f, 30.0f};
            DrawRectangleRec(speed_input, kPanelRaised);
            if (GuiTextBox(speed_input, head_turn_editor.text.data(),
                    static_cast<int>(head_turn_editor.text.size()), head_turn_editor.editing) != 0) {
                if (head_turn_editor.editing) {
                    actions.look_settings_changed |= head_turn_editor.Commit(settings);
                }
                head_turn_editor.editing = !head_turn_editor.editing;
            }
            DrawText("deg/s", static_cast<int>(panel.x + 266.0f),
                static_cast<int>(panel.y + 66.0f), 15, kMuted);
        } else if (options_tab == OptionsTab::Sense) {
            std::array<SliderRow, 8> rows{{
                {"Keep near", &settings.proximity_threat_range_m,
                    viewer::kMinProximityThreatRange, viewer::kMaxProximityThreatRange},
                {"Vision range", &settings.vision_range_m,
                    viewer::kMinVisionRange, viewer::kMaxVisionRange},
                {"Vision angle", &settings.head_vision_angle_degrees,
                    viewer::kMinVisionAngleDegrees, viewer::kMaxVisionAngleDegrees},
                {"Run toward", &settings.running_sound_toward_leeway_degrees,
                    viewer::kMinRunningSoundLeewayDegrees,
                    viewer::kMaxRunningSoundLeewayDegrees},
                {"Ignore min", &settings.non_threatening_minimum_seconds,
                    viewer::kMinNonThreateningSeconds, viewer::kMaxNonThreateningSeconds},
                {"Ignore max", &settings.non_threatening_maximum_seconds,
                    viewer::kMinNonThreateningSeconds, viewer::kMaxNonThreateningSeconds},
                {"Follow walk", &settings.follow_walk_distance_m,
                    viewer::kMinFollowDistance, viewer::kMaxFollowDistance},
                {"Follow stop", &settings.follow_stop_distance_m,
                    viewer::kMinFollowDistance, viewer::kMaxFollowDistance},
            }};
            float row_y = panel.y + 58.0f;
            for (std::size_t index = 0; index < rows.size(); ++index) {
                const SliderRow& row = rows[index];
                DrawText(row.label, static_cast<int>(panel.x + 16.0f),
                    static_cast<int>(row_y), 15, kText);
                const char* value = index < 2U || index >= 6U
                    ? TextFormat("%.1fm", *row.value)
                    : (index < 4U ? TextFormat("%.0f deg", *row.value)
                        : TextFormat("%.0fs", *row.value));
                DrawText(value, static_cast<int>(panel.x + 248.0f),
                    static_cast<int>(row_y), 15, kMuted);
                if (GuiSliderBar({panel.x + 16.0f, row_y + 21.0f, 288.0f, 16.0f},
                        nullptr, nullptr, row.value, row.minimum, row.maximum)) {
                    actions.perception_settings_changed = true;
                }
                row_y += 43.0f;
            }
            if (settings.non_threatening_minimum_seconds >
                settings.non_threatening_maximum_seconds) {
                std::swap(settings.non_threatening_minimum_seconds,
                    settings.non_threatening_maximum_seconds);
            }
            settings.follow_stop_distance_m = std::min(
                settings.follow_stop_distance_m, settings.follow_walk_distance_m);
        } else {
            GuiCheckBox({panel.x + 16.0f, panel.y + 62.0f, 24.0f, 24.0f},
                "Show sound reach", &settings.sound_visualization);
            DrawText("Max reach", static_cast<int>(panel.x + 16.0f),
                static_cast<int>(panel.y + 112.0f), 15, kText);
            DrawText(TextFormat("%.1fm", settings.sound_maximum_range_m),
                static_cast<int>(panel.x + 248.0f),
                static_cast<int>(panel.y + 112.0f), 15, kMuted);
            if (GuiSliderBar({panel.x + 16.0f, panel.y + 135.0f, 288.0f, 18.0f},
                    nullptr, nullptr, &settings.sound_maximum_range_m,
                    viewer::kMinSoundMaximumRange, viewer::kMaxSoundMaximumRange)) {
                actions.perception_settings_changed = true;
            }
        }
        const bool footer_locked = attack_stun_editor.dropdown_open;
        if (footer_locked) GuiLock();
        const Rectangle restore_button{panel.x + 16.0f, panel.y + 410.0f, 42.0f, 38.0f};
        const Rectangle save_button{panel.x + 64.0f, panel.y + 410.0f, 42.0f, 38.0f};
        actions.restore_saved_settings = IconButton(
            restore_button, ICON_RESTART, "Reset all options to saved", tooltip);
        actions.save_settings = IconButton(save_button, ICON_FILE_SAVE, "Save all options", tooltip);
        if (!settings_status.empty()) {
            DrawText(settings_status.c_str(), static_cast<int>(panel.x + 120.0f),
                static_cast<int>(panel.y + 422.0f), 13, kMuted);
        }
        if (footer_locked) GuiUnlock();

        if (draw_attack_dropdown) {
            const int previous_attack = attack_stun_editor.selected;
            if (GuiDropdownBox(attack_dropdown, attack_stun_editor.choices.c_str(),
                    &attack_stun_editor.selected, attack_stun_editor.dropdown_open) != 0) {
                attack_stun_editor.dropdown_open = !attack_stun_editor.dropdown_open;
            }
            if (attack_stun_editor.selected != previous_attack) attack_stun_editor.Sync(settings);
        }
    }
    return actions;
}

std::uint64_t NewSeed() {
    return static_cast<std::uint64_t>(
        std::chrono::high_resolution_clock::now().time_since_epoch().count());
}

std::filesystem::path LocalDataDirectory() {
#if defined(_WIN32)
    char* local_app_data = nullptr;
    std::size_t length = 0;
    if (_dupenv_s(&local_app_data, &length, "LOCALAPPDATA") == 0 && local_app_data != nullptr) {
        const std::filesystem::path path = std::filesystem::path(local_app_data) /
            "ProphecyStandaloneSim";
        std::free(local_app_data);
        return path;
    }
#else
    if (const char* local_app_data = std::getenv("LOCALAPPDATA")) {
        return std::filesystem::path(local_app_data) / "ProphecyStandaloneSim";
    }
#endif
    return std::filesystem::current_path();
}

std::string ControlSettingsPath() {
    return (LocalDataDirectory() / "camera_settings.json").string();
}

std::string OpeningLayoutPath() {
    return (LocalDataDirectory() / "opening-layout.json").string();
}

std::string LatestScreenshotPath() {
    return (LocalDataDirectory() / "latest-screenshot.png").string();
}

bool SaveCurrentWindowImage(const std::string& path) {
    const Image screenshot = LoadImageFromScreen();
    if (!IsImageValid(screenshot)) return false;
    const bool saved = ExportImage(screenshot, path.c_str());
    UnloadImage(screenshot);
    return saved;
}

viewer::OpeningLayout CaptureOpeningLayout(
    const sim::SimulationSnapshot& snapshot, std::uint32_t persistent_agent_count) {
    viewer::OpeningLayout layout{};
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        if (agent.id > persistent_agent_count) continue;
        std::vector<viewer::SavedAgentTransform>& team = agent.team == sim::Team::Hero
            ? layout.heroes
            : layout.villains;
        team.push_back({agent.position.x, agent.position.y, agent.facing_radians});
    }
    return layout;
}

struct Arguments {
    std::string scenario_path{};
    std::string rig_path{};
    std::string locomotion_poses_path{};
    std::string capture_path{};
    bool capture_options = false;
    bool capture_combat_options = false;
    bool capture_look_options = false;
    bool capture_sense_options = false;
    bool capture_sound_options = false;
    bool paired_mode = false;
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
        else if (argument == "--capture-combat-options") arguments.capture_combat_options = true;
        else if (argument == "--capture-look-options") arguments.capture_look_options = true;
        else if (argument == "--capture-sense-options") arguments.capture_sense_options = true;
        else if (argument == "--capture-sound-options") arguments.capture_sound_options = true;
        else if (argument == "--paired") arguments.paired_mode = true;
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
    GuiSetStyle(DROPDOWNBOX, DROPDOWN_ITEMS_SPACING, 0);
}

}  // namespace

int main(int argc, char** argv) {
    const Arguments arguments = ParseArguments(argc, argv);
    viewer::Scenario scenario = viewer::MakeFallbackScenario();
    std::string error;
    if (!viewer::LoadScenario(arguments.scenario_path, scenario, error)) {
        std::fprintf(stderr, "%s\nUsing the neutral fallback scenario.\n", error.c_str());
    }
    if (arguments.paired_mode) scenario.simulation.mode = sim::SimulationMode::Paired;
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
    viewer::ControlSettings saved_settings = settings;
    scenario.seed = settings.seed;
    scenario.simulation.hero_agent_count = settings.hero_agent_count;
    scenario.simulation.villain_agent_count = settings.villain_agent_count;
    scenario.simulation.agent_count = settings.hero_agent_count + settings.villain_agent_count;
    scenario.simulation.attack_cooldown_seconds = settings.attack_cooldown_seconds;
    scenario.simulation.parried_attack_cooldown_seconds = settings.parried_attack_cooldown_seconds;
    scenario.simulation.parry_probability = settings.parry_probability;
    scenario.simulation.head_turn_speed_degrees_per_second =
        settings.head_turn_speed_degrees_per_second;
    scenario.simulation.proximity_threat_range_m = settings.proximity_threat_range_m;
    scenario.simulation.vision_range_m = settings.vision_range_m;
    scenario.simulation.head_vision_angle_degrees = settings.head_vision_angle_degrees;
    scenario.simulation.sound_maximum_range_m = settings.sound_maximum_range_m;
    scenario.simulation.running_sound_toward_leeway_degrees =
        settings.running_sound_toward_leeway_degrees;
    scenario.simulation.non_threatening_minimum_seconds =
        settings.non_threatening_minimum_seconds;
    scenario.simulation.non_threatening_maximum_seconds =
        settings.non_threatening_maximum_seconds;
    scenario.simulation.follow_walk_distance_m = settings.follow_walk_distance_m;
    scenario.simulation.follow_stop_distance_m = settings.follow_stop_distance_m;
    scenario.simulation.target_commitment_seconds = settings.target_commitment_seconds;
    scenario.simulation.sector_influence_distance_m = settings.sector_influence_distance_m;
    scenario.simulation.sector_angle_variation_degrees =
        settings.sector_angle_variation_degrees;
    scenario.simulation.sector_radius_variation_m = settings.sector_radius_variation_m;
    scenario.simulation.ally_spacing_distance_m = settings.ally_spacing_distance_m;
    scenario.simulation.sword_attack_stun_seconds = settings.sword_attack_stun_seconds;
    scenario.simulation.melee_attack_stun_seconds = settings.melee_attack_stun_seconds;
    scenario.simulation.melee_wound_gain = settings.melee_wound_gain;
    scenario.simulation.wound_threshold = settings.wound_threshold;
    scenario.simulation.wound_decay_per_second = settings.wound_decay_per_second;
    scenario.simulation.leg_agonising_seconds = settings.leg_agonising_seconds;
    scenario.simulation.torso_agonising_seconds = settings.torso_agonising_seconds;
    scenario.simulation.head_passed_out_seconds = settings.head_passed_out_seconds;
    viewer::OpeningLayout opening_layout{};
    const bool opening_layout_loaded = viewer::LoadOpeningLayout(
        OpeningLayoutPath(), opening_layout, error);
    if (!opening_layout_loaded) settings_status = "Opening layout ignored";
    bool opening_layout_expanded = false;
    scenario.simulation.opening_transforms = viewer::BuildOpeningTransforms(opening_layout,
        settings.hero_agent_count, settings.villain_agent_count, scenario.seed,
        opening_layout_expanded);
    if (opening_layout_expanded) {
        const bool saved = viewer::SaveOpeningLayout(OpeningLayoutPath(), opening_layout, error);
        settings_status = saved ? "Opening layout expanded" : "Layout expansion save failed";
    }

    unsigned int flags = FLAG_WINDOW_RESIZABLE | FLAG_MSAA_4X_HINT | FLAG_VSYNC_HINT;
    if (arguments.background_reload) flags |= FLAG_WINDOW_UNFOCUSED | FLAG_WINDOW_HIDDEN;
    SetConfigFlags(flags);
    SetTraceLogLevel(LOG_WARNING);
    InitWindow(1500, 900, "Prophecy Standalone Simulation");
    if (arguments.background_reload) viewer::ShowWindowAtBottom(GetWindowHandle(), arguments.restore_foreground);
    SetWindowMinSize(1000, 650);
    SetTargetFPS(60);
    ConfigureGui();
    SolidBatch solid_batch{};
    solid_batch.Initialize();

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
    rewind.Reset(simulation);
#endif
    viewer::TelemetryServer telemetry{};
    if (arguments.telemetry && !telemetry.Start(arguments.telemetry_port, error)) {
        std::fprintf(stderr, "%s\n", error.c_str());
    }

    bool paused = !arguments.capture_path.empty();
    bool options_open = arguments.capture_options || arguments.capture_combat_options ||
        arguments.capture_look_options || arguments.capture_sense_options ||
        arguments.capture_sound_options;
    OptionsTab options_tab = arguments.capture_combat_options
        ? OptionsTab::Combat
        : (arguments.capture_look_options ? OptionsTab::Look
            : (arguments.capture_sense_options ? OptionsTab::Sense
                : (arguments.capture_sound_options ? OptionsTab::Sound : OptionsTab::Camera)));
    SeedInputState seed_input{};
    seed_input.Set(simulation.Seed());
    AttackStunEditorState attack_stun_editor{};
    attack_stun_editor.Initialize(locomotion_poses, settings);
    HeadTurnEditorState head_turn_editor{};
    head_turn_editor.Sync(settings);
    TeamCountEditorState team_count_editor{};
    team_count_editor.Sync(settings);
    float time_scale = 1.0f;
    double tick_accumulator = 0.0;
    BenchmarkResult benchmark{};
    int capture_frames = 0;
    AgentDoubleClick agent_double_click{};
    AgentTransformDrag agent_transform_drag{};
    std::vector<sim::AgentTransform> agent_transform_batch{};
    agent_transform_batch.reserve(sim::kMaxSimulationAgentCount);
    TickKeyRepeater tick_key_repeater{};
    sim::EntityId selected_agent_id = arguments.capture_follow_agent;
    AgentSelection selected_agents{};
    SelectOnlyAgent(selected_agents, selected_agent_id);

    while (!WindowShouldClose()) {
        const Rectangle transport{12.0f, 12.0f, 640.0f, 104.0f};
        const Rectangle info{static_cast<float>(GetScreenWidth()) - 342.0f, 12.0f, 330.0f, kInfoPanelHeight};
        const Rectangle options{static_cast<float>(GetScreenWidth()) - 332.0f,
            OptionsPanelTop(), 320.0f, kOptionsPanelHeight};
        const Vector2 mouse = GetMousePosition();
        const bool ui_hovered = CheckCollisionPointRec(mouse, transport) || CheckCollisionPointRec(mouse, info) ||
            (options_open && CheckCollisionPointRec(mouse, options));
        const bool text_input_active = seed_input.editing || attack_stun_editor.editing ||
            attack_stun_editor.dropdown_open || head_turn_editor.editing ||
            team_count_editor.hero_editing || team_count_editor.villain_editing;
        if (!text_input_active && ControlKeyDown() && IsKeyPressed(kAzertyLabelAKey)) {
            SelectAgentTeam(simulation.Snapshot(), selected_agent_id, selected_agents);
        }
        if (!text_input_active && IsKeyPressed(KEY_SPACE)) paused = !paused;
        const std::int64_t keyboard_tick_delta = text_input_active ? 0 : tick_key_repeater.Consume(
#if PROPHECY_ENABLE_REWIND
            IsKeyDown(KEY_LEFT),
#else
            false,
#endif
            IsKeyDown(KEY_RIGHT), GetFrameTime(), settings.arrow_repeat_ticks_per_second);
        if (keyboard_tick_delta != 0) {
            const std::uint64_t step_count = static_cast<std::uint64_t>(
                keyboard_tick_delta < 0 ? -keyboard_tick_delta : keyboard_tick_delta);
            const std::uint64_t tick_count = step_count * (ControlKeyDown()
                ? static_cast<std::uint64_t>(simulation.Config().tick_rate_hz)
                : 1U);
            if (keyboard_tick_delta < 0) {
#if PROPHECY_ENABLE_REWIND
                (void)rewind.SeekBackward(simulation, tick_count);
#endif
            } else {
                AdvanceTicks(simulation,
#if PROPHECY_ENABLE_REWIND
                    rewind,
#endif
                    tick_count);
            }
            if (paused) tick_accumulator = 0.0;
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

        const auto spawn_at_mouse = [&](sim::Team team) {
            Vector3 ground_point{};
            if (!GroundPointFromMouse(flying_camera.camera, mouse, ground_point)) return;
            const sim::SimulationConfig& config = simulation.Config();
            if (ground_point.x < config.world_min.x || ground_point.x > config.world_max.x ||
                ground_point.z < config.world_min.y || ground_point.z > config.world_max.y) return;
            const float toward_camera_x = flying_camera.camera.position.x - ground_point.x;
            const float toward_camera_z = flying_camera.camera.position.z - ground_point.z;
            float facing_radians = flying_camera.yaw + kPi;
            if (toward_camera_x * toward_camera_x + toward_camera_z * toward_camera_z > 1.0e-6f) {
                facing_radians = std::atan2(toward_camera_x, toward_camera_z);
            }
            (void)simulation.SpawnTransientAgent(team,
                {ground_point.x, ground_point.z, 0.0f}, facing_radians);
        };
        if (!text_input_active && !ui_hovered) {
            if (IsKeyPressed(KEY_R)) spawn_at_mouse(sim::Team::Villain);
            if (IsKeyPressed(KEY_B)) spawn_at_mouse(sim::Team::Hero);
        }

        if (!paused && agent_transform_drag.CapturesMouse()) {
#if PROPHECY_ENABLE_REWIND
            if (agent_transform_drag.editing) rewind.CommitTransformEdit(simulation);
#endif
            agent_transform_drag.Clear();
        }
        bool transform_mouse_captured = false;
        if (paused && !text_input_active && !ui_hovered &&
            IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            const bool rotating_team = ControlKeyDown() && selected_agents.count() > 1U;
            const sim::AgentSnapshot* picked = PickAgent(
                simulation.Snapshot(), flying_camera.camera, mouse, render_prediction_seconds,
                rotating_team ? &selected_agents : nullptr);
            if (picked != nullptr) {
                selected_agent_id = picked->id;
                if (!IsAgentSelected(selected_agents, picked->id)) {
                    SelectOnlyAgent(selected_agents, picked->id);
                }
                Vector3 ground_point{};
                if (GroundPointFromMouse(flying_camera.camera, mouse, ground_point)) {
                    agent_transform_drag.Begin(
                        simulation.Snapshot(), *picked, selected_agents, mouse, ground_point);
                } else if (agent_double_click.Register(*picked, mouse)) {
                    flying_camera.Follow(*picked, render_prediction_seconds);
                }
            } else if (rotating_team) {
                const sim::AgentSnapshot* anchor = FindAgent(
                    simulation.Snapshot(), selected_agent_id);
                Vector3 ground_point{};
                if (anchor != nullptr &&
                    GroundPointFromMouse(flying_camera.camera, mouse, ground_point)) {
                    agent_transform_drag.Begin(
                        simulation.Snapshot(), *anchor, selected_agents, mouse, ground_point);
                }
            } else {
                selected_agent_id = sim::kInvalidEntityId;
                selected_agents.reset();
                agent_double_click.Clear();
            }
        } else if (!paused && !text_input_active && !ui_hovered &&
            IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            const sim::AgentSnapshot* picked = PickAgent(
                simulation.Snapshot(), flying_camera.camera, mouse, render_prediction_seconds);
            if (picked != nullptr) {
                selected_agent_id = picked->id;
                SelectOnlyAgent(selected_agents, picked->id);
                if (agent_double_click.Register(*picked, mouse)) {
                    flying_camera.Follow(*picked, render_prediction_seconds);
                }
            } else {
                selected_agent_id = sim::kInvalidEntityId;
                selected_agents.reset();
                agent_double_click.Clear();
            }
        }
        if (paused && agent_transform_drag.CapturesMouse()) {
            transform_mouse_captured = true;
            if (IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
                const bool rotate = ControlKeyDown();
                const bool crossed_drag_threshold =
                    Vector2Distance(mouse, agent_transform_drag.start_mouse) >= 3.0f;
                if (rotate || crossed_drag_threshold) {
                    if (!agent_transform_drag.editing) {
                        bool edit_ready = true;
#if PROPHECY_ENABLE_REWIND
                        edit_ready = rewind.PrepareTransformEdit(simulation);
#endif
                        agent_transform_drag.editing = edit_ready;
                        if (edit_ready) agent_double_click.Clear();
                    }
                    Vector3 ground_point{};
                    if (agent_transform_drag.editing &&
                        GroundPointFromMouse(flying_camera.camera, mouse, ground_point)) {
                        agent_transform_drag.RebaseForMode(
                            simulation.Snapshot(), ground_point, rotate);
                        if (agent_transform_drag.BuildTransforms(
                                ground_point, rotate, simulation.Config(), agent_transform_batch)) {
                            (void)simulation.SetAgentTransforms(agent_transform_batch);
                        }
                    }
                }
            }
            if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) {
                const sim::AgentSnapshot* agent = FindAgent(
                    simulation.Snapshot(), agent_transform_drag.anchor_id);
                if (agent_transform_drag.editing) {
#if PROPHECY_ENABLE_REWIND
                    rewind.CommitTransformEdit(simulation);
#endif
                } else if (agent != nullptr) {
                    SelectOnlyAgent(selected_agents, agent->id);
                    if (agent_double_click.Register(*agent, mouse)) {
                        flying_camera.Follow(*agent, render_prediction_seconds);
                    }
                }
                agent_transform_drag.Clear();
                transform_mouse_captured = false;
            }
        }
        if (!text_input_active && (IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_KP_ENTER)) &&
            selected_agent_id != sim::kInvalidEntityId) {
            const sim::AgentSnapshot* selected = FindAgent(simulation.Snapshot(), selected_agent_id);
            if (selected != nullptr) flying_camera.Follow(*selected, render_prediction_seconds);
        }
        flying_camera.Update(settings, !text_input_active && !ui_hovered && !transform_mouse_captured,
            simulation.Snapshot(), render_prediction_seconds);

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
            equipment_joints, selected_agent_id, selected_agents, render_prediction_seconds,
            settings.sound_visualization, flying_camera.camera, solid_batch);
        EndMode3D();

        Tooltip tooltip{};
        const UiActions actions = DrawUi(scenario, simulation, paused, time_scale,
#if PROPHECY_ENABLE_REWIND
            rewind.active, rewind.DisplayHead(simulation),
#else
            false, simulation.Snapshot().tick,
#endif
            options_open, options_tab, settings, locomotion_poses,
            benchmark, settings_status, seed_input, attack_stun_editor, head_turn_editor,
            team_count_editor, selected_agent_id, selected_agents, tooltip);
        DrawTooltip(tooltip);
        EndDrawing();

        if (actions.screenshot) {
            const std::filesystem::path screenshot_path = LatestScreenshotPath();
            std::error_code filesystem_error;
            std::filesystem::create_directories(screenshot_path.parent_path(), filesystem_error);
            if (filesystem_error) {
                settings_status = "Screenshot failed";
            } else {
                settings_status = SaveCurrentWindowImage(screenshot_path.string())
                    ? "Screenshot saved"
                    : "Screenshot failed";
            }
        }
        if (actions.square_formation) {
            bool edit_ready = true;
#if PROPHECY_ENABLE_REWIND
            edit_ready = rewind.PrepareTransformEdit(simulation);
#endif
            const std::vector<sim::AgentTransform> transforms = BuildSquareFormation(
                simulation.Snapshot(), simulation.Config());
            const bool arranged = edit_ready && !transforms.empty() &&
                simulation.SetAgentTransforms(transforms);
#if PROPHECY_ENABLE_REWIND
            if (arranged) rewind.CommitTransformEdit(simulation);
#endif
            settings_status = arranged ? "Teams arranged in squares" : "Square arrangement failed";
        }
        if (actions.save_opening_layout) {
            viewer::OpeningLayout candidate = CaptureOpeningLayout(
                simulation.Snapshot(), simulation.Config().agent_count);
            bool expanded = false;
            std::vector<sim::AgentTransform> transforms = viewer::BuildOpeningTransforms(candidate,
                simulation.Config().hero_agent_count, simulation.Config().villain_agent_count,
                simulation.Seed(), expanded);
            const bool accepted = simulation.SetOpeningTransforms(std::move(transforms));
            const bool saved = accepted && viewer::SaveOpeningLayout(
                OpeningLayoutPath(), candidate, error);
            if (accepted) opening_layout = std::move(candidate);
            settings_status = saved ? "Opening layout saved" : "Opening layout save failed";
        }
        if (actions.stop_reset) {
            paused = true;
            simulation.Reset(simulation.Seed());
#if PROPHECY_ENABLE_REWIND
            rewind.Reset(simulation);
#endif
            tick_accumulator = 0.0;
        }
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
            rewind.Reset(simulation);
#endif
            tick_accumulator = 0.0;
        }
        if (actions.set_autonomous && simulation.Config().mode != sim::SimulationMode::Autonomous) {
            simulation.RestartInMode(sim::SimulationMode::Autonomous);
#if PROPHECY_ENABLE_REWIND
            rewind.Reset(simulation);
#endif
            tick_accumulator = 0.0;
        }
        if (actions.set_paired && simulation.Config().mode != sim::SimulationMode::Paired) {
            simulation.RestartInMode(sim::SimulationMode::Paired);
#if PROPHECY_ENABLE_REWIND
            rewind.Reset(simulation);
#endif
            tick_accumulator = 0.0;
        }
        if (actions.validate_success || actions.validate_failure) {
            const sim::AgentSnapshot* selected = FindAgent(simulation.Snapshot(), selected_agent_id);
            if (selected != nullptr) {
                const bool validated = simulation.ValidateAction(selected->id, selected->action.sequence,
                    actions.validate_success);
#if PROPHECY_ENABLE_REWIND
                if (validated) rewind.RefreshCurrent(simulation);
#else
                (void)validated;
#endif
            }
        }
        std::optional<std::uint64_t> requested_seed;
        if (actions.set_seed) requested_seed = actions.seed;
        if (actions.new_seed) requested_seed = NewSeed();
        if (requested_seed.has_value()) {
            simulation.Reset(*requested_seed);
#if PROPHECY_ENABLE_REWIND
            rewind.Reset(simulation);
#endif
            tick_accumulator = 0.0;
            settings.seed = *requested_seed;
            seed_input.Set(*requested_seed);

            viewer::ControlSettings persisted = saved_settings;
            persisted.seed = *requested_seed;
            const bool saved = viewer::SaveControlSettings(ControlSettingsPath(), persisted, error);
            if (saved) saved_settings.seed = *requested_seed;
            settings_status = saved ? "Seed saved" : "Seed save failed";
        }
        if (actions.benchmark) benchmark = RunHeadlessBenchmark(simulation.Config(), simulation.Seed());
        if (actions.combat_settings_changed) {
            simulation.UpdateCombatOptions(settings.attack_cooldown_seconds,
                settings.parried_attack_cooldown_seconds, settings.parry_probability,
                settings.sword_attack_stun_seconds, settings.melee_attack_stun_seconds);
#if PROPHECY_ENABLE_REWIND
            rewind.RefreshCurrent(simulation);
#endif
        }
        if (actions.tactics_settings_changed) {
            simulation.UpdateTacticsOptions(settings.target_commitment_seconds,
                settings.sector_influence_distance_m,
                settings.sector_angle_variation_degrees,
                settings.sector_radius_variation_m,
                settings.ally_spacing_distance_m);
#if PROPHECY_ENABLE_REWIND
            rewind.RefreshCurrent(simulation);
#endif
        }
        if (actions.wound_settings_changed) {
            simulation.UpdateWoundOptions(settings.melee_wound_gain, settings.wound_threshold,
                settings.wound_decay_per_second, settings.leg_agonising_seconds,
                settings.torso_agonising_seconds, settings.head_passed_out_seconds);
#if PROPHECY_ENABLE_REWIND
            rewind.RefreshCurrent(simulation);
#endif
        }
        if (actions.look_settings_changed) {
            simulation.UpdateLookOptions(settings.head_turn_speed_degrees_per_second);
#if PROPHECY_ENABLE_REWIND
            rewind.RefreshCurrent(simulation);
#endif
        }
        if (actions.perception_settings_changed) {
            simulation.UpdatePerceptionOptions(settings.proximity_threat_range_m,
                settings.vision_range_m, settings.head_vision_angle_degrees,
                settings.sound_maximum_range_m,
                settings.running_sound_toward_leeway_degrees,
                settings.non_threatening_minimum_seconds,
                settings.non_threatening_maximum_seconds,
                settings.follow_walk_distance_m, settings.follow_stop_distance_m);
#if PROPHECY_ENABLE_REWIND
            rewind.RefreshCurrent(simulation);
#endif
        }
        if (actions.team_counts_changed) {
            bool expanded = false;
            std::vector<sim::AgentTransform> transforms = viewer::BuildOpeningTransforms(
                opening_layout, settings.hero_agent_count, settings.villain_agent_count,
                simulation.Seed(), expanded);
            simulation.RestartWithTeamCounts(settings.hero_agent_count,
                settings.villain_agent_count, std::move(transforms));
            bool layout_saved = true;
            if (expanded) {
                layout_saved = viewer::SaveOpeningLayout(
                    OpeningLayoutPath(), opening_layout, error);
            }
#if PROPHECY_ENABLE_REWIND
            rewind.Reset(simulation);
#endif
            tick_accumulator = 0.0;
            selected_agent_id = sim::kInvalidEntityId;
            selected_agents.reset();

            viewer::ControlSettings persisted = saved_settings;
            persisted.hero_agent_count = settings.hero_agent_count;
            persisted.villain_agent_count = settings.villain_agent_count;
            const bool counts_saved = viewer::SaveControlSettings(
                ControlSettingsPath(), persisted, error);
            if (counts_saved) {
                saved_settings.hero_agent_count = settings.hero_agent_count;
                saved_settings.villain_agent_count = settings.villain_agent_count;
            }
            if (!counts_saved) settings_status = "Teams restarted; count save failed";
            else if (!layout_saved) settings_status = "Teams saved; layout save failed";
            else settings_status = expanded ? "Teams saved; layout expanded" : "Teams saved";
        }
        if (actions.restore_saved_settings) {
            const bool team_counts_changed = settings.hero_agent_count != saved_settings.hero_agent_count ||
                settings.villain_agent_count != saved_settings.villain_agent_count;
            settings = saved_settings;
            attack_stun_editor.Sync(settings);
            head_turn_editor.Sync(settings);
            team_count_editor.Sync(settings);
            if (team_counts_changed) {
                bool expanded = false;
                std::vector<sim::AgentTransform> transforms = viewer::BuildOpeningTransforms(
                    opening_layout, settings.hero_agent_count, settings.villain_agent_count,
                    simulation.Seed(), expanded);
                simulation.RestartWithTeamCounts(settings.hero_agent_count,
                    settings.villain_agent_count, std::move(transforms));
                if (expanded) {
                    (void)viewer::SaveOpeningLayout(OpeningLayoutPath(), opening_layout, error);
                }
                tick_accumulator = 0.0;
                selected_agent_id = sim::kInvalidEntityId;
                selected_agents.reset();
            }
            simulation.UpdateCombatOptions(settings.attack_cooldown_seconds,
                settings.parried_attack_cooldown_seconds, settings.parry_probability,
                settings.sword_attack_stun_seconds, settings.melee_attack_stun_seconds);
            simulation.UpdateWoundOptions(settings.melee_wound_gain, settings.wound_threshold,
                settings.wound_decay_per_second, settings.leg_agonising_seconds,
                settings.torso_agonising_seconds, settings.head_passed_out_seconds);
            simulation.UpdateLookOptions(settings.head_turn_speed_degrees_per_second);
            simulation.UpdatePerceptionOptions(settings.proximity_threat_range_m,
                settings.vision_range_m, settings.head_vision_angle_degrees,
                settings.sound_maximum_range_m,
                settings.running_sound_toward_leeway_degrees,
                settings.non_threatening_minimum_seconds,
                settings.non_threatening_maximum_seconds,
                settings.follow_walk_distance_m, settings.follow_stop_distance_m);
            simulation.UpdateTacticsOptions(settings.target_commitment_seconds,
                settings.sector_influence_distance_m,
                settings.sector_angle_variation_degrees,
                settings.sector_radius_variation_m,
                settings.ally_spacing_distance_m);
#if PROPHECY_ENABLE_REWIND
            if (team_counts_changed) rewind.Reset(simulation);
            else rewind.RefreshCurrent(simulation);
#endif
            settings_status = "Saved restored";
        }
        if (actions.save_settings) {
            const bool saved = viewer::SaveControlSettings(ControlSettingsPath(), settings, error);
            if (saved) saved_settings = settings;
            settings_status = saved ? "Saved" : "Save failed";
        }

        if (!arguments.capture_path.empty() && ++capture_frames >= 8) {
            (void)SaveCurrentWindowImage(arguments.capture_path);
            break;
        }
    }

    telemetry.Stop();
    solid_batch.Shutdown();
    CloseWindow();
    return 0;
}
