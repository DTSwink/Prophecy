#include "scenario.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <fstream>
#include <utility>

namespace prophecy::viewer {
namespace {

using Json = nlohmann::json;

sim::Vec3 ReadVec3(const Json& value, sim::Vec3 fallback = {}) {
    if (!value.is_array() || value.size() < 3U) return fallback;
    return {
        value[0].is_number() ? value[0].get<float>() : fallback.x,
        value[1].is_number() ? value[1].get<float>() : fallback.y,
        value[2].is_number() ? value[2].get<float>() : fallback.z,
    };
}

Color ReadColor(const Json& value, Color fallback) {
    if (!value.is_array() || value.size() < 3U) return fallback;
    const auto channel = [&value](std::size_t index, unsigned char fallback_value) {
        if (index >= value.size() || !value[index].is_number_integer()) return fallback_value;
        return static_cast<unsigned char>(std::clamp(value[index].get<int>(), 0, 255));
    };
    return {channel(0, fallback.r), channel(1, fallback.g), channel(2, fallback.b), channel(3, fallback.a)};
}

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

}  // namespace

Scenario MakeFallbackScenario() {
    Scenario scenario{};
    scenario.simulation = sim::MakeDefaultConfig();
    scenario.seed = 1337ULL;
    return scenario;
}

bool LoadScenario(const std::string& path, Scenario& scenario, std::string& error) {
    std::ifstream input(path);
    if (!input) {
        error = "Could not open scenario: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object()) {
        error = "Scenario JSON is invalid: " + path;
        return false;
    }

    Scenario loaded = MakeFallbackScenario();
    loaded.name = root.value("name", loaded.name);
    loaded.seed = root.value("seed", loaded.seed);
    if (root.contains("simulation") && root["simulation"].is_object()) {
        const Json& simulation = root["simulation"];
        const bool explicit_team_counts = simulation.contains("hero_agent_count") ||
            simulation.contains("villain_agent_count");
        loaded.simulation.hero_agent_count = simulation.value(
            "hero_agent_count", loaded.simulation.hero_agent_count);
        loaded.simulation.villain_agent_count = simulation.value(
            "villain_agent_count", loaded.simulation.villain_agent_count);
        if (!explicit_team_counts && simulation.contains("agent_count")) {
            const std::uint32_t total = std::max(2U, simulation.value("agent_count", 2U));
            loaded.simulation.hero_agent_count = total / 2U;
            loaded.simulation.villain_agent_count = total - loaded.simulation.hero_agent_count;
        }
        loaded.simulation.agent_count = loaded.simulation.hero_agent_count +
            loaded.simulation.villain_agent_count;
        loaded.simulation.tick_rate_hz = simulation.value("tick_rate_hz", loaded.simulation.tick_rate_hz);
        const std::string mode = simulation.value("mode", std::string(sim::ToString(loaded.simulation.mode)));
        loaded.simulation.mode = mode == "paired" ? sim::SimulationMode::Paired : sim::SimulationMode::Autonomous;
        loaded.simulation.sheathe_action_seconds = simulation.value(
            "sheathe_action_seconds", loaded.simulation.sheathe_action_seconds);
        loaded.simulation.unsheathe_action_seconds = simulation.value(
            "unsheathe_action_seconds", loaded.simulation.unsheathe_action_seconds);
        loaded.simulation.stick_pickup_action_seconds = simulation.value(
            "stick_pickup_action_seconds", loaded.simulation.stick_pickup_action_seconds);
        loaded.simulation.stick_drop_action_seconds = simulation.value(
            "stick_drop_action_seconds", loaded.simulation.stick_drop_action_seconds);
        loaded.simulation.attack_range_m = simulation.value(
            "attack_range_m", loaded.simulation.attack_range_m);
        loaded.simulation.attack_cooldown_seconds = simulation.value(
            "attack_cooldown_seconds", loaded.simulation.attack_cooldown_seconds);
        loaded.simulation.parried_attack_cooldown_seconds = simulation.value(
            "parried_attack_cooldown_seconds", loaded.simulation.parried_attack_cooldown_seconds);
        loaded.simulation.hit_probability = simulation.value(
            "hit_probability", loaded.simulation.hit_probability);
        loaded.simulation.parry_probability = simulation.value(
            "parry_probability", loaded.simulation.parry_probability);
        loaded.simulation.head_turn_speed_degrees_per_second = simulation.value(
            "head_turn_speed_degrees_per_second",
            loaded.simulation.head_turn_speed_degrees_per_second);
        loaded.simulation.proximity_threat_range_m = simulation.value(
            "proximity_threat_range_m", loaded.simulation.proximity_threat_range_m);
        loaded.simulation.vision_range_m = simulation.value(
            "vision_range_m", loaded.simulation.vision_range_m);
        loaded.simulation.head_vision_angle_degrees = simulation.value(
            "head_vision_angle_degrees", loaded.simulation.head_vision_angle_degrees);
        loaded.simulation.sound_maximum_range_m = simulation.value(
            "sound_maximum_range_m", loaded.simulation.sound_maximum_range_m);
        loaded.simulation.running_sound_toward_leeway_degrees = simulation.value(
            "running_sound_toward_leeway_degrees",
            loaded.simulation.running_sound_toward_leeway_degrees);
        loaded.simulation.non_threatening_minimum_seconds = simulation.value(
            "non_threatening_minimum_seconds",
            loaded.simulation.non_threatening_minimum_seconds);
        loaded.simulation.non_threatening_maximum_seconds = simulation.value(
            "non_threatening_maximum_seconds",
            loaded.simulation.non_threatening_maximum_seconds);
        loaded.simulation.follow_walk_distance_m = simulation.value(
            "follow_walk_distance_m", loaded.simulation.follow_walk_distance_m);
        loaded.simulation.follow_stop_distance_m = simulation.value(
            "follow_stop_distance_m", loaded.simulation.follow_stop_distance_m);
        loaded.simulation.target_commitment_seconds = simulation.value(
            "target_commitment_seconds", loaded.simulation.target_commitment_seconds);
        loaded.simulation.sector_influence_distance_m = simulation.value(
            "sector_influence_distance_m", loaded.simulation.sector_influence_distance_m);
        loaded.simulation.sector_angle_variation_degrees = simulation.value(
            "sector_angle_variation_degrees",
            loaded.simulation.sector_angle_variation_degrees);
        loaded.simulation.sector_radius_variation_m = simulation.value(
            "sector_radius_variation_m", loaded.simulation.sector_radius_variation_m);
        loaded.simulation.ally_spacing_distance_m = simulation.value(
            "ally_spacing_distance_m", loaded.simulation.ally_spacing_distance_m);
        if (simulation.contains("sword_attack_stun_seconds")) {
            ReadFloatArray(simulation["sword_attack_stun_seconds"],
                loaded.simulation.sword_attack_stun_seconds);
        }
        if (simulation.contains("melee_attack_stun_seconds")) {
            ReadFloatArray(simulation["melee_attack_stun_seconds"],
                loaded.simulation.melee_attack_stun_seconds);
        }
        loaded.simulation.melee_wound_gain = simulation.value(
            "melee_wound_gain", loaded.simulation.melee_wound_gain);
        loaded.simulation.wound_threshold = simulation.value(
            "wound_threshold", loaded.simulation.wound_threshold);
        loaded.simulation.wound_decay_per_second = simulation.value(
            "wound_decay_per_second", loaded.simulation.wound_decay_per_second);
        loaded.simulation.leg_agonising_seconds = simulation.value(
            "leg_agonising_seconds", loaded.simulation.leg_agonising_seconds);
        loaded.simulation.torso_agonising_seconds = simulation.value(
            "torso_agonising_seconds", loaded.simulation.torso_agonising_seconds);
        loaded.simulation.head_passed_out_seconds = simulation.value(
            "head_passed_out_seconds", loaded.simulation.head_passed_out_seconds);
        if (simulation.contains("world_min")) loaded.simulation.world_min = ReadVec3(simulation["world_min"], loaded.simulation.world_min);
        if (simulation.contains("world_max")) loaded.simulation.world_max = ReadVec3(simulation["world_max"], loaded.simulation.world_max);
        if (simulation.contains("initial_sticks") && simulation["initial_sticks"].is_array()) {
            for (const Json& entry : simulation["initial_sticks"]) {
                if (!entry.is_object() ||
                    loaded.simulation.initial_sticks.size() >= sim::kMaxSimulationStickCount) continue;
                sim::StickTransform transform{};
                if (entry.contains("position")) {
                    transform.position = ReadVec3(entry["position"]);
                }
                transform.facing_radians = entry.value("facing_radians", 0.0f);
                loaded.simulation.initial_sticks.push_back(transform);
            }
        }
    }
    if (root.contains("atmosphere") && root["atmosphere"].is_object()) {
        const Json& atmosphere = root["atmosphere"];
        if (atmosphere.contains("sky_color")) loaded.sky_color = ReadColor(atmosphere["sky_color"], loaded.sky_color);
        if (atmosphere.contains("ground_color")) loaded.ground_color = ReadColor(atmosphere["ground_color"], loaded.ground_color);
        if (atmosphere.contains("grid_color")) loaded.grid_color = ReadColor(atmosphere["grid_color"], loaded.grid_color);
    }
    if (root.contains("camera") && root["camera"].is_object()) {
        const Json& camera = root["camera"];
        if (camera.contains("focus")) loaded.camera_focus = ReadVec3(camera["focus"], loaded.camera_focus);
        loaded.camera_distance = camera.value("distance", loaded.camera_distance);
        loaded.camera_yaw = camera.value("yaw", loaded.camera_yaw);
        loaded.camera_pitch = camera.value("pitch", loaded.camera_pitch);
    }
    scenario = std::move(loaded);
    error.clear();
    return true;
}

}  // namespace prophecy::viewer
