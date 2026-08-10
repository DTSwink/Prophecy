#include "control_settings.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <cstdio>
#include <cstdlib>
#include <limits>

namespace {

namespace viewer = ::prophecy::viewer;

bool Equal(const viewer::ControlSettings& left, const viewer::ControlSettings& right) {
    return left.seed == right.seed &&
        left.hero_agent_count == right.hero_agent_count &&
        left.villain_agent_count == right.villain_agent_count &&
        left.look_sensitivity == right.look_sensitivity &&
        left.pan_sensitivity == right.pan_sensitivity &&
        left.flight_speed == right.flight_speed &&
        left.zoom_sensitivity == right.zoom_sensitivity &&
        left.arrow_repeat_ticks_per_second == right.arrow_repeat_ticks_per_second &&
        left.head_turn_speed_degrees_per_second == right.head_turn_speed_degrees_per_second &&
        left.proximity_threat_range_m == right.proximity_threat_range_m &&
        left.vision_range_m == right.vision_range_m &&
        left.head_vision_angle_degrees == right.head_vision_angle_degrees &&
        left.sound_maximum_range_m == right.sound_maximum_range_m &&
        left.running_sound_toward_leeway_degrees ==
            right.running_sound_toward_leeway_degrees &&
        left.non_threatening_minimum_seconds == right.non_threatening_minimum_seconds &&
        left.non_threatening_maximum_seconds == right.non_threatening_maximum_seconds &&
        left.follow_walk_distance_m == right.follow_walk_distance_m &&
        left.follow_stop_distance_m == right.follow_stop_distance_m &&
        left.target_commitment_seconds == right.target_commitment_seconds &&
        left.sector_influence_distance_m == right.sector_influence_distance_m &&
        left.containment_early_influence == right.containment_early_influence &&
        left.sector_angle_variation_degrees == right.sector_angle_variation_degrees &&
        left.sector_radius_variation_m == right.sector_radius_variation_m &&
        left.ally_spacing_distance_m == right.ally_spacing_distance_m &&
        left.crawl_speed_scale == right.crawl_speed_scale &&
        left.crawl_turn_scale == right.crawl_turn_scale &&
        left.sound_visualization == right.sound_visualization &&
        left.xray_agents == right.xray_agents &&
        left.attack_cooldown_seconds == right.attack_cooldown_seconds &&
        left.parried_attack_cooldown_seconds == right.parried_attack_cooldown_seconds &&
        left.attack_followup_probability == right.attack_followup_probability &&
        left.drawn_sword_attack_probability == right.drawn_sword_attack_probability &&
        left.parry_probability == right.parry_probability &&
        left.sword_attack_stun_seconds == right.sword_attack_stun_seconds &&
        left.melee_attack_stun_seconds == right.melee_attack_stun_seconds &&
        left.melee_wound_gain == right.melee_wound_gain &&
        left.wound_threshold == right.wound_threshold &&
        left.wound_decay_per_second == right.wound_decay_per_second &&
        left.leg_agonising_seconds == right.leg_agonising_seconds &&
        left.torso_agonising_seconds == right.torso_agonising_seconds &&
        left.head_passed_out_seconds == right.head_passed_out_seconds;
}

bool Equal(const viewer::OpeningLayout& left, const viewer::OpeningLayout& right) {
    const auto equal_team = [](const std::vector<viewer::SavedAgentTransform>& a,
                               const std::vector<viewer::SavedAgentTransform>& b) {
        if (a.size() != b.size()) return false;
        for (std::size_t index = 0; index < a.size(); ++index) {
            if (a[index].x != b[index].x || a[index].z != b[index].z ||
                a[index].facing_radians != b[index].facing_radians) return false;
        }
        return true;
    };
    return equal_team(left.heroes, right.heroes) && equal_team(left.villains, right.villains);
}

}  // namespace

