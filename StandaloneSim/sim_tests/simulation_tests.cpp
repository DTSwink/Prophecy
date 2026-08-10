#include "prophecy/sim/simulation.h"

#include <algorithm>
#include <array>
#include <bitset>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>
#include <string_view>
#include <vector>

namespace {

namespace sim = ::prophecy::sim;
int failures = 0;

void Check(bool condition, const char* message) {
    if (condition) return;
    std::fprintf(stderr, "FAIL: %s\n", message);
    ++failures;
}

bool EqualAgent(const sim::AgentSnapshot& a, const sim::AgentSnapshot& b) {
    if (a.id != b.id || a.team != b.team || a.position.x != b.position.x ||
        a.position.y != b.position.y || a.position.z != b.position.z ||
        a.facing_radians != b.facing_radians || a.locomotion_mode != b.locomotion_mode ||
        a.locomotion_response != b.locomotion_response || a.root_velocity.x != b.root_velocity.x ||
        a.root_velocity.y != b.root_velocity.y || a.root_velocity.z != b.root_velocity.z ||
        a.root_speed_mps != b.root_speed_mps ||
        a.speed_stick_direction_radians != b.speed_stick_direction_radians ||
        a.speed_stick_amplitude != b.speed_stick_amplitude ||
        a.orientation_stick_yaw_radians != b.orientation_stick_yaw_radians ||
        a.pose_phase != b.pose_phase || a.sword_equipped != b.sword_equipped ||
        a.sword_state != b.sword_state || a.held_weapon != b.held_weapon ||
        a.held_stick_id != b.held_stick_id ||
        a.dropped_sword_position.x != b.dropped_sword_position.x ||
        a.dropped_sword_position.y != b.dropped_sword_position.y ||
        a.dropped_sword_position.z != b.dropped_sword_position.z ||
        a.dropped_sword_yaw_radians != b.dropped_sword_yaw_radians ||
        a.action.sequence != b.action.sequence ||
        a.action.kind != b.action.kind || a.action.phase != b.action.phase ||
        a.action.hands != b.action.hands || a.action.weapon != b.action.weapon ||
        a.action.target_stick_id != b.action.target_stick_id ||
        a.action.target_position.x != b.action.target_position.x ||
        a.action.target_position.y != b.action.target_position.y ||
        a.action.target_position.z != b.action.target_position.z ||
        a.action.elapsed_seconds != b.action.elapsed_seconds ||
        a.action.duration_seconds != b.action.duration_seconds ||
        a.action.stun_duration_seconds != b.action.stun_duration_seconds ||
        a.action.progress != b.action.progress ||
        a.action.reach_alpha != b.action.reach_alpha ||
        a.action.animation_index != b.action.animation_index ||
        a.action.parried != b.action.parried ||
        a.action.validation_required != b.action.validation_required ||
        a.reaction.kind != b.reaction.kind ||
        a.reaction.elapsed_seconds != b.reaction.elapsed_seconds ||
        a.reaction.duration_seconds != b.reaction.duration_seconds ||
        a.reaction.progress != b.reaction.progress ||
        a.behavior_mode != b.behavior_mode || a.attack_target_id != b.attack_target_id ||
        a.follow_target_id != b.follow_target_id ||
        a.draw_retreat_target_id != b.draw_retreat_target_id ||
        a.rescue_executioner_id != b.rescue_executioner_id ||
        a.rescue_former_target_id != b.rescue_former_target_id ||
        a.rescue_head_hold_seconds_remaining != b.rescue_head_hold_seconds_remaining ||
        a.target_distance_m != b.target_distance_m || a.completed_attacks != b.completed_attacks ||
        a.attack_cooldown_seconds_remaining != b.attack_cooldown_seconds_remaining ||
        a.cooldown_strafe != b.cooldown_strafe ||
        a.cooldown_strafe_direction != b.cooldown_strafe_direction ||
        a.cooldown_strafe_target_distance_m != b.cooldown_strafe_target_distance_m ||
        a.cooldown_strafe_distance_remaining_m != b.cooldown_strafe_distance_remaining_m ||
        a.head_look_mode != b.head_look_mode ||
        a.head_look_target_id != b.head_look_target_id ||
        a.head_yaw_radians != b.head_yaw_radians ||
        a.head_pitch_radians != b.head_pitch_radians ||
        a.tactical_steering != b.tactical_steering ||
        a.tactical_threat_count != b.tactical_threat_count ||
        a.tactical_containment_influence != b.tactical_containment_influence ||
        a.tactical_threat_arc_radians != b.tactical_threat_arc_radians ||
        a.tactical_nearest_peer_separation_radians != b.tactical_nearest_peer_separation_radians ||
        a.tactical_view_center_yaw_radians != b.tactical_view_center_yaw_radians ||
        a.tactical_move_yaw_radians != b.tactical_move_yaw_radians ||
        a.tactical_sector_target_id != b.tactical_sector_target_id ||
        a.tactical_sector_index != b.tactical_sector_index ||
        a.tactical_sector_yaw_radians != b.tactical_sector_yaw_radians ||
        a.tactical_sector_radius_m != b.tactical_sector_radius_m ||
        a.tactical_sector_error_radians != b.tactical_sector_error_radians ||
        a.tactical_sector_influence != b.tactical_sector_influence ||
        a.target_commitment_seconds_remaining != b.target_commitment_seconds_remaining ||
        a.combat_context.committed_attacker_count != b.combat_context.committed_attacker_count ||
        a.combat_context.active_attacker_count != b.combat_context.active_attacker_count ||
        a.combat_context.allies_attacking_target != b.combat_context.allies_attacking_target ||
        a.combat_context.committed_attacker_ids != b.combat_context.committed_attacker_ids ||
        a.combat_context.active_attacker_ids != b.combat_context.active_attacker_ids ||
        a.combat_context.committed_attacker_id_count != b.combat_context.committed_attacker_id_count ||
        a.combat_context.active_attacker_id_count != b.combat_context.active_attacker_id_count ||
        a.perception.active_threat_count != b.perception.active_threat_count ||
        a.perception.finishing_target_count != b.perception.finishing_target_count ||
        a.perception.recognized_threat_count != b.perception.recognized_threat_count ||
        a.perception.proximity_threat_count != b.perception.proximity_threat_count ||
        a.perception.visible_threat_count != b.perception.visible_threat_count ||
        a.perception.active_threat_ids != b.perception.active_threat_ids ||
        a.perception.finishing_target_ids != b.perception.finishing_target_ids ||
        a.perception.active_threat_id_count != b.perception.active_threat_id_count ||
        a.perception.finishing_target_id_count != b.perception.finishing_target_id_count ||
        a.perception.sound_investigation_source_id !=
            b.perception.sound_investigation_source_id ||
        a.perception.non_threatening_source_count !=
            b.perception.non_threatening_source_count ||
        a.perception.scanning != b.perception.scanning ||
        a.state != b.state || a.state_seconds_remaining != b.state_seconds_remaining) return false;
    for (std::size_t index = 0; index < a.wounds.size(); ++index) {
        if (a.wounds[index].gauge != b.wounds[index].gauge ||
            a.wounds[index].gauge_percent != b.wounds[index].gauge_percent ||
            a.wounds[index].condition != b.wounds[index].condition ||
            a.wounds[index].injured != b.wounds[index].injured ||
            a.wounds[index].badly_injured != b.wounds[index].badly_injured) return false;
    }
    for (std::size_t index = 0; index < a.future_roots.size(); ++index) {
        if (a.future_roots[index].position.x != b.future_roots[index].position.x ||
            a.future_roots[index].position.z != b.future_roots[index].position.z ||
            a.future_roots[index].yaw_radians != b.future_roots[index].yaw_radians) return false;
    }
    return true;
}

bool EqualAgents(const sim::SimulationSnapshot& left, const sim::SimulationSnapshot& right) {
    if (left.agents.size() != right.agents.size()) return false;
    for (std::size_t index = 0; index < left.agents.size(); ++index) {
        if (!EqualAgent(left.agents[index], right.agents[index])) return false;
    }
    if (left.sound_event_count != right.sound_event_count) return false;
    for (std::size_t index = 0; index < left.sound_event_count; ++index) {
        const sim::SoundEventSnapshot& a = left.sound_events[index];
        const sim::SoundEventSnapshot& b = right.sound_events[index];
        if (a.sequence != b.sequence || a.emitted_tick != b.emitted_tick ||
            a.source_id != b.source_id ||
            a.secondary_source_id != b.secondary_source_id || a.kind != b.kind ||
            a.position.x != b.position.x || a.position.y != b.position.y ||
            a.position.z != b.position.z || a.maximum_range_m != b.maximum_range_m ||
            a.recipient_count != b.recipient_count) return false;
    }
    if (left.sticks.size() != right.sticks.size()) return false;
    for (std::size_t index = 0; index < left.sticks.size(); ++index) {
        const sim::StickSnapshot& a = left.sticks[index];
        const sim::StickSnapshot& b = right.sticks[index];
        if (a.id != b.id || a.position.x != b.position.x ||
            a.position.y != b.position.y || a.position.z != b.position.z ||
            a.facing_radians != b.facing_radians || a.holder_id != b.holder_id) return false;
    }
    return true;
}

const sim::SoundEventSnapshot* LatestSound(const sim::SimulationSnapshot& snapshot,
    sim::SoundEventKind kind) {
    for (std::size_t index = snapshot.sound_event_count; index > 0; --index) {
        if (snapshot.sound_events[index - 1U].kind == kind) {
            return &snapshot.sound_events[index - 1U];
        }
    }
    return nullptr;
}

void TestOpeningEncounter() {
    sim::Simulation first({}, 1337);
    sim::Simulation second({}, 1337);
    sim::Simulation different({}, 1338);
    Check(first.Snapshot().agents.size() == 2U, "the default scenario must contain exactly two agents");
    Check(first.Snapshot().agents[0].team == sim::Team::Hero &&
        first.Snapshot().agents[1].team == sim::Team::Villain, "the two agents must be on opposite teams");
    const sim::AgentSnapshot& hero = first.Snapshot().agents[0];
    const sim::AgentSnapshot& villain = first.Snapshot().agents[1];
    Check(std::fabs(hero.position.x + 2.5f) < 1.0e-6f &&
        std::fabs(villain.position.x - 2.5f) < 1.0e-6f &&
        hero.position.y == 0.0f && villain.position.y == 0.0f,
        "the encounter must start exactly five meters apart");
    Check(std::fabs(hero.facing_radians - 0.5f * 3.14159265358979323846f) < 1.0e-6f &&
        std::fabs(villain.facing_radians + 0.5f * 3.14159265358979323846f) < 1.0e-6f,
        "the opening agents must face each other");
    Check(hero.behavior_mode == sim::BehaviorMode::Idle &&
        villain.behavior_mode == sim::BehaviorMode::Idle &&
        hero.speed_stick_amplitude == 0.0f && villain.speed_stick_amplitude == 0.0f &&
        !hero.perception.scanning && !villain.perception.scanning,
        "both agents must start idle after their initial search is already complete");
    Check(hero.head_look_mode == sim::HeadLookMode::RootHeading &&
        hero.head_look_target_id == sim::kInvalidEntityId &&
        hero.head_yaw_radians == hero.facing_radians && hero.head_pitch_radians == 0.0f,
        "a stationary idle agent must look along its root heading");
    Check(first.Snapshot().agents[0].sword_equipped && first.Snapshot().agents[1].sword_equipped,
        "both default agents must own equipped swords");
    Check(hero.sword_state == sim::SwordState::Sheathed && villain.sword_state == sim::SwordState::Sheathed,
        "both agents must start with sheathed swords for this encounter");
    Check(EqualAgents(first.Snapshot(), second.Snapshot()), "the same seed must reproduce the opening state");
    Check(EqualAgents(first.Snapshot(), different.Snapshot()),
        "changing seed must not introduce random actions into the fixed encounter");
}

void TestThreeVersusOneTacticalSteering() {
    sim::SimulationConfig config{};
    config.hero_agent_count = 1;
    config.villain_agent_count = 3;
    config.mode = sim::SimulationMode::Paired;
    sim::Simulation simulation(config, 1337);
    const auto& opening = simulation.Snapshot().agents;
    Check(opening.size() == 4U && opening[0].team == sim::Team::Hero &&
        opening[1].team == sim::Team::Villain && opening[2].team == sim::Team::Villain &&
        opening[3].team == sim::Team::Villain,
        "the asymmetric scenario must contain one Hero and three Villains");
    Check(opening[0].position.y == 0.0f && opening[1].position.y == -3.0f &&
        opening[2].position.y == 0.0f && opening[3].position.y == 3.0f,
        "the one-versus-three teams must use centered three-meter lane spacing");
    for (int tick = 0; tick < 15; ++tick) simulation.Tick();
    const auto& agents = simulation.Snapshot().agents;
    constexpr std::array<sim::EntityId, 4> expected_targets{3U, 1U, 1U, 1U};
    constexpr std::array<std::uint32_t, 4> expected_pressure{3U, 0U, 1U, 0U};
    constexpr std::array<std::uint32_t, 4> expected_support{0U, 2U, 2U, 2U};
    bool context_matches = true;
    for (std::size_t index = 0; index < agents.size(); ++index) {
        context_matches = context_matches && agents[index].attack_target_id == expected_targets[index] &&
            agents[index].combat_context.committed_attacker_count == expected_pressure[index] &&
            agents[index].combat_context.active_attacker_count == 0U &&
            agents[index].combat_context.allies_attacking_target == expected_support[index];
    }
    Check(context_matches,
        "the centered formation must expose deterministic pressure and same-target support counts");
    Check(agents[0].combat_context.committed_attacker_id_count == 3U &&
        agents[0].combat_context.committed_attacker_ids[0] == 2U &&
        agents[0].combat_context.committed_attacker_ids[1] == 3U &&
        agents[0].combat_context.committed_attacker_ids[2] == 4U,
        "the lone Hero must expose all three stable committed Villain IDs");
    Check(agents[0].tactical_steering == sim::TacticalSteeringMode::OutnumberedView &&
            agents[0].tactical_threat_count == 3U &&
            agents[0].tactical_threat_arc_radians < sim::kOutnumberedViewConeRadians,
        "the lone Hero must center its approved view cone on all three mobile threats");
    std::bitset<sim::kApproachSectorCount> occupied_sectors{};
    bool valid_sector_reservations = true;
    for (std::size_t index = 1U; index < agents.size(); ++index) {
        const sim::AgentSnapshot& attacker = agents[index];
        valid_sector_reservations = valid_sector_reservations &&
            attacker.tactical_sector_target_id == 1U &&
            attacker.tactical_sector_index < sim::kApproachSectorCount &&
            !occupied_sectors.test(attacker.tactical_sector_index);
        if (attacker.tactical_sector_index < sim::kApproachSectorCount) {
            occupied_sectors.set(attacker.tactical_sector_index);
        }
    }
    Check(valid_sector_reservations,
        "same-target Villains must reserve distinct deterministic soft approach sectors");

    const float initial_outer_gap = agents[1].tactical_nearest_peer_separation_radians;
    for (int tick = 0; tick < 45; ++tick) simulation.Tick();
    Check(simulation.Snapshot().agents[1].tactical_nearest_peer_separation_radians > initial_outer_gap,
        "attacker spacing must increase the outer Villain's bearing gap before contact");

    int guard = 600;
    bool active_context_seen = false;
    while (--guard > 0 && !active_context_seen) {
        simulation.Tick();
        const auto& current = simulation.Snapshot().agents;
        for (const sim::AgentSnapshot& defender : current) {
            if (defender.combat_context.active_attacker_count == 0U) continue;
            bool ids_match_actions = true;
            for (std::size_t index = 0;
                index < defender.combat_context.active_attacker_id_count; ++index) {
                const sim::EntityId attacker_id = defender.combat_context.active_attacker_ids[index];
                const sim::AgentSnapshot& attacker = current[attacker_id - 1U];
                ids_match_actions = ids_match_actions && attacker.attack_target_id == defender.id &&
                    (attacker.action.kind == sim::ActionKind::SwordAttack ||
                        attacker.action.kind == sim::ActionKind::MeleeAttack);
            }
            active_context_seen = ids_match_actions;
            if (active_context_seen) break;
        }
    }
    Check(guard > 0 && active_context_seen,
        "active attacker IDs must be derived from attacks currently executing against the defender");

    float farthest_retreat_x = simulation.Snapshot().agents[0].position.x;
    int backward_streak = 0;
    int longest_backward_streak = 0;
    for (int tick = 0; tick < 600; ++tick) {
        const sim::AgentSnapshot& hero = simulation.Snapshot().agents[0];
        const bool moving_backward = hero.speed_stick_amplitude > 0.0f &&
            std::sin(hero.tactical_move_yaw_radians) < -0.25f;
        backward_streak = moving_backward ? backward_streak + 1 : 0;
        longest_backward_streak = std::max(longest_backward_streak, backward_streak);
        farthest_retreat_x = std::min(farthest_retreat_x, hero.position.x);
        simulation.Tick();
    }
    Check(longest_backward_streak < 120 && farthest_retreat_x > -6.5f,
        "the engagement anchor must prevent the outnumbered Hero from retreating indefinitely");
}

void TestTwoVersusFourGeneralizationAndCountRestart() {
    sim::SimulationConfig config{};
    config.hero_agent_count = 2;
    config.villain_agent_count = 4;
    config.mode = sim::SimulationMode::Paired;
    sim::Simulation simulation(config, 404);
    Check(simulation.Config().agent_count == 6U && simulation.Snapshot().agents.size() == 6U,
        "explicit two-versus-four counts must derive six total agents");
    for (int tick = 0; tick < 15; ++tick) simulation.Tick();
    const auto& agents = simulation.Snapshot().agents;
    Check(agents[0].combat_context.committed_attacker_count == 2U &&
            agents[1].combat_context.committed_attacker_count == 2U &&
            agents[0].tactical_steering == sim::TacticalSteeringMode::OutnumberedView &&
            agents[1].tactical_steering == sim::TacticalSteeringMode::OutnumberedView,
        "two-versus-four must derive independent two-attacker pressure groups per Hero");
    Check(agents[2].attack_target_id >= 1U && agents[2].attack_target_id <= 2U &&
            agents[3].attack_target_id >= 1U && agents[3].attack_target_id <= 2U &&
            agents[4].attack_target_id >= 1U && agents[4].attack_target_id <= 2U &&
            agents[5].attack_target_id >= 1U && agents[5].attack_target_id <= 2U,
        "generalized steering must give every Villain one of its perceived Hero targets");

    const std::uint64_t seed = simulation.Seed();
    simulation.RestartWithTeamCounts(1U, 3U);
    Check(simulation.Seed() == seed && simulation.Snapshot().tick == 0U &&
            simulation.Config().hero_agent_count == 1U &&
            simulation.Config().villain_agent_count == 3U &&
            simulation.Snapshot().agents.size() == 4U,
        "committing team counts must restart tick zero with the same seed");
}

void TestBalancedPerceivedTargetAllocation() {
    constexpr float kHalfPi = 1.57079632679489661923f;
    sim::SimulationConfig equal_config{};
    equal_config.hero_agent_count = 3;
    equal_config.villain_agent_count = 3;
    equal_config.mode = sim::SimulationMode::Paired;
    equal_config.opening_transforms = {
        {1U, {-8.0f, -1.0f, 0.0f}, kHalfPi},
        {2U, {-8.0f, 0.0f, 0.0f}, kHalfPi},
        {3U, {-8.0f, 1.0f, 0.0f}, kHalfPi},
        {4U, {-1.0f, 0.0f, 0.0f}, -kHalfPi},
        {5U, {7.0f, -4.0f, 0.0f}, -kHalfPi},
        {6U, {7.0f, 4.0f, 0.0f}, -kHalfPi},
    };
    sim::Simulation equal(equal_config, 5511);
    equal.Tick();

    std::array<std::uint32_t, 3> hero_target_loads{};
    std::array<std::uint32_t, 3> villain_target_loads{};
    for (std::size_t index = 0; index < 3U; ++index) {
        const sim::EntityId target_id = equal.Snapshot().agents[index].attack_target_id;
        if (target_id >= 4U && target_id <= 6U) ++hero_target_loads[target_id - 4U];
    }
    for (std::size_t index = 3U; index < 6U; ++index) {
        const sim::EntityId target_id = equal.Snapshot().agents[index].attack_target_id;
        if (target_id >= 1U && target_id <= 3U) ++villain_target_loads[target_id - 1U];
    }
    Check(hero_target_loads == std::array<std::uint32_t, 3>{1U, 1U, 1U},
        "three Heroes sharing one nearest enemy must address all three perceived Villains");
    Check(villain_target_loads == std::array<std::uint32_t, 3>{1U, 1U, 1U},
        "equal target spreading must apply identically to Villains");
    for (int tick = 0; tick < 10; ++tick) equal.Tick();
    Check(equal.Snapshot().agents[3].combat_context.committed_attacker_count == 1U &&
            equal.Snapshot().agents[4].combat_context.committed_attacker_count == 1U &&
            equal.Snapshot().agents[5].combat_context.committed_attacker_count == 1U,
        "balanced commitments must remain stable while agents begin their timed draws");

    sim::SimulationConfig unequal_config{};
    unequal_config.hero_agent_count = 5;
    unequal_config.villain_agent_count = 2;
    unequal_config.mode = sim::SimulationMode::Paired;
    unequal_config.opening_transforms = {
        {1U, {-8.0f, -4.0f, 0.0f}, kHalfPi},
        {2U, {-8.0f, -2.0f, 0.0f}, kHalfPi},
        {3U, {-8.0f, 0.0f, 0.0f}, kHalfPi},
        {4U, {-8.0f, 2.0f, 0.0f}, kHalfPi},
        {5U, {-8.0f, 4.0f, 0.0f}, kHalfPi},
        {6U, {8.0f, -1.0f, 0.0f}, -kHalfPi},
        {7U, {8.0f, 1.0f, 0.0f}, -kHalfPi},
    };
    sim::Simulation unequal(unequal_config, 5512);
    unequal.Tick();
    std::array<std::uint32_t, 2> unequal_loads{};
    for (std::size_t index = 0; index < 5U; ++index) {
        const sim::EntityId target_id = unequal.Snapshot().agents[index].attack_target_id;
        if (target_id == 6U || target_id == 7U) ++unequal_loads[target_id - 6U];
    }
    Check(unequal_loads[0] + unequal_loads[1] == 5U &&
            std::max(unequal_loads[0], unequal_loads[1]) -
                std::min(unequal_loads[0], unequal_loads[1]) <= 1U,
        "surplus attackers must distribute with target loads differing by at most one");
    Check(unequal.Snapshot().agents[5].attack_target_id !=
            unequal.Snapshot().agents[6].attack_target_id,
        "fewer attackers than visible targets must address different enemies first");

    sim::SimulationConfig constrained_config{};
    constrained_config.hero_agent_count = 2;
    constrained_config.villain_agent_count = 2;
    constrained_config.mode = sim::SimulationMode::Paired;
    constrained_config.vision_range_m = 5.0f;
    constrained_config.opening_transforms = {
        {1U, {0.0f, 0.0f, 0.0f}, kHalfPi},
        {2U, {4.0f, 1.0f, 0.0f}, kHalfPi},
        {3U, {4.0f, 0.0f, 0.0f}, -kHalfPi},
        {4U, {8.0f, 0.0f, 0.0f}, -kHalfPi},
    };
    sim::Simulation constrained(constrained_config, 5513);
    constrained.Tick();
    Check(constrained.Snapshot().agents[0].attack_target_id == 3U &&
            constrained.Snapshot().agents[1].attack_target_id == 4U,
        "an agent with one perceived choice must claim it before a flexible ally is assigned");
    Check(constrained.Snapshot().agents[0].perception.active_threat_count == 1U,
        "target spreading must not reveal an enemy outside an agent's own perception");

    sim::SimulationConfig coverage_config{};
    coverage_config.hero_agent_count = 3;
    coverage_config.villain_agent_count = 3;
    coverage_config.mode = sim::SimulationMode::Paired;
    coverage_config.vision_range_m = 5.0f;
    coverage_config.opening_transforms = {
        {1U, {-3.0f, -2.0f, 0.0f}, kHalfPi},
        {2U, {-3.0f, 2.0f, 0.0f}, kHalfPi},
        {3U, {-3.0f, 2.5f, 0.0f}, kHalfPi},
        {4U, {0.0f, 0.0f, 0.0f}, -kHalfPi},
        {5U, {0.0f, -4.0f, 0.0f}, -kHalfPi},
        {6U, {0.0f, 4.0f, 0.0f}, -kHalfPi},
    };
    sim::Simulation coverage(coverage_config, 5514);
    coverage.Tick();
    std::array<std::uint32_t, 3> constrained_loads{};
    for (std::size_t index = 0; index < 3U; ++index) {
        const sim::EntityId target_id = coverage.Snapshot().agents[index].attack_target_id;
        if (target_id >= 4U && target_id <= 6U) ++constrained_loads[target_id - 4U];
    }
    Check(constrained_loads == std::array<std::uint32_t, 3>{1U, 1U, 1U},
        "allocation must reroute an earlier choice when that is required to cover every reachable enemy");
}

void TestMessySectorReservationsAndMotion() {
    constexpr float kHalfPi = 1.57079632679489661923f;
    sim::SimulationConfig config{};
    config.hero_agent_count = 10U;
    config.villain_agent_count = 1U;
    config.mode = sim::SimulationMode::Paired;
    config.opening_transforms.reserve(11U);
    for (std::uint32_t index = 0; index < 10U; ++index) {
        config.opening_transforms.push_back({index + 1U,
            {-8.0f, (static_cast<float>(index) - 4.5f) * 0.2f, 0.0f}, kHalfPi});
    }
    config.opening_transforms.push_back({11U, {0.0f, 0.0f, 0.0f}, -kHalfPi});

    sim::Simulation first(config, 8801U);
    sim::Simulation repeated(config, 8801U);
    first.Tick();
    repeated.Tick();
    std::array<std::uint32_t, sim::kApproachSectorCount> occupancy{};
    bool valid_reservations = true;
    for (std::size_t index = 0; index < 10U; ++index) {
        const sim::AgentSnapshot& attacker = first.Snapshot().agents[index];
        valid_reservations = valid_reservations && attacker.attack_target_id == 11U &&
            attacker.tactical_sector_target_id == 11U &&
            attacker.tactical_sector_index < sim::kApproachSectorCount &&
            attacker.target_commitment_seconds_remaining ==
                sim::kDefaultTargetCommitmentSeconds;
        if (attacker.tactical_sector_index < sim::kApproachSectorCount) {
            ++occupancy[attacker.tactical_sector_index];
        }
    }
    const auto [minimum, maximum] = std::minmax_element(occupancy.begin(), occupancy.end());
    Check(valid_reservations && *minimum == 1U && *maximum == 2U,
        "ten same-target attackers must fill eight soft sectors with load differing by at most one");
    Check(EqualAgents(first.Snapshot(), repeated.Snapshot()),
        "the same seed must reproduce target commitment and sector reservations exactly");

    bool curved_motion_seen = false;
    bool diagonal_approach_seen = false;
    bool forward_diagonal_respected = true;
    for (int tick = 0; tick < 90; ++tick) {
        const std::vector<sim::AgentSnapshot> previous_agents = first.Snapshot().agents;
        first.Tick();
        repeated.Tick();
        const auto& agents = first.Snapshot().agents;
        const sim::AgentSnapshot& target = previous_agents[10];
        for (std::size_t left = 0; left < 10U; ++left) {
            if (agents[left].tactical_sector_influence <= 0.0f ||
                agents[left].speed_stick_amplitude == 0.0f) continue;
            const float direct_yaw = std::atan2(
                target.position.x - previous_agents[left].position.x,
                target.position.y - previous_agents[left].position.y);
            const float approach_offset = std::fabs(std::remainder(
                agents[left].tactical_move_yaw_radians - direct_yaw,
                2.0f * 3.14159265358979323846f));
            const float target_distance = std::hypot(
                target.position.x - previous_agents[left].position.x,
                target.position.y - previous_agents[left].position.y);
            diagonal_approach_seen |= approach_offset > 0.2f;
            if (agents[left].attack_cooldown_seconds_remaining <= 0.0f &&
                target_distance > config.attack_range_m + 0.01f &&
                approach_offset > std::atan(0.36f) + 0.001f) {
                forward_diagonal_respected = false;
            }
            for (std::size_t right = left + 1U;
                right < 10U && !curved_motion_seen; ++right) {
                if (agents[right].tactical_sector_influence <= 0.0f ||
                    agents[right].speed_stick_amplitude == 0.0f) continue;
                curved_motion_seen = std::fabs(std::remainder(
                    agents[left].tactical_move_yaw_radians -
                        agents[right].tactical_move_yaw_radians,
                    2.0f * 3.14159265358979323846f)) > 0.2f;
                if (curved_motion_seen) break;
            }
        }
    }
    Check(curved_motion_seen,
        "seeded sectors must produce visibly different curved approach directions near a target");
    Check(diagonal_approach_seen,
        "sector spacing must retain a visible diagonal component during approach");
    Check(forward_diagonal_respected,
        "far spacing must remain a charge-dominant diagonal toward the target");
    Check(EqualAgents(first.Snapshot(), repeated.Snapshot()),
        "curved sector steering must remain deterministic through locomotion and combat");
}

void TestMixedFlankRolesAcrossSeparateTargets() {
    constexpr float kHalfPi = 1.57079632679489661923f;
    constexpr float kPi = 3.14159265358979323846f;
    sim::SimulationConfig config{};
    config.hero_agent_count = 10U;
    config.villain_agent_count = 10U;
    config.mode = sim::SimulationMode::Paired;
    config.opening_transforms.reserve(20U);
    for (std::uint32_t index = 0; index < 10U; ++index) {
        const float lane = (static_cast<float>(index) - 4.5f) * 1.0f;
        config.opening_transforms.push_back({index + 1U, {-12.0f, lane, 0.0f}, kHalfPi});
        config.opening_transforms.push_back({index + 11U, {12.0f, lane, 0.0f}, -kHalfPi});
    }

    sim::Simulation simulation(config, 85555888353100ULL);
    sim::Simulation repeated(config, 85555888353100ULL);
    simulation.Tick();
    repeated.Tick();

    std::uint32_t flankers = 0U;
    std::uint32_t center_pushers = 0U;
    for (const sim::AgentSnapshot& agent : simulation.Snapshot().agents) {
        const auto target = std::find_if(simulation.Snapshot().agents.begin(),
            simulation.Snapshot().agents.end(), [&agent](const sim::AgentSnapshot& candidate) {
                return candidate.id == agent.attack_target_id;
            });
        if (target == simulation.Snapshot().agents.end()) continue;
        const float current_bearing = std::atan2(
            agent.position.x - target->position.x, agent.position.z - target->position.z);
        const float role_offset = std::fabs(std::remainder(
            agent.tactical_sector_yaw_radians - current_bearing, 2.0f * kPi));
        if (role_offset >= 0.75f * kHalfPi) ++flankers;
        if (role_offset <= 0.5f * kHalfPi) ++center_pushers;
    }
    Check(flankers >= 10U && center_pushers >= 1U,
        "separate-target battles must mix center pressure with seeded side and rear-quarter routes");

    bool attack_started = false;
    bool far_containment_seen = false;
    bool containment_ramp_seen = false;
    bool far_charge_respected = true;
    for (int tick = 0; tick < 300; ++tick) {
        const std::vector<sim::AgentSnapshot> previous_agents = simulation.Snapshot().agents;
        simulation.Tick();
        repeated.Tick();
        const auto& agents = simulation.Snapshot().agents;
        attack_started = attack_started || std::any_of(agents.begin(), agents.end(),
            [](const sim::AgentSnapshot& agent) {
                return agent.action.kind == sim::ActionKind::SwordAttack ||
                    agent.action.kind == sim::ActionKind::MeleeAttack ||
                    agent.completed_attacks > 0U;
            });
        for (const sim::AgentSnapshot& agent : agents) {
            if (agent.tactical_steering != sim::TacticalSteeringMode::OutnumberedView) continue;
            containment_ramp_seen |= agent.tactical_containment_influence > 0.25f;
            if (agent.speed_stick_amplitude <= 0.001f ||
                agent.tactical_containment_influence > 0.1f) continue;
            const auto previous_agent = std::find_if(previous_agents.begin(),
                previous_agents.end(), [&agent](const sim::AgentSnapshot& candidate) {
                    return candidate.id == agent.id;
                });
            const auto previous_target = std::find_if(previous_agents.begin(),
                previous_agents.end(), [&agent](const sim::AgentSnapshot& candidate) {
                    return candidate.id == agent.attack_target_id;
                });
            if (previous_agent == previous_agents.end() ||
                previous_target == previous_agents.end()) continue;
            far_containment_seen = true;
            const float direct_yaw = std::atan2(
                previous_target->position.x - previous_agent->position.x,
                previous_target->position.y - previous_agent->position.y);
            const float approach_offset = std::fabs(std::remainder(
                agent.tactical_move_yaw_radians - direct_yaw, 2.0f * kPi));
            far_charge_respected = far_charge_respected && approach_offset <= 0.35f;
        }
    }
    Check(attack_started, "flank routes must still converge into combat instead of orbiting targets");
    Check(far_containment_seen && far_charge_respected,
        "distant contain steering must preserve a charge-dominant diagonal toward the target");
    Check(containment_ramp_seen,
        "contain spacing must strengthen as the opposing formations approach contact");
    Check(EqualAgents(simulation.Snapshot(), repeated.Snapshot()),
        "mixed flank roles must remain deterministic through first contact");
}

void TestContainmentEarlyInfluenceOption() {
    constexpr float kPi = 3.14159265358979323846f;
    sim::SimulationConfig config{};
    config.hero_agent_count = 1U;
    config.villain_agent_count = 2U;
    config.mode = sim::SimulationMode::Paired;
    const float reference_distance = config.sector_influence_distance_m -
        0.3f * (config.sector_influence_distance_m - config.attack_range_m);
    const float lane_offset = 1.0f;
    const float forward_distance = std::sqrt(
        reference_distance * reference_distance - lane_offset * lane_offset);
    config.opening_transforms = {
        {1U, {0.0f, 0.0f, 0.0f}, 0.5f * kPi},
        {2U, {forward_distance, -lane_offset, 0.0f}, -0.5f * kPi},
        {3U, {forward_distance, lane_offset, 0.0f}, -0.5f * kPi},
    };

    sim::Simulation simulation(config, 8812U);
    for (int tick = 0; tick < 30 &&
        simulation.Snapshot().agents[0].tactical_steering !=
            sim::TacticalSteeringMode::OutnumberedView; ++tick) {
        simulation.Tick();
    }
    Check(simulation.Snapshot().agents[0].tactical_steering ==
            sim::TacticalSteeringMode::OutnumberedView &&
            std::fabs(simulation.Snapshot().agents[0].tactical_containment_influence - 0.1f) <
                0.001f,
        "the default early-spread option must produce ten-percent containment at its control point");

    simulation.UpdateTacticsOptions(config.target_commitment_seconds,
        config.sector_influence_distance_m, 0.2f,
        config.sector_angle_variation_degrees, config.sector_radius_variation_m,
        config.ally_spacing_distance_m);
    simulation.Tick();
    Check(std::fabs(simulation.Snapshot().agents[0].tactical_containment_influence - 0.2f) <
            0.001f,
        "a hot early-spread change must affect containment on the next fixed tick");
}

void TestIdleVisionActivationAndStrike() {
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    sim::Simulation simulation(config, 1337);
    Check(simulation.Snapshot().agents[0].behavior_mode == sim::BehaviorMode::Idle &&
        simulation.Snapshot().agents[0].position.x == -2.5f,
        "agents must start idle even when an opponent is visible");
    simulation.Tick();
    Check(simulation.Snapshot().tick == 1U &&
        simulation.Snapshot().agents[0].behavior_mode == sim::BehaviorMode::Attack &&
        simulation.Snapshot().agents[1].behavior_mode == sim::BehaviorMode::Attack,
        "an idle agent must wake on the first tick that it sees an opponent");
    Check(simulation.Snapshot().agents[0].attack_target_id == 2U &&
        simulation.Snapshot().agents[1].attack_target_id == 1U &&
        simulation.Snapshot().agents[0].target_distance_m == 5.0f,
        "vision activation must acquire the opposing agent without moving early");
    Check(simulation.Snapshot().agents[0].head_look_mode == sim::HeadLookMode::CombatTarget &&
        simulation.Snapshot().agents[0].head_look_target_id == 2U &&
        simulation.Snapshot().agents[1].head_look_target_id == 1U,
        "vision activation must immediately make each head track the opponent");
    int guard = 300;
    const sim::AgentSnapshot unsheathing = simulation.Snapshot().agents[0];
    Check(guard > 0 && unsheathing.action.phase == sim::ActionPhase::Reaching &&
        unsheathing.action.kind == sim::ActionKind::UnsheatheSword &&
        unsheathing.target_distance_m == 5.0f && unsheathing.speed_stick_amplitude == 0.0f,
        "vision activation must start the timed unsheathe action before any running");
    Check(unsheathing.action.duration_seconds > 0.8f && unsheathing.action.duration_seconds < 0.85f,
        "the unsheathe action must use the 1.7x-faster fixed-step duration");
    while (simulation.Snapshot().agents[0].sword_state != sim::SwordState::Drawn && --guard > 0) {
        simulation.Tick();
    }
    Check(guard > 0 && simulation.Snapshot().agents[0].position.x == -2.5f,
        "the sword must become fully drawn while the agent remains at its starting point");
    simulation.Tick();
    Check(simulation.Snapshot().agents[0].locomotion_mode == sim::LocomotionMode::Run &&
            simulation.Snapshot().agents[0].speed_stick_amplitude == 1.0f &&
            simulation.Snapshot().agents[0].position.x > -2.5f,
        "the run mover must receive its first nonzero stick only after drawing completes");
    bool full_approach_stick = true;
    while (simulation.Snapshot().agents[0].action.kind != sim::ActionKind::SwordAttack &&
        simulation.Snapshot().agents[0].action.kind != sim::ActionKind::MeleeAttack && --guard > 0) {
        const sim::AgentSnapshot& approaching = simulation.Snapshot().agents[0];
        if (approaching.target_distance_m > config.attack_range_m &&
            approaching.speed_stick_amplitude != 1.0f) full_approach_stick = false;
        simulation.Tick();
    }
    Check(full_approach_stick,
        "attack approach must retain a full Run stick with no unrequested close-range slowdown");
    const sim::AgentSnapshot started = simulation.Snapshot().agents[0];
    Check(guard > 0 && started.action.phase == sim::ActionPhase::Executing &&
        started.target_distance_m <= 1.25f,
        "a selected authored attack must start only inside the exact attack range");
    Check(started.action.duration_seconds >= 0.4f && started.action.duration_seconds <= 1.034f,
        "attack duration must come from the selected authored clip");
    while (simulation.Snapshot().agents[0].completed_attacks == 0U && --guard > 0) simulation.Tick();
    Check(guard > 0 && simulation.Snapshot().agents[0].completed_attacks == 1U,
        "an unopposed authored attack must complete after its clip duration");
}

void TestCooldownRetreatAndSeededStrafe() {
    constexpr float kPi = 3.14159265358979323846f;
    bool observed_strafe = false;
    bool observed_no_strafe = false;
    float minimum_strafe_distance = 2.0f;
    float maximum_strafe_distance = 0.0f;
    for (std::uint64_t seed = 1; seed <= 64; ++seed) {
        sim::SimulationConfig config{};
        config.mode = sim::SimulationMode::Paired;
        config.hero_agent_count = 1;
        config.villain_agent_count = 1;
        config.attack_range_m = 10.0f;
        config.sector_influence_distance_m = config.attack_range_m;
        config.attack_cooldown_seconds = 1.0f;
        config.attack_followup_probability = 0.0f;
        config.opening_transforms = {
            {1U, {-1.0f, 0.0f, 0.0f}, 0.5f * kPi},
            {2U, {1.0f, 0.0f, 0.0f}, -0.5f * kPi},
        };
        sim::Simulation simulation(config, seed);
        int guard = 180;
        while (simulation.Snapshot().agents[0].attack_cooldown_seconds_remaining <= 0.0f &&
            --guard > 0) {
            simulation.Tick();
        }
        Check(guard > 0, "a completed attack must enter cooldown");
        if (guard <= 0) continue;

        const sim::AgentSnapshot cooldown_started = simulation.Snapshot().agents[0];
        observed_strafe = observed_strafe || cooldown_started.cooldown_strafe;
        observed_no_strafe = observed_no_strafe || !cooldown_started.cooldown_strafe;
        if (cooldown_started.cooldown_strafe) {
            minimum_strafe_distance = std::min(minimum_strafe_distance,
                cooldown_started.cooldown_strafe_target_distance_m);
            maximum_strafe_distance = std::max(maximum_strafe_distance,
                cooldown_started.cooldown_strafe_target_distance_m);
            Check(cooldown_started.cooldown_strafe_target_distance_m >= 0.5f &&
                    cooldown_started.cooldown_strafe_target_distance_m <= 1.0f &&
                    cooldown_started.cooldown_strafe_distance_remaining_m ==
                        cooldown_started.cooldown_strafe_target_distance_m,
                "a strafing cooldown must choose a deterministic half-to-one-meter travel target");
        }
        simulation.Tick();
        const sim::AgentSnapshot moving = simulation.Snapshot().agents[0];
        Check(moving.attack_cooldown_seconds_remaining > 0.0f &&
                moving.speed_stick_amplitude == 1.0f,
            "an attacker closer than half range must retreat during cooldown");
        Check(moving.cooldown_strafe == cooldown_started.cooldown_strafe &&
                moving.cooldown_strafe_direction == cooldown_started.cooldown_strafe_direction,
            "the seeded cooldown strafe choice and side must remain fixed");

        const float expected_direction = cooldown_started.cooldown_strafe
            ? cooldown_started.cooldown_strafe_direction * 0.75f * kPi
            : kPi;
        const float direction_error = std::fabs(std::remainder(
            moving.speed_stick_direction_radians - expected_direction, 2.0f * kPi));
        Check(direction_error < 0.05f,
            "cooldown movement must combine retreat and optional tangential strafe in one stick");

        if (cooldown_started.cooldown_strafe) {
            bool strafe_finished_during_cooldown = false;
            float previous_remaining = moving.cooldown_strafe_distance_remaining_m;
            while (simulation.Snapshot().agents[0].attack_cooldown_seconds_remaining > 0.0f) {
                simulation.Tick();
                const sim::AgentSnapshot& current = simulation.Snapshot().agents[0];
                Check(current.cooldown_strafe_distance_remaining_m <= previous_remaining,
                    "measured cooldown strafe travel must only reduce its remaining distance");
                previous_remaining = current.cooldown_strafe_distance_remaining_m;
                if (!current.cooldown_strafe &&
                    current.attack_cooldown_seconds_remaining > 0.0f) {
                    strafe_finished_during_cooldown = true;
                }
            }
            Check(strafe_finished_during_cooldown,
                "the bounded strafe must finish before the full cooldown orbit can develop");
        }
    }
    Check(observed_strafe && observed_no_strafe,
        "the deterministic 50 percent cooldown roll must produce strafing and non-strafing runs");
    Check(maximum_strafe_distance - minimum_strafe_distance > 0.1f,
        "seeded cooldown strafe travel must vary within the half-to-one-meter range");
}

void TestDeterministicSoundEvents() {
    sim::SimulationConfig movement_config{};
    movement_config.mode = sim::SimulationMode::Paired;
    movement_config.attack_range_m = 0.25f;
    sim::Simulation movement(movement_config, 1337);
    while (movement.Snapshot().tick < 48U) movement.Tick();
    const sim::SoundEventSnapshot* movement_sound = LatestSound(
        movement.Snapshot(), sim::SoundEventKind::Locomotion);
    Check(movement_sound != nullptr && movement_sound->emitted_tick == 48U,
        "moving agents must emit their first eligible fixed-cadence sound on tick 48");
    if (movement_sound != nullptr) {
        const auto source = std::find_if(movement.Snapshot().agents.begin(),
            movement.Snapshot().agents.end(), [movement_sound](const sim::AgentSnapshot& agent) {
                return agent.id == movement_sound->source_id;
            });
        const float expected_range = source == movement.Snapshot().agents.end() ? -1.0f
            : sim::kSoundMaximumRangeMeters * std::clamp(
                source->root_speed_mps / sim::kRunSoundReferenceSpeedMps, 0.0f, 1.0f);
        Check(source != movement.Snapshot().agents.end() &&
            std::fabs(movement_sound->maximum_range_m - expected_range) < 1.0e-5f,
            "locomotion sound reach must interpolate from zero to three meters using root velocity");
    }
    const std::uint64_t locomotion_interval_ticks = static_cast<std::uint64_t>(std::lround(
        sim::kLocomotionSoundIntervalSeconds * movement_config.tick_rate_hz));
    Check(locomotion_interval_ticks == 6U && movement_sound != nullptr &&
        movement_sound->emitted_tick % locomotion_interval_ticks == 0U,
        "locomotion sound pulses must use an exact 0.2-second clock at 30 Hz");

    sim::SimulationConfig parry_config{};
    parry_config.mode = sim::SimulationMode::Paired;
    parry_config.hit_probability = 0.0f;
    parry_config.parry_probability = 1.0f;
    sim::Simulation parry(parry_config, 1337);
    int parry_guard = 900;
    while (LatestSound(parry.Snapshot(), sim::SoundEventKind::Parry) == nullptr && --parry_guard > 0) {
        parry.Tick();
    }
    const sim::SoundEventSnapshot* parry_sound = LatestSound(
        parry.Snapshot(), sim::SoundEventKind::Parry);
    Check(parry_guard > 0 && parry_sound != nullptr &&
        parry_sound->maximum_range_m == sim::kSoundMaximumRangeMeters,
        "a parry must immediately emit one three-meter sound event");

    sim::SimulationConfig crawl_config{};
    crawl_config.hit_probability = 1.0f;
    crawl_config.attack_cooldown_seconds = 0.0f;
    crawl_config.leg_agonising_seconds = 0.0f;
    crawl_config.torso_agonising_seconds = 0.0f;
    crawl_config.head_passed_out_seconds = 0.0f;
    sim::Simulation crawl(crawl_config, 1337);
    int crawl_guard = 1800;
    while (LatestSound(crawl.Snapshot(), sim::SoundEventKind::CrawlYell) == nullptr &&
        --crawl_guard > 0) {
        crawl.Tick();
    }
    const sim::SoundEventSnapshot* crawl_sound = LatestSound(
        crawl.Snapshot(), sim::SoundEventKind::CrawlYell);
    Check(crawl_guard > 0 && crawl_sound != nullptr &&
        crawl_sound->maximum_range_m == sim::kSoundMaximumRangeMeters,
        "entering crawl mode must emit one three-meter yell event");

    sim::Simulation repeated(movement_config, 1337);
    while (repeated.Snapshot().tick < movement.Snapshot().tick) repeated.Tick();
    Check(EqualAgents(movement.Snapshot(), repeated.Snapshot()),
        "sound events must replay identically from the same seed and tick");
}

void TestExecutionScreamRescue() {
    constexpr std::uint64_t kSeed = 3U;
    sim::SimulationConfig config{};
    config.hero_agent_count = 3;
    config.villain_agent_count = 3;
    config.sound_maximum_range_m = 30.034721f;
    config.vision_range_m = 100.0f;
    config.target_commitment_seconds = 0.0f;
    config.sector_influence_distance_m = config.attack_range_m;
    config.ally_spacing_distance_m = 0.0f;
    config.attack_followup_probability = 0.0f;
    config.drawn_sword_attack_probability = 0.9f;
    config.opening_transforms = {
        {1U, {-4.6173458f, -6.3535929f, 0.0f}, 0.6389511f},
        {2U, {-3.3673458f, -6.3535929f, 0.0f}, 1.2745177f},
        {3U, {-3.9923458f, -5.1035929f, 0.0f}, 1.2362672f},
        {4U, {2.0497274f, -6.0810809f, 0.0f}, -1.7502687f},
        {5U, {1.7638454f, 2.3790731f, 0.0f}, -1.7540561f},
        {6U, {1.5742397f, 3.7815456f, 0.0f}, -1.7689900f},
    };

    sim::Simulation simulation(config, kSeed);
    int guard = 2400;
    const sim::SoundEventSnapshot* scream = nullptr;
    while (--guard > 0) {
        simulation.Tick();
        scream = LatestSound(simulation.Snapshot(), sim::SoundEventKind::ExecutionScream);
        if (scream != nullptr && scream->emitted_tick == simulation.Snapshot().tick &&
            scream->recipient_count == 1U) break;
    }
    const sim::SimulationSnapshot scream_snapshot = simulation.Snapshot();
    scream = LatestSound(
        scream_snapshot, sim::SoundEventKind::ExecutionScream);
    Check(guard > 0 && scream != nullptr,
        "the saved wrath seed must produce an execution scream with a standing responder");
    if (guard <= 0 || scream == nullptr || scream->recipient_count != 1U) return;
    Check(scream->emitted_tick == scream_snapshot.tick && scream->recipient_count == 1U &&
            scream->maximum_range_m == config.sound_maximum_range_m,
        "wrath entry must emit one full-range scream with exactly one responder");

    const auto victim = std::find_if(scream_snapshot.agents.begin(),
        scream_snapshot.agents.end(), [scream](const sim::AgentSnapshot& agent) {
            return agent.id == scream->source_id;
        });
    const auto executioner = std::find_if(scream_snapshot.agents.begin(),
        scream_snapshot.agents.end(), [scream](const sim::AgentSnapshot& agent) {
            return agent.id == scream->secondary_source_id;
        });
    const auto responder = std::find_if(scream_snapshot.agents.begin(),
        scream_snapshot.agents.end(), [scream](const sim::AgentSnapshot& agent) {
            return agent.rescue_executioner_id == scream->secondary_source_id;
        });
    const std::size_t responder_count = static_cast<std::size_t>(std::count_if(
        scream_snapshot.agents.begin(), scream_snapshot.agents.end(),
        [scream](const sim::AgentSnapshot& agent) {
            return agent.rescue_executioner_id == scream->secondary_source_id;
        }));
    Check(victim != scream_snapshot.agents.end() &&
            executioner != scream_snapshot.agents.end() &&
            responder != scream_snapshot.agents.end() && responder_count == 1U &&
            responder->team == victim->team && executioner->team != victim->team,
        "the scream must select exactly one standing ally of the victim");
    if (victim == scream_snapshot.agents.end() ||
        executioner == scream_snapshot.agents.end() ||
        responder == scream_snapshot.agents.end()) return;
    const auto standing = [](sim::AgentState state) {
        return state == sim::AgentState::Normal || state == sim::AgentState::Slow ||
            state == sim::AgentState::Stunned;
    };
    const double responder_x = static_cast<double>(responder->position.x) - scream->position.x;
    const double responder_z = static_cast<double>(responder->position.y) - scream->position.y;
    const double responder_distance_squared =
        responder_x * responder_x + responder_z * responder_z;
    bool closer_ally_exists = false;
    for (const sim::AgentSnapshot& candidate : scream_snapshot.agents) {
        if (candidate.id == victim->id || candidate.id == responder->id ||
            candidate.team != victim->team || !standing(candidate.state)) continue;
        const double delta_x = static_cast<double>(candidate.position.x) - scream->position.x;
        const double delta_z = static_cast<double>(candidate.position.y) - scream->position.y;
        const double distance_squared = delta_x * delta_x + delta_z * delta_z;
        if (distance_squared < responder_distance_squared - 0.25) closer_ally_exists = true;
    }
    Check(!closer_ally_exists && responder->attack_target_id == scream->secondary_source_id &&
            responder->rescue_former_target_id != sim::kInvalidEntityId &&
            responder->rescue_head_hold_seconds_remaining > 0.0f &&
            responder->head_look_mode == sim::HeadLookMode::RescueFormerTarget &&
            responder->head_look_target_id == responder->rescue_former_target_id,
        "the closest ally must run at the executioner while initially looking at its former target");

    const sim::EntityId responder_id = responder->id;
    const sim::EntityId executioner_id = responder->rescue_executioner_id;
    const sim::EntityId former_target_id = responder->rescue_former_target_id;
    simulation.Tick();
    const sim::AgentSnapshot& next_responder =
        simulation.Snapshot().agents[static_cast<std::size_t>(responder_id - 1U)];
    const auto contains_active = [&next_responder](sim::EntityId id) {
        return std::find(next_responder.perception.active_threat_ids.begin(),
            next_responder.perception.active_threat_ids.begin() +
                next_responder.perception.active_threat_id_count, id) !=
            next_responder.perception.active_threat_ids.begin() +
                next_responder.perception.active_threat_id_count;
    };
    Check(next_responder.attack_target_id == executioner_id &&
            contains_active(executioner_id) && contains_active(former_target_id) &&
            next_responder.speed_stick_amplitude > 0.99f,
        "the rescue tick must run immediately and retain both active threats");

    while (simulation.Snapshot().agents[static_cast<std::size_t>(responder_id - 1U)]
            .rescue_executioner_id == executioner_id &&
        simulation.Snapshot().agents[static_cast<std::size_t>(responder_id - 1U)]
            .rescue_head_hold_seconds_remaining > 0.0f) {
        simulation.Tick();
    }
    const sim::AgentSnapshot& focused_responder =
        simulation.Snapshot().agents[static_cast<std::size_t>(responder_id - 1U)];
    if (focused_responder.rescue_executioner_id == executioner_id) {
        Check(focused_responder.head_look_mode == sim::HeadLookMode::CombatTarget &&
                focused_responder.head_look_target_id == executioner_id,
            "after one second the responder must move its head focus to the executioner");
    }

    sim::Simulation repeated(config, kSeed);
    while (repeated.Snapshot().tick < simulation.Snapshot().tick) repeated.Tick();
    Check(EqualAgents(simulation.Snapshot(), repeated.Snapshot()),
        "execution-scream rescue state must replay identically from the saved seed");
}

void TestHeadLookLimitsAndTurnRate() {
    constexpr float kPiF = 3.14159265358979323846f;
    const auto relative_yaw = [](const sim::AgentSnapshot& agent) {
        return std::remainder(agent.head_yaw_radians - agent.facing_radians,
            2.0f * 3.14159265358979323846f);
    };
    const auto grounded = [](sim::AgentState state) {
        return state == sim::AgentState::Agonising || state == sim::AgentState::PassedOut ||
            state == sim::AgentState::Crawling || state == sim::AgentState::Dead;
    };

    bool limits_respected = true;
    bool rate_respected = true;
    bool downward_target_seen = false;
    for (std::uint64_t seed = 1; seed <= 64 && !downward_target_seen; ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 0.0f;
        config.head_turn_speed_degrees_per_second = 30.0f;
        sim::Simulation simulation(config, seed);
        for (int tick = 0; tick < 1800 && !downward_target_seen; ++tick) {
            const std::array<sim::AgentSnapshot, 2> previous{
                simulation.Snapshot().agents[0], simulation.Snapshot().agents[1]};
            simulation.Tick();
            const auto& agents = simulation.Snapshot().agents;
            for (std::size_t index = 0; index < agents.size(); ++index) {
                const sim::AgentSnapshot& agent = agents[index];
                const float yaw_offset = relative_yaw(agent);
                limits_respected = limits_respected &&
                    std::fabs(yaw_offset) <= sim::kHeadYawLimitRadians + 1.0e-5f &&
                    std::fabs(agent.head_pitch_radians) <= sim::kHeadPitchLimitRadians + 1.0e-5f;
                const float previous_yaw_offset = relative_yaw(previous[index]);
                const float yaw_step = std::remainder(
                    yaw_offset - previous_yaw_offset, 2.0f * kPiF);
                const float pitch_step = agent.head_pitch_radians - previous[index].head_pitch_radians;
                const float maximum_step = 30.0f * kPiF / 180.0f / config.tick_rate_hz;
                rate_respected = rate_respected &&
                    std::fabs(yaw_step) <= maximum_step + 1.0e-5f &&
                    std::fabs(pitch_step) <= maximum_step + 1.0e-5f;

                if (agent.head_look_mode != sim::HeadLookMode::CombatTarget ||
                    agent.head_look_target_id == sim::kInvalidEntityId) continue;
                const auto target = std::find_if(agents.begin(), agents.end(),
                    [&agent](const sim::AgentSnapshot& candidate) {
                        return candidate.id == agent.head_look_target_id;
                    });
                if (target != agents.end() && grounded(target->state) && !grounded(agent.state) &&
                    agent.head_pitch_radians < -1.0e-4f) {
                    downward_target_seen = true;
                }
            }
        }
    }
    Check(limits_respected,
        "head yaw and pitch must remain within their fixed 120/80-degree limits");
    Check(rate_respected, "head yaw and pitch must obey the configured fixed-step turn speed");
    Check(downward_target_seen, "a combatant must pitch its head toward a grounded opponent's head");
}

void TestRecognitionBeforeProximityRetention() {
    constexpr float kPiF = 3.14159265358979323846f;
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    config.hero_agent_count = 1;
    config.villain_agent_count = 2;
    config.opening_transforms = {
        {1U, {0.0f, 0.0f, 0.0f}, 0.5f * kPiF},
        {2U, {10.0f, 0.0f, 0.0f}, -0.5f * kPiF},
        {3U, {-2.0f, 0.0f, 0.0f}, 0.5f * kPiF},
    };
    sim::Simulation simulation(config, 4104);
    const sim::AgentSnapshot& opening = simulation.Snapshot().agents[0];
    Check(opening.perception.recognized_threat_count == 1U &&
            opening.perception.active_threat_count == 1U &&
            opening.perception.visible_threat_count == 1U &&
            opening.perception.proximity_threat_count == 0U &&
            opening.behavior_mode == sim::BehaviorMode::Idle &&
            opening.attack_target_id == sim::kInvalidEntityId,
        "an unseen enemy inside proximity must not be identified before visual recognition");
    simulation.Tick();
    Check(simulation.Snapshot().agents[0].behavior_mode == sim::BehaviorMode::Attack &&
            simulation.Snapshot().agents[0].attack_target_id == 2U,
        "an initially visible enemy must wake the idle observer on its first tick");

    Check(simulation.SetAgentTransform({2U, {-120.0f, 0.0f, 0.0f}, 0.5f * kPiF}),
        "the initially recognized target must be movable out of view");
    Check(simulation.SetAgentTransform({3U, {-3.42f, 9.40f, 0.0f}, 0.0f}),
        "the unrecognized target must be placeable just beyond the initial vision hemisphere");
    const sim::AgentSnapshot& before_scan = simulation.Snapshot().agents[0];
    Check(before_scan.perception.recognized_threat_count == 1U &&
            before_scan.perception.active_threat_count == 0U,
        "proximity alone must not add an unseen enemy to recognition memory");

    bool scan_recognized = false;
    for (int scan_tick = 0; scan_tick < 60 && !scan_recognized; ++scan_tick) {
        simulation.Tick();
        const sim::AgentSnapshot& hero = simulation.Snapshot().agents[0];
        scan_recognized = hero.attack_target_id == 3U &&
            hero.perception.recognized_threat_count == 2U &&
            hero.perception.visible_threat_count == 1U;
    }
    Check(scan_recognized,
        "a head scan must recognize and select a standing enemy only after seeing it");
    if (!scan_recognized) return;

    simulation.UpdatePerceptionOptions(3.0f, 3.0f, 180.0f,
        config.sound_maximum_range_m, config.running_sound_toward_leeway_degrees,
        config.non_threatening_minimum_seconds, config.non_threatening_maximum_seconds,
        config.follow_walk_distance_m, config.follow_stop_distance_m);
    const sim::AgentSnapshot before_hidden_move = simulation.Snapshot().agents[0];
    const float hidden_bearing = before_hidden_move.head_yaw_radians + kPiF;
    Check(simulation.SetAgentTransform({3U,
            {before_hidden_move.position.x + 2.0f * std::sin(hidden_bearing),
                before_hidden_move.position.y + 2.0f * std::cos(hidden_bearing),
                0.0f}, 0.0f}),
        "a recognized target must be movable behind the current head direction");
    const sim::AgentSnapshot& retained = simulation.Snapshot().agents[0];
    Check(retained.perception.visible_threat_count == 0U &&
            retained.perception.proximity_threat_count == 1U &&
            retained.perception.active_threat_count == 1U &&
            retained.attack_target_id == 3U,
        "proximity must retain a previously seen threat without rediscovering unseen enemies");
}

void TestRearThreatRequiresSoundInvestigation() {
    constexpr float kPiF = 3.14159265358979323846f;
    constexpr float kRearBearingRadians = 175.0f * kPiF / 180.0f;
    constexpr float kDistance = 5.0f;
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    config.opening_transforms = {
        {1U, {0.0f, 0.0f, 0.0f}, 0.0f},
        {2U, {kDistance * std::sin(kRearBearingRadians),
            kDistance * std::cos(kRearBearingRadians), 0.0f},
            kRearBearingRadians - kPiF},
    };
    sim::Simulation simulation(config, 5105U);
    const sim::AgentSnapshot& opening_hero = simulation.Snapshot().agents[0];
    Check(opening_hero.behavior_mode == sim::BehaviorMode::Idle &&
            opening_hero.sword_state == sim::SwordState::Sheathed &&
            opening_hero.perception.visible_threat_count == 0U &&
            opening_hero.perception.recognized_threat_count == 0U &&
            !opening_hero.perception.scanning,
        "an unrecognized rear opponent must not disturb the completed idle opening state");

    bool qualifying_sound_seen = false;
    bool woke_before_sound = false;
    bool woke_after_sound = false;
    bool torso_assisted_yaw_seen = false;
    for (int guard = 0; guard < 600 && !woke_after_sound; ++guard) {
        simulation.Tick();
        const sim::SimulationSnapshot& snapshot = simulation.Snapshot();
        const sim::AgentSnapshot& hero = snapshot.agents[0];
        torso_assisted_yaw_seen = torso_assisted_yaw_seen ||
            std::fabs(hero.head_yaw_radians - hero.facing_radians) >
                80.0f * kPiF / 180.0f;
        const sim::SoundEventSnapshot* sound = LatestSound(snapshot, sim::SoundEventKind::Locomotion);
        if (sound != nullptr && sound->source_id == 2U && sound->emitted_tick == snapshot.tick) {
            const double distance = std::hypot(
                static_cast<double>(sound->position.x) - hero.position.x,
                static_cast<double>(sound->position.y) - hero.position.y);
            if (distance <= static_cast<double>(sound->maximum_range_m)) {
                qualifying_sound_seen = true;
            }
        }
        if (hero.behavior_mode == sim::BehaviorMode::Attack) {
            woke_before_sound = !qualifying_sound_seen;
            woke_after_sound = qualifying_sound_seen;
        }
    }
    Check(qualifying_sound_seen && !woke_before_sound && woke_after_sound &&
            torso_assisted_yaw_seen &&
            simulation.Snapshot().agents[0].perception.recognized_threat_count == 1U,
        "a near-directly-rear opponent must wake only after sound drives the 120-degree look range into visual recognition");
    const sim::AgentSnapshot& drawing_hero = simulation.Snapshot().agents[0];
    const sim::AgentSnapshot& incoming_villain = simulation.Snapshot().agents[1];
    const double toward_x = static_cast<double>(incoming_villain.position.x -
        drawing_hero.position.x);
    const double toward_z = static_cast<double>(incoming_villain.position.y -
        drawing_hero.position.y);
    const double intended_x = std::sin(static_cast<double>(drawing_hero.facing_radians) +
        drawing_hero.speed_stick_direction_radians);
    const double intended_z = std::cos(static_cast<double>(drawing_hero.facing_radians) +
        drawing_hero.speed_stick_direction_radians);
    Check(drawing_hero.draw_retreat_target_id == incoming_villain.id &&
            drawing_hero.action.kind == sim::ActionKind::UnsheatheSword &&
            drawing_hero.locomotion_mode == sim::LocomotionMode::Walk &&
            drawing_hero.speed_stick_amplitude == 1.0f &&
            intended_x * toward_x + intended_z * toward_z < 0.0,
        "a sound-confirmed running-toward threat must trigger timed drawing with a full Walk stick away from that threat");

    int draw_guard = 90;
    while (simulation.Snapshot().agents[0].sword_state != sim::SwordState::Drawn &&
        --draw_guard > 0) {
        simulation.Tick();
    }
    Check(draw_guard > 0 &&
            simulation.Snapshot().agents[0].draw_retreat_target_id == sim::kInvalidEntityId,
        "the sound-confirmed retreat must end when the sword becomes fully drawn");
}

void TestEmptyLookAroundSheathesSword() {
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    sim::Simulation simulation(config, 5108U);
    int draw_guard = 90;
    while (simulation.Snapshot().agents[0].sword_state != sim::SwordState::Drawn &&
        --draw_guard > 0) {
        simulation.Tick();
    }
    Check(draw_guard > 0, "the sheathe regression must first reach a fully drawn sword");
    if (draw_guard <= 0) return;

    Check(simulation.SetAgentTransform({2U, {120.0f, 0.0f, 0.0f}, 0.0f}),
        "the sheathe regression must move the opponent outside vision");
    simulation.UpdatePerceptionOptions(1.0f, 1.0f, 180.0f, 0.0f,
        15.0f, 30.0f, 40.0f, 7.0f, 2.0f);

    bool look_around_seen = false;
    bool timed_sheathe_seen = false;
    bool sheathed = false;
    for (int guard = 0; guard < 180 && !sheathed; ++guard) {
        simulation.Tick();
        const sim::AgentSnapshot& hero = simulation.Snapshot().agents[0];
        look_around_seen = look_around_seen || hero.perception.scanning;
        if (hero.action.kind == sim::ActionKind::SheatheSword) {
            timed_sheathe_seen = true;
            Check(hero.behavior_mode == sim::BehaviorMode::Idle &&
                    hero.speed_stick_amplitude == 0.0f,
                "post-search sheathing must remain idle and stationary");
        }
        sheathed = hero.sword_state == sim::SwordState::Sheathed;
    }
    Check(look_around_seen && timed_sheathe_seen && sheathed,
        "an empty bounded look-around must finish with the existing timed sword sheathe");
}

void TestSoundDirectionFilterRequiresAnActiveThreat() {
    constexpr float kPiF = 3.14159265358979323846f;
    sim::SimulationConfig idle_config{};
    idle_config.hero_agent_count = 2U;
    idle_config.villain_agent_count = 1U;
    idle_config.mode = sim::SimulationMode::Paired;
    idle_config.sound_maximum_range_m = 50.0f;
    idle_config.opening_transforms = {
        {1U, {-10.0f, -4.0f, 0.0f}, -0.5f * kPiF},
        {2U, {20.0f, -4.0f, 0.0f}, 0.5f * kPiF},
        {3U, {0.0f, -4.0f, 0.0f}, 0.5f * kPiF},
    };
    sim::Simulation idle_listener(idle_config, 5106U);

    bool non_directional_sound_heard = false;
    bool non_directional_sound_investigated = false;
    for (int guard = 0; guard < 300 && !non_directional_sound_investigated; ++guard) {
        idle_listener.Tick();
        const sim::SimulationSnapshot& snapshot = idle_listener.Snapshot();
        const sim::AgentSnapshot& listener = snapshot.agents[0];
        const sim::AgentSnapshot& source = snapshot.agents[2];
        const sim::SoundEventSnapshot* sound = LatestSound(snapshot,
            sim::SoundEventKind::Locomotion);
        if (sound != nullptr && sound->source_id == source.id &&
            sound->emitted_tick == snapshot.tick) {
            const double toward_x = static_cast<double>(listener.position.x - source.position.x);
            const double toward_z = static_cast<double>(listener.position.y - source.position.y);
            const double toward_dot = static_cast<double>(source.root_velocity.x) * toward_x +
                static_cast<double>(source.root_velocity.y) * toward_z;
            non_directional_sound_heard = non_directional_sound_heard ||
                (listener.perception.active_threat_count == 0U && toward_dot <= 0.0);
        }
        non_directional_sound_investigated = non_directional_sound_heard &&
            (listener.perception.sound_investigation_source_id == source.id ||
                listener.perception.recognized_threat_count > 0U);
    }
    Check(non_directional_sound_investigated,
        "an idle listener with no active threat must investigate an in-range enemy locomotion sound regardless of its direction");

    sim::SimulationConfig engaged_config = idle_config;
    engaged_config.villain_agent_count = 2U;
    engaged_config.opening_transforms = {
        {1U, {-10.0f, -4.0f, 0.0f}, -0.5f * kPiF},
        {2U, {20.0f, -4.0f, 0.0f}, 0.5f * kPiF},
        {3U, {-30.0f, -4.0f, 0.0f}, 0.5f * kPiF},
        {4U, {0.0f, -4.0f, 0.0f}, 0.5f * kPiF},
    };
    sim::Simulation engaged_listener(engaged_config, 5107U);

    bool away_sound_heard_while_engaged = false;
    bool away_sound_investigated_while_engaged = false;
    int ticks_after_away_sound = 0;
    for (int guard = 0; guard < 300 &&
         (!away_sound_heard_while_engaged || ticks_after_away_sound < 12); ++guard) {
        engaged_listener.Tick();
        const sim::SimulationSnapshot& snapshot = engaged_listener.Snapshot();
        const sim::AgentSnapshot& listener = snapshot.agents[0];
        const sim::SoundEventSnapshot* sound = LatestSound(snapshot,
            sim::SoundEventKind::Locomotion);
        if (sound != nullptr && sound->source_id == 4U &&
            sound->emitted_tick == snapshot.tick) {
            const sim::AgentSnapshot& source = snapshot.agents[3];
            const double toward_x = static_cast<double>(listener.position.x - source.position.x);
            const double toward_z = static_cast<double>(listener.position.y - source.position.y);
            const double toward_dot = static_cast<double>(source.root_velocity.x) * toward_x +
                static_cast<double>(source.root_velocity.y) * toward_z;
            away_sound_heard_while_engaged =
                listener.perception.active_threat_count > 0U && toward_dot <= 0.0;
        }
        if (away_sound_heard_while_engaged) {
            away_sound_investigated_while_engaged =
                away_sound_investigated_while_engaged ||
                listener.perception.sound_investigation_source_id == 4U;
            ++ticks_after_away_sound;
        }
    }
    Check(away_sound_heard_while_engaged && !away_sound_investigated_while_engaged,
        "a listener with an active threat must retain the running-toward direction filter for a new sound source");
}

void TestParryCancelsAttackAndDodgeDoesNot() {
    sim::SimulationConfig parry_config{};
    parry_config.mode = sim::SimulationMode::Paired;
    parry_config.hit_probability = 0.0f;
    parry_config.parry_probability = 1.0f;
    parry_config.parried_attack_cooldown_seconds = 1.5f;
    parry_config.attack_followup_probability = 0.0f;
    parry_config.drawn_sword_attack_probability = 0.9f;
    sim::Simulation parry(parry_config, 1337);
    int guard = 900;
    int defender_index = -1;
    while (--guard > 0 && defender_index < 0) {
        parry.Tick();
        for (int index = 0; index < 2; ++index) {
            if (parry.Snapshot().agents[index].reaction.kind == sim::ReactionKind::Parry) {
                defender_index = index;
                break;
            }
        }
    }
    Check(guard > 0, "a fully eligible 100 percent defense roll must eventually parry");
    if (defender_index >= 0) {
        parry.UpdateCombatOptions(parry.Config().attack_cooldown_seconds,
            parry.Config().parried_attack_cooldown_seconds, 1.0f,
            parry.Config().drawn_sword_attack_probability, parry.Config().parry_probability,
            parry.Config().sword_attack_stun_seconds, parry.Config().melee_attack_stun_seconds);
        const int attacker_index = 1 - defender_index;
        const sim::AgentSnapshot& attacker = parry.Snapshot().agents[attacker_index];
        const sim::AgentSnapshot& defender = parry.Snapshot().agents[defender_index];
        Check((attacker.action.kind == sim::ActionKind::SwordAttack ||
                attacker.action.kind == sim::ActionKind::MeleeAttack) && attacker.action.parried,
            "parry must cancel the attack result while preserving its simultaneous animation");
        Check(attacker.action.duration_seconds == defender.reaction.duration_seconds,
            "the attack and parry must use the same interval");
        const std::uint64_t parried_sequence = attacker.action.sequence;
        const std::uint32_t completed_before = attacker.completed_attacks;
        const float reaction_duration = parry.Snapshot().agents[defender_index].reaction.duration_seconds;
        Check(reaction_duration >= 0.4f && reaction_duration <= 1.034f,
            "the parry placeholder must retain the attack duration");
        while (guard > 0 && parry.Snapshot().agents[attacker_index].action.sequence == parried_sequence) {
            parry.Tick();
            --guard;
        }
        Check(guard > 0 && parry.Snapshot().agents[attacker_index].completed_attacks == completed_before,
            "a parried attack must finish visually without completing its gameplay result");
        Check(parry.Snapshot().agents[defender_index].reaction.kind == sim::ReactionKind::None,
            "the parry must end on the same tick as its attack");
        int ticks_until_next_attack = 0;
        while (ticks_until_next_attack < 90 &&
            parry.Snapshot().agents[attacker_index].action.kind != sim::ActionKind::SwordAttack &&
            parry.Snapshot().agents[attacker_index].action.kind != sim::ActionKind::MeleeAttack) {
            parry.Tick();
            ++ticks_until_next_attack;
        }
        Check(ticks_until_next_attack >= 45,
            "a parried attacker must wait the configured cooldown even at 100 percent follow-up");
    }

    sim::SimulationConfig dodge_config{};
    dodge_config.mode = sim::SimulationMode::Paired;
    dodge_config.hit_probability = 0.0f;
    dodge_config.parry_probability = 0.0f;
    dodge_config.attack_cooldown_seconds = 2.0f;
    dodge_config.attack_followup_probability = 0.0f;
    dodge_config.drawn_sword_attack_probability = 0.9f;
    sim::Simulation dodge(dodge_config, 1337);
    guard = 900;
    defender_index = -1;
    while (--guard > 0 && defender_index < 0) {
        dodge.Tick();
        for (int index = 0; index < 2; ++index) {
            if (dodge.Snapshot().agents[index].reaction.kind == sim::ReactionKind::Dodge) {
                defender_index = index;
                break;
            }
        }
    }
    Check(guard > 0, "a zero percent parry roll must eventually dodge");
    if (defender_index >= 0) {
        dodge.UpdateCombatOptions(dodge.Config().attack_cooldown_seconds,
            dodge.Config().parried_attack_cooldown_seconds, 1.0f,
            dodge.Config().drawn_sword_attack_probability, dodge.Config().parry_probability,
            dodge.Config().sword_attack_stun_seconds, dodge.Config().melee_attack_stun_seconds);
        const int attacker_index = 1 - defender_index;
        Check(dodge.Snapshot().agents[attacker_index].action.kind == sim::ActionKind::SwordAttack ||
            dodge.Snapshot().agents[attacker_index].action.kind == sim::ActionKind::MeleeAttack,
            "dodge must leave the incoming attack running");
        const std::uint64_t attack_sequence =
            dodge.Snapshot().agents[attacker_index].action.sequence;
        while (guard > 0 &&
            dodge.Snapshot().agents[attacker_index].action.sequence == attack_sequence) {
            dodge.Tick();
            --guard;
        }
        Check(guard > 0 &&
                dodge.Snapshot().agents[attacker_index].attack_cooldown_seconds_remaining == 0.0f,
            "a non-parried attack must bypass regular cooldown at 100 percent follow-up");
    }

    sim::SimulationConfig hit_config{};
    hit_config.mode = sim::SimulationMode::Paired;
    hit_config.hit_probability = 1.0f;
    hit_config.parry_probability = 1.0f;
    sim::Simulation hit(hit_config, 1337);
    guard = 900;
    defender_index = -1;
    while (--guard > 0 && defender_index < 0) {
        hit.Tick();
        for (int index = 0; index < 2; ++index) {
            if (hit.Snapshot().agents[index].reaction.kind == sim::ReactionKind::Hit) {
                defender_index = index;
                break;
            }
        }
    }
    Check(guard > 0, "a 100 percent hit roll must produce the passive hit outcome");
    if (defender_index >= 0) {
        const sim::AgentSnapshot& attacker = hit.Snapshot().agents[1 - defender_index];
        const sim::AgentSnapshot& defender = hit.Snapshot().agents[defender_index];
        Check((attacker.action.kind == sim::ActionKind::SwordAttack ||
                attacker.action.kind == sim::ActionKind::MeleeAttack) && !attacker.action.parried,
            "the hit outcome must be decided while the paired attack remains active");
        Check(defender.state != sim::AgentState::Stunned,
            "paired mode must not apply an automatic hit landing before Unreal reports it");
    }
}

void TestAutonomousHitLandingCancelsAndStuns() {
    bool verified = false;
    bool launch_verified = false;
    for (std::uint64_t seed = 1; seed <= 512 && !verified; ++seed) {
        sim::SimulationConfig config{};
        config.mode = sim::SimulationMode::Autonomous;
        config.hit_probability = 1.0f;
        sim::Simulation simulation(config, seed);
        int stunned_defender = -1;
        for (int tick = 0; tick < 900 && stunned_defender < 0; ++tick) {
            simulation.Tick();
            const auto& agents = simulation.Snapshot().agents;
            if (!launch_verified) {
                for (int defender = 0; defender < 2; ++defender) {
                    const int attacker = 1 - defender;
                    const bool attacker_active = agents[attacker].action.kind == sim::ActionKind::SwordAttack ||
                        agents[attacker].action.kind == sim::ActionKind::MeleeAttack;
                    if (agents[defender].reaction.kind != sim::ReactionKind::Hit || !attacker_active) continue;
                    const bool defender_attack_still_active =
                        agents[defender].action.kind == sim::ActionKind::SwordAttack ||
                        agents[defender].action.kind == sim::ActionKind::MeleeAttack;
                    const bool wounds_untouched = std::all_of(agents[defender].wounds.begin(),
                        agents[defender].wounds.end(), [](const sim::LimbWoundSnapshot& wound) {
                            return wound.condition == sim::LimbCondition::Normal && wound.gauge == 0.0f;
                        });
                    Check(defender_attack_still_active && agents[defender].state != sim::AgentState::Stunned &&
                            wounds_untouched && agents[attacker].action.progress < 1.0f,
                        "an autonomous hit must be chosen on launch without landing before the endpoint");
                    launch_verified = true;
                    break;
                }
            }
            for (int index = 0; index < 2; ++index) {
                if (agents[index].state == sim::AgentState::Stunned &&
                    agents[1 - index].state != sim::AgentState::Stunned) {
                    stunned_defender = index;
                    break;
                }
            }
        }
        if (stunned_defender < 0) continue;

        const sim::AgentSnapshot landed = simulation.Snapshot().agents[stunned_defender];
        Check(landed.action.kind == sim::ActionKind::None &&
                landed.state_seconds_remaining == 0.5f &&
                landed.speed_stick_amplitude == 0.0f,
            "an autonomous landed hit must cancel the defender attack and apply neutral stun input");
        for (int tick = 0; tick < 15; ++tick) simulation.Tick();
        const sim::AgentSnapshot resumed = simulation.Snapshot().agents[stunned_defender];
        Check(resumed.state != sim::AgentState::Stunned &&
                (resumed.action.kind == sim::ActionKind::SwordAttack ||
                    resumed.action.kind == sim::ActionKind::MeleeAttack),
            "a hit-canceled attack must receive no cooldown and may relaunch when stun expires");
        verified = true;
    }
    Check(launch_verified, "an autonomous attack launch must expose its hit decision immediately");
    Check(verified, "a deterministic autonomous seed must exercise a canceling mobile hit landing");
}

void TestStunnedDefenseUsesHitOrDodgeOnly() {
    const auto find_stunned_defense = [](float hit_probability, sim::ReactionKind expected) {
        for (std::uint64_t seed = 1; seed <= 512; ++seed) {
            sim::SimulationConfig config{};
            config.mode = sim::SimulationMode::Autonomous;
            config.hit_probability = hit_probability;
            config.parry_probability = 1.0f;
            config.sword_attack_stun_seconds.fill(3.0f);
            config.melee_attack_stun_seconds.fill(3.0f);
            sim::Simulation simulation(config, seed);
            for (int tick = 0; tick < 1200; ++tick) {
                simulation.Tick();
                const auto& agents = simulation.Snapshot().agents;
                for (int defender = 0; defender < 2; ++defender) {
                    const int attacker = 1 - defender;
                    if (agents[defender].state == sim::AgentState::Stunned &&
                        agents[defender].reaction.kind == expected &&
                        (agents[attacker].action.kind == sim::ActionKind::SwordAttack ||
                            agents[attacker].action.kind == sim::ActionKind::MeleeAttack) &&
                        agents[defender].reaction.elapsed_seconds <=
                            1.0f / config.tick_rate_hz + 1.0e-6f) {
                        return true;
                    }
                }
            }
        }
        return false;
    };

    Check(find_stunned_defense(0.0f, sim::ReactionKind::Dodge),
        "a stunned defender must dodge every defended outcome even with a 100 percent parry split");
    Check(find_stunned_defense(1.0f, sim::ReactionKind::Hit),
        "a stunned defender must retain the configured defense-hit probability");
}

void TestSeededAttackSelection() {
    std::array<bool, sim::kSwordAttackClipCount> sword_clips{};
    std::array<bool, sim::kMeleeAttackClipCount> melee_clips{};
    int sword_count = 0;
    int melee_count = 0;
    for (std::uint64_t seed = 1; seed <= 1024; ++seed) {
        sim::SimulationConfig config{};
        config.mode = sim::SimulationMode::Paired;
        sim::Simulation simulation(config, seed);
        int guard = 300;
        while (--guard > 0) {
            simulation.Tick();
            const sim::ActionSnapshot& action = simulation.Snapshot().agents[0].action;
            if (action.kind == sim::ActionKind::SwordAttack) {
                ++sword_count;
                if (action.animation_index < sword_clips.size()) sword_clips[action.animation_index] = true;
                break;
            }
            if (action.kind == sim::ActionKind::MeleeAttack) {
                ++melee_count;
                if (action.animation_index < melee_clips.size()) melee_clips[action.animation_index] = true;
                break;
            }
        }
        Check(guard > 0, "every seed must reach its first authored attack");
    }
    Check(sword_count > 750 && sword_count < 900 && melee_count > 100,
        "seeded attack selection must exercise the requested 80 percent sword and 20 percent melee split");
    Check(std::all_of(sword_clips.begin(), sword_clips.end(), [](bool seen) { return seen; }) &&
        std::all_of(melee_clips.begin(), melee_clips.end(), [](bool seen) { return seen; }),
        "seeded random selection must reach every authored sword and melee clip");
}

void TestAutonomousLimbWoundsAndStates() {
    std::array<bool, sim::kLimbCount> slash_injuries_seen{};
    bool melee_gauge_seen = false;
    bool slow_seen = false;
    bool torso_agony_seen = false;
    bool head_passed_out_seen = false;
    std::uint64_t torso_seed = 0;
    std::uint64_t head_seed = 0;
    std::uint64_t leg_seed = 0;
    int torso_agent = -1;
    int head_agent = -1;
    int leg_agent = -1;

    for (std::uint64_t seed = 1; seed <= 256; ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 30.0f;
        sim::Simulation simulation(config, seed);
        int guard = 300;
        bool wound_seen = false;
        while (--guard > 0 && !wound_seen) {
            simulation.Tick();
            for (const sim::AgentSnapshot& agent : simulation.Snapshot().agents) {
                for (const sim::LimbWoundSnapshot& wound : agent.wounds) {
                    wound_seen = wound_seen || wound.injured || wound.gauge > 0.0f;
                }
            }
        }
        Check(guard > 0, "every autonomous encounter must resolve its first undefended hit");
        for (std::size_t agent_index = 0; agent_index < simulation.Snapshot().agents.size(); ++agent_index) {
            const sim::AgentSnapshot& agent = simulation.Snapshot().agents[agent_index];
            int injured_count = 0;
            for (std::size_t index = 0; index < agent.wounds.size(); ++index) {
                const sim::LimbWoundSnapshot& wound = agent.wounds[index];
                if (wound.injured) {
                    ++injured_count;
                    slash_injuries_seen[index] = true;
                    Check(wound.condition == sim::LimbCondition::Injured &&
                        wound.gauge == 0.0f && wound.gauge_percent == 0.0f,
                        "a landed slash must advance its selected limb by exactly one stage");
                    if (index == static_cast<std::size_t>(sim::Limb::RightArm)) {
                        Check(agent.sword_state == sim::SwordState::Dropped,
                            "right-arm injury must drop a drawn sword at the injury location");
                    }
                } else if (wound.gauge > 0.0f) {
                    melee_gauge_seen = true;
                    const float expected = config.melee_wound_gain -
                        config.wound_decay_per_second / config.tick_rate_hz;
                    Check(std::fabs(wound.gauge - expected) < 0.001f,
                        "a landed melee must add 20 percentage points before lazy decay");
                    Check(std::fabs(wound.gauge_percent - wound.gauge) < 0.001f,
                        "the default threshold must expose the current-stage gauge as a percentage");
                }
            }
            if (injured_count == 1) {
                const bool head = agent.wounds[static_cast<std::size_t>(sim::Limb::Head)].injured;
                const bool torso = agent.wounds[static_cast<std::size_t>(sim::Limb::Torso)].injured;
                const bool left_leg = agent.wounds[static_cast<std::size_t>(sim::Limb::LeftLeg)].injured;
                const bool right_leg = agent.wounds[static_cast<std::size_t>(sim::Limb::RightLeg)].injured;
                if (head) {
                    head_passed_out_seen = true;
                    if (head_seed == 0) {
                        head_seed = seed;
                        head_agent = static_cast<int>(agent_index);
                    }
                    Check(agent.state == sim::AgentState::PassedOut &&
                        agent.state_seconds_remaining > 29.0f && agent.state_seconds_remaining <= 30.0f,
                        "head injury must enter the configured 30-second passed-out state");
                } else if (torso) {
                    torso_agony_seen = true;
                    if (torso_seed == 0) {
                        torso_seed = seed;
                        torso_agent = static_cast<int>(agent_index);
                    }
                    Check(agent.state == sim::AgentState::Agonising &&
                        agent.state_seconds_remaining > 9.0f && agent.state_seconds_remaining <= 10.0f,
                        "torso injury must enter the configured 10-second agony state");
                } else if (left_leg || right_leg) {
                    slow_seen = true;
                    if (leg_seed == 0) {
                        leg_seed = seed;
                        leg_agent = static_cast<int>(agent_index);
                    }
                    Check(agent.state == sim::AgentState::Stunned &&
                            agent.state_seconds_remaining == 0.5f,
                        "a leg hit must apply stun before the injured-leg slow state resumes");
                }
            }
        }
    }
    Check(std::all_of(slash_injuries_seen.begin(), slash_injuries_seen.end(),
            [](bool seen) { return seen; }),
        "uniform deterministic slash selection must reach all six limbs across seeds");
    Check(melee_gauge_seen, "seeded autonomous melee hits must exercise the growing gauge path");
    Check(slow_seen && torso_agony_seen && head_passed_out_seen,
        "seeded autonomous slash hits must exercise slow, agonising, and passed-out states");

    const auto check_timed_transition = [](std::uint64_t seed, int agent_index,
                                           sim::AgentState timed_state, int duration_ticks,
                                           const char* message) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 30.0f;
        config.sound_maximum_range_m = 30.0f;
        sim::Simulation simulation(config, seed);
        int guard = 300;
        while (--guard > 0 && simulation.Snapshot().agents[agent_index].state != timed_state) {
            simulation.Tick();
        }
        Check(guard > 0, message);
        for (int tick = 1; tick < duration_ticks; ++tick) simulation.Tick();
        Check(simulation.Snapshot().agents[agent_index].state == timed_state,
            "timed wound state must remain active until its final fixed step");
        simulation.Tick();
        const sim::AgentSnapshot& crawling = simulation.Snapshot().agents[agent_index];
        Check(crawling.state == sim::AgentState::Crawling &&
                crawling.locomotion_mode == sim::LocomotionMode::Crawl &&
                crawling.speed_stick_amplitude == 0.0f &&
                crawling.behavior_mode == sim::BehaviorMode::Idle &&
                crawling.attack_target_id == sim::kInvalidEntityId &&
                crawling.head_look_mode == sim::HeadLookMode::RootHeading &&
                crawling.head_look_target_id == sim::kInvalidEntityId &&
                !crawling.perception.scanning,
            "timed wound state must enter out-of-combat crawling on its exact configured tick");

        const sim::Team crawling_team = crawling.team;
        const sim::Team enemy_team = crawling_team == sim::Team::Hero
            ? sim::Team::Villain
            : sim::Team::Hero;
        Check(simulation.SetAgentTransform({crawling.id, {0.0f, 0.0f, 0.0f}, 0.0f}),
            "the crawling sound regression must orient its listener away from the source");
        const std::vector<sim::AgentSnapshot> existing_agents = simulation.Snapshot().agents;
        for (const sim::AgentSnapshot& agent : existing_agents) {
            if (agent.id == crawling.id) continue;
            Check(simulation.SetAgentTransform({agent.id, {40.0f, -40.0f, 0.0f}, 0.0f}),
                "the crawling sound regression must move the old combatant away");
        }
        const sim::EntityId bait_id = simulation.SpawnTransientAgent(
            crawling_team, {0.0f, 10.0f, 0.0f}, 3.14159265358979323846f);
        const sim::EntityId sound_source_id = simulation.SpawnTransientAgent(
            enemy_team, {0.0f, -2.0f, 0.0f}, 0.0f);
        Check(bait_id != sim::kInvalidEntityId && sound_source_id != sim::kInvalidEntityId,
            "the crawling sound regression must spawn a runner and its standing target");

        bool investigated_sound = false;
        bool returned_to_heading = false;
        bool forbidden_scan_or_combat = false;
        for (int tick = 0; tick < 180 && !returned_to_heading; ++tick) {
            simulation.Tick();
            const sim::AgentSnapshot& listener = simulation.Snapshot().agents[agent_index];
            forbidden_scan_or_combat = forbidden_scan_or_combat ||
                listener.perception.scanning ||
                listener.head_look_mode == sim::HeadLookMode::SearchScan ||
                listener.behavior_mode != sim::BehaviorMode::Idle ||
                listener.attack_target_id != sim::kInvalidEntityId ||
                listener.action.kind == sim::ActionKind::SwordAttack ||
                listener.action.kind == sim::ActionKind::MeleeAttack;
            if (listener.head_look_mode == sim::HeadLookMode::SoundInvestigation &&
                listener.head_look_target_id == sound_source_id) {
                investigated_sound = true;
            } else if (investigated_sound &&
                listener.head_look_mode == sim::HeadLookMode::RootHeading) {
                returned_to_heading = true;
            }
        }
        Check(investigated_sound && returned_to_heading,
            "a crawling agent must turn to a heard approaching enemy, then return to root heading");
        Check(!forbidden_scan_or_combat,
            "sound investigation must not re-enable crawl scanning, targeting, or attacks");
    };
    if (torso_seed != 0 && torso_agent >= 0) {
        check_timed_transition(torso_seed, torso_agent, sim::AgentState::Agonising, 300,
            "the recorded torso seed must reproduce agony");
    }
    if (head_seed != 0 && head_agent >= 0) {
        check_timed_transition(head_seed, head_agent, sim::AgentState::PassedOut, 900,
            "the recorded head seed must reproduce passed out");
    }
    if (leg_seed != 0 && leg_agent >= 0) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 30.0f;
        sim::Simulation simulation(config, leg_seed);
        int guard = 300;
        while (--guard > 0 && simulation.Snapshot().agents[leg_agent].state != sim::AgentState::Stunned) {
            simulation.Tick();
        }
        Check(guard > 0, "the recorded leg seed must reproduce stun");
        for (int tick = 0; tick < 15; ++tick) simulation.Tick();
        Check(simulation.Snapshot().agents[leg_agent].state == sim::AgentState::Slow,
            "one injured leg must resume in slow state after stun expires");
    }

    bool both_legs_seen = false;
    for (std::uint64_t seed = 1; seed <= 128 && !both_legs_seen; ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 0.0f;
        sim::Simulation simulation(config, seed);
        for (int tick = 0; tick < 1200 && !both_legs_seen; ++tick) {
            simulation.Tick();
            for (const sim::AgentSnapshot& agent : simulation.Snapshot().agents) {
                const bool both_legs =
                    agent.wounds[static_cast<std::size_t>(sim::Limb::LeftLeg)].injured &&
                    agent.wounds[static_cast<std::size_t>(sim::Limb::RightLeg)].injured;
                const bool other_critical =
                    agent.wounds[static_cast<std::size_t>(sim::Limb::Head)].injured ||
                    agent.wounds[static_cast<std::size_t>(sim::Limb::Torso)].injured;
                if (both_legs && !other_critical) {
                    both_legs_seen = true;
                    Check(agent.state == sim::AgentState::Agonising &&
                        agent.state_seconds_remaining > 2.0f && agent.state_seconds_remaining <= 3.0f,
                        "both injured legs must trigger the configured three-second agony");
                    break;
                }
            }
        }
    }
    Check(both_legs_seen, "seeded autonomous hits must exercise the both-legs transition");

    sim::SimulationConfig paired_config{};
    paired_config.mode = sim::SimulationMode::Paired;
    paired_config.hit_probability = 1.0f;
    sim::Simulation paired(paired_config, 1337);
    for (int tick = 0; tick < 300; ++tick) paired.Tick();
    for (const sim::AgentSnapshot& agent : paired.Snapshot().agents) {
        for (const sim::LimbWoundSnapshot& wound : agent.wounds) {
            Check(wound.condition == sim::LimbCondition::Normal &&
                    !wound.injured && !wound.badly_injured && wound.gauge == 0.0f,
                "paired mode must defer wound confirmation instead of resolving autonomous damage");
        }
    }
}

