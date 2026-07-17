#pragma once

#include "prophecy/sim/simulation.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace prophecy::viewer {

struct ControlSettings {
    std::uint64_t seed = 1337;
    std::uint32_t hero_agent_count = 1;
    std::uint32_t villain_agent_count = 3;
    float look_sensitivity = 0.007f;
    float pan_sensitivity = 0.10f;
    float flight_speed = 18.0f;
    float zoom_sensitivity = 2.5f;
    float arrow_repeat_ticks_per_second = 30.0f;
    float head_turn_speed_degrees_per_second =
        ::prophecy::sim::kDefaultHeadTurnSpeedDegreesPerSecond;
    float proximity_threat_range_m = ::prophecy::sim::kProximityThreatRangeMeters;
    float vision_range_m = ::prophecy::sim::kVisionRangeMeters;
    float head_vision_angle_degrees = 180.0f;
    float sound_maximum_range_m = ::prophecy::sim::kSoundMaximumRangeMeters;
    float running_sound_toward_leeway_degrees = 15.0f;
    float non_threatening_minimum_seconds = ::prophecy::sim::kNonThreateningMinimumSeconds;
    float non_threatening_maximum_seconds = ::prophecy::sim::kNonThreateningMaximumSeconds;
    float follow_walk_distance_m = ::prophecy::sim::kDefaultFollowWalkDistanceMeters;
    float follow_stop_distance_m = ::prophecy::sim::kDefaultFollowStopDistanceMeters;
    float target_commitment_seconds = ::prophecy::sim::kDefaultTargetCommitmentSeconds;
    float sector_influence_distance_m = ::prophecy::sim::kDefaultSectorInfluenceDistanceMeters;
    float sector_angle_variation_degrees = ::prophecy::sim::kDefaultSectorAngleVariationDegrees;
    float sector_radius_variation_m = ::prophecy::sim::kDefaultSectorRadiusVariationMeters;
    float ally_spacing_distance_m = ::prophecy::sim::kDefaultAllySpacingDistanceMeters;
    bool sound_visualization = true;
    float attack_cooldown_seconds = 1.0f;
    float parried_attack_cooldown_seconds = 1.5f;
    float parry_probability = 0.5f;
    std::array<float, ::prophecy::sim::kSwordAttackClipCount> sword_attack_stun_seconds =
        ::prophecy::sim::kDefaultSwordAttackStunSeconds;
    std::array<float, ::prophecy::sim::kMeleeAttackClipCount> melee_attack_stun_seconds =
        ::prophecy::sim::kDefaultMeleeAttackStunSeconds;
    float melee_wound_gain = 20.0f;
    float wound_threshold = 100.0f;
    float wound_decay_per_second = 1.0f;
    float leg_agonising_seconds = 3.0f;
    float torso_agonising_seconds = 10.0f;
    float head_passed_out_seconds = 30.0f;
};

struct SavedAgentTransform {
    float x = 0.0f;
    float z = 0.0f;
    float facing_radians = 0.0f;
};

struct OpeningLayout {
    std::vector<SavedAgentTransform> heroes{};
    std::vector<SavedAgentTransform> villains{};
};

constexpr float kMinLookSensitivity = 0.001f;
constexpr float kMaxLookSensitivity = 0.020f;
constexpr float kMinPanSensitivity = 0.01f;
constexpr float kMaxPanSensitivity = 0.30f;
constexpr float kMinFlightSpeed = 2.0f;
constexpr float kMaxFlightSpeed = 50.0f;
constexpr float kMinZoomSensitivity = 0.25f;
constexpr float kMaxZoomSensitivity = 6.0f;
constexpr float kMinArrowRepeatRate = 1.0f;
constexpr float kMaxArrowRepeatRate = 120.0f;
constexpr float kMinProximityThreatRange = 0.0f;
constexpr float kMaxProximityThreatRange = 25.0f;
constexpr float kMinVisionRange = 0.0f;
constexpr float kMaxVisionRange = 500.0f;
constexpr float kMinVisionAngleDegrees = 0.0f;
constexpr float kMaxVisionAngleDegrees = 360.0f;
constexpr float kMinSoundMaximumRange = 0.0f;
constexpr float kMaxSoundMaximumRange = 50.0f;
constexpr float kMinRunningSoundLeewayDegrees = 0.0f;
constexpr float kMaxRunningSoundLeewayDegrees = 180.0f;
constexpr float kMinNonThreateningSeconds = 0.0f;
constexpr float kMaxNonThreateningSeconds = 120.0f;
constexpr float kMinFollowDistance = 0.0f;
constexpr float kMaxFollowDistance = 25.0f;
constexpr float kMinTargetCommitmentSeconds = 0.0f;
constexpr float kMaxTargetCommitmentSeconds = 5.0f;
constexpr float kMinSectorInfluenceDistance = 1.25f;
constexpr float kMaxSectorInfluenceDistance = 50.0f;
constexpr float kMinSectorAngleVariationDegrees = 0.0f;
constexpr float kMaxSectorAngleVariationDegrees = 22.5f;
constexpr float kMinSectorRadiusVariation = 0.0f;
constexpr float kMaxSectorRadiusVariation = 1.0f;
constexpr float kMinAllySpacingDistance = 0.0f;
constexpr float kMaxAllySpacingDistance = 5.0f;
constexpr float kMinAttackCooldown = 0.0f;
constexpr float kMaxAttackCooldown = 5.0f;
constexpr float kMinParryProbability = 0.0f;
constexpr float kMaxParryProbability = 1.0f;
constexpr float kMinMeleeWoundGain = 0.0f;
constexpr float kMaxMeleeWoundGain = 100.0f;
constexpr float kMinWoundThreshold = 20.0f;
constexpr float kMaxWoundThreshold = 200.0f;
constexpr float kMinWoundDecay = 0.0f;
constexpr float kMaxWoundDecay = 20.0f;
constexpr float kMinWoundStateSeconds = 0.0f;
constexpr float kMaxWoundStateSeconds = 120.0f;
constexpr std::uint32_t kMinTeamAgentCount = ::prophecy::sim::kMinTeamAgentCount;
constexpr std::uint32_t kMaxTeamAgentCount = ::prophecy::sim::kMaxTeamAgentCount;

ControlSettings DefaultControlSettings() noexcept;
bool LoadControlSettings(const std::string& path, ControlSettings& settings, std::string& error);
bool SaveControlSettings(const std::string& path, const ControlSettings& settings, std::string& error);
bool LoadOpeningLayout(const std::string& path, OpeningLayout& layout, std::string& error);
bool SaveOpeningLayout(const std::string& path, const OpeningLayout& layout, std::string& error);
std::vector<::prophecy::sim::AgentTransform> BuildOpeningTransforms(OpeningLayout& layout,
    std::uint32_t hero_count, std::uint32_t villain_count, std::uint64_t seed,
    bool& expanded);

}  // namespace prophecy::viewer
