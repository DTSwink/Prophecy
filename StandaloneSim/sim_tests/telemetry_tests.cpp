#include "telemetry.h"

#include <nlohmann/json.hpp>

#include <cstdio>
#include <cstdlib>

int main() {
    namespace sim = ::prophecy::sim;
    namespace viewer = ::prophecy::viewer;
    sim::Simulation simulation({}, 99);
    const sim::StickId stick_id = simulation.SpawnStick({-2.5f, 0.0f, 0.0f}, 0.0f);
    (void)simulation.RequestPickUpStick(1U, stick_id);
    for (int tick = 0; tick < 17; ++tick) simulation.Tick();
    viewer::TelemetryViewState view{};
    view.paused = true;
    view.render_fps = 60;
    view.rewind_head_tick = 17;
    view.selected_agent_id = 1;
    const nlohmann::json root = nlohmann::json::parse(
        viewer::SerializeTelemetrySnapshot("test", simulation.Snapshot(), simulation.Config(), view));
    const bool valid = root.value("schema", "") == "prophecy.locomotion-sim.snapshot.v1" &&
        root["simulation"]["tick"] == 17U && root["simulation"]["agent_count"] == 2U &&
        root["viewer"]["paused"] == true && root["viewer"]["selected_agent_id"] == 1U &&
        root["agents"].size() == 2U &&
        root["agents"][0].contains("id") && root["agents"][0].contains("position") &&
        root["agents"][0].contains("facing_radians") && root["agents"][0].contains("team") &&
        root["agents"][0]["equipment"]["sword_equipped"] == true &&
        root["agents"][0]["equipment"].contains("sword_state") &&
        root["agents"][0]["equipment"].contains("held_weapon") &&
        root["agents"][0]["equipment"]["held_stick_id"] == 0U &&
        root["agents"][0]["equipment"].contains("dropped_sword_position") &&
        root["agents"][0]["behavior"]["mode"] == "attack" &&
        root["agents"][0]["behavior"]["attack_target_id"] == 2U &&
        root["agents"][0]["behavior"].contains("follow_target_id") &&
        root["agents"][0]["behavior"].contains("draw_retreat_target_id") &&
        root["agents"][0]["behavior"].contains("target_distance_m") &&
        root["agents"][0]["behavior"].contains("completed_attacks") &&
        root["agents"][0]["behavior"].contains("attack_cooldown_seconds_remaining") &&
        root["agents"][0]["behavior"].contains("cooldown_strafe") &&
        root["agents"][0]["behavior"].contains("cooldown_strafe_direction") &&
        root["agents"][0]["behavior"].contains("cooldown_strafe_target_distance_m") &&
        root["agents"][0]["behavior"].contains("cooldown_strafe_distance_remaining_m") &&
        root["agents"][0]["behavior"].contains("state") &&
        root["agents"][0]["behavior"].contains("state_seconds_remaining") &&
        root["agents"][0]["combat_context"].contains("committed_attacker_count") &&
        root["agents"][0]["combat_context"].contains("active_attacker_count") &&
        root["agents"][0]["combat_context"].contains("allies_attacking_target") &&
        root["agents"][0]["combat_context"]["committed_attacker_ids"].is_array() &&
        root["agents"][0]["combat_context"]["active_attacker_ids"].is_array() &&
        root["agents"][0]["perception"].contains("recognized_threat_count") &&
        root["agents"][0]["perception"].contains("active_threat_count") &&
        root["agents"][0]["perception"].contains("finishing_target_count") &&
        root["agents"][0]["perception"].contains("proximity_threat_count") &&
        root["agents"][0]["perception"].contains("visible_threat_count") &&
        root["agents"][0]["perception"]["active_threat_ids"].is_array() &&
        root["agents"][0]["perception"]["finishing_target_ids"].is_array() &&
        root["agents"][0]["perception"].contains("sound_investigation_source_id") &&
        root["agents"][0]["perception"].contains("non_threatening_source_count") &&
        root["agents"][0]["perception"].contains("scanning") &&
        root["agents"][0]["tactical_steering"].contains("mode") &&
        root["agents"][0]["tactical_steering"].contains("threat_count") &&
        root["agents"][0]["tactical_steering"].contains("threat_arc_radians") &&
        root["agents"][0]["tactical_steering"].contains("nearest_peer_separation_radians") &&
        root["agents"][0]["tactical_steering"].contains("view_center_yaw_radians") &&
        root["agents"][0]["tactical_steering"].contains("move_yaw_radians") &&
        root["agents"][0]["tactical_steering"].contains("sector_target_id") &&
        root["agents"][0]["tactical_steering"].contains("sector_index") &&
        root["agents"][0]["tactical_steering"].contains("sector_yaw_radians") &&
        root["agents"][0]["tactical_steering"].contains("sector_radius_m") &&
        root["agents"][0]["tactical_steering"].contains("sector_error_radians") &&
        root["agents"][0]["tactical_steering"].contains("sector_influence") &&
        root["agents"][0]["tactical_steering"].contains(
            "target_commitment_seconds_remaining") &&
        root["agents"][0]["look"]["mode"] == "combat" &&
        root["agents"][0]["look"]["target_id"] == 2U &&
        root["agents"][0]["look"].contains("yaw_radians") &&
        root["agents"][0]["look"].contains("pitch_radians") &&
        root["agents"][0]["wounds"].size() == sim::kLimbCount &&
        root["agents"][0]["wounds"]["head"].contains("gauge_percent") &&
        root["agents"][0]["wounds"]["head"].contains("condition") &&
        root["agents"][0]["wounds"]["right_leg"].contains("injured") &&
        root["agents"][0]["wounds"]["right_leg"].contains("badly_injured") &&
        root["agents"][0]["action"].contains("phase") &&
        root["agents"][0]["action"].contains("weapon") &&
        root["agents"][0]["action"]["target_stick_id"] == stick_id &&
        root["agents"][0]["action"].contains("target_position") &&
        root["agents"][0]["action"].contains("progress") &&
        root["agents"][0]["action"].contains("duration_seconds") &&
        root["agents"][0]["action"].contains("stun_duration_seconds") &&
        root["agents"][0]["action"].contains("animation_index") &&
        root["agents"][0]["action"].contains("parried") &&
        root["agents"][0]["reaction"].contains("kind") &&
        root["agents"][0]["reaction"].contains("duration_seconds") &&
        root["simulation"]["mode"] == "autonomous" &&
        root["simulation"]["hero_agent_count"] == 1U &&
        root["simulation"]["villain_agent_count"] == 1U &&
        root["simulation"]["attack_cooldown_seconds"] == 1.0f &&
        root["simulation"]["parried_attack_cooldown_seconds"] == 1.5f &&
        root["simulation"]["hit_probability"] == 0.2f &&
        root["simulation"]["parry_probability"] == 0.5f &&
        root["simulation"]["stick_pickup_action_seconds"] == 1.0f &&
        root["simulation"]["stick_drop_action_seconds"] == 0.1f &&
        root["simulation"]["head_velocity_threshold_mps"] == 0.5f &&
        root["simulation"]["head_turn_speed_degrees_per_second"] == 360.0f &&
        root["simulation"]["proximity_threat_range_m"] == 3.0f &&
        root["simulation"]["vision_range_m"] == 100.0f &&
        root["simulation"]["head_vision_angle_degrees"] == 180.0f &&
        root["simulation"]["running_sound_toward_leeway_degrees"] == 15.0f &&
        root["simulation"]["non_threatening_minimum_seconds"] == 30.0f &&
        root["simulation"]["non_threatening_maximum_seconds"] == 40.0f &&
        root["simulation"]["follow_walk_distance_m"] == 7.0f &&
        root["simulation"]["follow_stop_distance_m"] == 2.0f &&
        root["simulation"]["target_assignment_rate_hz"] == 5.0f &&
        root["simulation"]["approach_sector_count"] == sim::kApproachSectorCount &&
        root["simulation"]["target_commitment_seconds"] == 1.5f &&
        root["simulation"]["sector_influence_distance_m"] == 30.0f &&
        root["simulation"]["sector_angle_variation_degrees"] == 12.0f &&
        root["simulation"]["sector_radius_variation_m"] == 0.15f &&
        root["simulation"]["ally_spacing_distance_m"] == 2.0f &&
        root["simulation"]["grunt_propagation_agent_limit"] == 5U &&
        root["simulation"].contains("head_yaw_limit_radians") &&
        root["simulation"].contains("head_pitch_limit_radians") &&
        root["simulation"].contains("outnumbered_view_cone_radians") &&
        root["simulation"].contains("attacker_separation_radians") &&
        root["simulation"]["sword_attack_stun_seconds"].size() ==
            sim::kSwordAttackClipCount &&
        root["simulation"]["melee_attack_stun_seconds"].size() ==
            sim::kMeleeAttackClipCount &&
        root["simulation"]["sword_attack_stun_seconds"][0] == 0.5f &&
        root["simulation"]["melee_attack_stun_seconds"][0] == 0.5f &&
        root["simulation"]["melee_wound_gain"] == 20.0f &&
        root["simulation"]["wound_threshold"] == 100.0f &&
        root["simulation"]["wound_decay_per_second"] == 1.0f &&
        root["simulation"]["leg_agonising_seconds"] == 3.0f &&
        root["simulation"]["torso_agonising_seconds"] == 10.0f &&
        root["simulation"]["head_passed_out_seconds"] == 30.0f &&
        root["sound"]["locomotion_interval_seconds"] == 0.2f &&
        root["sound"]["maximum_range_m"] == 3.0f &&
        root["sound"]["propagation_mps"] == 1.0f &&
        root["sound"]["run_reference_speed_mps"] == 5.0f &&
        root["sound"]["events"].is_array() &&
        !root["sound"]["events"].empty() &&
        root["sound"]["events"][0].contains("recipient_count") &&
        root["sticks"].size() == 1U && root["sticks"][0]["id"] == stick_id &&
        root["sticks"][0]["holder_id"] == 0U &&
        root["agents"][0]["locomotion"]["future_roots"].size() == sim::kFutureRootWindow &&
        root["agents"][0]["locomotion"].contains("speed_stick_amplitude") &&
        !root.contains("battle_tuning");
    if (!valid) {
        std::fprintf(stderr, "FAIL: simulation telemetry schema is incomplete\n");
        return EXIT_FAILURE;
    }
    std::printf("Locomotion telemetry serialization test passed.\n");
    return EXIT_SUCCESS;
}