void TestStagedVitalWoundsAndDeadTargetDisengagement() {
    bool badly_injured_vital_seen = false;
    bool dead_seen = false;
    bool survivor_disengaged = false;
    for (std::uint64_t seed = 1; seed <= 128 && !survivor_disengaged; ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 0.0f;
        config.melee_wound_gain = 100.0f;
        config.wound_decay_per_second = 0.0f;
        sim::Simulation simulation(config, seed);
        for (int tick = 0; tick < 4000; ++tick) {
            simulation.Tick();
            for (const sim::AgentSnapshot& agent : simulation.Snapshot().agents) {
                const sim::LimbWoundSnapshot& head =
                    agent.wounds[static_cast<std::size_t>(sim::Limb::Head)];
                const sim::LimbWoundSnapshot& torso =
                    agent.wounds[static_cast<std::size_t>(sim::Limb::Torso)];
                if (agent.state != sim::AgentState::Dead &&
                    (head.condition == sim::LimbCondition::BadlyInjured ||
                        torso.condition == sim::LimbCondition::BadlyInjured)) {
                    badly_injured_vital_seen = true;
                    Check(agent.state == sim::AgentState::PassedOut ||
                            agent.state == sim::AgentState::Agonising,
                        "a badly injured vital must remain grounded without entering crawl");
                }
                if (agent.state == sim::AgentState::Dead) {
                    dead_seen = true;
                    Check((head.condition == sim::LimbCondition::BadlyInjured &&
                            head.gauge_percent == 100.0f) ||
                            (torso.condition == sim::LimbCondition::BadlyInjured &&
                                torso.gauge_percent == 100.0f),
                        "death must require a third full gauge on a badly injured head or torso");
                }
            }
            if (!dead_seen) continue;

            simulation.Tick();
            const sim::SimulationSnapshot& settled = simulation.Snapshot();
            int survivor_index = -1;
            for (std::size_t index = 0; index < settled.agents.size(); ++index) {
                const sim::AgentSnapshot& agent = settled.agents[index];
                const sim::AgentSnapshot& opponent = settled.agents[1U - index];
                if (agent.state == sim::AgentState::Dead) {
                    Check(agent.behavior_mode == sim::BehaviorMode::Idle &&
                            agent.attack_target_id == sim::kInvalidEntityId,
                        "a dead agent must have no active target or attack behavior");
                } else if (opponent.state == sim::AgentState::Dead) {
                    survivor_disengaged = true;
                    survivor_index = static_cast<int>(index);
                    Check(agent.attack_target_id == sim::kInvalidEntityId &&
                            agent.speed_stick_amplitude == 0.0f,
                    "a survivor must stop and clear a dead opponent on the next fixed step");
                }
            }
            const std::vector<sim::AgentSnapshot> frozen = settled.agents;
            bool survivor_idled_after_scan = survivor_index < 0;
            for (int frozen_tick = 0; frozen_tick < 60; ++frozen_tick) {
                simulation.Tick();
                if (survivor_index >= 0 &&
                    simulation.Snapshot().agents[static_cast<std::size_t>(survivor_index)].behavior_mode ==
                        sim::BehaviorMode::Idle) {
                    survivor_idled_after_scan = true;
                }
            }
            Check(survivor_idled_after_scan,
                "a survivor must idle after one bounded left-right search finds no living opponent");
            for (std::size_t index = 0; index < frozen.size(); ++index) {
                if (frozen[index].state != sim::AgentState::Dead) continue;
                const sim::AgentSnapshot& after = simulation.Snapshot().agents[index];
                Check(after.position.x == frozen[index].position.x &&
                        after.position.y == frozen[index].position.y &&
                        after.position.z == frozen[index].position.z &&
                        after.facing_radians == frozen[index].facing_radians &&
                        after.root_speed_mps == 0.0f && after.pose_phase == frozen[index].pose_phase,
                    "a dead agent must keep an exact fixed root and pose phase across later ticks");
            }
            break;
        }
    }
    Check(badly_injured_vital_seen,
        "seeded combat must expose a living badly injured vital before lethal damage");
    Check(dead_seen, "a third vital gauge must eventually produce a dead agent");
    Check(survivor_disengaged, "seeded combat must expose a survivor disengaging from a dead target");
}