int main() {
    const std::filesystem::path directory = std::filesystem::temp_directory_path() / "prophecy_neutral_settings_test";
    const std::filesystem::path path = directory / "camera.json";
    std::error_code ignored;
    std::filesystem::remove_all(directory, ignored);

    viewer::ControlSettings expected{};
    expected.seed = std::numeric_limits<std::uint64_t>::max();
    expected.hero_agent_count = 0;
    expected.villain_agent_count = 4;
    expected.look_sensitivity = 0.011f;
    expected.pan_sensitivity = 0.21f;
    expected.flight_speed = 31.0f;
    expected.zoom_sensitivity = 4.5f;
    expected.arrow_repeat_ticks_per_second = 42.0f;
    expected.head_turn_speed_degrees_per_second = 725.0f;
    expected.proximity_threat_range_m = 4.0f;
    expected.vision_range_m = 180.0f;
    expected.head_vision_angle_degrees = 210.0f;
    expected.sound_maximum_range_m = 8.0f;
    expected.running_sound_toward_leeway_degrees = 22.0f;
    expected.non_threatening_minimum_seconds = 25.0f;
    expected.non_threatening_maximum_seconds = 45.0f;
    expected.follow_walk_distance_m = 9.0f;
    expected.follow_stop_distance_m = 3.0f;
    expected.target_commitment_seconds = 2.0f;
    expected.sector_influence_distance_m = 7.0f;
    expected.containment_early_influence = 0.12f;
    expected.sector_angle_variation_degrees = 8.0f;
    expected.sector_radius_variation_m = 0.2f;
    expected.ally_spacing_distance_m = 1.8f;
    expected.crawl_speed_scale = 0.25f;
    expected.crawl_turn_scale = 0.15f;
    expected.sound_visualization = false;
    expected.xray_agents = true;
    expected.attack_cooldown_seconds = 2.0f;
    expected.parried_attack_cooldown_seconds = 3.0f;
    expected.attack_followup_probability = 0.35f;
    expected.drawn_sword_attack_probability = 0.65f;
    expected.parry_probability = 0.65f;
    for (std::size_t index = 0; index < expected.sword_attack_stun_seconds.size(); ++index) {
        expected.sword_attack_stun_seconds[index] = 0.1f * static_cast<float>(index + 1U);
    }
    for (std::size_t index = 0; index < expected.melee_attack_stun_seconds.size(); ++index) {
        expected.melee_attack_stun_seconds[index] = 0.2f * static_cast<float>(index + 1U);
    }
    expected.melee_wound_gain = 25.0f;
    expected.wound_threshold = 90.0f;
    expected.wound_decay_per_second = 2.0f;
    expected.leg_agonising_seconds = 4.0f;
    expected.torso_agonising_seconds = 12.0f;
    expected.head_passed_out_seconds = 35.0f;
    std::string error;
    if (!viewer::SaveControlSettings(path.string(), expected, error)) {
        std::fprintf(stderr, "FAIL: %s\n", error.c_str());
        return EXIT_FAILURE;
    }
    viewer::ControlSettings loaded{};
    if (!viewer::LoadControlSettings(path.string(), loaded, error) || !Equal(expected, loaded)) {
        std::fprintf(stderr, "FAIL: options did not round-trip\n");
        return EXIT_FAILURE;
    }

    std::ofstream(path) << R"({"simulation":{"seed":42,"hero_agent_count":0,"villain_agent_count":1000},"camera":{"look_sensitivity":100,"pan_sensitivity":-1,"flight_speed":500,"zoom_sensitivity":0},"transport":{"arrow_repeat_ticks_per_second":1000},"look":{"head_turn_speed_degrees_per_second":-1},"locomotion":{"crawl_speed_scale":-1,"crawl_turn_scale":2},"perception":{"proximity_threat_range_m":100,"vision_range_m":1000,"head_vision_angle_degrees":1000,"sound_maximum_range_m":100,"running_sound_toward_leeway_degrees":1000,"non_threatening_minimum_seconds":200,"non_threatening_maximum_seconds":-1,"follow_walk_distance_m":100,"follow_stop_distance_m":100},"tactics":{"target_commitment_seconds":100,"sector_influence_distance_m":100,"containment_early_influence":100,"sector_angle_variation_degrees":100,"sector_radius_variation_m":100,"ally_spacing_distance_m":100},"visualization":{"sound_events":false},"combat":{"attack_cooldown_seconds":-1,"parried_attack_cooldown_seconds":10,"attack_followup_probability":-1,"drawn_sword_attack_probability":4,"parry_probability":4,"sword_attack_stun_seconds":[-1,-1,-1,-1,-1,-1,-1],"melee_attack_stun_seconds":[-1,-1,-1,-1,-1,-1,-1,-1,-1]},"wounds":{"melee_wound_gain":-1,"wound_threshold":1000,"wound_decay_per_second":1000,"leg_agonising_seconds":-1,"torso_agonising_seconds":1000,"head_passed_out_seconds":1000}})";
    if (!viewer::LoadControlSettings(path.string(), loaded, error) ||
        loaded.seed != 42U ||
        loaded.hero_agent_count != viewer::kMinTeamAgentCount ||
        loaded.villain_agent_count != viewer::kMaxTeamAgentCount ||
        loaded.look_sensitivity != viewer::kMaxLookSensitivity ||
        loaded.pan_sensitivity != viewer::kMinPanSensitivity ||
        loaded.flight_speed != viewer::kMaxFlightSpeed ||
        loaded.zoom_sensitivity != viewer::kMinZoomSensitivity ||
        loaded.arrow_repeat_ticks_per_second != viewer::kMaxArrowRepeatRate ||
        loaded.head_turn_speed_degrees_per_second != 0.0f ||
        loaded.proximity_threat_range_m != viewer::kMaxProximityThreatRange ||
        loaded.vision_range_m != viewer::kMaxVisionRange ||
        loaded.head_vision_angle_degrees != viewer::kMaxVisionAngleDegrees ||
        loaded.sound_maximum_range_m != viewer::kMaxSoundMaximumRange ||
        loaded.running_sound_toward_leeway_degrees !=
            viewer::kMaxRunningSoundLeewayDegrees ||
        loaded.non_threatening_minimum_seconds != viewer::kMinNonThreateningSeconds ||
        loaded.non_threatening_maximum_seconds != viewer::kMaxNonThreateningSeconds ||
        loaded.follow_walk_distance_m != viewer::kMaxFollowDistance ||
        loaded.follow_stop_distance_m != viewer::kMaxFollowDistance ||
        loaded.target_commitment_seconds != viewer::kMaxTargetCommitmentSeconds ||
        loaded.sector_influence_distance_m != viewer::kMaxSectorInfluenceDistance ||
        loaded.containment_early_influence != viewer::kMaxContainmentEarlyInfluence ||
        loaded.sector_angle_variation_degrees != viewer::kMaxSectorAngleVariationDegrees ||
        loaded.sector_radius_variation_m != viewer::kMaxSectorRadiusVariation ||
        loaded.ally_spacing_distance_m != viewer::kMaxAllySpacingDistance ||
        loaded.crawl_speed_scale != viewer::kMinCrawlScale ||
        loaded.crawl_turn_scale != viewer::kMaxCrawlScale ||
         loaded.sound_visualization != false ||
         loaded.attack_cooldown_seconds != viewer::kMinAttackCooldown ||
         loaded.parried_attack_cooldown_seconds != viewer::kMaxAttackCooldown ||
         loaded.attack_followup_probability != viewer::kMinAttackFollowupProbability ||
         loaded.drawn_sword_attack_probability != viewer::kMaxDrawnSwordAttackProbability ||
         loaded.parry_probability != viewer::kMaxParryProbability ||
        !std::all_of(loaded.sword_attack_stun_seconds.begin(), loaded.sword_attack_stun_seconds.end(),
            [](float seconds) { return seconds == 0.0f; }) ||
        !std::all_of(loaded.melee_attack_stun_seconds.begin(), loaded.melee_attack_stun_seconds.end(),
            [](float seconds) { return seconds == 0.0f; }) ||
        loaded.melee_wound_gain != viewer::kMinMeleeWoundGain ||
        loaded.wound_threshold != viewer::kMaxWoundThreshold ||
        loaded.wound_decay_per_second != viewer::kMaxWoundDecay ||
        loaded.leg_agonising_seconds != viewer::kMinWoundStateSeconds ||
        loaded.torso_agonising_seconds != viewer::kMaxWoundStateSeconds ||
        loaded.head_passed_out_seconds != viewer::kMaxWoundStateSeconds) {
        std::fprintf(stderr, "FAIL: options were not clamped\n");
        return EXIT_FAILURE;
    }

    std::ofstream(path) << R"({"combat":{"sword_attack_stun_seconds":[0.1,0.2,0.3,0.4,0.5,0.6]}})";
    viewer::ControlSettings upgraded{};
    if (!viewer::LoadControlSettings(path.string(), upgraded, error) ||
        upgraded.sword_attack_stun_seconds[0] != 0.1f ||
        upgraded.sword_attack_stun_seconds[1] != 0.2f ||
        upgraded.sword_attack_stun_seconds[2] != 0.3f ||
        upgraded.sword_attack_stun_seconds[3] != 0.4f ||
        upgraded.sword_attack_stun_seconds[4] != 0.5f ||
        upgraded.sword_attack_stun_seconds[5] != 0.6f ||
        upgraded.sword_attack_stun_seconds[6] != 0.5f) {
        std::fprintf(stderr, "FAIL: six-clip settings did not preserve existing values and default pike\n");
        return EXIT_FAILURE;
    }

    const std::filesystem::path layout_path = directory / "opening-layout.json";
    viewer::OpeningLayout expected_layout{};
    expected_layout.heroes = {{-2.0f, 0.0f, 1.0f}};
    expected_layout.villains = {{2.0f, -3.0f, -1.0f}, {2.0f, 3.0f, -1.0f}};
    if (!viewer::SaveOpeningLayout(layout_path.string(), expected_layout, error)) {
        std::fprintf(stderr, "FAIL: %s\n", error.c_str());
        return EXIT_FAILURE;
    }
    viewer::OpeningLayout loaded_layout{};
    if (!viewer::LoadOpeningLayout(layout_path.string(), loaded_layout, error) ||
        !Equal(expected_layout, loaded_layout)) {
        std::fprintf(stderr, "FAIL: opening layout did not round-trip\n");
        return EXIT_FAILURE;
    }
    viewer::OpeningLayout repeated_layout = loaded_layout;
    bool expanded = false;
    const std::vector<::prophecy::sim::AgentTransform> expanded_transforms =
        viewer::BuildOpeningTransforms(loaded_layout, 3U, 4U, 77U, expanded);
    bool repeated_expanded = false;
    const std::vector<::prophecy::sim::AgentTransform> repeated_transforms =
        viewer::BuildOpeningTransforms(repeated_layout, 3U, 4U, 77U, repeated_expanded);
    if (!expanded || !repeated_expanded || loaded_layout.heroes.size() != 3U ||
        loaded_layout.villains.size() != 4U || expanded_transforms.size() != 7U ||
        repeated_transforms.size() != expanded_transforms.size()) {
        std::fprintf(stderr, "FAIL: opening layout did not expand to requested team counts\n");
        return EXIT_FAILURE;
    }
    for (std::size_t index = 0; index < expanded_transforms.size(); ++index) {
        const auto& current = expanded_transforms[index];
        const auto& repeated = repeated_transforms[index];
        if (current.id != index + 1U || current.position.x != repeated.position.x ||
            current.position.y != repeated.position.y ||
            current.facing_radians != repeated.facing_radians ||
            current.position.x < -2.0f || current.position.x > 2.0f ||
            current.position.y < -3.0f || current.position.y > 3.0f) {
            std::fprintf(stderr, "FAIL: opening layout expansion was not deterministic inside its blob\n");
            return EXIT_FAILURE;
        }
    }

    viewer::OpeningLayout empty_layout{};
    if (!viewer::SaveOpeningLayout(layout_path.string(), empty_layout, error) ||
        !viewer::LoadOpeningLayout(layout_path.string(), loaded_layout, error) ||
        !loaded_layout.heroes.empty() || !loaded_layout.villains.empty()) {
        std::fprintf(stderr, "FAIL: an empty zero-versus-zero opening layout did not round-trip\n");
        return EXIT_FAILURE;
    }
    bool empty_expanded = false;
    if (!viewer::BuildOpeningTransforms(loaded_layout, 0U, 0U, 77U, empty_expanded).empty() ||
        empty_expanded) {
        std::fprintf(stderr, "FAIL: a zero-versus-zero opening layout produced transforms\n");
        return EXIT_FAILURE;
    }

    viewer::OpeningLayout one_sided_layout{};
    one_sided_layout.villains = {{2.0f, 1.0f, -1.0f}};
    if (!viewer::SaveOpeningLayout(layout_path.string(), one_sided_layout, error) ||
        !viewer::LoadOpeningLayout(layout_path.string(), loaded_layout, error) ||
        !Equal(one_sided_layout, loaded_layout)) {
        std::fprintf(stderr, "FAIL: a zero-versus-one opening layout did not round-trip\n");
        return EXIT_FAILURE;
    }
    bool one_sided_expanded = false;
    const std::vector<::prophecy::sim::AgentTransform> one_sided_transforms =
        viewer::BuildOpeningTransforms(loaded_layout, 2U, 0U, 77U, one_sided_expanded);
    if (!one_sided_expanded || loaded_layout.heroes.size() != 2U ||
        one_sided_transforms.size() != 2U) {
        std::fprintf(stderr, "FAIL: an empty team did not expand from the saved layout blob\n");
        return EXIT_FAILURE;
    }
    std::filesystem::remove_all(directory, ignored);
    std::printf("Options tests passed.\n");
    return EXIT_SUCCESS;
}
