#include "unreal_bridge.h"

#include "../../bridge/sim_bridge_protocol.h"

#include "prophecy/sim/locomotion.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstring>
#include <vector>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <Windows.h>
#endif

namespace prophecy::viewer {
namespace {

constexpr float kVillagerCorrectionDistanceMeters = 0.20f;
constexpr float kPi = 3.14159265358979323846f;
constexpr float kTau = 2.0f * kPi;

float WrapAngle(float angle) noexcept {
    angle = std::fmod(angle + kPi, kTau);
    if (angle < 0.0f) angle += kTau;
    return angle - kPi;
}

#if defined(_WIN32)
LONG AtomicRead(volatile std::int32_t* value) noexcept {
    return InterlockedCompareExchange(reinterpret_cast<volatile LONG*>(value), 0, 0);
}

void AtomicWrite(volatile std::int32_t* value, const LONG next) noexcept {
    InterlockedExchange(reinterpret_cast<volatile LONG*>(value), next);
}

void BeginWrite(volatile std::int32_t* sequence) noexcept {
    InterlockedIncrement(reinterpret_cast<volatile LONG*>(sequence));
}

void EndWrite(volatile std::int32_t* sequence) noexcept {
    std::atomic_thread_fence(std::memory_order_seq_cst);
    InterlockedIncrement(reinterpret_cast<volatile LONG*>(sequence));
}
#endif

}  // namespace

struct UnrealBridge::Impl {
#if defined(_WIN32)
    HANDLE mapping = nullptr;
#endif
    bridge::SharedState* shared = nullptr;
    std::int32_t last_unreal_sequence = 0;
    std::vector<bridge::AgentState> unreal_frame{};
    bool has_unreal_frame = false;
};

UnrealBridge::~UnrealBridge() {
    Close();
}

bool UnrealBridge::Open(const std::string& mapping_name, std::string& error) {
    Close();
#if defined(_WIN32)
    const std::wstring wide_name(mapping_name.begin(), mapping_name.end());
    HANDLE mapping = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, wide_name.c_str());
    if (mapping == nullptr) {
        error = "Could not open the Unreal PIE bridge mapping.";
        return false;
    }
    void* address = MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0,
        sizeof(bridge::SharedState));
    if (address == nullptr) {
        CloseHandle(mapping);
        error = "Could not map the Unreal PIE bridge payload.";
        return false;
    }
    auto* shared = static_cast<bridge::SharedState*>(address);
    if (shared->magic != bridge::kMagic || shared->version != bridge::kVersion ||
        shared->byte_size != sizeof(bridge::SharedState) || shared->villager_count == 0U ||
        shared->villager_count > bridge::kMaximumVillagerCount ||
        shared->total_agent_count != shared->villager_count + 1U) {
        UnmapViewOfFile(address);
        CloseHandle(mapping);
        error = "The Unreal PIE bridge payload is incompatible or invalid.";
        return false;
    }
    impl_ = new Impl();
    impl_->mapping = mapping;
    impl_->shared = shared;
    impl_->unreal_frame.resize(shared->total_agent_count);
    error.clear();
    return true;
#else
    (void)mapping_name;
    error = "The Unreal PIE bridge is currently available only on Windows.";
    return false;
#endif
}

void UnrealBridge::Close() noexcept {
    if (impl_ == nullptr) return;
#if defined(_WIN32)
    if (impl_->shared != nullptr) UnmapViewOfFile(impl_->shared);
    if (impl_->mapping != nullptr) CloseHandle(impl_->mapping);
#endif
    delete impl_;
    impl_ = nullptr;
}

bool UnrealBridge::IsOpen() const noexcept {
    return impl_ != nullptr && impl_->shared != nullptr;
}

bool UnrealBridge::ShutdownRequested() const noexcept {
#if defined(_WIN32)
    return IsOpen() && AtomicRead(&impl_->shared->shutdown_requested) != 0;
#else
    return false;
#endif
}

std::size_t UnrealBridge::VillagerCount() const noexcept {
    return IsOpen() ? impl_->shared->villager_count : 0U;
}

std::size_t UnrealBridge::TotalAgentCount() const noexcept {
    return IsOpen() ? impl_->shared->total_agent_count : 0U;
}

bool UnrealBridge::InitializeCrowd(navigation::CrowdRuntime& crowd,
    std::string& error) noexcept {
    if (!IsOpen() || crowd.AgentCount() != TotalAgentCount()) {
        error = "The bridge and navigation crowd agent counts do not match.";
        PublishError(error);
        return false;
    }
    const bridge::AgentState player = impl_->shared->initial_player;
    const std::array<float, 3> position{
        player.position[0], player.position[1], player.position[2]};
    if (!crowd.SetAgentTransform(VillagerCount(), position,
            player.facing_radians, false)) {
        error = "The placed Unreal player is not close enough to the cached village navmesh.";
        PublishError(error);
        return false;
    }
#if defined(_WIN32)
    AtomicWrite(&impl_->shared->sim_ready, 1);
#endif
    Publish(crowd);
    error.clear();
    return true;
}