void TestGroundedHitsOnlyChangeVitals() {
    bool focused_hit_seen = false;
    for (std::uint64_t seed = 1; seed <= 256 && !focused_hit_seen; ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 30.0f;
        config.attack_followup_probability = 0.0f;
        config.wound_decay_per_second = 0.0f;
        sim::Simulation simulation(config, seed);
        int tracked = -1;
        std::array<sim::LimbWoundSnapshot, sim::kLimbCount> before{};
        for (int tick = 0; tick < 5000 && !focused_hit_seen; ++tick) {
            if (tracked < 0) {
                for (int index = 0; index < 2; ++index) {
                    const sim::AgentState state = simulation.Snapshot().agents[index].state;
                    const bool grounded = state == sim::AgentState::Agonising ||
                        state == sim::AgentState::PassedOut || state == sim::AgentState::Crawling;
                    if (grounded &&
                        simulation.Snapshot().agents[1 - index].state != sim::AgentState::Dead) {
                        tracked = index;
                        before = simulation.Snapshot().agents[index].wounds;
                        break;
                    }
                }
            }
            simulation.Tick();
            if (tracked < 0) continue;

            const auto& after = simulation.Snapshot().agents[tracked].wounds;
            const bool head_changed = after[static_cast<std::size_t>(sim::Limb::Head)].condition !=
                    before[static_cast<std::size_t>(sim::Limb::Head)].condition ||
                after[static_cast<std::size_t>(sim::Limb::Head)].gauge !=
                    before[static_cast<std::size_t>(sim::Limb::Head)].gauge;
            const bool torso_changed = after[static_cast<std::size_t>(sim::Limb::Torso)].condition !=
                    before[static_cast<std::size_t>(sim::Limb::Torso)].condition ||
                after[static_cast<std::size_t>(sim::Limb::Torso)].gauge !=
                    before[static_cast<std::size_t>(sim::Limb::Torso)].gauge;
            if (!head_changed && !torso_changed) continue;

            focused_hit_seen = true;
            const sim::AgentSnapshot& finisher = simulation.Snapshot().agents[1 - tracked];
            Check(finisher.attack_cooldown_seconds_remaining > 0.0f &&
                    !finisher.cooldown_strafe &&
                    finisher.cooldown_strafe_target_distance_m == 0.0f,
                "grounded finishing must retain cooldown timing without lateral cooldown movement");
            for (sim::Limb limb : {sim::Limb::LeftArm, sim::Limb::RightArm,
                     sim::Limb::LeftLeg, sim::Limb::RightLeg}) {
                const std::size_t index = static_cast<std::size_t>(limb);
                Check(after[index].condition == before[index].condition &&
                        after[index].gauge == before[index].gauge,
                    "a hit launched at a grounded defender must not change an outer limb");
            }
        }
    }
    Check(focused_hit_seen,
        "seeded combat must exercise a grounded hit focused on torso or head");
}

