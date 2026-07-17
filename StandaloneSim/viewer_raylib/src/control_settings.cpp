#include "control_settings.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <utility>

namespace prophecy::viewer {
namespace {

using Json = nlohmann::json;

template <std::size_t Size>
void ReadFloatArray(const Json& value, std::array<float, Size>& output) {
    if (!value.is_array() || value.empty() || value.size() > Size) return;
    std::array<float, Size> parsed = output;
    for (std::size_t index = 0; index < value.size(); ++index) {
        if (!value[index].is_number()) return;
        parsed[index] = value[index].get<float>();
    }
    output = parsed;
}

template <std::size_t Size>
void NormalizeStunDurations(std::array<float, Size>& values) {
    for (float& value : values) {
        if (!std::isfinite(value)) value = 0.5f;
        else value = std::max(0.0f, value);
    }
}

void ClampSettings(ControlSettings& settings) {
    settings.hero_agent_count = std::clamp(
        settings.hero_agent_count, kMinTeamAgentCount, kMaxTeamAgentCount);
    settings.villain_agent_count = std::clamp(
        settings.villain_agent_count, kMinTeamAgentCount, kMaxTeamAgentCount);
    settings.look_sensitivity = std::clamp(settings.look_sensitivity, kMinLookSensitivity, kMaxLookSensitivity);
    settings.pan_sensitivity = std::clamp(settings.pan_sensitivity, kMinPanSensitivity, kMaxPanSensitivity);
    settings.flight_speed = std::clamp(settings.flight_speed, kMinFlightSpeed, kMaxFlightSpeed);
    settings.zoom_sensitivity = std::clamp(settings.zoom_sensitivity, kMinZoomSensitivity, kMaxZoomSensitivity);
    settings.arrow_repeat_ticks_per_second = std::clamp(settings.arrow_repeat_ticks_per_second,
        kMinArrowRepeatRate, kMaxArrowRepeatRate);
    settings.head_turn_speed_degrees_per_second =
        std::isfinite(settings.head_turn_speed_degrees_per_second)
        ? std::max(0.0f, settings.head_turn_speed_degrees_per_second)
        : ::prophecy::sim::kDefaultHeadTurnSpeedDegreesPerSecond;
    settings.proximity_threat_range_m = std::clamp(settings.proximity_threat_range_m,
        kMinProximityThreatRange, kMaxProximityThreatRange);
    settings.vision_range_m = std::clamp(
        settings.vision_range_m, kMinVisionRange, kMaxVisionRange);
    settings.head_vision_angle_degrees = std::clamp(settings.head_vision_angle_degrees,
        kMinVisionAngleDegrees, kMaxVisionAngleDegrees);
    settings.sound_maximum_range_m = std::clamp(settings.sound_maximum_range_m,
        kMinSoundMaximumRange, kMaxSoundMaximumRange);
    settings.running_sound_toward_leeway_degrees = std::clamp(
        settings.running_sound_toward_leeway_degrees,
        kMinRunningSoundLeewayDegrees, kMaxRunningSoundLeewayDegrees);
    settings.non_threatening_minimum_seconds = std::clamp(
        settings.non_threatening_minimum_seconds,
        kMinNonThreateningSeconds, kMaxNonThreateningSeconds);
    settings.non_threatening_maximum_seconds = std::clamp(
        settings.non_threatening_maximum_seconds,
        kMinNonThreateningSeconds, kMaxNonThreateningSeconds);
    if (settings.non_threatening_minimum_seconds >
        settings.non_threatening_maximum_seconds) {
        std::swap(settings.non_threatening_minimum_seconds,
            settings.non_threatening_maximum_seconds);
    }
    settings.follow_walk_distance_m = std::clamp(
        settings.follow_walk_distance_m, kMinFollowDistance, kMaxFollowDistance);
    settings.follow_stop_distance_m = std::clamp(
        settings.follow_stop_distance_m, kMinFollowDistance, settings.follow_walk_distance_m);
    settings.target_commitment_seconds = std::clamp(settings.target_commitment_seconds,
        kMinTargetCommitmentSeconds, kMaxTargetCommitmentSeconds);
    settings.sector_influence_distance_m = std::clamp(settings.sector_influence_distance_m,
        kMinSectorInfluenceDistance, kMaxSectorInfluenceDistance);
    settings.sector_angle_variation_degrees = std::clamp(
        settings.sector_angle_variation_degrees,
        kMinSectorAngleVariationDegrees, kMaxSectorAngleVariationDegrees);
    settings.sector_radius_variation_m = std::clamp(settings.sector_radius_variation_m,
        kMinSectorRadiusVariation, kMaxSectorRadiusVariation);
    settings.ally_spacing_distance_m = std::clamp(settings.ally_spacing_distance_m,
        kMinAllySpacingDistance, kMaxAllySpacingDistance);
    settings.attack_cooldown_seconds = std::clamp(
        settings.attack_cooldown_seconds, kMinAttackCooldown, kMaxAttackCooldown);
    settings.parried_attack_cooldown_seconds = std::clamp(
        settings.parried_attack_cooldown_seconds, kMinAttackCooldown, kMaxAttackCooldown);
    settings.parry_probability = std::clamp(
        settings.parry_probability, kMinParryProbability, kMaxParryProbability);
    NormalizeStunDurations(settings.sword_attack_stun_seconds);
    NormalizeStunDurations(settings.melee_attack_stun_seconds);
    settings.melee_wound_gain = std::clamp(
        settings.melee_wound_gain, kMinMeleeWoundGain, kMaxMeleeWoundGain);
    settings.wound_threshold = std::clamp(
        settings.wound_threshold, kMinWoundThreshold, kMaxWoundThreshold);
    settings.wound_decay_per_second = std::clamp(
        settings.wound_decay_per_second, kMinWoundDecay, kMaxWoundDecay);
    settings.leg_agonising_seconds = std::clamp(
        settings.leg_agonising_seconds, kMinWoundStateSeconds, kMaxWoundStateSeconds);
    settings.torso_agonising_seconds = std::clamp(
        settings.torso_agonising_seconds, kMinWoundStateSeconds, kMaxWoundStateSeconds);
    settings.head_passed_out_seconds = std::clamp(
        settings.head_passed_out_seconds, kMinWoundStateSeconds, kMaxWoundStateSeconds);
}

std::uint64_t Mix64(std::uint64_t value) noexcept {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

float UnitRandom(std::uint64_t value) noexcept {
    return static_cast<float>(Mix64(value) >> 40U) * (1.0f / 16777216.0f);
}

bool ReadSavedTransforms(const Json& value, std::vector<SavedAgentTransform>& transforms) {
    if (!value.is_array() || value.size() > kMaxTeamAgentCount) return false;
    std::vector<SavedAgentTransform> parsed;
    parsed.reserve(value.size());
    for (const Json& item : value) {
        if (!item.is_object() || !item.contains("position") || !item["position"].is_array() ||
            item["position"].size() != 2U || !item["position"][0].is_number() ||
            !item["position"][1].is_number() || !item.contains("facing_radians") ||
            !item["facing_radians"].is_number()) return false;
        const SavedAgentTransform transform{item["position"][0].get<float>(),
            item["position"][1].get<float>(), item["facing_radians"].get<float>()};
        if (!std::isfinite(transform.x) || !std::isfinite(transform.z) ||
            !std::isfinite(transform.facing_radians)) return false;
        parsed.push_back(transform);
    }
    transforms = std::move(parsed);
    return true;
}

Json WriteSavedTransforms(const std::vector<SavedAgentTransform>& transforms) {
    Json output = Json::array();
    for (const SavedAgentTransform& transform : transforms) {
        output.push_back({
            {"position", {transform.x, transform.z}},
            {"facing_radians", transform.facing_radians},
        });
    }
    return output;
}

}  // namespace

ControlSettings DefaultControlSettings() noexcept {
    return {};
}

bool LoadControlSettings(const std::string& path, ControlSettings& settings, std::string& error) {
    settings = DefaultControlSettings();
    if (!std::filesystem::exists(path)) {
        error.clear();
        return true;
    }

    std::ifstream input(path);
    if (!input) {
        error = "Could not open options: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object()) {
        error = "Options JSON is invalid: " + path;
        return false;
    }

    const Json& camera = root.contains("camera") && root["camera"].is_object() ? root["camera"] : root;
    if (root.contains("simulation") && root["simulation"].is_object()) {
        settings.seed = root["simulation"].value("seed", settings.seed);
        settings.hero_agent_count = root["simulation"].value(
            "hero_agent_count", settings.hero_agent_count);
        settings.villain_agent_count = root["simulation"].value(
            "villain_agent_count", settings.villain_agent_count);
    }
    settings.look_sensitivity = camera.value("look_sensitivity", settings.look_sensitivity);
    settings.pan_sensitivity = camera.value("pan_sensitivity", settings.pan_sensitivity);
    settings.flight_speed = camera.value("flight_speed", settings.flight_speed);
    settings.zoom_sensitivity = camera.value("zoom_sensitivity", settings.zoom_sensitivity);
    if (root.contains("transport") && root["transport"].is_object()) {
        settings.arrow_repeat_ticks_per_second = root["transport"].value(
            "arrow_repeat_ticks_per_second", settings.arrow_repeat_ticks_per_second);
    }
    if (root.contains("look") && root["look"].is_object()) {
        settings.head_turn_speed_degrees_per_second = root["look"].value(
            "head_turn_speed_degrees_per_second",
            settings.head_turn_speed_degrees_per_second);
    }
    if (root.contains("perception") && root["perception"].is_object()) {
        const Json& perception = root["perception"];
        settings.proximity_threat_range_m = perception.value(
            "proximity_threat_range_m", settings.proximity_threat_range_m);
        settings.vision_range_m = perception.value("vision_range_m", settings.vision_range_m);
        settings.head_vision_angle_degrees = perception.value(
            "head_vision_angle_degrees", settings.head_vision_angle_degrees);
        settings.sound_maximum_range_m = perception.value(
            "sound_maximum_range_m", settings.sound_maximum_range_m);
        settings.running_sound_toward_leeway_degrees = perception.value(
            "running_sound_toward_leeway_degrees",
            settings.running_sound_toward_leeway_degrees);
        settings.non_threatening_minimum_seconds = perception.value(
            "non_threatening_minimum_seconds",
            settings.non_threatening_minimum_seconds);
        settings.non_threatening_maximum_seconds = perception.value(
            "non_threatening_maximum_seconds",
            settings.non_threatening_maximum_seconds);
        settings.follow_walk_distance_m = perception.value(
            "follow_walk_distance_m", settings.follow_walk_distance_m);
        settings.follow_stop_distance_m = perception.value(
            "follow_stop_distance_m", settings.follow_stop_distance_m);
    }
    if (root.contains("visualization") && root["visualization"].is_object()) {
        settings.sound_visualization = root["visualization"].value(
            "sound_events", settings.sound_visualization);
    }
    if (root.contains("tactics") && root["tactics"].is_object()) {
        const Json& tactics = root["tactics"];
        settings.target_commitment_seconds = tactics.value(
            "target_commitment_seconds", settings.target_commitment_seconds);
        settings.sector_influence_distance_m = tactics.value(
            "sector_influence_distance_m", settings.sector_influence_distance_m);
        settings.sector_angle_variation_degrees = tactics.value(
            "sector_angle_variation_degrees", settings.sector_angle_variation_degrees);
        settings.sector_radius_variation_m = tactics.value(
            "sector_radius_variation_m", settings.sector_radius_variation_m);
        settings.ally_spacing_distance_m = tactics.value(
            "ally_spacing_distance_m", settings.ally_spacing_distance_m);
    }
    if (root.contains("combat") && root["combat"].is_object()) {
        const Json& combat = root["combat"];
        settings.attack_cooldown_seconds = combat.value(
            "attack_cooldown_seconds", settings.attack_cooldown_seconds);
        settings.parried_attack_cooldown_seconds = combat.value(
            "parried_attack_cooldown_seconds", settings.parried_attack_cooldown_seconds);
        settings.parry_probability = combat.value("parry_probability", settings.parry_probability);
        if (combat.contains("sword_attack_stun_seconds")) {
            ReadFloatArray(combat["sword_attack_stun_seconds"], settings.sword_attack_stun_seconds);
        }
        if (combat.contains("melee_attack_stun_seconds")) {
            ReadFloatArray(combat["melee_attack_stun_seconds"], settings.melee_attack_stun_seconds);
        }
    }
    if (root.contains("wounds") && root["wounds"].is_object()) {
        const Json& wounds = root["wounds"];
        settings.melee_wound_gain = wounds.value("melee_wound_gain", settings.melee_wound_gain);
        settings.wound_threshold = wounds.value("wound_threshold", settings.wound_threshold);
        settings.wound_decay_per_second = wounds.value(
            "wound_decay_per_second", settings.wound_decay_per_second);
        settings.leg_agonising_seconds = wounds.value(
            "leg_agonising_seconds", settings.leg_agonising_seconds);
        settings.torso_agonising_seconds = wounds.value(
            "torso_agonising_seconds", settings.torso_agonising_seconds);
        settings.head_passed_out_seconds = wounds.value(
            "head_passed_out_seconds", settings.head_passed_out_seconds);
    }
    ClampSettings(settings);
    error.clear();
    return true;
}

bool SaveControlSettings(const std::string& path, const ControlSettings& settings, std::string& error) {
    std::error_code directory_error;
    const std::filesystem::path output_path(path);
    std::filesystem::create_directories(output_path.parent_path(), directory_error);
    if (directory_error) {
        error = "Could not create the options directory.";
        return false;
    }

    ControlSettings clamped = settings;
    ClampSettings(clamped);
    std::ofstream output(output_path, std::ios::trunc);
    if (!output) {
        error = "Could not write options: " + path;
        return false;
    }
    output << Json{
        {"simulation", {
            {"seed", clamped.seed},
            {"hero_agent_count", clamped.hero_agent_count},
            {"villain_agent_count", clamped.villain_agent_count},
        }},
        {"camera", {
            {"look_sensitivity", clamped.look_sensitivity},
            {"pan_sensitivity", clamped.pan_sensitivity},
            {"flight_speed", clamped.flight_speed},
            {"zoom_sensitivity", clamped.zoom_sensitivity},
        }},
        {"transport", {
            {"arrow_repeat_ticks_per_second", clamped.arrow_repeat_ticks_per_second},
        }},
        {"look", {
            {"head_turn_speed_degrees_per_second",
                clamped.head_turn_speed_degrees_per_second},
        }},
        {"perception", {
            {"proximity_threat_range_m", clamped.proximity_threat_range_m},
            {"vision_range_m", clamped.vision_range_m},
            {"head_vision_angle_degrees", clamped.head_vision_angle_degrees},
            {"sound_maximum_range_m", clamped.sound_maximum_range_m},
            {"running_sound_toward_leeway_degrees",
                clamped.running_sound_toward_leeway_degrees},
            {"non_threatening_minimum_seconds",
                clamped.non_threatening_minimum_seconds},
            {"non_threatening_maximum_seconds",
                clamped.non_threatening_maximum_seconds},
            {"follow_walk_distance_m", clamped.follow_walk_distance_m},
            {"follow_stop_distance_m", clamped.follow_stop_distance_m},
        }},
        {"visualization", {
            {"sound_events", clamped.sound_visualization},
        }},
        {"tactics", {
            {"target_commitment_seconds", clamped.target_commitment_seconds},
            {"sector_influence_distance_m", clamped.sector_influence_distance_m},
            {"sector_angle_variation_degrees", clamped.sector_angle_variation_degrees},
            {"sector_radius_variation_m", clamped.sector_radius_variation_m},
            {"ally_spacing_distance_m", clamped.ally_spacing_distance_m},
        }},
        {"combat", {
            {"attack_cooldown_seconds", clamped.attack_cooldown_seconds},
            {"parried_attack_cooldown_seconds", clamped.parried_attack_cooldown_seconds},
            {"parry_probability", clamped.parry_probability},
            {"sword_attack_stun_seconds", clamped.sword_attack_stun_seconds},
            {"melee_attack_stun_seconds", clamped.melee_attack_stun_seconds},
        }},
        {"wounds", {
            {"melee_wound_gain", clamped.melee_wound_gain},
            {"wound_threshold", clamped.wound_threshold},
            {"wound_decay_per_second", clamped.wound_decay_per_second},
            {"leg_agonising_seconds", clamped.leg_agonising_seconds},
            {"torso_agonising_seconds", clamped.torso_agonising_seconds},
            {"head_passed_out_seconds", clamped.head_passed_out_seconds},
        }},
    }.dump(2) << '\n';
    if (!output) {
        error = "Writing options failed: " + path;
        return false;
    }
    error.clear();
    return true;
}

bool LoadOpeningLayout(const std::string& path, OpeningLayout& layout, std::string& error) {
    layout = {};
    if (!std::filesystem::exists(path)) {
        error.clear();
        return true;
    }
    std::ifstream input(path);
    if (!input) {
        error = "Could not open opening layout: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object() || !root.contains("heroes") ||
        !root.contains("villains") || !ReadSavedTransforms(root["heroes"], layout.heroes) ||
        !ReadSavedTransforms(root["villains"], layout.villains)) {
        layout = {};
        error = "Opening layout JSON is invalid: " + path;
        return false;
    }
    error.clear();
    return true;
}

bool SaveOpeningLayout(const std::string& path, const OpeningLayout& layout, std::string& error) {
    if (layout.heroes.size() > kMaxTeamAgentCount ||
        layout.villains.size() > kMaxTeamAgentCount) {
        error = "Opening layout must contain zero through 100 agents per team.";
        return false;
    }
    std::error_code directory_error;
    const std::filesystem::path output_path(path);
    std::filesystem::create_directories(output_path.parent_path(), directory_error);
    if (directory_error) {
        error = "Could not create the opening layout directory.";
        return false;
    }
    std::ofstream output(output_path, std::ios::trunc);
    if (!output) {
        error = "Could not write opening layout: " + path;
        return false;
    }
    output << Json{
        {"version", 1},
        {"heroes", WriteSavedTransforms(layout.heroes)},
        {"villains", WriteSavedTransforms(layout.villains)},
    }.dump(2) << '\n';
    if (!output) {
        error = "Writing opening layout failed: " + path;
        return false;
    }
    error.clear();
    return true;
}

std::vector<::prophecy::sim::AgentTransform> BuildOpeningTransforms(OpeningLayout& layout,
    std::uint32_t hero_count, std::uint32_t villain_count, std::uint64_t seed,
    bool& expanded) {
    expanded = false;
    hero_count = std::clamp(hero_count, kMinTeamAgentCount, kMaxTeamAgentCount);
    villain_count = std::clamp(villain_count, kMinTeamAgentCount, kMaxTeamAgentCount);
    if (hero_count == 0U && villain_count == 0U) return {};

    const SavedAgentTransform* first = !layout.heroes.empty()
        ? &layout.heroes.front()
        : (!layout.villains.empty() ? &layout.villains.front() : nullptr);
    if (first == nullptr) return {};

    float minimum_x = first->x;
    float maximum_x = minimum_x;
    float minimum_z = first->z;
    float maximum_z = minimum_z;
    const auto include_bounds = [&](const std::vector<SavedAgentTransform>& transforms) {
        for (const SavedAgentTransform& transform : transforms) {
            minimum_x = std::min(minimum_x, transform.x);
            maximum_x = std::max(maximum_x, transform.x);
            minimum_z = std::min(minimum_z, transform.z);
            maximum_z = std::max(maximum_z, transform.z);
        }
    };
    include_bounds(layout.heroes);
    include_bounds(layout.villains);

    const auto expand_team = [&](std::vector<SavedAgentTransform>& transforms,
                                 std::uint32_t count, std::uint64_t team_salt,
                                 float default_facing_radians) {
        const std::size_t source_count = transforms.size();
        while (transforms.size() < count) {
            const std::uint64_t index = transforms.size();
            const float x_alpha = UnitRandom(seed ^ team_salt ^ (index * 0x9e3779b97f4a7c15ULL));
            const float z_alpha = UnitRandom(seed ^ team_salt ^ (index * 0xbf58476d1ce4e5b9ULL));
            transforms.push_back({
                minimum_x + (maximum_x - minimum_x) * x_alpha,
                minimum_z + (maximum_z - minimum_z) * z_alpha,
                source_count > 0U
                    ? transforms[index % source_count].facing_radians
                    : default_facing_radians,
            });
            expanded = true;
        }
    };
    expand_team(layout.heroes, hero_count, 0x4845524f4c41594fULL, 1.5707963f);
    expand_team(layout.villains, villain_count, 0x56494c4c4c41594fULL, -1.5707963f);

    std::vector<::prophecy::sim::AgentTransform> output;
    output.reserve(static_cast<std::size_t>(hero_count) + villain_count);
    const auto append_team = [&](const std::vector<SavedAgentTransform>& transforms,
                                 std::uint32_t count) {
        for (std::uint32_t index = 0; index < count; ++index) {
            const SavedAgentTransform& transform = transforms[index];
            output.push_back({static_cast<::prophecy::sim::EntityId>(output.size() + 1U),
                {transform.x, transform.z, 0.0f}, transform.facing_radians});
        }
    };
    append_team(layout.heroes, hero_count);
    append_team(layout.villains, villain_count);
    return output;
}

}  // namespace prophecy::viewer