void UnrealBridge::ApplyUnrealTransforms(navigation::CrowdRuntime& crowd) noexcept {
#if defined(_WIN32)
    if (!IsOpen()) return;
    const LONG first = AtomicRead(&impl_->shared->unreal_sequence);
    if (first <= 0 || (first & 1) != 0 || first == impl_->last_unreal_sequence) return;
    const std::size_t count = TotalAgentCount();
    std::memcpy(impl_->unreal_frame.data(), impl_->shared->unreal_agents,
        count * sizeof(bridge::AgentState));
    std::atomic_thread_fence(std::memory_order_seq_cst);
    const LONG second = AtomicRead(&impl_->shared->unreal_sequence);
    if (first != second || (second & 1) != 0) return;

    for (std::size_t index = 0U; index < count; ++index) {
        const bridge::AgentState& state = impl_->unreal_frame[index];
        if (state.active == 0U) continue;
        const navigation::CrowdAgentSample current = crowd.Agent(index);
        const float dx = state.position[0] - current.position[0];
        const float dy = state.position[1] - current.position[1];
        const float dz = state.position[2] - current.position[2];
        const bool is_player = index >= VillagerCount();
        const bool world_blocked = !is_player && state.physical_world_blocked != 0U;
        if (!is_player && !world_blocked && dx * dx + dy * dy + dz * dz <=
                kVillagerCorrectionDistanceMeters * kVillagerCorrectionDistanceMeters) {
            continue;
        }
        const std::array<float, 3> position{
            state.position[0], state.position[1], state.position[2]};
        (void)crowd.SetAgentTransform(index, position, state.facing_radians,
            !is_player && !world_blocked);
    }
    impl_->has_unreal_frame = true;
    impl_->last_unreal_sequence = second;
#else
    (void)crowd;
#endif
}

void UnrealBridge::Publish(const navigation::CrowdRuntime& crowd) noexcept {
#if defined(_WIN32)
    if (!IsOpen()) return;
    BeginWrite(&impl_->shared->sim_sequence);
    const std::size_t count = std::min(TotalAgentCount(), crowd.AgentCount());
    for (std::size_t index = 0U; index < count; ++index) {
        const navigation::CrowdAgentSample sample = crowd.Agent(index);
        bridge::AgentState& state = impl_->shared->sim_agents[index];
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            state.position[axis] = sample.position[axis];
            state.velocity[axis] = sample.velocity[axis];
        }
        state.facing_radians = sample.facing_radians;
        state.speed_direction_radians = 0.0f;
        state.speed_amplitude = 0.0f;
        state.orientation_yaw_radians = sample.facing_radians;
        state.speed_scale = 1.0f;
        state.turn_scale = 1.0f;
        state.locomotion_mode = 0U;
        if (index < VillagerCount() && sample.locomotion_active) {
            const float horizontal_speed = std::hypot(sample.velocity[0], sample.velocity[1]);
            if (horizontal_speed > 0.01f) {
                const float world_direction = std::atan2(sample.velocity[0], sample.velocity[1]);
                const bridge::AgentState& actual = impl_->unreal_frame[index];
                const float actual_facing = impl_->has_unreal_frame && actual.active != 0U
                    ? actual.facing_radians : sample.facing_radians;
                state.speed_direction_radians = WrapAngle(world_direction - actual_facing);
                const double speed_cap = prophecy::sim::DirectionalSpeedCap(
                    prophecy::sim::LocomotionMode::Walk,
                    state.speed_direction_radians);
                state.speed_amplitude = static_cast<float>(std::clamp(
                    static_cast<double>(horizontal_speed) / speed_cap, 0.0, 1.0));
                state.orientation_yaw_radians = world_direction;
            }
        }
        state.active = sample.active ? 1U : 0U;
    }
    EndWrite(&impl_->shared->sim_sequence);
#else
    (void)crowd;
#endif
}

navigation::CrowdAgentSample UnrealBridge::DisplayAgent(const std::size_t index,
    const navigation::CrowdAgentSample& planned) const noexcept {
    if (!IsOpen() || !impl_->has_unreal_frame || index >= impl_->unreal_frame.size()) {
        return planned;
    }
    const bridge::AgentState& actual = impl_->unreal_frame[index];
    if (actual.active == 0U) return planned;
    navigation::CrowdAgentSample displayed = planned;
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        displayed.position[axis] = actual.position[axis];
        displayed.velocity[axis] = actual.velocity[axis];
    }
    displayed.facing_radians = actual.facing_radians;
    displayed.locomotion_active = std::hypot(actual.velocity[0], actual.velocity[1]) > 0.01f;
    displayed.active = true;
    return displayed;
}

void UnrealBridge::PublishError(const std::string& error) noexcept {
    if (!IsOpen()) return;
    const std::size_t count = std::min(error.size(), sizeof(impl_->shared->error_message) - 1U);
    std::memcpy(impl_->shared->error_message, error.data(), count);
    impl_->shared->error_message[count] = '\0';
}

}  // namespace prophecy::viewer