void TestGroundedAttackWeaponRules() {
    std::array<bool, 3> grounded_sword_clips{};
    bool fallback_kick_seen = false;
    const auto all_grounded_sword_clips_seen = [&grounded_sword_clips]() {
        return std::all_of(grounded_sword_clips.begin(), grounded_sword_clips.end(),
            [](bool seen) { return seen; });
    };
    for (std::uint64_t seed = 1; seed <= 2048 &&
         (!all_grounded_sword_clips_seen() || !fallback_kick_seen); ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 0.0f;
        config.melee_wound_gain = 100.0f;
        config.wound_decay_per_second = 0.0f;
        config.leg_agonising_seconds = 0.0f;
        config.torso_agonising_seconds = 0.0f;
        config.head_passed_out_seconds = 0.0f;
        sim::Simulation simulation(config, seed);

        for (int tick = 0; tick < 1200 &&
             (!all_grounded_sword_clips_seen() || !fallback_kick_seen); ++tick) {
            const std::vector<sim::AgentSnapshot> before = simulation.Snapshot().agents;
            simulation.Tick();
            const auto& after = simulation.Snapshot().agents;
            for (std::size_t attacker_index = 0; attacker_index < before.size(); ++attacker_index) {
                const sim::AgentSnapshot& prior_attacker = before[attacker_index];
                if (prior_attacker.attack_target_id == sim::kInvalidEntityId ||
                    prior_attacker.attack_target_id > before.size()) continue;
                const sim::AgentSnapshot& prior_target =
                    before[static_cast<std::size_t>(prior_attacker.attack_target_id - 1U)];
                const bool grounded = prior_target.state == sim::AgentState::Agonising ||
                    prior_target.state == sim::AgentState::PassedOut ||
                    prior_target.state == sim::AgentState::Crawling;
                const sim::AgentSnapshot& current_attacker = after[attacker_index];
                const bool new_attack = current_attacker.action.sequence !=
                        prior_attacker.action.sequence &&
                    (current_attacker.action.kind == sim::ActionKind::SwordAttack ||
                        current_attacker.action.kind == sim::ActionKind::MeleeAttack);
                if (!grounded || !new_attack) continue;

                const bool right_arm_usable = prior_attacker.wounds[
                    static_cast<std::size_t>(sim::Limb::RightArm)].condition ==
                    sim::LimbCondition::Normal;
                const bool usable_sword = prior_attacker.sword_equipped &&
                    prior_attacker.sword_state == sim::SwordState::Drawn && right_arm_usable;
                if (usable_sword) {
                    Check(current_attacker.action.kind == sim::ActionKind::SwordAttack,
                        "an agent with a usable drawn sword must only use sword attacks against a grounded target");
                    const std::uint8_t clip = current_attacker.action.animation_index;
                    const bool allowed = clip == 6U || clip == 4U || clip == 1U;
                    Check(allowed,
                        "grounded sword finishing must use only pike, slashRD, or slashLD");
                    if (clip == 6U) {
                        grounded_sword_clips[0] = true;
                    }
                    else if (clip == 4U) grounded_sword_clips[1] = true;
                    else if (clip == 1U) grounded_sword_clips[2] = true;
                } else {
                    fallback_kick_seen = true;
                    Check(current_attacker.action.kind == sim::ActionKind::MeleeAttack &&
                            (current_attacker.action.animation_index == 5U ||
                                current_attacker.action.animation_index == 6U),
                        "an agent without a usable sword must only use authored kicks against a grounded target");
                }
            }
        }
    }
    Check(all_grounded_sword_clips_seen(),
        "seeded combat must exercise pike, slashRD, and slashLD grounded finishing");
    Check(fallback_kick_seen,
        "seeded combat must exercise kick-only finishing after sword use becomes unavailable");
}

void TestMoverDrivenMotionAndFutureRoots() {
    sim::Simulation simulation({}, 42);
    const sim::SimulationSnapshot initial = simulation.Snapshot();
    for (int tick = 0; tick < 45; ++tick) simulation.Tick();
    const sim::SimulationSnapshot& moved = simulation.Snapshot();
    Check(moved.tick == 45U, "fixed-step ticks must advance monotonically");
    Check(std::fabs(moved.time_seconds - 1.5) < 1.0e-9,
        "simulation time must derive exactly from the 30 Hz tick");
    Check(!EqualAgents(initial, moved), "attack-mode stick commands must produce mover-authored root motion");
    for (const sim::AgentSnapshot& agent : moved.agents) {
        Check(agent.root_speed_mps > 0.0f, "each locomotion agent must publish nonzero root speed");
        Check(agent.future_roots.size() == sim::kFutureRootWindow,
            "each locomotion agent must publish exactly eight future roots");
        Check(agent.future_roots.front().position.x != static_cast<double>(agent.position.x) ||
            agent.future_roots.front().position.z != static_cast<double>(agent.position.y),
            "the first future root must advance from the current root");
    }
}

void TestLocomotionPrimitives() {
    Check(sim::DirectionFromAngle(0.0).x == 0.0 && sim::DirectionFromAngle(0.0).z == 1.0,
        "zero stick angle must use the dataset's positive-Z convention");
    Check(std::fabs(sim::DirectionalSpeedCap(sim::LocomotionMode::Walk, 0.0) - 2.0000178813934326) < 1.0e-12,
        "walk forward cap must match the source dataset");
    Check(std::fabs(sim::DirectionalSpeedCap(sim::LocomotionMode::Run, 0.0) - 5.0) < 1.0e-12,
        "run forward cap must match the source dataset");
    Check(std::fabs(sim::DirectionalSpeedCap(sim::LocomotionMode::Crawl, 0.0) -
            sim::DirectionalSpeedCap(sim::LocomotionMode::Walk, 0.0)) < 1.0e-12 &&
            std::string_view(sim::ToString(sim::LocomotionMode::Crawl)) == "Crawl",
        "crawl must derive its directional speed profile from Walk while remaining inspectable");
    sim::LocomotionState state{};
    sim::LocomotionIntent intent{sim::LocomotionMode::Run, 0.0, 1.0, 0.0};
    sim::StepLocomotion(state, intent, 1.0 / 30.0);
    Check(state.position.z > 0.0 && state.velocity.z > 0.0,
        "forward run stick must infer forward root motion");

    sim::LocomotionState walk_speed{};
    sim::LocomotionState crawl_speed{};
    const sim::LocomotionIntent walk_intent{
        sim::LocomotionMode::Walk, 0.0, 1.0, 0.0, 1.0, 1.0};
    const sim::LocomotionIntent crawl_intent{
        sim::LocomotionMode::Crawl, 0.0, 1.0, 0.0, 0.2, 0.2};
    for (int tick = 0; tick < 300; ++tick) {
        sim::StepLocomotion(walk_speed, walk_intent, 1.0 / 30.0);
        sim::StepLocomotion(crawl_speed, crawl_intent, 1.0 / 30.0);
    }
    const double walk_velocity = std::hypot(walk_speed.velocity.x, walk_speed.velocity.z);
    const double crawl_velocity = std::hypot(crawl_speed.velocity.x, crawl_speed.velocity.z);
    Check(std::fabs(crawl_velocity / walk_velocity - 0.2) < 0.001,
        "the crawl controller must cap root speed at its configured fraction of Walk");

    sim::LocomotionState walk_turn{};
    sim::LocomotionState crawl_turn{};
    sim::LocomotionIntent turning_walk = walk_intent;
    sim::LocomotionIntent turning_crawl = crawl_intent;
    turning_walk.orientation_yaw_radians = 1.57079632679489661923;
    turning_crawl.orientation_yaw_radians = turning_walk.orientation_yaw_radians;
    sim::StepLocomotion(walk_turn, turning_walk, 1.0 / 30.0);
    sim::StepLocomotion(crawl_turn, turning_crawl, 1.0 / 30.0);
    Check(std::fabs(crawl_turn.yaw_radians) < std::fabs(walk_turn.yaw_radians) &&
            std::fabs(crawl_turn.yaw_radians / walk_turn.yaw_radians - 0.2) < 0.001,
        "the crawl controller must scale the normal mover's root turn by its configured fraction");
}

void TestEditableOpeningTransformsAndReplay() {
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    config.opening_transforms = {
        {1U, {-6.0f, 2.0f, 0.0f}, 0.25f},
        {2U, {4.0f, -3.0f, 0.0f}, -0.75f},
    };
    sim::Simulation simulation(config, 6060);
    Check(simulation.Snapshot().agents[0].position.x == -6.0f &&
            simulation.Snapshot().agents[0].position.y == 2.0f &&
            simulation.Snapshot().agents[0].facing_radians == 0.25f &&
            simulation.Snapshot().agents[1].position.x == 4.0f &&
            simulation.Snapshot().agents[1].position.y == -3.0f,
        "configured opening transforms must replace the generated formation at tick zero");

    for (int tick = 0; tick < 50; ++tick) simulation.Tick();
    const sim::Vec3 velocity_before = simulation.Snapshot().agents[0].root_velocity;
    Check(simulation.SetAgentTransform({1U, {7.0f, -4.0f, 0.0f}, 1.1f}),
        "a valid live agent transform must be editable");
    Check(simulation.SetAgentTransform({1U, {8.0f, -3.0f, 0.0f}, 1.2f}),
        "a second edit on the same paused tick must be accepted");
    const sim::AgentSnapshot edited = simulation.Snapshot().agents[0];
    Check(edited.position.x == 8.0f && edited.position.y == -3.0f &&
            edited.facing_radians == 1.2f &&
            edited.root_velocity.x == velocity_before.x &&
            edited.root_velocity.y == velocity_before.y &&
            edited.root_velocity.z == velocity_before.z,
        "paused transform edits must preserve the mover's current velocity exactly");
#if PROPHECY_ENABLE_REWIND
    Check(simulation.RecordedReplay().transform_events.size() == 1U &&
            simulation.RecordedReplay().transform_events[0].tick == 50U &&
            simulation.RecordedReplay().transform_events[0].transform.position.x == 8.0f,
        "same-agent edits on one paused tick must coalesce to the final transform event");
#endif

    for (int tick = 0; tick < 20; ++tick) simulation.Tick();
    const sim::SimulationSnapshot expected = simulation.Snapshot();
    const sim::ReplayLog tape = simulation.RecordedReplay();
#if PROPHECY_ENABLE_REWIND
    Check(simulation.SeekReplay(tape, expected.tick) && EqualAgents(simulation.Snapshot(), expected),
        "replay must reproduce movement after an exact-tick transform edit");
    Check(simulation.BranchRecordingFromReplay(),
        "a paused replay tick must be able to become a new deterministic edit branch");
#endif

    std::vector<sim::AgentTransform> saved_opening;
    for (const sim::AgentSnapshot& agent : simulation.Snapshot().agents) {
        saved_opening.push_back({agent.id, agent.position, agent.facing_radians});
    }
    const sim::Vec3 saved_first_position = saved_opening.front().position;
    Check(simulation.SetOpeningTransforms(std::move(saved_opening)),
        "a complete opening layout must be accepted for the next reset");
    simulation.Reset(simulation.Seed());
    Check(simulation.Snapshot().agents[0].position.x == saved_first_position.x &&
            simulation.Snapshot().agents[0].position.y == saved_first_position.y,
        "reset must begin from the saved opening layout");

    sim::Simulation group_edit(config, 6061);
    for (int tick = 0; tick < 12; ++tick) group_edit.Tick();
    const sim::SimulationSnapshot before_group_edit = group_edit.Snapshot();
    const std::vector<sim::AgentTransform> group_transforms{
        {1U, {-2.0f, 5.0f, 0.0f}, -0.4f},
        {2U, {3.0f, 6.0f, 0.0f}, 0.9f},
    };
    Check(group_edit.SetAgentTransforms(group_transforms),
        "a complete valid transform batch must be accepted atomically");
    Check(group_edit.Snapshot().agents[0].position.x == -2.0f &&
            group_edit.Snapshot().agents[0].position.y == 5.0f &&
            group_edit.Snapshot().agents[1].position.x == 3.0f &&
            group_edit.Snapshot().agents[1].position.y == 6.0f &&
            group_edit.Snapshot().agents[0].root_velocity.x ==
                before_group_edit.agents[0].root_velocity.x &&
            group_edit.Snapshot().agents[1].root_velocity.y ==
                before_group_edit.agents[1].root_velocity.y,
        "a group transform must move every member while preserving mover velocity");
    const sim::SimulationSnapshot valid_group_edit = group_edit.Snapshot();
    const std::vector<sim::AgentTransform> duplicate_ids{
        {1U, {10.0f, 10.0f, 0.0f}, 0.0f},
        {1U, {-10.0f, -10.0f, 0.0f}, 0.0f},
    };
    Check(!group_edit.SetAgentTransforms(duplicate_ids) &&
            EqualAgents(group_edit.Snapshot(), valid_group_edit),
        "an invalid group transform must reject the whole batch without partial movement");
#if PROPHECY_ENABLE_REWIND
    group_edit.Tick();
    const sim::SimulationSnapshot replayed_group_edit = group_edit.Snapshot();
    const sim::ReplayLog group_tape = group_edit.RecordedReplay();
    Check(group_tape.transform_events.size() == 2U,
        "a group transform must record one replay event per member");
    Check(group_edit.SeekReplay(group_tape, replayed_group_edit.tick) &&
            EqualAgents(group_edit.Snapshot(), replayed_group_edit),
        "replay must reproduce movement following a group transform");
#endif
}

void TestReplayAndReset() {
    sim::Simulation simulation({}, 2026);
    for (int tick = 0; tick < 137; ++tick) simulation.Tick();
    const sim::SimulationSnapshot expected = simulation.Snapshot();
    for (int tick = 137; tick < 400; ++tick) simulation.Tick();
    const sim::ReplayLog tape = simulation.RecordedReplay();
#if PROPHECY_ENABLE_REWIND
    Check(tape.seed == 2026U && tape.end_tick == 400U, "rewind tape must retain seed and live head tick");
    Check(simulation.SeekReplay(tape, 137U), "an in-range locomotion tick must be seekable");
    Check(simulation.Snapshot().tick == 137U && EqualAgents(simulation.Snapshot(), expected),
        "replay must reproduce the exact root and future-window state at a requested tick");
    Check(!simulation.SeekReplay(tape, 401U), "replay seek must reject ticks beyond the recorded head");
    Check(simulation.SeekReplay(tape, tape.end_tick), "the live head must be replayable");
    Check(simulation.ResumeRecordingFromReplay(), "recording must resume at the replay head");
#else
    Check(tape.end_tick == 0U && !simulation.IsReplaying(),
        "shipping builds must carry no rewind history or replay state");
#endif
    simulation.Reset(2026);
    Check(simulation.Snapshot().tick == 0U, "reset must return to tick zero");
    Check(simulation.RecordedReplay().end_tick == 0U, "reset must clear the rewind head");
}

void TestTransientSpawnsDoNotEnterReplay() {
    sim::Simulation simulation({}, 1337);
    const sim::EntityId villain_id = simulation.SpawnTransientAgent(
        sim::Team::Villain, {3.0f, 4.0f, 0.0f}, 0.75f);
    Check(villain_id == 3U && simulation.HasTransientAgents() &&
        simulation.Config().agent_count == 2U && simulation.Snapshot().agents.size() == 3U,
        "a transient spawn must append to live state without changing persistent team counts");
    const sim::AgentSnapshot& villain = simulation.Snapshot().agents.back();
    Check(villain.team == sim::Team::Villain && villain.position.x == 3.0f &&
        villain.position.y == 4.0f && villain.facing_radians == 0.75f,
        "a transient spawn must preserve its requested team, ground point, and facing");
    Check(villain.state == sim::AgentState::Normal && villain.sword_equipped &&
        villain.sword_state == sim::SwordState::Sheathed,
        "a transient spawn must start normal, equipped, and undrawn");

    for (int tick = 0; tick < 8; ++tick) simulation.Tick();
#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog tape = simulation.RecordedReplay();
    Check(simulation.SeekReplay(tape, tape.end_tick) &&
        !simulation.HasTransientAgents() && simulation.Snapshot().agents.size() == 2U,
        "replaying the live tick must reconstruct the timeline without transient spawns");
#else
    simulation.Reset(simulation.Seed());
    Check(!simulation.HasTransientAgents() && simulation.Snapshot().agents.size() == 2U,
        "a shipping reset must discard transient spawns when replay is compiled out");
#endif

    const sim::EntityId hero_id = simulation.SpawnTransientAgent(
        sim::Team::Hero, {-3.0f, -4.0f, 0.0f}, -0.5f);
    Check(hero_id == 3U && simulation.Snapshot().agents.back().team == sim::Team::Hero,
        "a transient Hero must use the next live ID after replay reconstruction");
    simulation.Reset(simulation.Seed());
    Check(!simulation.HasTransientAgents() && simulation.Snapshot().agents.size() == 2U,
        "reset must discard every transient spawn");
}

void TestCheckpointReplay() {
#if PROPHECY_ENABLE_REWIND
    sim::Simulation simulation({}, 4040);
    for (int tick = 0; tick < 120; ++tick) simulation.Tick();
    simulation.UpdateCombatOptions(2.0f, 2.5f, 0.5f, 0.8f, 0.75f,
        sim::kDefaultSwordAttackStunSeconds, sim::kDefaultMeleeAttackStunSeconds);
    std::unique_ptr<sim::Simulation> checkpoint = simulation.CreateRewindCheckpoint();
    for (int tick = 120; tick < 160; ++tick) simulation.Tick();
    simulation.UpdateWoundOptions(25.0f, 90.0f, 2.0f, 4.0f, 12.0f, 35.0f);
    for (int tick = 160; tick < 197; ++tick) simulation.Tick();
    const sim::SimulationSnapshot expected = simulation.Snapshot();
    for (int tick = 197; tick < 600; ++tick) simulation.Tick();
    const sim::ReplayLog tape = simulation.RecordedReplay();

    Check(simulation.RestoreRewindCheckpoint(*checkpoint, tape),
        "a runtime checkpoint must restore against the completed replay tape");
    while (simulation.Snapshot().tick < expected.tick) simulation.Tick();
    Check(EqualAgents(simulation.Snapshot(), expected),
        "checkpoint replay must reproduce exact agent state after later deterministic inputs");
    Check(simulation.Config().attack_cooldown_seconds == 2.0f &&
        simulation.Config().wound_threshold == 90.0f,
        "checkpoint replay must retain earlier options and apply later option events");
#endif
}

void TestCheckpointSeekPerformance() {
#if PROPHECY_ENABLE_REWIND
    sim::Simulation simulation({}, 5050);
    std::vector<std::unique_ptr<sim::Simulation>> checkpoints;
    checkpoints.reserve(601);
    checkpoints.push_back(simulation.CreateRewindCheckpoint());
    for (int tick = 1; tick <= 18'000; ++tick) {
        simulation.Tick();
        if (tick % 30 == 0) checkpoints.push_back(simulation.CreateRewindCheckpoint());
    }
    const sim::ReplayLog tape = simulation.RecordedReplay();
    const auto start = std::chrono::steady_clock::now();
    for (std::size_t index = checkpoints.size(); index-- > 0;) {
        Check(simulation.RestoreRewindCheckpoint(*checkpoints[index], tape),
            "cached checkpoint restore must remain valid across a long run");
        const std::uint64_t target = std::min<std::uint64_t>(
            simulation.Snapshot().tick + 29U, tape.end_tick);
        while (simulation.Snapshot().tick < target) simulation.Tick();
    }
    const double elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - start).count();
    Check(elapsed < 1.0, "hundreds of cached backward seeks must complete without UI-scale lag");
#endif
}

void TestLiveLocomotionOptionsReplay() {
    sim::Simulation simulation({}, 2028U);
    for (int tick = 0; tick < 20; ++tick) simulation.Tick();
    const std::uint64_t option_tick = simulation.Snapshot().tick;
    simulation.UpdateLocomotionOptions(0.35f, 0.15f);
    Check(simulation.Snapshot().tick == option_tick,
        "changing crawl options must not restart or advance the simulation");
    Check(simulation.Config().crawl_speed_scale == 0.35f &&
            simulation.Config().crawl_turn_scale == 0.15f,
        "crawl speed and turn options must apply immediately");
    for (int tick = 0; tick < 40; ++tick) simulation.Tick();
#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog tape = simulation.RecordedReplay();
    Check(tape.locomotion_options_events.size() == 1U &&
            tape.locomotion_options_events[0].tick == option_tick,
        "a live crawl-option change must be recorded at its exact tick");
    Check(simulation.SeekReplay(tape, option_tick),
        "the crawl-option tick must remain seekable");
    Check(simulation.Config().crawl_speed_scale == 0.35f &&
            simulation.Config().crawl_turn_scale == 0.15f,
        "replay must restore crawl options at the recorded tick");
#endif
}

void TestLiveCombatOptionsReplay() {
    sim::Simulation simulation({}, 2027);
    for (int tick = 0; tick < 20; ++tick) simulation.Tick();
    const std::uint64_t option_tick = simulation.Snapshot().tick;
    std::array<float, sim::kSwordAttackClipCount> sword_stuns = sim::kDefaultSwordAttackStunSeconds;
    std::array<float, sim::kMeleeAttackClipCount> melee_stuns = sim::kDefaultMeleeAttackStunSeconds;
    sword_stuns[2] = 0.8f;
    melee_stuns[4] = 1.1f;
    simulation.UpdateCombatOptions(2.0f, 2.5f, 0.25f, 0.70f, 0.75f,
        sword_stuns, melee_stuns);
    Check(simulation.Snapshot().tick == option_tick,
        "changing combat options must not restart or advance the simulation");
    Check(simulation.Config().attack_cooldown_seconds == 2.0f &&
        simulation.Config().parried_attack_cooldown_seconds == 2.5f &&
        simulation.Config().attack_followup_probability == 0.25f &&
        simulation.Config().drawn_sword_attack_probability == 0.70f &&
        simulation.Config().parry_probability == 0.75f &&
        simulation.Config().sword_attack_stun_seconds[2] == 0.8f &&
        simulation.Config().melee_attack_stun_seconds[4] == 1.1f,
        "combat options must apply immediately");
    for (int tick = 0; tick < 40; ++tick) simulation.Tick();
#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog tape = simulation.RecordedReplay();
    Check(tape.combat_options_events.size() == 1U &&
        tape.combat_options_events[0].tick == option_tick,
        "a live combat option change must be recorded at its exact tick");
    Check(simulation.SeekReplay(tape, option_tick),
        "the option-change tick must remain seekable");
    Check(simulation.Config().attack_cooldown_seconds == 2.0f &&
        simulation.Config().parried_attack_cooldown_seconds == 2.5f &&
        simulation.Config().attack_followup_probability == 0.25f &&
        simulation.Config().drawn_sword_attack_probability == 0.70f &&
        simulation.Config().parry_probability == 0.75f &&
        simulation.Config().sword_attack_stun_seconds[2] == 0.8f &&
        simulation.Config().melee_attack_stun_seconds[4] == 1.1f,
        "replay must restore combat options at the recorded tick");
#endif
}

void TestLiveWoundOptionsReplay() {
    sim::Simulation simulation({}, 3030);
    for (int tick = 0; tick < 20; ++tick) simulation.Tick();
    const std::uint64_t option_tick = simulation.Snapshot().tick;
    simulation.UpdateWoundOptions(25.0f, 90.0f, 2.0f, 4.0f, 12.0f, 35.0f);
    Check(simulation.Snapshot().tick == option_tick,
        "changing wound options must not restart or advance the simulation");
    Check(simulation.Config().melee_wound_gain == 25.0f &&
        simulation.Config().wound_threshold == 90.0f &&
        simulation.Config().wound_decay_per_second == 2.0f &&
        simulation.Config().leg_agonising_seconds == 4.0f &&
        simulation.Config().torso_agonising_seconds == 12.0f &&
        simulation.Config().head_passed_out_seconds == 35.0f,
        "all wound options must apply immediately");
    for (int tick = 0; tick < 40; ++tick) simulation.Tick();
#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog tape = simulation.RecordedReplay();
    Check(tape.wound_options_events.size() == 1U &&
        tape.wound_options_events[0].tick == option_tick,
        "a live wound-option change must be recorded at its exact tick");
    Check(simulation.SeekReplay(tape, option_tick), "the wound-option tick must remain seekable");
    Check(simulation.Config().melee_wound_gain == 25.0f &&
        simulation.Config().wound_threshold == 90.0f &&
        simulation.Config().head_passed_out_seconds == 35.0f,
        "replay must restore wound options at the recorded tick");
#endif
}

void TestLiveLookOptionsReplay() {
    sim::Simulation simulation({}, 9090);
    for (int tick = 0; tick < 20; ++tick) simulation.Tick();
    const std::uint64_t option_tick = simulation.Snapshot().tick;
    simulation.UpdateLookOptions(75.0f);
    simulation.UpdatePerceptionOptions(4.0f, 150.0f, 210.0f, 7.0f,
        25.0f, 20.0f, 45.0f, 9.0f, 3.0f);
    Check(simulation.Snapshot().tick == option_tick,
        "changing look options must not restart or advance the simulation");
    Check(simulation.Config().head_turn_speed_degrees_per_second == 75.0f &&
            simulation.Config().proximity_threat_range_m == 4.0f &&
            simulation.Config().vision_range_m == 150.0f &&
            simulation.Config().head_vision_angle_degrees == 210.0f &&
            simulation.Config().sound_maximum_range_m == 7.0f &&
            simulation.Config().running_sound_toward_leeway_degrees == 25.0f &&
            simulation.Config().non_threatening_minimum_seconds == 20.0f &&
            simulation.Config().non_threatening_maximum_seconds == 45.0f &&
            simulation.Config().follow_walk_distance_m == 9.0f &&
            simulation.Config().follow_stop_distance_m == 3.0f,
        "look and perception thresholds must apply immediately");
    for (int tick = 0; tick < 40; ++tick) simulation.Tick();
#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog tape = simulation.RecordedReplay();
    Check(tape.look_options_events.size() == 2U &&
        tape.look_options_events[0].tick == option_tick &&
        tape.look_options_events[1].tick == option_tick,
        "live look and perception changes must be recorded at their exact tick");
    Check(simulation.SeekReplay(tape, option_tick), "the look-option tick must remain seekable");
    Check(simulation.Config().head_turn_speed_degrees_per_second == 75.0f &&
            simulation.Config().proximity_threat_range_m == 4.0f &&
            simulation.Config().vision_range_m == 150.0f &&
            simulation.Config().head_vision_angle_degrees == 210.0f &&
            simulation.Config().sound_maximum_range_m == 7.0f &&
            simulation.Config().running_sound_toward_leeway_degrees == 25.0f &&
            simulation.Config().non_threatening_minimum_seconds == 20.0f &&
            simulation.Config().non_threatening_maximum_seconds == 45.0f &&
            simulation.Config().follow_walk_distance_m == 9.0f &&
            simulation.Config().follow_stop_distance_m == 3.0f,
        "replay must restore look and perception options at the recorded tick");
#endif
}

void TestLiveTacticsOptionsReplay() {
    sim::Simulation simulation({}, 9191U);
    for (int tick = 0; tick < 20; ++tick) simulation.Tick();
    const std::uint64_t option_tick = simulation.Snapshot().tick;
    simulation.UpdateTacticsOptions(2.0f, 7.0f, 0.12f, 8.0f, 0.2f, 1.8f);
    Check(simulation.Snapshot().tick == option_tick,
        "changing tactics options must not restart or advance the simulation");
    Check(simulation.Config().target_commitment_seconds == 2.0f &&
            simulation.Config().sector_influence_distance_m == 7.0f &&
            simulation.Config().containment_early_influence == 0.12f &&
            simulation.Config().sector_angle_variation_degrees == 8.0f &&
            simulation.Config().sector_radius_variation_m == 0.2f &&
            simulation.Config().ally_spacing_distance_m == 1.8f,
        "all tactics options must apply immediately");
    for (int tick = 0; tick < 40; ++tick) simulation.Tick();
#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog tape = simulation.RecordedReplay();
    Check(tape.tactics_options_events.size() == 1U &&
            tape.tactics_options_events[0].tick == option_tick,
        "a live tactics-option change must be recorded at its exact tick");
    Check(simulation.SeekReplay(tape, option_tick),
        "the tactics-option tick must remain seekable");
    Check(simulation.Config().target_commitment_seconds == 2.0f &&
            simulation.Config().sector_influence_distance_m == 7.0f &&
            simulation.Config().containment_early_influence == 0.12f &&
            simulation.Config().sector_angle_variation_degrees == 8.0f &&
            simulation.Config().sector_radius_variation_m == 0.2f &&
            simulation.Config().ally_spacing_distance_m == 1.8f,
        "replay must restore tactics options at the recorded tick");
#endif
}

void TestConfigNormalization() {
    sim::SimulationConfig config{};
    config.hero_agent_count = 0;
    config.villain_agent_count = 1000;
    config.tick_rate_hz = 0.0f;
    config.world_min = {5.0f, 7.0f, 0.0f};
    config.world_max = {-5.0f, -7.0f, 0.0f};
    config.sheathe_action_seconds = 0.0f;
    config.unsheathe_action_seconds = 100.0f;
    config.stick_pickup_action_seconds = 100.0f;
    config.stick_drop_action_seconds = 0.0f;
    config.attack_range_m = 100.0f;
    config.attack_cooldown_seconds = 100.0f;
    config.parried_attack_cooldown_seconds = -1.0f;
    config.attack_followup_probability = -1.0f;
    config.drawn_sword_attack_probability = 4.0f;
    config.hit_probability = -1.0f;
    config.parry_probability = 4.0f;
    config.head_turn_speed_degrees_per_second = -1.0f;
    config.proximity_threat_range_m = 1000.0f;
    config.vision_range_m = -1.0f;
    config.head_vision_angle_degrees = 1000.0f;
    config.sound_maximum_range_m = 1000.0f;
    config.running_sound_toward_leeway_degrees = -1.0f;
    config.non_threatening_minimum_seconds = 700.0f;
    config.non_threatening_maximum_seconds = -1.0f;
    config.target_commitment_seconds = 100.0f;
    config.sector_influence_distance_m = 100.0f;
    config.containment_early_influence = 100.0f;
    config.sector_angle_variation_degrees = 100.0f;
    config.sector_radius_variation_m = 100.0f;
    config.ally_spacing_distance_m = 100.0f;
    config.crawl_speed_scale = -1.0f;
    config.crawl_turn_scale = 2.0f;
    config.melee_wound_gain = -1.0f;
    config.wound_threshold = 0.0f;
    config.wound_decay_per_second = 1000.0f;
    config.leg_agonising_seconds = -1.0f;
    config.torso_agonising_seconds = 1000.0f;
    config.head_passed_out_seconds = 1000.0f;
    sim::Simulation simulation(config, 1);
    Check(simulation.Config().hero_agent_count == sim::kMinTeamAgentCount &&
            simulation.Config().villain_agent_count == sim::kMaxTeamAgentCount &&
            simulation.Config().agent_count == 100U,
        "each team count must normalize independently to the zero-through-one-hundred range");
    Check(simulation.Config().tick_rate_hz == 1.0f, "tick rate must never normalize below one hertz");
    Check(simulation.Config().world_min.x == -5.0f && simulation.Config().world_max.y == 7.0f,
        "inverted world bounds must normalize");
    Check(simulation.Config().sheathe_action_seconds == 0.1f &&
        simulation.Config().unsheathe_action_seconds == 30.0f &&
        simulation.Config().stick_pickup_action_seconds == 30.0f &&
        simulation.Config().stick_drop_action_seconds == 0.1f,
        "action durations must normalize to finite timed bounds");
    Check(simulation.Config().attack_range_m == 10.0f &&
        simulation.Config().attack_cooldown_seconds == 30.0f &&
        simulation.Config().parried_attack_cooldown_seconds == 0.0f &&
        simulation.Config().attack_followup_probability == 0.0f &&
        simulation.Config().drawn_sword_attack_probability == 1.0f &&
        simulation.Config().hit_probability == 0.0f &&
        simulation.Config().parry_probability == 1.0f &&
        simulation.Config().head_turn_speed_degrees_per_second == 0.0f &&
        simulation.Config().proximity_threat_range_m == 100.0f &&
        simulation.Config().vision_range_m == 0.0f &&
        simulation.Config().head_vision_angle_degrees == 360.0f &&
        simulation.Config().sound_maximum_range_m == 50.0f &&
        simulation.Config().running_sound_toward_leeway_degrees == 0.0f &&
        simulation.Config().non_threatening_minimum_seconds == 0.0f &&
        simulation.Config().non_threatening_maximum_seconds == 600.0f &&
        simulation.Config().target_commitment_seconds == 10.0f &&
        simulation.Config().sector_influence_distance_m == 50.0f &&
        simulation.Config().containment_early_influence == 0.2f &&
        simulation.Config().sector_angle_variation_degrees == 22.5f &&
        simulation.Config().sector_radius_variation_m == 1.0f &&
        simulation.Config().ally_spacing_distance_m == 5.0f &&
        simulation.Config().crawl_speed_scale == 0.0f &&
        simulation.Config().crawl_turn_scale == 1.0f &&
        simulation.Config().melee_wound_gain == 0.0f &&
        simulation.Config().wound_threshold == 1.0f &&
        simulation.Config().wound_decay_per_second == 100.0f &&
        simulation.Config().leg_agonising_seconds == 0.0f &&
        simulation.Config().torso_agonising_seconds == 120.0f &&
        simulation.Config().head_passed_out_seconds == 120.0f,
        "attack timing and range must normalize to finite bounds");
    simulation.RestartInMode(sim::SimulationMode::Paired);
    Check(simulation.Snapshot().tick == 0U && simulation.Config().mode == sim::SimulationMode::Paired,
        "changing simulation mode must restart a deterministic run at tick zero");
}

void TestZeroTeamCounts() {
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    config.hero_agent_count = 0U;
    config.villain_agent_count = 2U;
    sim::Simulation simulation(config, 17U);
    Check(simulation.Config().agent_count == 2U && simulation.Snapshot().agents.size() == 2U &&
            std::all_of(simulation.Snapshot().agents.begin(), simulation.Snapshot().agents.end(),
                [](const sim::AgentSnapshot& agent) { return agent.team == sim::Team::Villain; }),
        "zero Heroes must leave an all-Villain simulation");

    simulation.RestartWithTeamCounts(2U, 0U);
    Check(simulation.Config().agent_count == 2U && simulation.Snapshot().agents.size() == 2U &&
            std::all_of(simulation.Snapshot().agents.begin(), simulation.Snapshot().agents.end(),
                [](const sim::AgentSnapshot& agent) { return agent.team == sim::Team::Hero; }),
        "zero Villains must leave an all-Hero simulation");

    simulation.RestartWithTeamCounts(0U, 0U);
    simulation.Tick();
    simulation.Tick();
    Check(simulation.Config().agent_count == 0U && simulation.Snapshot().agents.empty() &&
            simulation.Snapshot().tick == 2U,
        "zero-versus-zero must remain a valid ticking simulation");
}

void TestPersistentStickLifecycleAndReplay() {
    sim::SimulationConfig config{};
    config.hero_agent_count = 2U;
    config.villain_agent_count = 0U;
    config.mode = sim::SimulationMode::Autonomous;
    sim::Simulation simulation(config, 71U);

    const sim::StickId stick_id = simulation.SpawnStick({-2.5f, -1.5f, 0.0f}, 0.25f);
    Check(stick_id != sim::kInvalidStickId && simulation.Snapshot().sticks.size() == 1U,
        "spawning a training stick must create one persistent world entity");
    Check(simulation.RequestPickUpStick(1U, stick_id) &&
        simulation.Snapshot().agents[0].action.kind == sim::ActionKind::PickUpStick &&
        simulation.Snapshot().agents[0].action.duration_seconds == 1.0f,
        "stick pickup must enter the central one-second timed action");
    for (int tick = 0; tick < 29; ++tick) simulation.Tick();
    Check(simulation.Snapshot().sticks[0].holder_id == sim::kInvalidEntityId,
        "a stick must remain on the ground until its pickup duration completes");
    simulation.Tick();
    Check(simulation.Snapshot().agents[0].held_weapon == sim::WeaponKind::Stick &&
        simulation.Snapshot().agents[0].held_stick_id == stick_id &&
        simulation.Snapshot().agents[0].sword_equipped &&
        simulation.Snapshot().agents[0].sword_state == sim::SwordState::Sheathed &&
        simulation.Snapshot().sticks[0].holder_id == 1U,
        "pickup must preserve the equipped sheathed sword while placing the stick in hand");

    Check(simulation.RequestDropStick(1U) &&
        simulation.Snapshot().agents[0].action.kind == sim::ActionKind::DropStick &&
        simulation.Snapshot().agents[0].action.duration_seconds == 0.1f,
        "stick drop must enter the central 0.1-second timed action");
    simulation.Tick();
    simulation.Tick();
    Check(simulation.Snapshot().sticks[0].holder_id == 1U,
        "a stick must remain held until its drop duration completes");
    simulation.Tick();
    Check(simulation.Snapshot().sticks[0].holder_id == sim::kInvalidEntityId &&
        simulation.Snapshot().agents[0].held_weapon == sim::WeaponKind::None,
        "a completed drop must leave the same stick entity on the ground");

    Check(simulation.RequestPickUpStick(2U, stick_id),
        "a different agent must be able to request pickup of a dropped stick");
    for (int tick = 0; tick < 30; ++tick) simulation.Tick();
    Check(simulation.Snapshot().sticks[0].holder_id == 2U &&
        simulation.Snapshot().agents[1].held_stick_id == stick_id,
        "a dropped stick must persist and become held by another agent");

#if PROPHECY_ENABLE_REWIND
    const sim::ReplayLog replay = simulation.RecordedReplay();
    sim::Simulation replayed({}, 1U);
    Check(replayed.SeekReplay(replay, replay.end_tick) &&
        EqualAgents(simulation.Snapshot(), replayed.Snapshot()),
        "spawn, pickup, drop, and repickup commands must replay to identical stick state");
#endif
}

void TestDrawnSwordSheathesBeforeStickPickup() {
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    config.initial_sticks.push_back({sim::kInvalidStickId, {-2.5f, 0.0f, 0.0f}, 0.0f});
    sim::Simulation simulation(config, 1337U);
    int guard = 300;
    while (--guard > 0 && !(simulation.Snapshot().agents[0].sword_state == sim::SwordState::Drawn &&
        simulation.Snapshot().agents[0].action.kind == sim::ActionKind::None)) {
        simulation.Tick();
    }
    Check(guard > 0 && simulation.RequestPickUpStick(1U, 1U) &&
        simulation.Snapshot().agents[0].action.kind == sim::ActionKind::SheatheSword,
        "a drawn sword must begin sheathing before stick pickup can start");
    while (--guard > 0 &&
        simulation.Snapshot().agents[0].action.kind != sim::ActionKind::PickUpStick) {
        simulation.Tick();
    }
    Check(guard > 0 &&
        simulation.Snapshot().agents[0].sword_state == sim::SwordState::Sheathed,
        "the queued pickup must start only after the sword is fully sheathed");
}

void TestStickCombatUsesMeleeDamageAndSilentParries() {
    constexpr float kHalfPi = 1.57079632679489661923f;
    sim::SimulationConfig damage_config{};
    damage_config.hit_probability = 1.0f;
    damage_config.parry_probability = 0.0f;
    damage_config.wound_decay_per_second = 0.0f;
    damage_config.opening_transforms = {
        {1U, {-0.5f, 0.0f, 0.0f}, kHalfPi},
        {2U, {0.5f, 0.0f, 0.0f}, -kHalfPi},
    };
    damage_config.initial_sticks = {
        {1U, {-0.5f, 0.0f, 0.0f}, 0.0f},
        {2U, {0.5f, 0.0f, 0.0f}, 0.0f},
    };
    sim::Simulation damage(damage_config, 81U);
    Check(damage.RequestPickUpStick(1U, 1U) && damage.RequestPickUpStick(2U, 2U),
        "both combatants must be able to pick up their training sticks");
    bool saw_stick_attack = false;
    bool saw_gauge_damage = false;
    for (int tick = 0; tick < 300 && !saw_gauge_damage; ++tick) {
        damage.Tick();
        for (const sim::AgentSnapshot& agent : damage.Snapshot().agents) {
            saw_stick_attack |= agent.action.kind == sim::ActionKind::SwordAttack &&
                agent.action.weapon == sim::WeaponKind::Stick;
            for (const sim::LimbWoundSnapshot& wound : agent.wounds) {
                saw_gauge_damage |= wound.gauge > 0.0f;
            }
        }
    }
    Check(saw_stick_attack && saw_gauge_damage,
        "stick strikes must use sword clips while adding melee wound gauge damage");
    Check(std::all_of(damage.Snapshot().agents.begin(), damage.Snapshot().agents.end(),
            [](const sim::AgentSnapshot& agent) {
                return std::all_of(agent.wounds.begin(), agent.wounds.end(),
                    [](const sim::LimbWoundSnapshot& wound) {
                        return wound.condition == sim::LimbCondition::Normal;
                    });
            }),
        "a first 20-percent stick strike must not apply instant sword injury");

    sim::SimulationConfig parry_config = damage_config;
    parry_config.mode = sim::SimulationMode::Paired;
    parry_config.hit_probability = 0.0f;
    parry_config.parry_probability = 1.0f;
    sim::Simulation parry(parry_config, 83U);
    Check(parry.RequestPickUpStick(2U, 2U),
        "stick parry test must begin with the defender's stick queued for pickup");
    bool saw_parry = false;
    for (int tick = 0; tick < 3000 && !saw_parry; ++tick) {
        parry.Tick();
        saw_parry = std::any_of(parry.Snapshot().agents.begin(), parry.Snapshot().agents.end(),
            [](const sim::AgentSnapshot& agent) {
                return agent.reaction.kind == sim::ReactionKind::Parry;
            });
    }
    Check(saw_parry, "a real sword and training stick must remain eligible to parry each other");
    Check(LatestSound(parry.Snapshot(), sim::SoundEventKind::Parry) == nullptr,
        "any parry involving a training stick must remain silent");
}

void TestDowningDropsHandHeldEquipment() {
    const auto standing = [](sim::AgentState state) {
        return state == sim::AgentState::Normal || state == sim::AgentState::Slow ||
            state == sim::AgentState::Stunned;
    };
    const auto living_on_floor = [](sim::AgentState state) {
        return state == sim::AgentState::Agonising || state == sim::AgentState::PassedOut ||
            state == sim::AgentState::Crawling;
    };

    bool drawn_sword_drop_seen = false;
    for (std::uint64_t seed = 1U; seed <= 128U && !drawn_sword_drop_seen; ++seed) {
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.parry_probability = 0.0f;
        config.attack_cooldown_seconds = 0.0f;
        config.wound_decay_per_second = 0.0f;
        sim::Simulation simulation(config, seed);
        sim::SimulationSnapshot previous = simulation.Snapshot();
        for (int tick = 0; tick < 1200 && !drawn_sword_drop_seen; ++tick) {
            simulation.Tick();
            const sim::SimulationSnapshot& current = simulation.Snapshot();
            for (std::size_t index = 0; index < current.agents.size(); ++index) {
                const sim::AgentSnapshot& before = previous.agents[index];
                const sim::AgentSnapshot& after = current.agents[index];
                if (!standing(before.state) || before.sword_state != sim::SwordState::Drawn ||
                    !living_on_floor(after.state)) continue;
                drawn_sword_drop_seen = true;
                Check(after.sword_state == sim::SwordState::Dropped,
                    "downing must drop a sword that was in the agent's hand");
                break;
            }
            previous = current;
        }
    }
    Check(drawn_sword_drop_seen,
        "the deterministic battle set must exercise downing a drawn-sword holder");

    bool club_drop_seen = false;
    for (std::uint64_t seed = 1U; seed <= 128U && !club_drop_seen; ++seed) {
        constexpr float kHalfPi = 1.57079632679489661923f;
        sim::SimulationConfig config{};
        config.hit_probability = 1.0f;
        config.parry_probability = 0.0f;
        config.attack_cooldown_seconds = 0.0f;
        config.wound_decay_per_second = 0.0f;
        config.wound_threshold = 20.0f;
        config.melee_wound_gain = 20.0f;
        config.opening_transforms = {
            {1U, {-0.5f, 0.0f, 0.0f}, kHalfPi},
            {2U, {0.5f, 0.0f, 0.0f}, -kHalfPi},
        };
        config.initial_sticks = {
            {1U, {-0.5f, 0.0f, 0.0f}, 0.0f},
            {2U, {0.5f, 0.0f, 0.0f}, 0.0f},
        };
        sim::Simulation simulation(config, seed);
        Check(simulation.RequestPickUpStick(1U, 1U) &&
                simulation.RequestPickUpStick(2U, 2U),
            "the downing test must begin with both clubs queued for pickup");
        sim::SimulationSnapshot previous = simulation.Snapshot();
        for (int tick = 0; tick < 1200 && !club_drop_seen; ++tick) {
            simulation.Tick();
            const sim::SimulationSnapshot& current = simulation.Snapshot();
            for (std::size_t index = 0; index < current.agents.size(); ++index) {
                const sim::AgentSnapshot& before = previous.agents[index];
                const sim::AgentSnapshot& after = current.agents[index];
                if (!standing(before.state) || before.held_stick_id == sim::kInvalidStickId ||
                    !living_on_floor(after.state)) continue;
                club_drop_seen = true;
                const sim::StickSnapshot& club = current.sticks[before.held_stick_id - 1U];
                Check(after.held_stick_id == sim::kInvalidStickId &&
                        after.held_weapon == sim::WeaponKind::None &&
                        club.holder_id == sim::kInvalidEntityId,
                    "downing must release a held club into persistent world state");
                Check(after.sword_state == sim::SwordState::Sheathed,
                    "downing a club holder must leave its owned sheathed sword equipped");
                break;
            }
            previous = current;
        }
    }
    Check(club_drop_seen,
        "the deterministic battle set must exercise downing a club holder");
}

void TestRealSwordClashAlertsIdleAgentsOnBothTeams() {
    sim::SimulationConfig config{};
    config.mode = sim::SimulationMode::Paired;
    config.hit_probability = 0.0f;
    config.parry_probability = 1.0f;
    config.sound_maximum_range_m = 30.0f;
    config.target_commitment_seconds = 0.0f;
    config.sector_influence_distance_m = config.attack_range_m;
    config.ally_spacing_distance_m = 0.0f;

    std::uint64_t selected_seed = 0U;
    std::uint64_t clash_tick = 0U;
    for (std::uint64_t seed = 1U; seed <= 64U && clash_tick == 0U; ++seed) {
        sim::Simulation baseline(config, seed);
        for (int guard = 0; guard < 900; ++guard) {
            baseline.Tick();
            const sim::SoundEventSnapshot* clash = LatestSound(
                baseline.Snapshot(), sim::SoundEventKind::Parry);
            if (clash != nullptr && clash->emitted_tick == baseline.Snapshot().tick &&
                clash->emitted_tick % 6U != 0U) {
                selected_seed = seed;
                clash_tick = clash->emitted_tick;
                break;
            }
        }
    }
    Check(clash_tick > 1U, "the deterministic search must find a real-sword clash tick");
    if (clash_tick <= 1U) return;

    sim::Simulation observed(config, selected_seed);
    while (observed.Snapshot().tick + 1U < clash_tick) observed.Tick();
    const sim::EntityId hero_listener = observed.SpawnTransientAgent(
        sim::Team::Hero, {0.0f, 15.0f, 0.0f}, 0.0f);
    const sim::EntityId villain_listener = observed.SpawnTransientAgent(
        sim::Team::Villain, {0.0f, -15.0f, 0.0f}, 3.14159265358979323846f);
    observed.Tick();
    const sim::SoundEventSnapshot* clash = LatestSound(
        observed.Snapshot(), sim::SoundEventKind::Parry);
    Check(clash != nullptr && clash->emitted_tick == clash_tick &&
        clash->secondary_source_id != sim::kInvalidEntityId,
        "a real-sword clash must identify both sword participants in its sound event");
    if (clash == nullptr) return;
    const sim::AgentSnapshot& hero = observed.Snapshot().agents[hero_listener - 1U];
    const sim::AgentSnapshot& villain = observed.Snapshot().agents[villain_listener - 1U];
    const sim::AgentSnapshot& source = observed.Snapshot().agents[clash->source_id - 1U];
    const sim::AgentSnapshot& secondary =
        observed.Snapshot().agents[clash->secondary_source_id - 1U];
    const sim::EntityId expected_hero_source = source.team == sim::Team::Villain
        ? source.id : secondary.id;
    const sim::EntityId expected_villain_source = source.team == sim::Team::Hero
        ? source.id : secondary.id;
    Check(hero.behavior_mode == sim::BehaviorMode::Idle &&
        hero.perception.sound_investigation_source_id == expected_hero_source &&
        hero.head_look_mode == sim::HeadLookMode::SoundInvestigation,
        "an idle Hero must turn to investigate the Villain participant in a nearby sword clash");
    Check(villain.behavior_mode == sim::BehaviorMode::Idle &&
        villain.perception.sound_investigation_source_id == expected_villain_source &&
        villain.head_look_mode == sim::HeadLookMode::SoundInvestigation,
        "an idle Villain must turn to investigate the Hero participant in a nearby sword clash");
}

void TestPostBattleSweepFinishesSeenNonDeadEnemiesAndRescans() {
    bool acquired_from_sweep = false;
    bool validated_living_finishing_target = false;
    bool finished_all = false;
    bool rescanned_after_finishing = false;
    bool triggered_while_enemy_standing = false;
    bool observed_mixed_standing_and_grounded_team = false;
    for (std::uint64_t seed = 1U; seed <= 64U && !rescanned_after_finishing; ++seed) {
        sim::SimulationConfig config{};
        config.hero_agent_count = 2U;
        config.villain_agent_count = 2U;
        config.hit_probability = 1.0f;
        config.attack_cooldown_seconds = 0.0f;
        config.parried_attack_cooldown_seconds = 0.0f;
        config.wound_decay_per_second = 0.0f;
        config.leg_agonising_seconds = 0.0f;
        config.torso_agonising_seconds = 0.0f;
        config.head_passed_out_seconds = 0.0f;
        config.head_turn_speed_degrees_per_second = 1440.0f;
        sim::Simulation simulation(config, seed);
        sim::EntityId finisher_id = sim::kInvalidEntityId;
        sim::Team finisher_team = sim::Team::Hero;

        for (int tick = 0; tick < 1800 && !rescanned_after_finishing; ++tick) {
            simulation.Tick();
            const sim::SimulationSnapshot& snapshot = simulation.Snapshot();
            bool hero_standing = false;
            bool hero_grounded = false;
            bool villain_standing = false;
            bool villain_grounded = false;
            for (const sim::AgentSnapshot& candidate : snapshot.agents) {
                const bool standing = candidate.state == sim::AgentState::Normal ||
                    candidate.state == sim::AgentState::Slow ||
                    candidate.state == sim::AgentState::Stunned;
                const bool grounded = !standing && candidate.state != sim::AgentState::Dead;
                if (candidate.team == sim::Team::Hero) {
                    hero_standing |= standing;
                    hero_grounded |= grounded;
                } else {
                    villain_standing |= standing;
                    villain_grounded |= grounded;
                }
            }
            observed_mixed_standing_and_grounded_team |=
                (hero_standing && hero_grounded) || (villain_standing && villain_grounded);
            for (const sim::AgentSnapshot& agent : snapshot.agents) {
                if (agent.perception.finishing_target_count == 0U) continue;
                triggered_while_enemy_standing |= std::any_of(
                    snapshot.agents.begin(), snapshot.agents.end(),
                    [&agent](const sim::AgentSnapshot& candidate) {
                        const bool standing = candidate.state == sim::AgentState::Normal ||
                            candidate.state == sim::AgentState::Slow ||
                            candidate.state == sim::AgentState::Stunned;
                        return candidate.team != agent.team && standing;
                    });
                acquired_from_sweep = true;
                finisher_id = agent.id;
                finisher_team = agent.team;
                Check(agent.perception.active_threat_count >=
                        agent.perception.finishing_target_count &&
                        agent.perception.finishing_target_id_count > 0U,
                    "grounded enemies found by an empty sweep must enter the active-target set");
                for (std::size_t index = 0;
                    index < agent.perception.finishing_target_id_count; ++index) {
                    const sim::AgentSnapshot& target = snapshot.agents[
                        agent.perception.finishing_target_ids[index] - 1U];
                    if (target.state == sim::AgentState::Dead) continue;
                    validated_living_finishing_target = true;
                    Check(target.team != agent.team &&
                            (target.state == sim::AgentState::Agonising ||
                                target.state == sim::AgentState::PassedOut ||
                                target.state == sim::AgentState::Crawling),
                        "a finishing target must be a living enemy on the floor");
                }
            }

            if (finisher_id == sim::kInvalidEntityId) continue;
            const bool living_enemy_remains = std::any_of(
                snapshot.agents.begin(), snapshot.agents.end(),
                [finisher_team](const sim::AgentSnapshot& agent) {
                    return agent.team != finisher_team && agent.state != sim::AgentState::Dead;
                });
            if (!living_enemy_remains) finished_all = true;
            const sim::AgentSnapshot& finisher = snapshot.agents[finisher_id - 1U];
            if (finished_all && finisher.perception.finishing_target_count == 0U &&
                finisher.head_look_mode == sim::HeadLookMode::SearchScan) {
                rescanned_after_finishing = true;
            }
        }
    }
    Check(acquired_from_sweep,
        "a completed empty-standing sweep must acquire a seen living grounded enemy");
    Check(validated_living_finishing_target,
        "the promoted finishing set must contain a living enemy observed during the sweep");
    Check(!triggered_while_enemy_standing,
        "the post-battle finishing phase must never trigger while one enemy remains standing");
    Check(observed_mixed_standing_and_grounded_team,
        "the finishing-phase gate regression must exercise a team with standing and grounded survivors");
    Check(finished_all,
        "the sweep-acquired grounded target set must be finished until no living enemy remains");
    Check(rescanned_after_finishing,
        "emptying the finishing-target set must naturally start another head sweep");
}

void TestTickPerformance() {
    sim::Simulation simulation({}, 7);
    constexpr int ticks = 250'000;
    const auto start = std::chrono::steady_clock::now();
    for (int tick = 0; tick < ticks; ++tick) simulation.Tick();
    const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    Check(elapsed < 3.0, "two-agent locomotion ticking and future roots must remain lightweight");

    sim::SimulationConfig asymmetric_config{};
    asymmetric_config.hero_agent_count = 1;
    asymmetric_config.villain_agent_count = 100;
    asymmetric_config.mode = sim::SimulationMode::Paired;
    sim::Simulation asymmetric(asymmetric_config, 8);
    constexpr int asymmetric_ticks = 900;
    const auto asymmetric_start = std::chrono::steady_clock::now();
    for (int tick = 0; tick < asymmetric_ticks; ++tick) asymmetric.Tick();
    const double asymmetric_elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - asymmetric_start).count();
    Check(asymmetric_elapsed < 3.0,
        "one-versus-one-hundred target-group steering must remain lightweight");

    sim::SimulationConfig battle_config{};
    battle_config.hero_agent_count = 50U;
    battle_config.villain_agent_count = 50U;
    battle_config.mode = sim::SimulationMode::Paired;
    battle_config.opening_transforms.reserve(100U);
    constexpr float kHalfPi = 1.57079632679489661923f;
    for (std::uint32_t index = 0; index < 50U; ++index) {
        const float column = static_cast<float>(index % 5U);
        const float row = static_cast<float>(index / 5U) - 4.5f;
        battle_config.opening_transforms.push_back({index + 1U,
            {-10.0f + 0.8f * column, 0.8f * row, 0.0f}, kHalfPi});
    }
    for (std::uint32_t index = 0; index < 50U; ++index) {
        const float column = static_cast<float>(index % 5U);
        const float row = static_cast<float>(index / 5U) - 4.5f;
        battle_config.opening_transforms.push_back({index + 51U,
            {10.0f - 0.8f * column, 0.8f * row, 0.0f}, -kHalfPi});
    }
    sim::Simulation battle(battle_config, 9U);
    constexpr int battle_ticks = 450;
    const auto battle_start = std::chrono::steady_clock::now();
    for (int tick = 0; tick < battle_ticks; ++tick) battle.Tick();
    const double battle_elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - battle_start).count();
    Check(battle_elapsed < 3.0,
        "fifty-versus-fifty load balancing and sector steering must remain lightweight");
}

}  // namespace

int main() {
    TestOpeningEncounter();
    TestThreeVersusOneTacticalSteering();
    TestTwoVersusFourGeneralizationAndCountRestart();
    TestBalancedPerceivedTargetAllocation();
    TestMessySectorReservationsAndMotion();
    TestMixedFlankRolesAcrossSeparateTargets();
    TestContainmentEarlyInfluenceOption();
    TestMoverDrivenMotionAndFutureRoots();
    TestIdleVisionActivationAndStrike();
    TestCooldownRetreatAndSeededStrafe();
    TestDeterministicSoundEvents();
    TestExecutionScreamRescue();
    TestHeadLookLimitsAndTurnRate();
    TestRecognitionBeforeProximityRetention();
    TestRearThreatRequiresSoundInvestigation();
    TestEmptyLookAroundSheathesSword();
    TestSoundDirectionFilterRequiresAnActiveThreat();
    TestParryCancelsAttackAndDodgeDoesNot();
    TestAutonomousHitLandingCancelsAndStuns();
    TestStunnedDefenseUsesHitOrDodgeOnly();
    TestSeededAttackSelection();
    TestAutonomousLimbWoundsAndStates();
    TestStagedVitalWoundsAndDeadTargetDisengagement();
    TestGroundedHitsOnlyChangeVitals();
    TestGroundedAttackWeaponRules();
    TestLocomotionPrimitives();
    TestEditableOpeningTransformsAndReplay();
    TestReplayAndReset();
    TestTransientSpawnsDoNotEnterReplay();
    TestCheckpointReplay();
    TestCheckpointSeekPerformance();
    TestLiveLocomotionOptionsReplay();
    TestLiveCombatOptionsReplay();
    TestLiveWoundOptionsReplay();
    TestLiveLookOptionsReplay();
    TestLiveTacticsOptionsReplay();
    TestConfigNormalization();
    TestZeroTeamCounts();
    TestPersistentStickLifecycleAndReplay();
    TestDrawnSwordSheathesBeforeStickPickup();
    TestStickCombatUsesMeleeDamageAndSilentParries();
    TestDowningDropsHandHeldEquipment();
    TestRealSwordClashAlertsIdleAgentsOnBothTeams();
    TestPostBattleSweepFinishesSeenNonDeadEnemiesAndRescans();
    TestTickPerformance();
    if (failures == 0) std::printf("All locomotion simulation tests passed.\n");
    return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
