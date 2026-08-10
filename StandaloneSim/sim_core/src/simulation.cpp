#include "prophecy/sim/simulation.h"

#include <algorithm>
#include <array>
#include <bitset>
#include <cmath>
#include <iterator>
#include <limits>
#include <utility>

namespace prophecy::sim {
namespace {

constexpr double kPi = 3.1415926535897932384626433832795;
constexpr float kAttackSourceFps = 30.0f;
constexpr double kMaximumApproachLateralRatio = 0.36;

template <std::size_t Size>
void NormalizeStunDurations(std::array<float, Size>& values) noexcept {
    for (float& value : values) {
        if (!std::isfinite(value)) value = 0.5f;
        else value = std::max(0.0f, value);
    }
}

float NormalizeHeadTurnSpeed(float value) noexcept {
    return std::isfinite(value) ? std::max(0.0f, value) : kDefaultHeadTurnSpeedDegreesPerSecond;
}

struct AttackClipSpec {
    std::uint32_t frame_count;
    HandUsage hands;
    Limb limb;
};

constexpr std::array<AttackClipSpec, kSwordAttackClipCount> kSwordAttackClips{{
    {24U, HandUsage::Right, Limb::RightArm}, {31U, HandUsage::Right, Limb::RightArm},
    {25U, HandUsage::Right, Limb::RightArm}, {27U, HandUsage::Right, Limb::RightArm},
    {25U, HandUsage::Right, Limb::RightArm}, {25U, HandUsage::Right, Limb::RightArm},
    {18U, HandUsage::Right, Limb::RightArm},
}};

// Append-only clip IDs preserve existing replay/settings indices: slashLD=1, slashRD=4, pike=6.
constexpr std::array<std::uint8_t, 3> kGroundedSwordAttackClips{{6U, 4U, 1U}};

constexpr std::array<AttackClipSpec, 9> kMeleeAttackClips{{
    {13U, HandUsage::None, Limb::Head}, {15U, HandUsage::Left, Limb::LeftArm},
    {15U, HandUsage::Right, Limb::RightArm}, {12U, HandUsage::Left, Limb::LeftArm},
    {13U, HandUsage::Right, Limb::RightArm}, {17U, HandUsage::None, Limb::LeftLeg},
    {17U, HandUsage::None, Limb::RightLeg}, {19U, HandUsage::Left, Limb::LeftArm},
    {15U, HandUsage::Right, Limb::RightArm},
}};

constexpr std::size_t LimbIndex(Limb limb) noexcept {
    return static_cast<std::size_t>(limb);
}

bool IsIncapacitated(AgentState state) noexcept {
    return state == AgentState::Agonising || state == AgentState::PassedOut ||
        state == AgentState::Crawling || state == AgentState::Dead;
}

bool CanInvestigateSound(AgentState state) noexcept {
    return state != AgentState::Agonising && state != AgentState::PassedOut &&
        state != AgentState::Dead;
}

bool IsGroundedTarget(AgentState state) noexcept {
    return state == AgentState::Agonising || state == AgentState::PassedOut ||
        state == AgentState::Crawling;
}

std::uint64_t Mix64(std::uint64_t value) noexcept {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

double UnitRandom(std::uint64_t value) noexcept {
    return static_cast<double>(Mix64(value) >> 11U) * (1.0 / 9007199254740992.0);
}

bool NormalizeTransform(const SimulationConfig& config, AgentTransform& transform) noexcept {
    if (!std::isfinite(transform.position.x) || !std::isfinite(transform.position.y) ||
        !std::isfinite(transform.facing_radians)) return false;
    transform.position.x = std::clamp(transform.position.x, config.world_min.x, config.world_max.x);
    transform.position.y = std::clamp(transform.position.y, config.world_min.y, config.world_max.y);
    transform.position.z = 0.0f;
    transform.facing_radians = static_cast<float>(std::remainder(
        static_cast<double>(transform.facing_radians), 2.0 * kPi));
    return true;
}

bool NormalizeStickTransform(const SimulationConfig& config, StickTransform& transform) noexcept {
    AgentTransform normalized{};
    normalized.position = transform.position;
    normalized.facing_radians = transform.facing_radians;
    if (!NormalizeTransform(config, normalized)) return false;
    transform.position = normalized.position;
    transform.facing_radians = normalized.facing_radians;
    return true;
}

SimulationConfig NormalizeConfig(SimulationConfig config) noexcept {
    config.hero_agent_count = std::clamp(
        config.hero_agent_count, kMinTeamAgentCount, kMaxTeamAgentCount);
    config.villain_agent_count = std::clamp(
        config.villain_agent_count, kMinTeamAgentCount, kMaxTeamAgentCount);
    config.agent_count = config.hero_agent_count + config.villain_agent_count;
    config.tick_rate_hz = std::max(1.0f, config.tick_rate_hz);
    config.sheathe_action_seconds = std::clamp(config.sheathe_action_seconds, 0.1f, 30.0f);
    config.unsheathe_action_seconds = std::clamp(config.unsheathe_action_seconds, 0.1f, 30.0f);
    config.stick_pickup_action_seconds = std::clamp(
        config.stick_pickup_action_seconds, 0.1f, 30.0f);
    config.stick_drop_action_seconds = std::clamp(
        config.stick_drop_action_seconds, 0.1f, 30.0f);
    config.attack_range_m = std::clamp(config.attack_range_m, 0.25f, 10.0f);
    config.attack_cooldown_seconds = std::clamp(config.attack_cooldown_seconds, 0.0f, 30.0f);
    config.parried_attack_cooldown_seconds = std::clamp(
        config.parried_attack_cooldown_seconds, 0.0f, 30.0f);
    config.attack_followup_probability = std::clamp(
        config.attack_followup_probability, 0.0f, 1.0f);
    config.drawn_sword_attack_probability = std::clamp(
        config.drawn_sword_attack_probability, 0.0f, 1.0f);
    config.hit_probability = std::clamp(config.hit_probability, 0.0f, 1.0f);
    config.parry_probability = std::clamp(config.parry_probability, 0.0f, 1.0f);
    config.head_turn_speed_degrees_per_second = NormalizeHeadTurnSpeed(
        config.head_turn_speed_degrees_per_second);
    config.proximity_threat_range_m = std::clamp(config.proximity_threat_range_m, 0.0f, 100.0f);
    config.vision_range_m = std::clamp(config.vision_range_m, 0.0f, 500.0f);
    config.head_vision_angle_degrees = std::clamp(config.head_vision_angle_degrees, 0.0f, 360.0f);
    config.sound_maximum_range_m = std::clamp(config.sound_maximum_range_m, 0.0f, 50.0f);
    config.running_sound_toward_leeway_degrees = std::clamp(
        config.running_sound_toward_leeway_degrees, 0.0f, 180.0f);
    config.non_threatening_minimum_seconds = std::clamp(
        config.non_threatening_minimum_seconds, 0.0f, 600.0f);
    config.non_threatening_maximum_seconds = std::clamp(
        config.non_threatening_maximum_seconds, 0.0f, 600.0f);
    if (config.non_threatening_minimum_seconds > config.non_threatening_maximum_seconds) {
        std::swap(config.non_threatening_minimum_seconds,
            config.non_threatening_maximum_seconds);
    }
    config.follow_walk_distance_m = std::clamp(config.follow_walk_distance_m, 0.0f, 100.0f);
    config.follow_stop_distance_m = std::clamp(
        config.follow_stop_distance_m, 0.0f, config.follow_walk_distance_m);
    config.target_commitment_seconds = std::clamp(
        config.target_commitment_seconds, 0.0f, 10.0f);
    config.sector_influence_distance_m = std::clamp(
        config.sector_influence_distance_m, config.attack_range_m, 50.0f);
    config.containment_early_influence = std::clamp(
        config.containment_early_influence, 0.0f, 0.2f);
    config.sector_angle_variation_degrees = std::clamp(
        config.sector_angle_variation_degrees, 0.0f, 22.5f);
    config.sector_radius_variation_m = std::clamp(
        config.sector_radius_variation_m, 0.0f, 1.0f);
    config.ally_spacing_distance_m = std::clamp(
        config.ally_spacing_distance_m, 0.0f, 5.0f);
    config.crawl_speed_scale = std::clamp(config.crawl_speed_scale, 0.0f, 1.0f);
    config.crawl_turn_scale = std::clamp(config.crawl_turn_scale, 0.0f, 1.0f);
    NormalizeStunDurations(config.sword_attack_stun_seconds);
    NormalizeStunDurations(config.melee_attack_stun_seconds);
    config.melee_wound_gain = std::clamp(config.melee_wound_gain, 0.0f, 500.0f);
    config.wound_threshold = std::clamp(config.wound_threshold, 1.0f, 500.0f);
    config.wound_decay_per_second = std::clamp(config.wound_decay_per_second, 0.0f, 100.0f);
    config.leg_agonising_seconds = std::clamp(config.leg_agonising_seconds, 0.0f, 120.0f);
    config.torso_agonising_seconds = std::clamp(config.torso_agonising_seconds, 0.0f, 120.0f);
    config.head_passed_out_seconds = std::clamp(config.head_passed_out_seconds, 0.0f, 120.0f);
    if (config.world_min.x > config.world_max.x) std::swap(config.world_min.x, config.world_max.x);
    if (config.world_min.y > config.world_max.y) std::swap(config.world_min.y, config.world_max.y);
    if (config.opening_transforms.size() != config.agent_count) {
        config.opening_transforms.clear();
    } else {
        for (std::size_t index = 0; index < config.opening_transforms.size(); ++index) {
            AgentTransform& transform = config.opening_transforms[index];
            transform.id = static_cast<EntityId>(index + 1U);
            if (!NormalizeTransform(config, transform)) {
                config.opening_transforms.clear();
                break;
            }
        }
    }
    if (config.initial_sticks.size() > kMaxSimulationStickCount) {
        config.initial_sticks.resize(kMaxSimulationStickCount);
    }
    for (std::size_t index = 0; index < config.initial_sticks.size(); ++index) {
        StickTransform& transform = config.initial_sticks[index];
        transform.id = static_cast<StickId>(index + 1U);
        if (!NormalizeStickTransform(config, transform)) {
            transform = {};
            transform.id = static_cast<StickId>(index + 1U);
        }
    }
    return config;
}

double AngleTo(Vec2 from, Vec2 to) noexcept {
    return std::atan2(to.x - from.x, to.z - from.z);
}

double WrapAngle(double angle) noexcept {
    return std::remainder(angle, 2.0 * kPi);
}

Vec2 Add(Vec2 left, Vec2 right) noexcept {
    return {left.x + right.x, left.z + right.z};
}

Vec2 Scale(Vec2 value, double scale) noexcept {
    return {value.x * scale, value.z * scale};
}

double Length(Vec2 value) noexcept {
    return std::hypot(value.x, value.z);
}

Vec2 UnitOrZero(Vec2 value) noexcept {
    const double length = Length(value);
    return length > 1.0e-8 ? Scale(value, 1.0 / length) : Vec2{};
}

double MoveAngleTowards(double current, double target, double maximum_delta) noexcept {
    const double delta = WrapAngle(target - current);
    if (std::fabs(delta) <= maximum_delta) return WrapAngle(target);
    return WrapAngle(current + std::copysign(maximum_delta, delta));
}

double MoveTowards(double current, double target, double maximum_delta) noexcept {
    const double delta = target - current;
    if (std::fabs(delta) <= maximum_delta) return target;
    return current + std::copysign(maximum_delta, delta);
}

double HeadAnchorHeight(AgentState state) noexcept {
    constexpr double kReferenceHeadHeight = 1.495376;
    if (state == AgentState::Agonising) return 0.10 + kReferenceHeadHeight * 0.28;
    if (state == AgentState::PassedOut) return 0.09;
    if (state == AgentState::Crawling) return 0.10 + kReferenceHeadHeight * 0.32;
    if (state == AgentState::Dead) return 0.055;
    return kReferenceHeadHeight;
}

float PosePhase(const LocomotionState& state, LocomotionMode mode) noexcept {
    // Full-body source cycles span 120 walk frames at 2 m/s and 75 run frames at 5 m/s.
    const double cycle_distance = mode == LocomotionMode::Run ? 12.5 : 8.00007152557373;
    return static_cast<float>(std::fmod(state.distance_travelled, cycle_distance) / cycle_distance);
}

}  // namespace

struct Simulation::Impl final {
    struct ActionRuntime {
        std::uint64_t sequence = 0;
        ActionKind kind = ActionKind::None;
        ActionPhase phase = ActionPhase::Idle;
        HandUsage hands = HandUsage::None;
        WeaponKind weapon = WeaponKind::None;
        StickId target_stick_id = kInvalidStickId;
        Vec2 target_position{};
        std::uint32_t phase_elapsed_ticks = 0;
        std::uint32_t total_elapsed_ticks = 0;
        std::uint32_t duration_ticks = 1;
        std::uint32_t stun_duration_ticks = 0;
        float duration_seconds = 0.0f;
        float stun_duration_seconds = 0.0f;
        std::uint8_t animation_index = 0;
        EntityId pending_hit_defender_id = kInvalidEntityId;
        bool parried = false;
        bool validation_required = false;
    };

    struct StickRuntime {
        StickId id = kInvalidStickId;
        Vec2 position{};
        double facing_radians = 0.0;
        EntityId holder_id = kInvalidEntityId;
    };

    struct ReactionRuntime {
        ReactionKind kind = ReactionKind::None;
        std::uint32_t elapsed_ticks = 0;
        std::uint32_t duration_ticks = 1;
        float duration_seconds = 0.0f;
    };

    struct LimbWoundRuntime {
        float gauge = 0.0f;
        std::uint64_t updated_tick = 0;
        LimbCondition condition = LimbCondition::Normal;
    };

    struct AgentRuntime {
        EntityId id = kInvalidEntityId;
        Team team = Team::Hero;
        LocomotionState locomotion{};
        LocomotionIntent intent{};
        bool sword_equipped = true;
        SwordState sword_state = SwordState::Sheathed;
        StickId held_stick_id = kInvalidStickId;
        StickId pending_stick_pickup_id = kInvalidStickId;
        Vec2 dropped_sword_position{};
        double dropped_sword_yaw_radians = 0.0;
        BehaviorMode behavior_mode = BehaviorMode::Idle;
        bool combat_enabled = false;
        EntityId attack_target_id = kInvalidEntityId;
        EntityId follow_target_id = kInvalidEntityId;
        EntityId draw_retreat_target_id = kInvalidEntityId;
        EntityId rescue_executioner_id = kInvalidEntityId;
        EntityId rescue_former_target_id = kInvalidEntityId;
        std::uint64_t rescue_head_hold_until_tick = 0;
        float target_distance_m = 0.0f;
        Vec2 engagement_anchor{};
        TacticalSteeringMode tactical_steering = TacticalSteeringMode::Direct;
        std::uint32_t tactical_threat_count = 0;
        double tactical_containment_influence = 0.0;
        double tactical_threat_arc_radians = 0.0;
        double tactical_nearest_peer_separation_radians = 0.0;
        double tactical_view_center_yaw_radians = 0.0;
        double tactical_move_yaw_radians = 0.0;
        EntityId approach_sector_target_id = kInvalidEntityId;
        std::uint8_t approach_sector_index = static_cast<std::uint8_t>(kApproachSectorCount);
        double approach_sector_yaw_radians = 0.0;
        double approach_sector_radius_m = 0.0;
        double tactical_sector_error_radians = 0.0;
        double tactical_sector_influence = 0.0;
        std::uint32_t target_commitment_ticks_remaining = 0;
        HeadLookMode head_look_mode = HeadLookMode::RootHeading;
        EntityId head_look_target_id = kInvalidEntityId;
        double head_yaw_offset_radians = 0.0;
        double head_pitch_radians = 0.0;
        double head_scan_direction = 1.0;
        std::uint8_t head_scan_endpoint_count = 0;
        EntityId sound_investigation_source_id = kInvalidEntityId;
        std::bitset<kMaxSimulationAgentCount> recognized_threats{};
        std::bitset<kMaxSimulationAgentCount> non_dead_seen_during_scan{};
        std::bitset<kMaxSimulationAgentCount> finishing_targets{};
        EntityId pending_grunt_target_id = kInvalidEntityId;
        bool suppress_next_grunt = false;
        std::array<std::uint64_t, kMaxSimulationAgentCount> non_threatening_until_ticks{};
        std::uint32_t completed_attacks = 0;
        std::uint32_t attack_cooldown_ticks_remaining = 0;
        bool cooldown_strafe_enabled = false;
        double cooldown_strafe_direction = 1.0;
        double cooldown_strafe_target_distance_m = 0.0;
        double cooldown_strafe_distance_remaining_m = 0.0;
        Vec2 cooldown_strafe_last_position{};
        bool attack_requested = false;
        AgentState state = AgentState::Normal;
        std::uint32_t state_ticks_remaining = 0;
        std::array<LimbWoundRuntime, kLimbCount> wounds{};
        ActionRuntime action{};
        ReactionRuntime reaction{};
    };

    struct LandingEvent {
        EntityId attacker_id = kInvalidEntityId;
        EntityId defender_id = kInvalidEntityId;
        ActionRuntime attack{};
    };

    struct StartedAttack {
        EntityId attacker_id = kInvalidEntityId;
        EntityId defender_id = kInvalidEntityId;
        ActionRuntime action{};
        bool defender_attacking_at_launch = false;
    };

    struct ThreatArc {
        std::uint32_t count = 0;
        double center_yaw_radians = 0.0;
        double span_radians = 0.0;
    };

    struct PerceptionRuntime {
        std::bitset<kMaxSimulationAgentCount> active_threats{};
        PerceptionSnapshot snapshot{};
        EntityId nearest_proximity_id = kInvalidEntityId;
        EntityId nearest_visible_id = kInvalidEntityId;
    };

    explicit Impl(SimulationConfig in_config, std::uint64_t in_seed) noexcept
        : config(NormalizeConfig(std::move(in_config))) {
        agents.reserve(kMaxSimulationAgentCount);
        snapshot.agents.reserve(kMaxSimulationAgentCount);
        sticks.reserve(kMaxSimulationStickCount);
        snapshot.sticks.reserve(kMaxSimulationStickCount);
        landing_events.reserve(kMaxSimulationAgentCount);
        started_attacks.reserve(kMaxSimulationAgentCount);
        perceptions.resize(config.agent_count);
        Reset(in_seed);
    }

    void BeginTimedAction(AgentRuntime& agent, ActionKind kind, HandUsage hands,
        ActionPhase active_phase, float requested_duration_seconds, bool validation_required,
        std::uint8_t animation_index = 0, float stun_duration_seconds = 0.0f) noexcept {
        const std::uint32_t duration_ticks = std::max(1U, static_cast<std::uint32_t>(
            std::lround(static_cast<double>(requested_duration_seconds) * config.tick_rate_hz)));
        agent.action = {};
        agent.action.sequence = next_action_sequence++;
        agent.action.kind = kind;
        agent.action.phase = active_phase;
        agent.action.hands = hands;
        agent.action.duration_ticks = duration_ticks;
        agent.action.duration_seconds = static_cast<float>(duration_ticks) / config.tick_rate_hz;
        agent.action.stun_duration_ticks = CooldownTicks(stun_duration_seconds);
        agent.action.stun_duration_seconds = static_cast<float>(agent.action.stun_duration_ticks) /
            config.tick_rate_hz;
        agent.action.animation_index = animation_index;
        agent.action.validation_required = validation_required;
    }

    void EmitSound(const AgentRuntime& agent, SoundEventKind kind, float maximum_range_m,
        EntityId secondary_source_id = kInvalidEntityId,
        std::uint8_t recipient_count = 0U) noexcept {
        SoundEventSnapshot event{};
        event.sequence = next_sound_event_sequence++;
        event.emitted_tick = tick + 1U;
        event.source_id = agent.id;
        event.secondary_source_id = secondary_source_id;
        event.kind = kind;
        event.position = {static_cast<float>(agent.locomotion.position.x),
            static_cast<float>(agent.locomotion.position.z), 0.0f};
        event.maximum_range_m = std::clamp(maximum_range_m, 0.0f, config.sound_maximum_range_m);
        event.recipient_count = recipient_count;
        if (sound_event_count < sound_events.size()) {
            const std::size_t write_index = (sound_event_start + sound_event_count) % sound_events.size();
            sound_events[write_index] = event;
            ++sound_event_count;
            return;
        }
        sound_events[sound_event_start] = event;
        sound_event_start = (sound_event_start + 1U) % sound_events.size();
    }

    void ClearExecutionRescue(AgentRuntime& agent) noexcept {
        agent.rescue_executioner_id = kInvalidEntityId;
        agent.rescue_former_target_id = kInvalidEntityId;
        agent.rescue_head_hold_until_tick = 0;
    }

    void EmitExecutionScream(AgentRuntime& victim, AgentRuntime& executioner) noexcept {
        AgentRuntime* responder = nullptr;
        double nearest_distance_squared = std::numeric_limits<double>::infinity();
        const double maximum_range_squared =
            static_cast<double>(config.sound_maximum_range_m) * config.sound_maximum_range_m;
        for (AgentRuntime& candidate : agents) {
            if (candidate.id == victim.id || candidate.team != victim.team ||
                !IsStandingThreat(candidate)) continue;
            const double delta_x = candidate.locomotion.position.x - victim.locomotion.position.x;
            const double delta_z = candidate.locomotion.position.z - victim.locomotion.position.z;
            const double distance_squared = delta_x * delta_x + delta_z * delta_z;
            if (distance_squared > maximum_range_squared) continue;
            if (distance_squared < nearest_distance_squared - 1.0e-9 ||
                (std::fabs(distance_squared - nearest_distance_squared) <= 1.0e-9 &&
                    (responder == nullptr || candidate.id < responder->id))) {
                responder = &candidate;
                nearest_distance_squared = distance_squared;
            }
        }

        EmitSound(victim, SoundEventKind::ExecutionScream, config.sound_maximum_range_m,
            executioner.id, responder == nullptr ? 0U : 1U);
        if (responder == nullptr) return;

        EntityId former_target_id = responder->attack_target_id;
        AgentRuntime* former_target = FindRuntime(former_target_id);
        if (former_target == nullptr || former_target->team == responder->team ||
            former_target->state == AgentState::Dead) {
            former_target_id = kInvalidEntityId;
        }

        responder->rescue_executioner_id = executioner.id;
        responder->rescue_former_target_id = former_target_id;
        responder->rescue_head_hold_until_tick = tick + 1U + CooldownTicks(1.0f);
        responder->behavior_mode = BehaviorMode::Attack;
        responder->attack_target_id = executioner.id;
        responder->follow_target_id = kInvalidEntityId;
        responder->sound_investigation_source_id = kInvalidEntityId;
        responder->head_scan_endpoint_count = 0U;
        responder->recognized_threats.set(static_cast<std::size_t>(executioner.id - 1U));
        if (former_target_id != kInvalidEntityId) {
            responder->recognized_threats.set(
                static_cast<std::size_t>(former_target_id - 1U));
        }
    }

    void RefreshExecutionRescues() noexcept {
        for (AgentRuntime& responder : agents) {
            if (responder.rescue_executioner_id == kInvalidEntityId) continue;
            AgentRuntime* executioner = FindRuntime(responder.rescue_executioner_id);
            if (IsIncapacitated(responder.state) || executioner == nullptr ||
                executioner->team == responder.team || !IsStandingThreat(*executioner)) {
                ClearExecutionRescue(responder);
                continue;
            }
            AgentRuntime* former_target = FindRuntime(responder.rescue_former_target_id);
            if (former_target == nullptr || former_target->team == responder.team ||
                former_target->state == AgentState::Dead) {
                responder.rescue_former_target_id = kInvalidEntityId;
            }
            responder.behavior_mode = BehaviorMode::Attack;
            responder.attack_target_id = executioner->id;
            responder.follow_target_id = kInvalidEntityId;
            responder.recognized_threats.set(
                static_cast<std::size_t>(executioner->id - 1U));
        }
    }

    void EmitLocomotionSounds() noexcept {
        const std::uint32_t interval_ticks = std::max(1U, static_cast<std::uint32_t>(std::lround(
            static_cast<double>(kLocomotionSoundIntervalSeconds) * config.tick_rate_hz)));
        if ((tick + 1U) % interval_ticks != 0U) return;
        for (const AgentRuntime& agent : agents) {
            if (IsIncapacitated(agent.state)) continue;
            const float speed_mps = static_cast<float>(std::hypot(
                agent.locomotion.velocity.x, agent.locomotion.velocity.z));
            const float maximum_range_m = config.sound_maximum_range_m *
                std::clamp(speed_mps / kRunSoundReferenceSpeedMps, 0.0f, 1.0f);
            if (maximum_range_m > 0.0f) {
                EmitSound(agent, SoundEventKind::Locomotion, maximum_range_m);
            }
        }
    }

    bool RunningToward(const AgentRuntime& source, const AgentRuntime& listener) const noexcept {
        if (source.intent.mode != LocomotionMode::Run) return false;
        const Vec2 velocity{source.locomotion.velocity.x, source.locomotion.velocity.z};
        const Vec2 toward_listener{
            listener.locomotion.position.x - source.locomotion.position.x,
            listener.locomotion.position.z - source.locomotion.position.z};
        const double speed = Length(velocity);
        const double distance = Length(toward_listener);
        if (speed <= 1.0e-6 || distance <= 1.0e-6) return false;
        const double cosine = (velocity.x * toward_listener.x + velocity.z * toward_listener.z) /
            (speed * distance);
        const double leeway_radians = static_cast<double>(
            config.running_sound_toward_leeway_degrees) * kPi / 180.0;
        return cosine >= std::cos(leeway_radians);
    }

    void UpdateSoundAwareness(std::uint64_t effective_tick) noexcept {
        for (std::size_t offset = 0; offset < sound_event_count; ++offset) {
            const std::size_t event_index =
                (sound_event_start + sound_event_count - 1U - offset) % sound_events.size();
            const SoundEventSnapshot& event =
                sound_events[event_index];
            if (event.emitted_tick < effective_tick) break;
            if (effective_tick != event.emitted_tick || event.maximum_range_m <= 0.0f) continue;
            AgentRuntime* source = FindRuntime(event.source_id);
            AgentRuntime* secondary = FindRuntime(event.secondary_source_id);
            if (event.kind == SoundEventKind::Parry) {
                if (source == nullptr || secondary == nullptr) continue;
                for (AgentRuntime& listener : agents) {
                    if (listener.behavior_mode != BehaviorMode::Idle ||
                        !CanInvestigateSound(listener.state) ||
                        listener.sound_investigation_source_id != kInvalidEntityId ||
                        IsAttacking(listener) || listener.reaction.kind != ReactionKind::None) continue;
                    AgentRuntime* enemy_source = listener.team == source->team ? secondary : source;
                    if (enemy_source->team == listener.team || enemy_source->id == listener.id) continue;
                    const double event_delta_x = static_cast<double>(event.position.x) -
                        listener.locomotion.position.x;
                    const double event_delta_z = static_cast<double>(event.position.y) -
                        listener.locomotion.position.z;
                    if (std::hypot(event_delta_x, event_delta_z) >
                        static_cast<double>(event.maximum_range_m)) continue;
                    listener.sound_investigation_source_id = enemy_source->id;
                }
                continue;
            }
            if (event.kind != SoundEventKind::Locomotion || source == nullptr ||
                !IsStandingThreat(*source)) continue;
            for (AgentRuntime& listener : agents) {
                if (listener.team == source->team || !CanInvestigateSound(listener.state) ||
                    listener.sound_investigation_source_id != kInvalidEntityId ||
                    listener.rescue_executioner_id != kInvalidEntityId) continue;
                const double event_delta_x = static_cast<double>(event.position.x) -
                    listener.locomotion.position.x;
                const double event_delta_z = static_cast<double>(event.position.y) -
                    listener.locomotion.position.z;
                const double event_distance = std::hypot(event_delta_x, event_delta_z);
                if (event_distance > static_cast<double>(event.maximum_range_m)) continue;
                const std::size_t source_index = static_cast<std::size_t>(source->id - 1U);
                const bool already_active = InsideHeadVisionHemisphere(listener, *source) ||
                    (listener.recognized_threats.test(source_index) &&
                        InsideProximityRadius(listener, *source));
                const std::size_t listener_index = static_cast<std::size_t>(listener.id - 1U);
                // Engaged listeners filter distractions by direction; idle listeners check any movement.
                const bool has_active_threats = listener_index < perceptions.size() &&
                    perceptions[listener_index].active_threats.any();
                if (already_active || (has_active_threats && !RunningToward(*source, listener)) ||
                    IsAttacking(listener) ||
                    listener.reaction.kind == ReactionKind::Parry ||
                    listener.reaction.kind == ReactionKind::Dodge) continue;
                if (listener.non_threatening_until_ticks[source_index] > effective_tick) continue;
                listener.sound_investigation_source_id = source->id;
            }
        }
    }

    void ProcessGruntDiscoveries() noexcept {
        std::bitset<kMaxSimulationAgentCount> received_grunt{};
        for (std::size_t source_index = 0; source_index < agents.size(); ++source_index) {
            AgentRuntime& source = agents[source_index];
            const EntityId target_id = source.pending_grunt_target_id;
            if (target_id == kInvalidEntityId) continue;
            source.pending_grunt_target_id = kInvalidEntityId;
            if (source.suppress_next_grunt) {
                source.suppress_next_grunt = false;
                continue;
            }

            AgentRuntime* target = FindRuntime(target_id);
            if (target == nullptr || target->team == source.team ||
                !IsStandingThreat(source) || !IsStandingThreat(*target)) continue;

            std::array<std::size_t, kGruntPropagationAgentLimit> listener_indices{};
            std::array<double, kGruntPropagationAgentLimit> listener_distances{};
            std::size_t listener_count = 0;
            const double maximum_distance_squared =
                static_cast<double>(config.sound_maximum_range_m) * config.sound_maximum_range_m;
            for (std::size_t listener_index = 0; listener_index < agents.size(); ++listener_index) {
                const AgentRuntime& listener = agents[listener_index];
                if (listener_index == source_index || listener.team != source.team ||
                    IsIncapacitated(listener.state) || received_grunt.test(listener_index)) continue;
                const double delta_x = listener.locomotion.position.x - source.locomotion.position.x;
                const double delta_z = listener.locomotion.position.z - source.locomotion.position.z;
                const double distance_squared = delta_x * delta_x + delta_z * delta_z;
                if (distance_squared > maximum_distance_squared) continue;

                std::size_t insertion = 0;
                while (insertion < listener_count &&
                    distance_squared >= listener_distances[insertion]) ++insertion;
                if (insertion >= kGruntPropagationAgentLimit) continue;
                if (listener_count < kGruntPropagationAgentLimit) ++listener_count;
                for (std::size_t shift = listener_count - 1U; shift > insertion; --shift) {
                    listener_indices[shift] = listener_indices[shift - 1U];
                    listener_distances[shift] = listener_distances[shift - 1U];
                }
                listener_indices[insertion] = listener_index;
                listener_distances[insertion] = distance_squared;
            }

            EmitSound(source, SoundEventKind::Grunt, config.sound_maximum_range_m,
                target_id, static_cast<std::uint8_t>(listener_count));
            for (std::size_t index = 0; index < listener_count; ++index) {
                const std::size_t listener_index = listener_indices[index];
                AgentRuntime& listener = agents[listener_index];
                received_grunt.set(listener_index);
                if (listener.pending_grunt_target_id == target_id) {
                    listener.pending_grunt_target_id = kInvalidEntityId;
                }
                listener.sound_investigation_source_id = kInvalidEntityId;
                listener.draw_retreat_target_id = kInvalidEntityId;
                if (InsideHeadVisionHemisphere(listener, *target)) {
                    listener.behavior_mode = BehaviorMode::Attack;
                    listener.attack_target_id = target_id;
                    listener.follow_target_id = kInvalidEntityId;
                    listener.suppress_next_grunt = false;
                    listener.head_scan_endpoint_count = 0U;
                } else {
                    listener.behavior_mode = BehaviorMode::Follow;
                    listener.attack_target_id = kInvalidEntityId;
                    listener.follow_target_id = source.id;
                    listener.suppress_next_grunt = true;
                }
            }
        }
    }

    std::uint64_t DecisionWord(const AgentRuntime& agent, std::uint64_t salt) const noexcept {
        return Mix64(seed ^ (static_cast<std::uint64_t>(agent.id) << 32U) ^
            next_action_sequence ^ (tick * 0x9e3779b97f4a7c15ULL) ^ salt);
    }

    bool LimbInjured(const AgentRuntime& agent, Limb limb) const noexcept {
        return agent.wounds[LimbIndex(limb)].condition != LimbCondition::Normal;
    }

    WeaponKind HeldWeapon(const AgentRuntime& agent) const noexcept {
        if (agent.held_stick_id != kInvalidStickId) return WeaponKind::Stick;
        if (agent.sword_equipped && agent.sword_state == SwordState::Drawn) {
            return WeaponKind::Sword;
        }
        return WeaponKind::None;
    }

    StickRuntime* FindStick(StickId id) noexcept {
        if (id == kInvalidStickId || id > sticks.size()) return nullptr;
        StickRuntime& stick = sticks[static_cast<std::size_t>(id - 1U)];
        return stick.id == id ? &stick : nullptr;
    }

    const StickRuntime* FindStick(StickId id) const noexcept {
        if (id == kInvalidStickId || id > sticks.size()) return nullptr;
        const StickRuntime& stick = sticks[static_cast<std::size_t>(id - 1U)];
        return stick.id == id ? &stick : nullptr;
    }

    bool BeginAttack(AgentRuntime& agent) noexcept {
        constexpr std::uint64_t kAttackKindSalt = 0x41545441434b4b49ULL;
        constexpr std::uint64_t kAttackClipSalt = 0x41545441434b434cULL;
        const AgentRuntime* target = FindRuntime(agent.attack_target_id);
        const bool grounded_target = target != nullptr && IsGroundedTarget(target->state);
        const WeaponKind weapon = HeldWeapon(agent);
        const bool weapon_available = weapon != WeaponKind::None &&
            !LimbInjured(agent, Limb::RightArm);
        const double attack_kind_roll = UnitRandom(DecisionWord(agent, kAttackKindSalt));
        const bool sword_attack = weapon_available &&
            (grounded_target
                ? weapon == WeaponKind::Sword
                : attack_kind_roll < (weapon == WeaponKind::Sword
                    ? static_cast<double>(config.drawn_sword_attack_probability)
                    : 0.9));
        if (sword_attack) {
            const std::uint64_t clip_decision = DecisionWord(agent, kAttackClipSalt);
            const std::uint8_t clip = grounded_target
                ? kGroundedSwordAttackClips[clip_decision % kGroundedSwordAttackClips.size()]
                : static_cast<std::uint8_t>(clip_decision % kSwordAttackClips.size());
            const AttackClipSpec& spec = kSwordAttackClips[clip];
            BeginTimedAction(agent, ActionKind::SwordAttack, spec.hands, ActionPhase::Executing,
                static_cast<float>(spec.frame_count) / kAttackSourceFps,
                false, clip, config.sword_attack_stun_seconds[clip]);
            agent.action.weapon = weapon;
            return true;
        }
        std::array<std::uint8_t, kMeleeAttackClips.size()> valid_clips{};
        std::size_t valid_count = 0;
        for (std::size_t index = 0; index < kMeleeAttackClips.size(); ++index) {
            const Limb attack_limb = kMeleeAttackClips[index].limb;
            const bool kick = attack_limb == Limb::LeftLeg || attack_limb == Limb::RightLeg;
            if ((!grounded_target || kick) && !LimbInjured(agent, attack_limb)) {
                valid_clips[valid_count++] = static_cast<std::uint8_t>(index);
            }
        }
        if (valid_count == 0) return false;
        const std::uint8_t clip = valid_clips[DecisionWord(agent, kAttackClipSalt) % valid_count];
        const AttackClipSpec& spec = kMeleeAttackClips[clip];
        BeginTimedAction(agent, ActionKind::MeleeAttack, spec.hands, ActionPhase::Executing,
            static_cast<float>(spec.frame_count) / kAttackSourceFps,
            false, clip, config.melee_attack_stun_seconds[clip]);
        return true;
    }

    void BeginAttackCooldown(AgentRuntime& agent, float seconds,
        std::uint64_t action_sequence) noexcept {
        constexpr std::uint64_t kCooldownMovementSalt = 0x434f4f4c4d4f5645ULL;
        constexpr std::uint64_t kCooldownDistanceSalt = 0x5354524146454449ULL;
        agent.attack_cooldown_ticks_remaining = CooldownTicks(seconds);
        agent.cooldown_strafe_last_position = agent.locomotion.position;
        const AgentRuntime* target = FindRuntime(agent.attack_target_id);
        const bool grounded_finishing = target != nullptr && IsGroundedTarget(target->state);
        if (agent.attack_cooldown_ticks_remaining == 0U || grounded_finishing) {
            agent.cooldown_strafe_enabled = false;
            agent.cooldown_strafe_direction = 1.0;
            agent.cooldown_strafe_target_distance_m = 0.0;
            agent.cooldown_strafe_distance_remaining_m = 0.0;
            return;
        }
        const std::uint64_t decision = Mix64(seed ^
            (static_cast<std::uint64_t>(agent.id) << 32U) ^ action_sequence ^
            kCooldownMovementSalt);
        agent.cooldown_strafe_enabled = (decision & 1U) == 0U;
        agent.cooldown_strafe_direction = (decision & 2U) == 0U ? -1.0 : 1.0;
        agent.cooldown_strafe_target_distance_m = agent.cooldown_strafe_enabled
            ? 0.5 + 0.5 * UnitRandom(decision ^ kCooldownDistanceSalt)
            : 0.0;
        agent.cooldown_strafe_distance_remaining_m =
            agent.cooldown_strafe_target_distance_m;
    }

    bool BeginStickPickup(AgentRuntime& agent, StickId stick_id) noexcept {
        StickRuntime* stick = FindStick(stick_id);
        if (stick == nullptr || stick->holder_id != kInvalidEntityId ||
            agent.held_stick_id != kInvalidStickId ||
            agent.sword_state != SwordState::Sheathed ||
            LimbInjured(agent, Limb::RightArm)) return false;
        BeginTimedAction(agent, ActionKind::PickUpStick, HandUsage::Right,
            ActionPhase::Reaching, config.stick_pickup_action_seconds,
            config.mode == SimulationMode::Paired);
        agent.action.target_stick_id = stick_id;
        agent.action.target_position = stick->position;
        return true;
    }

    void DropHeldStickNow(AgentRuntime& agent) noexcept {
        StickRuntime* stick = FindStick(agent.held_stick_id);
        if (stick != nullptr && stick->holder_id == agent.id) {
            stick->holder_id = kInvalidEntityId;
            stick->position = agent.locomotion.position;
            stick->facing_radians = agent.locomotion.yaw_radians;
        }
        agent.held_stick_id = kInvalidStickId;
    }

    void DropDrawnSwordNow(AgentRuntime& agent) noexcept {
        if (agent.sword_state != SwordState::Drawn) return;
        agent.sword_state = SwordState::Dropped;
        agent.dropped_sword_position = agent.locomotion.position;
        agent.dropped_sword_yaw_radians = agent.locomotion.yaw_radians;
    }

    void DropHandHeldEquipmentForDowning(AgentRuntime& agent) noexcept {
        if (agent.held_stick_id != kInvalidStickId) DropHeldStickNow(agent);
        DropDrawnSwordNow(agent);
        agent.pending_stick_pickup_id = kInvalidStickId;
    }

    void CompleteAction(AgentRuntime& agent, bool success) noexcept {
        const ActionRuntime completed_action = agent.action;
        const ActionKind completed_kind = completed_action.kind;
        const bool completed_attack = completed_kind == ActionKind::SwordAttack ||
            completed_kind == ActionKind::MeleeAttack;
        const bool attack_was_parried = completed_attack && completed_action.parried;
        const std::uint64_t completed_sequence = completed_action.sequence;
        if (success) {
            if (completed_kind == ActionKind::SheatheSword) agent.sword_state = SwordState::Sheathed;
            else if (completed_kind == ActionKind::UnsheatheSword) {
                agent.sword_state = SwordState::Drawn;
                agent.draw_retreat_target_id = kInvalidEntityId;
            }
            else if (completed_kind == ActionKind::PickUpStick) {
                StickRuntime* stick = FindStick(completed_action.target_stick_id);
                if (stick != nullptr && stick->holder_id == kInvalidEntityId &&
                    agent.held_stick_id == kInvalidStickId) {
                    stick->holder_id = agent.id;
                    agent.held_stick_id = stick->id;
                }
            }
            else if (completed_kind == ActionKind::DropStick) {
                DropHeldStickNow(agent);
            }
            else if (completed_attack && !attack_was_parried) ++agent.completed_attacks;
        }
        agent.action = {};
        if (completed_kind == ActionKind::SheatheSword) {
            const StickId queued_stick_id = agent.pending_stick_pickup_id;
            agent.pending_stick_pickup_id = kInvalidStickId;
            if (success && queued_stick_id != kInvalidStickId) {
                (void)BeginStickPickup(agent, queued_stick_id);
            }
        }
        if (completed_attack) {
            constexpr std::uint64_t kFollowupSalt = 0x464f4c4c4f575550ULL;
            const bool immediate_followup = !attack_was_parried &&
                UnitRandom(seed ^ completed_sequence ^
                    (static_cast<std::uint64_t>(agent.id) << 32U) ^ kFollowupSalt) <
                    config.attack_followup_probability;
            const float cooldown_seconds = attack_was_parried
                ? config.parried_attack_cooldown_seconds
                : (immediate_followup ? 0.0f : config.attack_cooldown_seconds);
            BeginAttackCooldown(agent, cooldown_seconds, completed_sequence);
        }
    }

    bool AdvanceAction(AgentRuntime& agent) noexcept {
        if (agent.action.phase == ActionPhase::Reaching || agent.action.phase == ActionPhase::Executing) {
            ++agent.action.total_elapsed_ticks;
            ++agent.action.phase_elapsed_ticks;
            if (agent.action.phase_elapsed_ticks >= agent.action.duration_ticks) {
                if (agent.action.validation_required) {
                    agent.action.phase = ActionPhase::AwaitingValidation;
                    agent.action.phase_elapsed_ticks = 0;
                } else {
                    return true;
                }
            }
        }
        return false;
    }

    bool IsAttacking(const AgentRuntime& agent) const noexcept {
        return agent.action.kind == ActionKind::SwordAttack || agent.action.kind == ActionKind::MeleeAttack;
    }

    std::uint32_t CooldownTicks(float seconds) const noexcept {
        if (!std::isfinite(seconds) || seconds <= 0.0f) return 0U;
        const double ticks = std::round(static_cast<double>(seconds) * config.tick_rate_hz);
        if (ticks >= static_cast<double>(std::numeric_limits<std::uint32_t>::max())) {
            return std::numeric_limits<std::uint32_t>::max();
        }
        return static_cast<std::uint32_t>(ticks);
    }

    void MarkAttackParried(AgentRuntime& attacker, std::uint64_t sequence) noexcept {
        if (!IsAttacking(attacker) || attacker.action.sequence != sequence) return;
        attacker.action.parried = true;
    }

    void MarkPendingHit(AgentRuntime& attacker, std::uint64_t sequence,
        EntityId defender_id) noexcept {
        if (!IsAttacking(attacker) || attacker.action.sequence != sequence) return;
        attacker.action.pending_hit_defender_id = defender_id;
    }

    void CancelAttackOnHit(AgentRuntime& defender) noexcept {
        if (!IsAttacking(defender)) return;
        defender.action = {};
        defender.attack_requested = false;
    }

    float CurrentWoundGauge(const LimbWoundRuntime& wound) const noexcept {
        const double elapsed_seconds = static_cast<double>(tick - wound.updated_tick) /
            static_cast<double>(config.tick_rate_hz);
        return std::max(0.0f, wound.gauge -
            static_cast<float>(elapsed_seconds) * config.wound_decay_per_second);
    }

    void MaterializeWounds(AgentRuntime& agent) noexcept {
        for (LimbWoundRuntime& wound : agent.wounds) {
            wound.gauge = CurrentWoundGauge(wound);
            wound.updated_tick = tick;
        }
    }

    void EnterCrawling(AgentRuntime& agent) noexcept {
        if (agent.state == AgentState::Crawling) return;
        ClearExecutionRescue(agent);
        DropHandHeldEquipmentForDowning(agent);
        agent.combat_enabled = false;
        agent.behavior_mode = BehaviorMode::Idle;
        agent.attack_target_id = kInvalidEntityId;
        agent.follow_target_id = kInvalidEntityId;
        agent.draw_retreat_target_id = kInvalidEntityId;
        agent.pending_grunt_target_id = kInvalidEntityId;
        agent.non_dead_seen_during_scan.reset();
        agent.finishing_targets.reset();
        agent.head_scan_endpoint_count = 2U;
        agent.suppress_next_grunt = false;
        agent.state = AgentState::Crawling;
        agent.state_ticks_remaining = 0;
        EmitSound(agent, SoundEventKind::CrawlYell, config.sound_maximum_range_m);
    }

    void EnterTimedState(AgentRuntime& agent, AgentState state, float seconds) noexcept {
        ClearExecutionRescue(agent);
        DropHandHeldEquipmentForDowning(agent);
        agent.action = {};
        agent.pending_stick_pickup_id = kInvalidStickId;
        agent.attack_requested = false;
        agent.intent.speed_amplitude = 0.0;
        if (agent.behavior_mode == BehaviorMode::Follow) agent.behavior_mode = BehaviorMode::Idle;
        agent.follow_target_id = kInvalidEntityId;
        agent.suppress_next_grunt = false;
        const std::uint32_t duration_ticks = CooldownTicks(seconds);
        if (duration_ticks == 0U) {
            EnterCrawling(agent);
            return;
        }
        agent.state = state;
        agent.state_ticks_remaining = duration_ticks;
    }

    bool VitalBadlyInjured(const AgentRuntime& agent) const noexcept {
        return agent.wounds[LimbIndex(Limb::Head)].condition == LimbCondition::BadlyInjured ||
            agent.wounds[LimbIndex(Limb::Torso)].condition == LimbCondition::BadlyInjured;
    }

    void StopForIncapacitation(AgentRuntime& agent) noexcept {
        ClearExecutionRescue(agent);
        agent.action = {};
        agent.pending_stick_pickup_id = kInvalidStickId;
        agent.attack_requested = false;
        agent.intent.speed_amplitude = 0.0;
        if (agent.behavior_mode == BehaviorMode::Follow) agent.behavior_mode = BehaviorMode::Idle;
        agent.follow_target_id = kInvalidEntityId;
        agent.suppress_next_grunt = false;
    }

    void KillAgent(AgentRuntime& agent) noexcept {
        DropHandHeldEquipmentForDowning(agent);
        StopForIncapacitation(agent);
        agent.combat_enabled = false;
        agent.behavior_mode = BehaviorMode::Idle;
        agent.attack_target_id = kInvalidEntityId;
        agent.follow_target_id = kInvalidEntityId;
        agent.draw_retreat_target_id = kInvalidEntityId;
        agent.target_distance_m = 0.0f;
        agent.locomotion.velocity = {};
        agent.locomotion.previous_yaw_radians = agent.locomotion.yaw_radians;
        agent.locomotion.response = LocomotionResponse::Stop;
        agent.state = AgentState::Dead;
        agent.state_ticks_remaining = 0;
    }

    void ApplyInitialInjuryEffects(AgentRuntime& agent, Limb limb) noexcept {
        if (agent.state == AgentState::Dead) return;
        if (limb == Limb::RightArm && agent.held_stick_id != kInvalidStickId) {
            DropHeldStickNow(agent);
            agent.pending_stick_pickup_id = kInvalidStickId;
            if (agent.action.kind == ActionKind::PickUpStick ||
                agent.action.kind == ActionKind::DropStick ||
                agent.action.kind == ActionKind::SwordAttack) {
                agent.action = {};
            }
        }
        if (limb == Limb::RightArm && agent.sword_state == SwordState::Drawn) {
            DropDrawnSwordNow(agent);
            if (agent.action.kind == ActionKind::SwordAttack) {
                const std::uint64_t interrupted_sequence = agent.action.sequence;
                agent.action = {};
                BeginAttackCooldown(agent, config.attack_cooldown_seconds, interrupted_sequence);
            }
        } else if (limb == Limb::RightArm &&
            agent.action.kind == ActionKind::UnsheatheSword) {
            agent.action = {};
        }

        if (limb == Limb::Head) {
            EnterTimedState(agent, AgentState::PassedOut, config.head_passed_out_seconds);
            return;
        }
        if (limb == Limb::Torso) {
            if (agent.state != AgentState::PassedOut) {
                EnterTimedState(agent, AgentState::Agonising, config.torso_agonising_seconds);
            }
            return;
        }
        if (limb == Limb::LeftLeg || limb == Limb::RightLeg) {
            const bool both_legs = LimbInjured(agent, Limb::LeftLeg) &&
                LimbInjured(agent, Limb::RightLeg);
            if (both_legs) {
                if (agent.state != AgentState::PassedOut && !LimbInjured(agent, Limb::Torso)) {
                    EnterTimedState(agent, AgentState::Agonising, config.leg_agonising_seconds);
                }
            } else if (agent.state == AgentState::Normal) {
                agent.state = AgentState::Slow;
            }
        }
    }

    void ApplyBadInjuryEffects(AgentRuntime& agent, Limb limb) noexcept {
        if (agent.state == AgentState::Dead || (limb != Limb::Head && limb != Limb::Torso)) return;
        DropHandHeldEquipmentForDowning(agent);
        StopForIncapacitation(agent);
        agent.state = limb == Limb::Head ||
                agent.wounds[LimbIndex(Limb::Head)].condition != LimbCondition::Normal
            ? AgentState::PassedOut
            : AgentState::Agonising;
        agent.state_ticks_remaining = 0;
    }

    bool AdvanceWoundStage(AgentRuntime& agent, Limb limb) noexcept {
        LimbWoundRuntime& wound = agent.wounds[LimbIndex(limb)];
        wound.gauge = 0.0f;
        wound.updated_tick = tick;
        if (wound.condition == LimbCondition::Normal) {
            wound.condition = LimbCondition::Injured;
            ApplyInitialInjuryEffects(agent, limb);
            return true;
        }
        if (wound.condition == LimbCondition::Injured) {
            wound.condition = LimbCondition::BadlyInjured;
            ApplyBadInjuryEffects(agent, limb);
            return true;
        }
        if (limb == Limb::Head || limb == Limb::Torso) {
            wound.gauge = config.wound_threshold;
            KillAgent(agent);
            return true;
        }
        wound.gauge = config.wound_threshold;
        return false;
    }

    void ApplyGaugeDamage(AgentRuntime& agent, Limb limb, float damage) noexcept {
        LimbWoundRuntime& wound = agent.wounds[LimbIndex(limb)];
        wound.gauge = CurrentWoundGauge(wound);
        wound.updated_tick = tick;
        while (damage > 0.0f && agent.state != AgentState::Dead) {
            const float remaining = config.wound_threshold - wound.gauge;
            if (damage < remaining) {
                wound.gauge += damage;
                return;
            }
            damage -= remaining;
            if (!AdvanceWoundStage(agent, limb)) return;
        }
    }

    bool ApplyAutonomousWound(AgentRuntime& defender, EntityId attacker_id,
        const ActionRuntime& attack) noexcept {
        if (config.mode != SimulationMode::Autonomous) return false;
        const bool standing_before_hit = IsStandingThreat(defender);
        constexpr std::uint64_t kLimbSalt = 0x574f554e445f4c4dULL;
        const std::uint64_t limb_roll = Mix64(seed ^ attack.sequence ^
            (static_cast<std::uint64_t>(defender.id) << 32U) ^
            static_cast<std::uint64_t>(attacker_id) ^ kLimbSalt);
        const Limb limb = IsGroundedTarget(defender.state)
            ? (limb_roll % 10U < 8U ? Limb::Torso : Limb::Head)
            : static_cast<Limb>(limb_roll % kLimbCount);
        if (attack.kind == ActionKind::SwordAttack && attack.weapon == WeaponKind::Sword) {
            (void)AdvanceWoundStage(defender, limb);
            return standing_before_hit && IsGroundedTarget(defender.state);
        }
        if (attack.kind == ActionKind::MeleeAttack ||
            (attack.kind == ActionKind::SwordAttack && attack.weapon == WeaponKind::Stick)) {
            ApplyGaugeDamage(defender, limb, config.melee_wound_gain);
        }
        return standing_before_hit && IsGroundedTarget(defender.state);
    }

    AgentState MobileStateFromWounds(const AgentRuntime& agent) const noexcept {
        return LimbInjured(agent, Limb::LeftLeg) || LimbInjured(agent, Limb::RightLeg)
            ? AgentState::Slow
            : AgentState::Normal;
    }

    void EnterStunned(AgentRuntime& agent, const ActionRuntime& attack) noexcept {
        if (IsIncapacitated(agent.state) || attack.stun_duration_ticks == 0U) return;
        agent.state = AgentState::Stunned;
        agent.state_ticks_remaining = attack.stun_duration_ticks;
        agent.intent.speed_amplitude = 0.0;
        agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians;
    }

    void StepAgentState(AgentRuntime& agent) noexcept {
        if (agent.target_commitment_ticks_remaining > 0U) {
            --agent.target_commitment_ticks_remaining;
        }
        if (agent.state == AgentState::Stunned) {
            if (agent.state_ticks_remaining > 0U) --agent.state_ticks_remaining;
            if (agent.state_ticks_remaining == 0U) agent.state = MobileStateFromWounds(agent);
            return;
        }
        if (agent.state != AgentState::Agonising && agent.state != AgentState::PassedOut) return;
        if (VitalBadlyInjured(agent)) return;
        if (agent.state_ticks_remaining > 0U) --agent.state_ticks_remaining;
        if (agent.state_ticks_remaining == 0U) EnterCrawling(agent);
    }

    void StepReaction(AgentRuntime& agent) noexcept {
        if (agent.reaction.kind == ReactionKind::None) return;
        ++agent.reaction.elapsed_ticks;
        if (agent.reaction.elapsed_ticks >= agent.reaction.duration_ticks) agent.reaction = {};
    }

    void BeginReaction(AgentRuntime& defender, AgentRuntime& attacker,
        const ActionRuntime& attack, bool defender_attacking_at_launch) noexcept {
        constexpr std::uint64_t kHitSalt = 0x4849545f524f4c4cULL;
        constexpr std::uint64_t kParrySalt = 0x50415252595f524fULL;
        const bool attacker_visible = InsideHeadVisionHemisphere(defender, attacker);
        if (attacker_visible && defender.behavior_mode == BehaviorMode::Wrath) {
            CancelAttackOnHit(defender);
            defender.behavior_mode = BehaviorMode::Attack;
            defender.attack_target_id = NearestPerceivedStandingOpponent(defender);
            defender_attacking_at_launch = false;
        }
        const bool stunned_at_launch = defender.state == AgentState::Stunned;
        const bool hit_roll = !attacker_visible || defender_attacking_at_launch ||
            IsIncapacitated(defender.state) ||
            UnitRandom(seed ^ attack.sequence ^
                (static_cast<std::uint64_t>(defender.id) << 32U) ^ kHitSalt) < config.hit_probability;
        const bool parry_roll = UnitRandom(seed ^ attack.sequence ^
            (static_cast<std::uint64_t>(defender.id) << 32U) ^ kParrySalt) < config.parry_probability;
        const WeaponKind defender_weapon = HeldWeapon(defender);
        const bool can_parry_weapon = attack.kind != ActionKind::SwordAttack ||
            defender_weapon != WeaponKind::None;
        const bool can_parry_action = defender.action.kind != ActionKind::UnsheatheSword;
        defender.reaction.kind = hit_roll
            ? ReactionKind::Hit
            : (!stunned_at_launch && parry_roll && can_parry_weapon && can_parry_action
                ? ReactionKind::Parry
                : ReactionKind::Dodge);
        defender.reaction.elapsed_ticks = 0;
        defender.reaction.duration_ticks = attack.duration_ticks;
        defender.reaction.duration_seconds = attack.duration_seconds;
        if (defender.reaction.kind == ReactionKind::Parry) {
            MarkAttackParried(attacker, attack.sequence);
            if (attack.weapon == WeaponKind::Sword &&
                defender_weapon == WeaponKind::Sword) {
                EmitSound(defender, SoundEventKind::Parry,
                    config.sound_maximum_range_m, attacker.id);
            }
        }
        else if (defender.reaction.kind == ReactionKind::Hit &&
            config.mode == SimulationMode::Autonomous) {
            MarkPendingHit(attacker, attack.sequence, defender.id);
        }
    }

    void StepActions() noexcept {
        landing_events.clear();

        for (AgentRuntime& agent : agents) {
            if (!AdvanceAction(agent)) continue;
            if (IsAttacking(agent) && agent.action.pending_hit_defender_id != kInvalidEntityId) {
                landing_events.push_back({
                    agent.id, agent.action.pending_hit_defender_id, agent.action});
            }
            CompleteAction(agent, true);
        }

        for (const LandingEvent& event : landing_events) {
            AgentRuntime* attacker = FindRuntime(event.attacker_id);
            AgentRuntime* defender = FindRuntime(event.defender_id);
            if (defender == nullptr || defender->state == AgentState::Dead) continue;
            CancelAttackOnHit(*defender);
            if (defender->behavior_mode == BehaviorMode::Wrath) {
                defender->behavior_mode = BehaviorMode::Attack;
                defender->attack_target_id = NearestPerceivedStandingOpponent(*defender);
            }
            const bool downed = ApplyAutonomousWound(
                *defender, event.attacker_id, event.attack);
            EnterStunned(*defender, event.attack);
            if (downed && attacker != nullptr && !IsIncapacitated(attacker->state)) {
                if (attacker->rescue_executioner_id != kInvalidEntityId) {
                    attacker->behavior_mode = BehaviorMode::Attack;
                    attacker->attack_target_id = attacker->rescue_executioner_id;
                    continue;
                }
                constexpr std::uint64_t kWrathSalt = 0x57524154485f524fULL;
                const bool enter_wrath = UnitRandom(seed ^ event.attack.sequence ^
                    (static_cast<std::uint64_t>(attacker->id) << 32U) ^
                    static_cast<std::uint64_t>(defender->id) ^ kWrathSalt) <
                    static_cast<double>(kWrathProbability);
                attacker->behavior_mode = enter_wrath
                    ? BehaviorMode::Wrath
                    : BehaviorMode::Attack;
                attacker->attack_target_id = enter_wrath
                    ? defender->id
                    : NearestPerceivedStandingOpponent(*attacker);
                if (enter_wrath) EmitExecutionScream(*defender, *attacker);
            }
        }
    }

    void StartRequestedAttacks() noexcept {
        started_attacks.clear();
        for (AgentRuntime& agent : agents) {
            if (!agent.attack_requested) continue;
            agent.attack_requested = false;
            if (BeginAttack(agent)) {
                started_attacks.push_back({agent.id, agent.attack_target_id, agent.action});
            }
        }
        for (StartedAttack& event : started_attacks) {
            AgentRuntime* defender = FindRuntime(event.defender_id);
            event.defender_attacking_at_launch = defender != nullptr && IsAttacking(*defender);
        }
        for (const StartedAttack& event : started_attacks) {
            AgentRuntime* attacker = FindRuntime(event.attacker_id);
            if (attacker == nullptr) continue;
            AgentRuntime* defender = FindRuntime(event.defender_id);
            if (defender != nullptr) {
                BeginReaction(*defender, *attacker, event.action, event.defender_attacking_at_launch);
            }
        }
    }

    AgentRuntime* FindRuntime(EntityId id) noexcept {
        if (id == kInvalidEntityId || id > agents.size()) return nullptr;
        AgentRuntime& agent = agents[static_cast<std::size_t>(id - 1U)];
        return agent.id == id ? &agent : nullptr;
    }

    const AgentRuntime* FindRuntime(EntityId id) const noexcept {
        if (id == kInvalidEntityId || id > agents.size()) return nullptr;
        const AgentRuntime& agent = agents[static_cast<std::size_t>(id - 1U)];
        return agent.id == id ? &agent : nullptr;
    }

    static bool IsStandingThreat(const AgentRuntime& agent) noexcept {
        return !IsIncapacitated(agent.state);
    }

    double HeadWorldYaw(const AgentRuntime& agent) const noexcept {
        return WrapAngle(agent.locomotion.yaw_radians + agent.head_yaw_offset_radians);
    }

    bool InsideHeadVisionHemisphere(const AgentRuntime& observer,
        const AgentRuntime& candidate) const noexcept {
        const double delta_x = candidate.locomotion.position.x - observer.locomotion.position.x;
        const double delta_z = candidate.locomotion.position.z - observer.locomotion.position.z;
        const double distance_squared = delta_x * delta_x + delta_z * delta_z;
        if (distance_squared > static_cast<double>(config.vision_range_m) * config.vision_range_m) {
            return false;
        }
        const double bearing = std::atan2(delta_x, delta_z);
        const double vision_angle_radians = static_cast<double>(
            config.head_vision_angle_degrees) * kPi / 180.0;
        return std::fabs(WrapAngle(bearing - HeadWorldYaw(observer))) <=
            0.5 * vision_angle_radians;
    }

    bool InsideProximityRadius(const AgentRuntime& observer,
        const AgentRuntime& candidate) const noexcept {
        const double delta_x = candidate.locomotion.position.x - observer.locomotion.position.x;
        const double delta_z = candidate.locomotion.position.z - observer.locomotion.position.z;
        return delta_x * delta_x + delta_z * delta_z <=
            static_cast<double>(config.proximity_threat_range_m) * config.proximity_threat_range_m;
    }

    void BuildPerceptions() noexcept {
        perceptions.resize(agents.size());
        bool hero_standing = false;
        bool villain_standing = false;
        for (const AgentRuntime& agent : agents) {
            if (!IsStandingThreat(agent)) continue;
            if (agent.team == Team::Hero) hero_standing = true;
            else villain_standing = true;
        }
        for (std::size_t observer_index = 0; observer_index < agents.size(); ++observer_index) {
            AgentRuntime& observer = agents[observer_index];
            PerceptionRuntime& perception = perceptions[observer_index];
            perception = {};
            const bool standing_enemy_exists = observer.team == Team::Hero
                ? villain_standing
                : hero_standing;
            if (standing_enemy_exists) observer.finishing_targets.reset();
            double nearest_proximity_distance = std::numeric_limits<double>::infinity();
            double nearest_visible_distance = std::numeric_limits<double>::infinity();
            double nearest_new_visible_distance = std::numeric_limits<double>::infinity();
            EntityId nearest_new_visible_id = kInvalidEntityId;
            for (std::size_t candidate_index = 0; candidate_index < agents.size(); ++candidate_index) {
                const AgentRuntime& candidate = agents[candidate_index];
                if (candidate.team == observer.team) continue;
                if (!IsStandingThreat(candidate)) {
                    if (candidate.state == AgentState::Dead) {
                        observer.finishing_targets.reset(candidate_index);
                    }
                    if (candidate.state == AgentState::Dead ||
                        !observer.finishing_targets.test(candidate_index)) {
                        observer.recognized_threats.reset(candidate_index);
                        continue;
                    }
                    observer.recognized_threats.set(candidate_index);
                    perception.active_threats.set(candidate_index);
                    ++perception.snapshot.active_threat_count;
                    ++perception.snapshot.finishing_target_count;
                    ++perception.snapshot.recognized_threat_count;
                    if (perception.snapshot.active_threat_id_count <
                        perception.snapshot.active_threat_ids.size()) {
                        perception.snapshot.active_threat_ids[
                            perception.snapshot.active_threat_id_count++] = candidate.id;
                    }
                    if (perception.snapshot.finishing_target_id_count <
                        perception.snapshot.finishing_target_ids.size()) {
                        perception.snapshot.finishing_target_ids[
                            perception.snapshot.finishing_target_id_count++] = candidate.id;
                    }
                    if (InsideProximityRadius(observer, candidate)) {
                        ++perception.snapshot.proximity_threat_count;
                    }
                    if (InsideHeadVisionHemisphere(observer, candidate)) {
                        ++perception.snapshot.visible_threat_count;
                    }
                    continue;
                }
                const double delta_x = candidate.locomotion.position.x - observer.locomotion.position.x;
                const double delta_z = candidate.locomotion.position.z - observer.locomotion.position.z;
                const double distance_squared = delta_x * delta_x + delta_z * delta_z;
                const bool proximity = distance_squared <=
                    static_cast<double>(config.proximity_threat_range_m) *
                        config.proximity_threat_range_m;
                const double vision_angle_radians = static_cast<double>(
                    config.head_vision_angle_degrees) * kPi / 180.0;
                const bool visible = distance_squared <=
                        static_cast<double>(config.vision_range_m) * config.vision_range_m &&
                    std::fabs(WrapAngle(std::atan2(delta_x, delta_z) - HeadWorldYaw(observer))) <=
                        0.5 * vision_angle_radians;
                const bool previously_recognized =
                    observer.recognized_threats.test(candidate_index);
                if (visible) {
                    observer.recognized_threats.set(candidate_index);
                    if (!previously_recognized && distance_squared < nearest_new_visible_distance) {
                        nearest_new_visible_distance = distance_squared;
                        nearest_new_visible_id = candidate.id;
                    }
                }
                const bool recognized = observer.recognized_threats.test(candidate_index);
                if (recognized) ++perception.snapshot.recognized_threat_count;
                if (!visible && !(recognized && proximity)) continue;
                perception.active_threats.set(candidate_index);
                ++perception.snapshot.active_threat_count;
                if (perception.snapshot.active_threat_id_count <
                    perception.snapshot.active_threat_ids.size()) {
                    perception.snapshot.active_threat_ids[
                        perception.snapshot.active_threat_id_count++] = candidate.id;
                }
                if (recognized && proximity) {
                    ++perception.snapshot.proximity_threat_count;
                    if (distance_squared < nearest_proximity_distance) {
                        nearest_proximity_distance = distance_squared;
                        perception.nearest_proximity_id = candidate.id;
                    }
                }
                if (visible) {
                    ++perception.snapshot.visible_threat_count;
                    if (distance_squared < nearest_visible_distance) {
                        nearest_visible_distance = distance_squared;
                        perception.nearest_visible_id = candidate.id;
                    }
                }
            }
            const auto force_rescue_threat = [&](EntityId target_id) {
                if (target_id == kInvalidEntityId || target_id > agents.size()) return;
                const std::size_t target_index = static_cast<std::size_t>(target_id - 1U);
                const AgentRuntime& target = agents[target_index];
                if (target.team == observer.team || target.state == AgentState::Dead) return;
                if (!observer.recognized_threats.test(target_index)) {
                    observer.recognized_threats.set(target_index);
                    ++perception.snapshot.recognized_threat_count;
                }
                if (perception.active_threats.test(target_index)) return;
                perception.active_threats.set(target_index);
                ++perception.snapshot.active_threat_count;
                if (perception.snapshot.active_threat_id_count <
                    perception.snapshot.active_threat_ids.size()) {
                    perception.snapshot.active_threat_ids[
                        perception.snapshot.active_threat_id_count++] = target.id;
                }
            };
            if (observer.rescue_executioner_id != kInvalidEntityId) {
                force_rescue_threat(observer.rescue_executioner_id);
                force_rescue_threat(observer.rescue_former_target_id);
            }
            perception.snapshot.sound_investigation_source_id =
                observer.sound_investigation_source_id;
            if (observer.pending_grunt_target_id == kInvalidEntityId &&
                nearest_new_visible_id != kInvalidEntityId && !IsIncapacitated(observer.state)) {
                observer.pending_grunt_target_id = nearest_new_visible_id;
            }
            for (std::uint64_t until_tick : observer.non_threatening_until_ticks) {
                if (until_tick > tick) ++perception.snapshot.non_threatening_source_count;
            }
            perception.snapshot.scanning = observer.head_look_mode == HeadLookMode::SearchScan;
        }
    }

    EntityId NearestPerceivedStandingOpponent(const AgentRuntime& agent) const noexcept {
        if (agent.id == kInvalidEntityId || agent.id > perceptions.size()) return kInvalidEntityId;
        const PerceptionRuntime& perception = perceptions[static_cast<std::size_t>(agent.id - 1U)];
        const auto valid = [this, &agent](EntityId id) {
            if (id == kInvalidEntityId || id > agents.size()) return false;
            const AgentRuntime& candidate = agents[static_cast<std::size_t>(id - 1U)];
            return candidate.team != agent.team && IsStandingThreat(candidate);
        };
        if (valid(perception.nearest_proximity_id)) return perception.nearest_proximity_id;
        if (valid(perception.nearest_visible_id)) return perception.nearest_visible_id;
        return kInvalidEntityId;
    }

    EntityId NearestVisibleStandingOpponent(const AgentRuntime& agent) const noexcept {
        if (agent.id == kInvalidEntityId || agent.id > perceptions.size()) return kInvalidEntityId;
        const EntityId id = perceptions[static_cast<std::size_t>(agent.id - 1U)].nearest_visible_id;
        if (id == kInvalidEntityId || id > agents.size()) return kInvalidEntityId;
        const AgentRuntime& candidate = agents[static_cast<std::size_t>(id - 1U)];
        return candidate.team != agent.team && IsStandingThreat(candidate)
            ? id
            : kInvalidEntityId;
    }

    EntityId NearestFinishingTarget(const AgentRuntime& agent) const noexcept {
        EntityId nearest_id = kInvalidEntityId;
        double nearest_distance_squared = std::numeric_limits<double>::infinity();
        for (std::size_t index = 0; index < agents.size(); ++index) {
            if (!agent.finishing_targets.test(index)) continue;
            const AgentRuntime& candidate = agents[index];
            if (candidate.team == agent.team || candidate.state == AgentState::Dead ||
                IsStandingThreat(candidate)) continue;
            const double delta_x = candidate.locomotion.position.x - agent.locomotion.position.x;
            const double delta_z = candidate.locomotion.position.z - agent.locomotion.position.z;
            const double distance_squared = delta_x * delta_x + delta_z * delta_z;
            if (distance_squared < nearest_distance_squared) {
                nearest_distance_squared = distance_squared;
                nearest_id = candidate.id;
            }
        }
        return nearest_id;
    }

    EntityId NearestActiveOpponent(const AgentRuntime& agent) const noexcept {
        const EntityId standing = NearestPerceivedStandingOpponent(agent);
        return standing != kInvalidEntityId ? standing : NearestFinishingTarget(agent);
    }

    bool IsBalancedStandingCandidate(
        const AgentRuntime& attacker, std::size_t target_index) const noexcept {
        if (attacker.id == kInvalidEntityId || attacker.id > perceptions.size() ||
            target_index >= agents.size()) return false;
        const AgentRuntime& target = agents[target_index];
        return target.team != attacker.team && IsStandingThreat(target) &&
            perceptions[static_cast<std::size_t>(attacker.id - 1U)]
                .active_threats.test(target_index);
    }

    std::uint64_t TargetAssignmentIntervalTicks() const noexcept {
        return std::max<std::uint64_t>(1U, static_cast<std::uint64_t>(std::lround(
            static_cast<double>(config.tick_rate_hz) /
            static_cast<double>(kTargetAssignmentRateHz))));
    }

    bool NeedsBalancedTargetAssignment() const noexcept {
        if (config.target_commitment_seconds <= 0.0f &&
            config.sector_influence_distance_m <= config.attack_range_m + 1.0e-3f) return true;
        if (tick % TargetAssignmentIntervalTicks() == 0U) return true;
        for (std::size_t agent_index = 0; agent_index < agents.size(); ++agent_index) {
            const AgentRuntime& attacker = agents[agent_index];
            if (!attacker.combat_enabled || IsIncapacitated(attacker.state) ||
                (attacker.behavior_mode != BehaviorMode::Idle &&
                    attacker.behavior_mode != BehaviorMode::Attack)) continue;
            const AgentRuntime* current = FindRuntime(attacker.attack_target_id);
            if (current != nullptr && current->team != attacker.team &&
                IsStandingThreat(*current)) continue;
            for (std::size_t target_index = 0; target_index < agents.size(); ++target_index) {
                if (IsBalancedStandingCandidate(attacker, target_index)) return true;
            }
        }
        return false;
    }

    void AssignBalancedStandingTargets() noexcept {
        std::array<EntityId, kMaxSimulationAgentCount> assignments{};
        std::array<std::uint16_t, kMaxSimulationAgentCount> target_loads{};
        std::array<std::uint16_t, kMaxSimulationAgentCount> candidate_counts{};
        std::array<std::array<std::uint16_t, kMaxSimulationAgentCount>,
            kMaxSimulationAgentCount> candidate_order{};
        std::array<std::size_t, kMaxSimulationAgentCount> assignment_order{};
        std::array<std::size_t, kMaxSimulationAgentCount> unique_target_owners{};
        std::bitset<kMaxSimulationAgentCount> locked_attackers{};
        std::size_t assignment_count = 0;

        unique_target_owners.fill(std::numeric_limits<std::size_t>::max());

        for (std::size_t agent_index = 0; agent_index < agents.size(); ++agent_index) {
            const AgentRuntime& attacker = agents[agent_index];
            if (!attacker.combat_enabled || IsIncapacitated(attacker.state) ||
                (attacker.behavior_mode != BehaviorMode::Idle &&
                    attacker.behavior_mode != BehaviorMode::Attack)) continue;

            const AgentRuntime* rescue_executioner =
                FindRuntime(attacker.rescue_executioner_id);
            if (rescue_executioner != nullptr &&
                rescue_executioner->team != attacker.team &&
                IsStandingThreat(*rescue_executioner)) {
                assignments[agent_index] = rescue_executioner->id;
                locked_attackers.set(agent_index);
                ++target_loads[static_cast<std::size_t>(rescue_executioner->id - 1U)];
                continue;
            }

            const AgentRuntime* current_target = FindRuntime(attacker.attack_target_id);
            if (IsAttacking(attacker) && current_target != nullptr &&
                current_target->team != attacker.team && current_target->state != AgentState::Dead) {
                assignments[agent_index] = current_target->id;
                locked_attackers.set(agent_index);
                if (IsStandingThreat(*current_target)) {
                    ++target_loads[static_cast<std::size_t>(current_target->id - 1U)];
                }
                continue;
            }
            if (attacker.target_commitment_ticks_remaining > 0U &&
                current_target != nullptr &&
                IsBalancedStandingCandidate(attacker,
                    static_cast<std::size_t>(current_target->id - 1U))) {
                assignments[agent_index] = current_target->id;
                locked_attackers.set(agent_index);
                ++target_loads[static_cast<std::size_t>(current_target->id - 1U)];
                continue;
            }

            for (std::size_t target_index = 0; target_index < agents.size(); ++target_index) {
                if (IsBalancedStandingCandidate(attacker, target_index)) {
                    candidate_order[agent_index][candidate_counts[agent_index]++] =
                        static_cast<std::uint16_t>(target_index);
                }
            }
            if (candidate_counts[agent_index] > 0U) {
                assignment_order[assignment_count++] = agent_index;
            }
        }

        std::sort(assignment_order.begin(), assignment_order.begin() + assignment_count,
            [&candidate_counts, this](std::size_t left, std::size_t right) {
                if (candidate_counts[left] != candidate_counts[right]) {
                    return candidate_counts[left] < candidate_counts[right];
                }
                return agents[left].id < agents[right].id;
            });

        for (std::size_t order_index = 0; order_index < assignment_count; ++order_index) {
            const std::size_t agent_index = assignment_order[order_index];
            const AgentRuntime& attacker = agents[agent_index];
            auto& ordered_candidates = candidate_order[agent_index];
            std::sort(ordered_candidates.begin(),
                ordered_candidates.begin() + candidate_counts[agent_index],
                [&attacker, this](std::uint16_t left, std::uint16_t right) {
                    const AgentRuntime& left_target = agents[left];
                    const AgentRuntime& right_target = agents[right];
                    const double left_x = left_target.locomotion.position.x -
                        attacker.locomotion.position.x;
                    const double left_z = left_target.locomotion.position.z -
                        attacker.locomotion.position.z;
                    const double right_x = right_target.locomotion.position.x -
                        attacker.locomotion.position.x;
                    const double right_z = right_target.locomotion.position.z -
                        attacker.locomotion.position.z;
                    const double left_distance = left_x * left_x + left_z * left_z;
                    const double right_distance = right_x * right_x + right_z * right_z;
                    if (std::fabs(left_distance - right_distance) > 1.0e-9) {
                        return left_distance < right_distance;
                    }
                    const bool left_is_current = left_target.id == attacker.attack_target_id;
                    const bool right_is_current = right_target.id == attacker.attack_target_id;
                    if (left_is_current != right_is_current) return left_is_current;
                    return left_target.id < right_target.id;
                });
        }

        auto assign_unique_target = [&](auto&& self, std::size_t agent_index,
                                        std::bitset<kMaxSimulationAgentCount>& visited_targets)
                noexcept -> bool {
            for (std::size_t candidate_index = 0;
                    candidate_index < candidate_counts[agent_index];
                    ++candidate_index) {
                const std::size_t target_index = candidate_order[agent_index][candidate_index];
                if (target_loads[target_index] != 0U) continue;
                if (visited_targets.test(target_index)) continue;
                visited_targets.set(target_index);
                const std::size_t previous_owner = unique_target_owners[target_index];
                if (previous_owner == std::numeric_limits<std::size_t>::max() ||
                    self(self, previous_owner, visited_targets)) {
                    unique_target_owners[target_index] = agent_index;
                    assignments[agent_index] = agents[target_index].id;
                    return true;
                }
            }
            return false;
        };

        for (std::size_t order_index = 0; order_index < assignment_count; ++order_index) {
            std::bitset<kMaxSimulationAgentCount> visited_targets{};
            assign_unique_target(assign_unique_target, assignment_order[order_index],
                visited_targets);
        }
        for (std::size_t target_index = 0; target_index < agents.size(); ++target_index) {
            if (unique_target_owners[target_index] !=
                std::numeric_limits<std::size_t>::max()) {
                ++target_loads[target_index];
            }
        }

        for (std::size_t order_index = 0; order_index < assignment_count; ++order_index) {
            const std::size_t agent_index = assignment_order[order_index];
            if (assignments[agent_index] != kInvalidEntityId) continue;
            const AgentRuntime& attacker = agents[agent_index];
            EntityId best_target_id = kInvalidEntityId;
            std::uint16_t best_load = std::numeric_limits<std::uint16_t>::max();
            double best_distance_squared = std::numeric_limits<double>::infinity();

            for (std::size_t target_index = 0; target_index < agents.size(); ++target_index) {
                if (!IsBalancedStandingCandidate(attacker, target_index)) continue;
                const AgentRuntime& target = agents[target_index];
                const double delta_x = target.locomotion.position.x - attacker.locomotion.position.x;
                const double delta_z = target.locomotion.position.z - attacker.locomotion.position.z;
                const double distance_squared = delta_x * delta_x + delta_z * delta_z;
                const std::uint16_t load = target_loads[target_index];
                const bool closer = distance_squared < best_distance_squared - 1.0e-9;
                const bool same_distance = std::fabs(distance_squared - best_distance_squared) <= 1.0e-9;
                const bool best_is_current = best_target_id == attacker.attack_target_id;
                const bool current_target_tie = same_distance &&
                    target.id == attacker.attack_target_id &&
                    !best_is_current;
                if (load < best_load || (load == best_load &&
                        (closer || current_target_tie ||
                            (same_distance && !current_target_tie && !best_is_current &&
                                (best_target_id == kInvalidEntityId || target.id < best_target_id))))) {
                    best_target_id = target.id;
                    best_load = load;
                    best_distance_squared = distance_squared;
                }
            }
            if (best_target_id != kInvalidEntityId) {
                assignments[agent_index] = best_target_id;
                ++target_loads[static_cast<std::size_t>(best_target_id - 1U)];
            }
        }

        for (std::size_t agent_index = 0; agent_index < agents.size(); ++agent_index) {
            AgentRuntime& attacker = agents[agent_index];
            if (!attacker.combat_enabled || IsIncapacitated(attacker.state) ||
                (attacker.behavior_mode != BehaviorMode::Idle &&
                    attacker.behavior_mode != BehaviorMode::Attack) ||
                locked_attackers.test(agent_index)) continue;
            if (assignments[agent_index] != kInvalidEntityId) {
                const bool target_changed = attacker.attack_target_id != assignments[agent_index];
                attacker.attack_target_id = assignments[agent_index];
                if (target_changed) {
                    attacker.target_commitment_ticks_remaining =
                        CooldownTicks(config.target_commitment_seconds);
                }
                if (attacker.behavior_mode == BehaviorMode::Idle) {
                    attacker.behavior_mode = BehaviorMode::Attack;
                    attacker.head_scan_endpoint_count = 0U;
                }
                continue;
            }

            const AgentRuntime* current_target = FindRuntime(attacker.attack_target_id);
            if (current_target == nullptr || current_target->team == attacker.team ||
                !IsGroundedTarget(current_target->state)) {
                attacker.attack_target_id = kInvalidEntityId;
            }
        }
    }

    void ClearApproachSector(AgentRuntime& agent) noexcept {
        agent.approach_sector_target_id = kInvalidEntityId;
        agent.approach_sector_index = static_cast<std::uint8_t>(kApproachSectorCount);
        agent.approach_sector_yaw_radians = 0.0;
        agent.approach_sector_radius_m = 0.0;
        agent.tactical_sector_error_radians = 0.0;
        agent.tactical_sector_influence = 0.0;
    }

    void RefreshApproachSectors() noexcept {
        std::array<std::array<std::uint16_t, kApproachSectorCount>,
            kMaxSimulationAgentCount> occupancy{};
        const auto valid_reservation = [this](const AgentRuntime& agent) {
            if (agent.behavior_mode != BehaviorMode::Attack ||
                agent.approach_sector_target_id != agent.attack_target_id ||
                agent.approach_sector_index >= kApproachSectorCount) return false;
            const AgentRuntime* target = FindRuntime(agent.attack_target_id);
            return target != nullptr && target->team != agent.team && IsStandingThreat(*target);
        };

        for (AgentRuntime& agent : agents) {
            if (!valid_reservation(agent)) {
                ClearApproachSector(agent);
                continue;
            }
            ++occupancy[static_cast<std::size_t>(agent.attack_target_id - 1U)]
                [agent.approach_sector_index];
        }

        constexpr std::uint64_t kPreferenceSalt = 0x534543544f525052ULL;
        constexpr std::uint64_t kAngleSalt = 0x534543544f52414eULL;
        constexpr std::uint64_t kRadiusSalt = 0x534543544f525241ULL;
        for (AgentRuntime& agent : agents) {
            if (agent.approach_sector_target_id != kInvalidEntityId ||
                agent.behavior_mode != BehaviorMode::Attack) continue;
            const AgentRuntime* target = FindRuntime(agent.attack_target_id);
            if (target == nullptr || target->team == agent.team || !IsStandingThreat(*target)) continue;

            const std::uint64_t key = seed ^
                (static_cast<std::uint64_t>(agent.id) << 32U) ^
                static_cast<std::uint64_t>(target->id);
            constexpr std::array<int, kApproachSectorCount> kApproachRoleOffsets{
                -3, -2, -2, 0, 0, 2, 2, 3};
            const double sector_step = 2.0 * kPi / static_cast<double>(kApproachSectorCount);
            const double current_bearing = AngleTo(
                target->locomotion.position, agent.locomotion.position);
            const auto current_sector = static_cast<std::size_t>(std::llround(
                WrapAngle(current_bearing) / sector_step +
                static_cast<double>(kApproachSectorCount))) % kApproachSectorCount;
            const std::size_t role = static_cast<std::size_t>(
                Mix64(key ^ kPreferenceSalt) % kApproachRoleOffsets.size());
            const std::size_t preferred = static_cast<std::size_t>(
                (static_cast<int>(current_sector) + kApproachRoleOffsets[role] +
                    static_cast<int>(kApproachSectorCount)) %
                static_cast<int>(kApproachSectorCount));
            std::size_t best_sector = preferred;
            std::uint16_t best_occupancy = std::numeric_limits<std::uint16_t>::max();
            std::size_t best_preference_distance = kApproachSectorCount;
            for (std::size_t sector = 0; sector < kApproachSectorCount; ++sector) {
                const std::size_t clockwise = (sector + kApproachSectorCount - preferred) %
                    kApproachSectorCount;
                const std::size_t counter_clockwise =
                    (preferred + kApproachSectorCount - sector) % kApproachSectorCount;
                const std::size_t preference_distance = std::min(clockwise, counter_clockwise);
                const std::uint16_t sector_occupancy = occupancy[
                    static_cast<std::size_t>(target->id - 1U)][sector];
                if (sector_occupancy < best_occupancy ||
                    (sector_occupancy == best_occupancy &&
                        preference_distance < best_preference_distance)) {
                    best_sector = sector;
                    best_occupancy = sector_occupancy;
                    best_preference_distance = preference_distance;
                }
            }
            ++occupancy[static_cast<std::size_t>(target->id - 1U)][best_sector];

            const double angle_unit = 2.0 * UnitRandom(key ^ kAngleSalt) - 1.0;
            const double radius_unit = 2.0 * UnitRandom(key ^ kRadiusSalt) - 1.0;
            if (agent.target_commitment_ticks_remaining == 0U) {
                agent.target_commitment_ticks_remaining =
                    CooldownTicks(config.target_commitment_seconds);
            }
            agent.approach_sector_target_id = target->id;
            agent.approach_sector_index = static_cast<std::uint8_t>(best_sector);
            agent.approach_sector_yaw_radians = WrapAngle(
                static_cast<double>(best_sector) * sector_step +
                angle_unit * static_cast<double>(config.sector_angle_variation_degrees) *
                    kPi / 180.0);
            agent.approach_sector_radius_m = std::max(0.25,
                static_cast<double>(config.attack_range_m) +
                radius_unit * static_cast<double>(config.sector_radius_variation_m));
        }
    }

    void CaptureNonDeadSeenDuringScan(AgentRuntime& agent) noexcept {
        for (std::size_t index = 0; index < agents.size(); ++index) {
            const AgentRuntime& candidate = agents[index];
            if (candidate.team != agent.team && candidate.state != AgentState::Dead &&
                InsideHeadVisionHemisphere(agent, candidate)) {
                agent.non_dead_seen_during_scan.set(index);
            }
        }
    }

    EntityId ResolveCompletedSweep(AgentRuntime& agent) noexcept {
        EntityId nearest_seen_standing = kInvalidEntityId;
        double nearest_seen_standing_distance = std::numeric_limits<double>::infinity();
        bool standing_enemy_exists = false;
        for (std::size_t index = 0; index < agents.size(); ++index) {
            const AgentRuntime& candidate = agents[index];
            if (candidate.team == agent.team || candidate.state == AgentState::Dead) continue;
            if (IsStandingThreat(candidate)) {
                standing_enemy_exists = true;
                if (!agent.non_dead_seen_during_scan.test(index)) continue;
                agent.recognized_threats.set(index);
                const double delta_x = candidate.locomotion.position.x - agent.locomotion.position.x;
                const double delta_z = candidate.locomotion.position.z - agent.locomotion.position.z;
                const double distance_squared = delta_x * delta_x + delta_z * delta_z;
                if (distance_squared < nearest_seen_standing_distance) {
                    nearest_seen_standing_distance = distance_squared;
                    nearest_seen_standing = candidate.id;
                }
            }
        }
        if (standing_enemy_exists) {
            agent.non_dead_seen_during_scan.reset();
            return nearest_seen_standing;
        }
        for (std::size_t index = 0; index < agents.size(); ++index) {
            if (!agent.non_dead_seen_during_scan.test(index)) continue;
            const AgentRuntime& candidate = agents[index];
            if (candidate.team != agent.team && candidate.state != AgentState::Dead) {
                agent.finishing_targets.set(index);
            }
        }
        agent.non_dead_seen_during_scan.reset();
        return NearestFinishingTarget(agent);
    }

    void UpdateHeadLook(AgentRuntime& agent, double dt) noexcept {
        if (agent.state == AgentState::Dead) return;

        const double root_yaw = agent.locomotion.yaw_radians;
        const bool crawling = agent.state == AgentState::Crawling;
        double desired_yaw = root_yaw;
        double desired_pitch = 0.0;
        agent.head_look_mode = HeadLookMode::RootHeading;
        agent.head_look_target_id = kInvalidEntityId;

        AgentRuntime* sound_source = FindRuntime(agent.sound_investigation_source_id);
        if (sound_source != nullptr && (sound_source->team == agent.team ||
            sound_source->state == AgentState::Dead)) {
            agent.sound_investigation_source_id = kInvalidEntityId;
            sound_source = nullptr;
        }
        const bool actively_defending = agent.reaction.kind == ReactionKind::Parry ||
            agent.reaction.kind == ReactionKind::Dodge;
        const bool investigate_sound = sound_source != nullptr && !IsAttacking(agent) &&
            !actively_defending;
        const bool combat_behavior = agent.behavior_mode == BehaviorMode::Attack ||
            agent.behavior_mode == BehaviorMode::Wrath;
        const AgentRuntime* combat_target = combat_behavior
            ? FindRuntime(agent.attack_target_id)
            : nullptr;
        const AgentRuntime* rescue_former_target =
            tick + 1U < agent.rescue_head_hold_until_tick
            ? FindRuntime(agent.rescue_former_target_id)
            : nullptr;
        if (rescue_former_target != nullptr &&
            (rescue_former_target->team == agent.team ||
                rescue_former_target->state == AgentState::Dead)) {
            rescue_former_target = nullptr;
        }
        const AgentRuntime* follow_target = agent.behavior_mode == BehaviorMode::Follow
            ? FindRuntime(agent.follow_target_id)
            : nullptr;
        if (rescue_former_target != nullptr) {
            agent.head_look_mode = HeadLookMode::RescueFormerTarget;
            agent.head_look_target_id = rescue_former_target->id;
            const double delta_x = rescue_former_target->locomotion.position.x -
                agent.locomotion.position.x;
            const double delta_z = rescue_former_target->locomotion.position.z -
                agent.locomotion.position.z;
            desired_yaw = std::atan2(delta_x, delta_z);
            desired_pitch = std::atan2(
                HeadAnchorHeight(rescue_former_target->state) - HeadAnchorHeight(agent.state),
                std::hypot(delta_x, delta_z));
        } else if (investigate_sound) {
            agent.head_look_mode = HeadLookMode::SoundInvestigation;
            agent.head_look_target_id = sound_source->id;
            desired_yaw = AngleTo(agent.locomotion.position, sound_source->locomotion.position);
            desired_pitch = std::atan2(
                HeadAnchorHeight(sound_source->state) - HeadAnchorHeight(agent.state),
                std::hypot(sound_source->locomotion.position.x - agent.locomotion.position.x,
                    sound_source->locomotion.position.z - agent.locomotion.position.z));
        } else if (combat_target != nullptr && combat_target->state != AgentState::Dead) {
            agent.head_look_mode = HeadLookMode::CombatTarget;
            agent.head_look_target_id = combat_target->id;
            const double delta_x = combat_target->locomotion.position.x - agent.locomotion.position.x;
            const double delta_z = combat_target->locomotion.position.z - agent.locomotion.position.z;
            const double horizontal_distance = std::hypot(delta_x, delta_z);
            desired_yaw = std::atan2(delta_x, delta_z);
            desired_pitch = std::atan2(
                HeadAnchorHeight(combat_target->state) - HeadAnchorHeight(agent.state),
                horizontal_distance);
        } else if (follow_target != nullptr && follow_target->team == agent.team &&
            IsStandingThreat(*follow_target)) {
            agent.head_look_mode = HeadLookMode::FollowTarget;
            agent.head_look_target_id = follow_target->id;
            const double delta_x = follow_target->locomotion.position.x - agent.locomotion.position.x;
            const double delta_z = follow_target->locomotion.position.z - agent.locomotion.position.z;
            desired_yaw = std::atan2(delta_x, delta_z);
            desired_pitch = std::atan2(
                HeadAnchorHeight(follow_target->state) - HeadAnchorHeight(agent.state),
                std::hypot(delta_x, delta_z));
        } else if (agent.behavior_mode == BehaviorMode::Attack && !crawling) {
            agent.head_look_mode = HeadLookMode::SearchScan;
            desired_yaw = WrapAngle(root_yaw + agent.head_scan_direction *
                static_cast<double>(kHeadYawLimitRadians));
        } else {
            const double root_speed = std::hypot(
                agent.locomotion.velocity.x, agent.locomotion.velocity.z);
            if (!crawling && root_speed >= kHeadVelocityThresholdMps) {
                agent.head_look_mode = HeadLookMode::RootVelocity;
                desired_yaw = std::atan2(
                    agent.locomotion.velocity.x, agent.locomotion.velocity.z);
            }
        }

        const double yaw_limit = static_cast<double>(kHeadYawLimitRadians);
        const double pitch_limit = static_cast<double>(kHeadPitchLimitRadians);
        const double desired_relative_yaw = std::clamp(
            WrapAngle(desired_yaw - root_yaw), -yaw_limit, yaw_limit);
        desired_yaw = WrapAngle(root_yaw + desired_relative_yaw);
        desired_pitch = std::clamp(desired_pitch, -pitch_limit, pitch_limit);

        agent.head_yaw_offset_radians = std::clamp(
            agent.head_yaw_offset_radians, -yaw_limit, yaw_limit);
        agent.head_pitch_radians = std::clamp(
            agent.head_pitch_radians, -pitch_limit, pitch_limit);

        const double maximum_delta = static_cast<double>(
            config.head_turn_speed_degrees_per_second) * kPi / 180.0 * dt;
        agent.head_yaw_offset_radians = MoveTowards(
            agent.head_yaw_offset_radians, desired_relative_yaw, maximum_delta);
        agent.head_pitch_radians = MoveTowards(
            agent.head_pitch_radians, desired_pitch, maximum_delta);

        agent.head_yaw_offset_radians = std::clamp(
            WrapAngle(agent.head_yaw_offset_radians), -yaw_limit, yaw_limit);
        agent.head_pitch_radians = std::clamp(
            agent.head_pitch_radians, -pitch_limit, pitch_limit);

        if (agent.head_look_mode == HeadLookMode::SearchScan) {
            CaptureNonDeadSeenDuringScan(agent);
        }
        if (agent.head_look_mode == HeadLookMode::SearchScan &&
            std::fabs(WrapAngle(agent.head_yaw_offset_radians - desired_relative_yaw)) <= 1.0e-5) {
            agent.head_scan_direction = -agent.head_scan_direction;
            ++agent.head_scan_endpoint_count;
            if (agent.head_scan_endpoint_count >= 2U) {
                agent.attack_target_id = ResolveCompletedSweep(agent);
                agent.behavior_mode = agent.attack_target_id == kInvalidEntityId
                    ? BehaviorMode::Idle
                    : BehaviorMode::Attack;
                if (agent.attack_target_id != kInvalidEntityId) {
                    agent.head_scan_endpoint_count = 0U;
                }
                agent.target_distance_m = 0.0f;
            }
        }
        if (agent.head_look_mode == HeadLookMode::SoundInvestigation && sound_source != nullptr) {
            if (InsideHeadVisionHemisphere(agent, *sound_source)) {
                if (!crawling && RunningToward(*sound_source, agent) && agent.sword_equipped &&
                    agent.sword_state == SwordState::Sheathed &&
                    !LimbInjured(agent, Limb::RightArm)) {
                    agent.draw_retreat_target_id = sound_source->id;
                }
                agent.recognized_threats.set(static_cast<std::size_t>(sound_source->id - 1U));
                agent.sound_investigation_source_id = kInvalidEntityId;
            } else if (std::fabs(WrapAngle(
                    agent.head_yaw_offset_radians - desired_relative_yaw)) <= 1.0e-5) {
                constexpr std::uint64_t kNonThreateningSalt = 0x4e4f4e5448524541ULL;
                const double duration_seconds =
                    static_cast<double>(config.non_threatening_minimum_seconds) +
                    UnitRandom(seed ^ (static_cast<std::uint64_t>(agent.id) << 32U) ^
                        static_cast<std::uint64_t>(sound_source->id) ^ tick ^ kNonThreateningSalt) *
                    static_cast<double>(config.non_threatening_maximum_seconds -
                        config.non_threatening_minimum_seconds);
                const std::uint64_t duration_ticks = static_cast<std::uint64_t>(std::ceil(
                    duration_seconds * static_cast<double>(config.tick_rate_hz)));
                agent.non_threatening_until_ticks[
                    static_cast<std::size_t>(sound_source->id - 1U)] = tick + duration_ticks;
                agent.sound_investigation_source_id = kInvalidEntityId;
            }
        }
    }

    void UpdateHeadLooks(double dt) noexcept {
        for (AgentRuntime& agent : agents) UpdateHeadLook(agent, dt);
    }

    bool IsCurrentMobileAttacker(const AgentRuntime& attacker, EntityId defender_id) const noexcept {
        return attacker.behavior_mode == BehaviorMode::Attack &&
            attacker.attack_target_id == defender_id && !IsIncapacitated(attacker.state);
    }

    ThreatArc MeasureThreatArc(const AgentRuntime& defender, Vec2 observer_position) const noexcept {
        ThreatArc result{};
        if (defender.id == kInvalidEntityId || defender.id > perceptions.size()) return result;
        const std::size_t defender_index = static_cast<std::size_t>(defender.id - 1U);
        const PerceptionRuntime& perception = perceptions[defender_index];
        std::array<double, kMaxSimulationAgentCount> bearings{};
        for (std::size_t threat_index = 0; threat_index < agents.size(); ++threat_index) {
            if (!perception.active_threats.test(threat_index)) continue;
            const AgentRuntime& threat = agents[threat_index];
            if (!IsStandingThreat(threat)) continue;
            bearings[result.count] = WrapAngle(
                AngleTo(observer_position, threat.locomotion.position));
            ++result.count;
        }
        if (result.count == 0U) return result;
        if (result.count == 1U) {
            result.center_yaw_radians = bearings[0];
            return result;
        }

        std::sort(bearings.begin(), bearings.begin() + result.count);
        double largest_gap = -1.0;
        double arc_start = bearings[0];
        for (std::size_t index = 0; index < result.count; ++index) {
            const double next = index + 1U < result.count
                ? bearings[index + 1U]
                : bearings[0] + 2.0 * kPi;
            const double gap = next - bearings[index];
            if (gap > largest_gap + 1.0e-9) {
                largest_gap = gap;
                arc_start = WrapAngle(next);
            }
        }
        result.span_radians = 2.0 * kPi - largest_gap;
        result.center_yaw_radians = WrapAngle(
            arc_start + 0.5 * result.span_radians);
        return result;
    }

    double NearestPeerSeparation(const AgentRuntime& agent, const AgentRuntime& target,
        double& signed_spacing_push) const noexcept {
        signed_spacing_push = 0.0;
        if (target.id == kInvalidEntityId || target.id > committed_heads.size()) return 0.0;
        const double own_bearing = AngleTo(target.locomotion.position, agent.locomotion.position);
        double nearest = 2.0 * kPi;
        bool peer_seen = false;
        const std::size_t target_index = static_cast<std::size_t>(target.id - 1U);
        for (std::int32_t peer_index = committed_heads[target_index]; peer_index >= 0;
            peer_index = next_committed[static_cast<std::size_t>(peer_index)]) {
            const AgentRuntime& peer = agents[static_cast<std::size_t>(peer_index)];
            if (peer.id == agent.id || !IsCurrentMobileAttacker(peer, target.id)) continue;
            peer_seen = true;
            double delta = WrapAngle(
                AngleTo(target.locomotion.position, peer.locomotion.position) - own_bearing);
            const double separation = std::fabs(delta);
            nearest = std::min(nearest, separation);
            if (separation >= static_cast<double>(kAttackerSeparationRadians)) continue;
            if (separation < 1.0e-6) delta = agent.id < peer.id ? 1.0 : -1.0;
            const double pressure = 1.0 - separation /
                static_cast<double>(kAttackerSeparationRadians);
            signed_spacing_push -= std::copysign(pressure, delta);
        }
        signed_spacing_push = std::clamp(signed_spacing_push, -1.0, 1.0);
        return peer_seen ? nearest : 0.0;
    }

    Vec2 NearbyAllySeparation(const AgentRuntime& agent) const noexcept {
        const double radius = static_cast<double>(config.ally_spacing_distance_m);
        if (radius <= 1.0e-6) return {};
        Vec2 separation{};
        double total_pressure = 0.0;
        constexpr std::uint64_t kOverlapSalt = 0x414c4c5953504143ULL;
        for (const AgentRuntime& ally : agents) {
            if (ally.id == agent.id || ally.team != agent.team || !IsStandingThreat(ally)) continue;
            Vec2 away{agent.locomotion.position.x - ally.locomotion.position.x,
                agent.locomotion.position.z - ally.locomotion.position.z};
            double distance = Length(away);
            if (distance >= radius) continue;
            if (distance <= 1.0e-6) {
                const EntityId lower = std::min(agent.id, ally.id);
                const EntityId upper = std::max(agent.id, ally.id);
                const double yaw = UnitRandom(seed ^
                    (static_cast<std::uint64_t>(lower) << 32U) ^
                    static_cast<std::uint64_t>(upper) ^ kOverlapSalt) * 2.0 * kPi;
                away = DirectionFromAngle(yaw);
                if (agent.id > ally.id) away = Scale(away, -1.0);
                distance = 0.0;
            } else {
                away = Scale(away, 1.0 / distance);
            }
            const double pressure = 1.0 - distance / radius;
            separation = Add(separation, Scale(away, pressure));
            total_pressure += pressure;
        }
        const double length = Length(separation);
        if (length <= 1.0e-8) return {};
        return Scale(separation, std::min(1.0, total_pressure) / length);
    }

    double ContainmentInfluence(double distance) const noexcept {
        constexpr double kEarlyReferenceProximity = 0.3;
        const double inner = static_cast<double>(config.attack_range_m);
        const double outer = static_cast<double>(config.sector_influence_distance_m);
        if (outer <= inner + 1.0e-3) return distance <= inner ? 1.0 : 0.0;
        const double proximity = std::clamp(
            (outer - distance) / (outer - inner), 0.0, 1.0);
        const double reference_squared =
            kEarlyReferenceProximity * kEarlyReferenceProximity;
        const double reference_cubed = reference_squared * kEarlyReferenceProximity;
        const double blend = (static_cast<double>(config.containment_early_influence) -
            reference_cubed) /
            (reference_squared * (1.0 - kEarlyReferenceProximity));
        const double squared = proximity * proximity;
        const double cubed = squared * proximity;
        return std::clamp(cubed + blend * (squared - cubed), 0.0, 1.0);
    }

    Vec2 OutnumberedMovement(const AgentRuntime& agent, const AgentRuntime& target,
        const ThreatArc& threat_arc, double distance,
        double containment_influence) const noexcept {
        Vec2 pursuit{};
        if (distance > static_cast<double>(config.attack_range_m)) {
            pursuit = UnitOrZero({target.locomotion.position.x - agent.locomotion.position.x,
                target.locomotion.position.z - agent.locomotion.position.z});
        }
        if (threat_arc.span_radians <= static_cast<double>(kOutnumberedViewConeRadians)) {
            return UnitOrZero(Add(pursuit, Scale(NearbyAllySeparation(agent),
                1.4 * containment_influence)));
        }

        const Vec2 escape = DirectionFromAngle(threat_arc.center_yaw_radians + kPi);
        const Vec2 to_anchor{agent.engagement_anchor.x - agent.locomotion.position.x,
            agent.engagement_anchor.z - agent.locomotion.position.z};
        const double anchor_distance = Length(to_anchor);
        const double anchor_weight = std::clamp(anchor_distance /
            static_cast<double>(config.attack_range_m), 0.0, 2.0);
        Vec2 containment = Add(escape, Scale(UnitOrZero(to_anchor), 1.5 * anchor_weight));
        if (distance > static_cast<double>(config.attack_range_m)) {
            containment = Add(containment, Scale(pursuit, 0.35));
        }
        Vec2 movement = Add(Scale(pursuit, 1.0 - containment_influence),
            Scale(containment, containment_influence));
        return UnitOrZero(Add(movement, Scale(NearbyAllySeparation(agent),
            1.4 * containment_influence)));
    }

    void UpdateApproachSectorDiagnostics(AgentRuntime& agent,
        const AgentRuntime& target, double distance) noexcept {
        agent.tactical_sector_error_radians = 0.0;
        agent.tactical_sector_influence = 0.0;
        if (agent.approach_sector_target_id != target.id ||
            agent.approach_sector_index >= kApproachSectorCount ||
            IsGroundedTarget(target.state)) return;
        const double outer_radius = static_cast<double>(config.sector_influence_distance_m);
        if (outer_radius <= static_cast<double>(config.attack_range_m) + 1.0e-3) return;
        const double inner_radius = std::min(outer_radius - 1.0e-3,
            std::max(0.25, agent.approach_sector_radius_m));
        const double linear_influence = std::clamp(
            (outer_radius - distance) / std::max(1.0e-3, outer_radius - inner_radius),
            0.0, 1.0);
        agent.tactical_sector_influence = std::sqrt(linear_influence);
        const double bearing = AngleTo(target.locomotion.position, agent.locomotion.position);
        agent.tactical_sector_error_radians = WrapAngle(
            agent.approach_sector_yaw_radians - bearing);
    }

    Vec2 SectorApproachMovement(const AgentRuntime& agent, const AgentRuntime& target,
        double distance, double signed_spacing_push) const noexcept {
        Vec2 movement{};
        Vec2 direct_to_target{};
        if (distance > static_cast<double>(config.attack_range_m)) {
            direct_to_target = UnitOrZero({
                target.locomotion.position.x - agent.locomotion.position.x,
                target.locomotion.position.z - agent.locomotion.position.z});
            movement = direct_to_target;
        }
        const double bearing = AngleTo(target.locomotion.position, agent.locomotion.position);
        const Vec2 positive_tangent{std::cos(bearing), -std::sin(bearing)};
        if (agent.tactical_sector_influence > 0.0) {
            const double sector_step = 2.0 * kPi / static_cast<double>(kApproachSectorCount);
            const double error_scale = std::clamp(
                std::fabs(agent.tactical_sector_error_radians) / sector_step, 0.0, 1.0);
            const double sector_push = std::copysign(
                3.0 * agent.tactical_sector_influence * error_scale,
                agent.tactical_sector_error_radians);
            movement = Add(movement, Scale(positive_tangent, sector_push));
        }
        if (std::fabs(signed_spacing_push) > 1.0e-6) {
            movement = Add(movement, Scale(positive_tangent, 1.1 * signed_spacing_push));
        }
        movement = Add(movement, Scale(NearbyAllySeparation(agent), 1.4));
        if (distance > static_cast<double>(config.attack_range_m)) {
            const double lateral = std::clamp(
                movement.x * positive_tangent.x + movement.z * positive_tangent.z,
                -kMaximumApproachLateralRatio, kMaximumApproachLateralRatio);
            movement = Add(direct_to_target, Scale(positive_tangent, lateral));
        }
        return UnitOrZero(movement);
    }

    void UpdateBehavior(AgentRuntime& agent) noexcept {
        agent.attack_requested = false;
        agent.intent.speed_direction_radians = 0.0;
        agent.intent.speed_scale = 1.0;
        agent.intent.turn_scale = 1.0;
        agent.tactical_steering = TacticalSteeringMode::Direct;
        agent.tactical_threat_count = 0;
        agent.tactical_containment_influence = 0.0;
        agent.tactical_threat_arc_radians = 0.0;
        agent.tactical_nearest_peer_separation_radians = 0.0;
        agent.tactical_view_center_yaw_radians = agent.locomotion.yaw_radians;
        agent.tactical_move_yaw_radians = agent.locomotion.yaw_radians;
        agent.tactical_sector_error_radians = 0.0;
        agent.tactical_sector_influence = 0.0;
        if (agent.state == AgentState::Crawling) {
            agent.intent.mode = LocomotionMode::Crawl;
            agent.intent.speed_amplitude = 0.0;
            agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians;
            agent.intent.speed_scale = config.crawl_speed_scale;
            agent.intent.turn_scale = config.crawl_turn_scale;
            agent.target_distance_m = 0.0f;
            return;
        }
        if (agent.behavior_mode == BehaviorMode::Idle && agent.combat_enabled) {
            agent.attack_target_id = NearestPerceivedStandingOpponent(agent);
            if (agent.attack_target_id != kInvalidEntityId) {
                agent.behavior_mode = BehaviorMode::Attack;
                agent.head_scan_endpoint_count = 0;
            } else if (agent.head_scan_endpoint_count >= 2U &&
                agent.sword_state == SwordState::Drawn &&
                agent.action.phase == ActionPhase::Idle) {
                BeginTimedAction(agent, ActionKind::SheatheSword, HandUsage::Right,
                    ActionPhase::Reaching, config.sheathe_action_seconds, false);
            }
        }
        if (agent.behavior_mode == BehaviorMode::Follow) {
            const EntityId visible_enemy_id = NearestVisibleStandingOpponent(agent);
            if (visible_enemy_id != kInvalidEntityId) {
                agent.behavior_mode = BehaviorMode::Attack;
                agent.attack_target_id = visible_enemy_id;
                agent.follow_target_id = kInvalidEntityId;
                agent.suppress_next_grunt = false;
                agent.head_scan_endpoint_count = 0U;
            } else {
                AgentRuntime* follow_target = FindRuntime(agent.follow_target_id);
                if (follow_target == nullptr || follow_target->team != agent.team ||
                    !IsStandingThreat(*follow_target) || IsIncapacitated(agent.state)) {
                    agent.behavior_mode = BehaviorMode::Idle;
                    agent.follow_target_id = kInvalidEntityId;
                    agent.suppress_next_grunt = false;
                    agent.intent.mode = LocomotionMode::Walk;
                    agent.intent.speed_amplitude = 0.0;
                    agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians;
                    agent.target_distance_m = 0.0f;
                    return;
                }

                const double target_yaw = AngleTo(
                    agent.locomotion.position, follow_target->locomotion.position);
                const double distance = std::hypot(
                    follow_target->locomotion.position.x - agent.locomotion.position.x,
                    follow_target->locomotion.position.z - agent.locomotion.position.z);
                agent.target_distance_m = static_cast<float>(distance);
                agent.intent.orientation_yaw_radians = target_yaw;
                agent.tactical_view_center_yaw_radians = target_yaw;
                agent.tactical_move_yaw_radians = target_yaw;
                const bool actively_defending = agent.reaction.kind == ReactionKind::Parry ||
                    agent.reaction.kind == ReactionKind::Dodge;
                if (agent.state == AgentState::Stunned || IsAttacking(agent) || actively_defending ||
                    distance <= static_cast<double>(config.follow_stop_distance_m)) {
                    agent.intent.mode = LocomotionMode::Walk;
                    agent.intent.speed_amplitude = 0.0;
                    return;
                }
                agent.intent.mode = agent.state == AgentState::Slow ||
                        distance <= static_cast<double>(config.follow_walk_distance_m)
                    ? LocomotionMode::Walk
                    : LocomotionMode::Run;
                agent.intent.speed_amplitude = 1.0;
                agent.intent.speed_direction_radians = WrapAngle(
                    target_yaw - agent.locomotion.yaw_radians);
                return;
            }
        }
        if (agent.behavior_mode != BehaviorMode::Attack &&
            agent.behavior_mode != BehaviorMode::Wrath) {
            agent.intent.mode = LocomotionMode::Walk;
            agent.intent.speed_amplitude = 0.0;
            agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians;
            agent.target_distance_m = 0.0f;
            return;
        }

        AgentRuntime* target = FindRuntime(agent.attack_target_id);
        if (agent.behavior_mode == BehaviorMode::Wrath) {
            if (target == nullptr || !IsGroundedTarget(target->state)) {
                agent.behavior_mode = BehaviorMode::Attack;
                agent.attack_target_id = NearestPerceivedStandingOpponent(agent);
                target = FindRuntime(agent.attack_target_id);
            }
        } else if (target == nullptr || target->state == AgentState::Dead) {
            agent.attack_target_id = NearestActiveOpponent(agent);
            target = FindRuntime(agent.attack_target_id);
        }
        if (target != nullptr) {
            agent.head_scan_endpoint_count = 0;
            agent.non_dead_seen_during_scan.reset();
        }
        if (target == nullptr || target->id != agent.draw_retreat_target_id) {
            agent.draw_retreat_target_id = kInvalidEntityId;
        }
        if (target == nullptr || target->state == AgentState::Dead) {
            agent.intent.speed_amplitude = 0.0;
            agent.intent.mode = LocomotionMode::Walk;
            agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians;
            agent.target_distance_m = 0.0f;
            return;
        }

        const double delta_x = target->locomotion.position.x - agent.locomotion.position.x;
        const double delta_z = target->locomotion.position.z - agent.locomotion.position.z;
        const double distance = std::hypot(delta_x, delta_z);
        agent.target_distance_m = static_cast<float>(distance);
        agent.intent.mode = agent.state == AgentState::Slow
            ? LocomotionMode::Walk
            : LocomotionMode::Run;
        const double target_yaw = AngleTo(agent.locomotion.position, target->locomotion.position);
        agent.intent.orientation_yaw_radians = target_yaw;
        agent.tactical_view_center_yaw_radians = target_yaw;
        agent.tactical_move_yaw_radians = target_yaw;

        const ThreatArc threat_arc = agent.behavior_mode == BehaviorMode::Wrath
            ? ThreatArc{}
            : MeasureThreatArc(agent, agent.locomotion.position);
        double signed_spacing_push = 0.0;
        const bool grounded_target = IsGroundedTarget(target->state);
        const double nearest_peer_separation = grounded_target
            ? 0.0
            : NearestPeerSeparation(agent, *target, signed_spacing_push);
        UpdateApproachSectorDiagnostics(agent, *target, distance);
        if (threat_arc.count >= 2U) {
            agent.tactical_steering = TacticalSteeringMode::OutnumberedView;
            agent.tactical_threat_count = threat_arc.count;
            agent.tactical_containment_influence = ContainmentInfluence(distance);
            agent.tactical_threat_arc_radians = threat_arc.span_radians;
            agent.tactical_view_center_yaw_radians = threat_arc.center_yaw_radians;
        } else if (agent.tactical_sector_influence > 0.0 &&
            std::fabs(agent.tactical_sector_error_radians) > 0.0174533) {
            agent.tactical_steering = TacticalSteeringMode::ApproachSector;
            agent.tactical_nearest_peer_separation_radians = nearest_peer_separation;
        } else if (nearest_peer_separation > 0.0 || std::fabs(signed_spacing_push) > 1.0e-6) {
            agent.tactical_nearest_peer_separation_radians = nearest_peer_separation;
            if (nearest_peer_separation < static_cast<double>(kAttackerSeparationRadians)) {
                agent.tactical_steering = TacticalSteeringMode::AttackerSpacing;
            }
        }

        if (IsIncapacitated(agent.state)) {
            agent.intent.speed_amplitude = 0.0;
            return;
        }

        if (agent.state == AgentState::Stunned) {
            agent.intent.speed_amplitude = 0.0;
            agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians;
            return;
        }

        if (grounded_target && agent.sword_equipped &&
            !LimbInjured(agent, Limb::RightArm) &&
            agent.held_stick_id != kInvalidStickId) {
            agent.intent.speed_amplitude = 0.0;
            if (agent.action.phase == ActionPhase::Idle) {
                (void)RequestDropStickValues(agent.id);
            }
            return;
        }

        if (agent.held_stick_id == kInvalidStickId && agent.sword_equipped &&
            agent.sword_state == SwordState::Sheathed &&
            !LimbInjured(agent, Limb::RightArm)) {
            const bool retreat_while_drawing = agent.draw_retreat_target_id == target->id;
            if (retreat_while_drawing) {
                const double movement_yaw = WrapAngle(target_yaw + kPi);
                agent.intent.mode = LocomotionMode::Walk;
                agent.intent.speed_amplitude = 1.0;
                agent.intent.speed_direction_radians = WrapAngle(
                    movement_yaw - agent.locomotion.yaw_radians);
                agent.tactical_move_yaw_radians = movement_yaw;
            } else {
                agent.intent.speed_amplitude = 0.0;
            }
            if (agent.action.phase == ActionPhase::Idle) {
                BeginTimedAction(agent, ActionKind::UnsheatheSword, HandUsage::Right,
                    ActionPhase::Reaching, config.unsheathe_action_seconds, false);
            }
            return;
        }

        const bool actively_defending = agent.reaction.kind == ReactionKind::Parry ||
            agent.reaction.kind == ReactionKind::Dodge;
        const bool execution_rescue = agent.rescue_executioner_id != kInvalidEntityId &&
            target->id == agent.rescue_executioner_id;
        if (execution_rescue &&
            (agent.action.phase != ActionPhase::Idle || actively_defending)) {
            Vec2 movement{};
            if (agent.tactical_steering == TacticalSteeringMode::OutnumberedView) {
                agent.intent.orientation_yaw_radians = threat_arc.center_yaw_radians;
                movement = OutnumberedMovement(agent, *target, threat_arc, distance,
                    agent.tactical_containment_influence);
            } else {
                movement = SectorApproachMovement(agent, *target, distance,
                    signed_spacing_push);
            }
            const double movement_length = Length(movement);
            agent.intent.speed_amplitude = movement_length > 1.0e-6 ? 1.0 : 0.0;
            if (movement_length > 1.0e-6) {
                const double movement_yaw = std::atan2(movement.x, movement.z);
                agent.tactical_move_yaw_radians = movement_yaw;
                agent.intent.speed_direction_radians = WrapAngle(
                    movement_yaw - agent.locomotion.yaw_radians);
            }
            return;
        }
        if (agent.action.phase != ActionPhase::Idle || actively_defending) {
            agent.intent.speed_amplitude = 0.0;
            return;
        }
        if (agent.attack_cooldown_ticks_remaining > 0U) {
            --agent.attack_cooldown_ticks_remaining;
        }
        const bool cooling_down = agent.attack_cooldown_ticks_remaining > 0U;
        if (!cooling_down) {
            agent.cooldown_strafe_enabled = false;
            agent.cooldown_strafe_direction = 1.0;
            agent.cooldown_strafe_target_distance_m = 0.0;
            agent.cooldown_strafe_distance_remaining_m = 0.0;
        }

        if (distance <= static_cast<double>(config.attack_range_m) &&
            agent.attack_cooldown_ticks_remaining == 0U) {
            agent.intent.speed_amplitude = 0.0;
            agent.attack_requested = true;
            return;
        }

        Vec2 movement{};
        if (grounded_target) {
            if (distance > static_cast<double>(config.attack_range_m)) {
                movement = UnitOrZero({delta_x, delta_z});
            }
        } else if (agent.tactical_steering == TacticalSteeringMode::OutnumberedView) {
            agent.intent.orientation_yaw_radians = threat_arc.center_yaw_radians;
            movement = OutnumberedMovement(agent, *target, threat_arc, distance,
                agent.tactical_containment_influence);
        } else {
            movement = SectorApproachMovement(agent, *target, distance, signed_spacing_push);
        }
        if (cooling_down && !grounded_target) {
            const double spacing_distance = 0.5 * static_cast<double>(config.attack_range_m);
            if (distance < spacing_distance) {
                movement = Add(movement, DirectionFromAngle(target_yaw + kPi));
            }
            if (agent.cooldown_strafe_enabled) {
                const Vec2 strafe_direction = DirectionFromAngle(target_yaw +
                    agent.cooldown_strafe_direction * 0.5 * kPi);
                const Vec2 displacement{
                    agent.locomotion.position.x - agent.cooldown_strafe_last_position.x,
                    agent.locomotion.position.z - agent.cooldown_strafe_last_position.z};
                const double strafe_travel = std::max(0.0,
                    displacement.x * strafe_direction.x + displacement.z * strafe_direction.z);
                agent.cooldown_strafe_distance_remaining_m = std::max(0.0,
                    agent.cooldown_strafe_distance_remaining_m - strafe_travel);
                if (agent.cooldown_strafe_distance_remaining_m > 1.0e-6) {
                    movement = Add(movement, strafe_direction);
                } else {
                    agent.cooldown_strafe_enabled = false;
                }
            }
            agent.cooldown_strafe_last_position = agent.locomotion.position;
        }
        const double movement_length = Length(movement);
        agent.intent.speed_amplitude = movement_length > 1.0e-6 ? 1.0 : 0.0;
        if (movement_length > 1.0e-6) {
            const double movement_yaw = std::atan2(movement.x, movement.z);
            agent.tactical_move_yaw_radians = movement_yaw;
            agent.intent.speed_direction_radians = WrapAngle(
                movement_yaw - agent.locomotion.yaw_radians);
        }
    }

    void RefreshTargetDistances() noexcept {
        for (AgentRuntime& agent : agents) {
            const EntityId target_id = agent.behavior_mode == BehaviorMode::Follow
                ? agent.follow_target_id
                : agent.attack_target_id;
            const AgentRuntime* target = FindRuntime(target_id);
            agent.target_distance_m = target == nullptr ? 0.0f : static_cast<float>(std::hypot(
                target->locomotion.position.x - agent.locomotion.position.x,
                target->locomotion.position.z - agent.locomotion.position.z));
        }
    }

    bool ResolveValidation(EntityId agent_id, std::uint64_t action_sequence, bool success) noexcept {
        const auto runtime = std::find_if(agents.begin(), agents.end(),
            [agent_id](const AgentRuntime& agent) { return agent.id == agent_id; });
        if (runtime == agents.end() || runtime->action.phase != ActionPhase::AwaitingValidation ||
            runtime->action.sequence != action_sequence) return false;
        CompleteAction(*runtime, success);
        return true;
    }

    void ApplyLocomotionOptionValues(float crawl_speed_scale, float crawl_turn_scale) noexcept {
        config.crawl_speed_scale = std::clamp(crawl_speed_scale, 0.0f, 1.0f);
        config.crawl_turn_scale = std::clamp(crawl_turn_scale, 0.0f, 1.0f);
        for (AgentRuntime& agent : agents) {
            if (agent.state != AgentState::Crawling) continue;
            agent.intent.speed_scale = config.crawl_speed_scale;
            agent.intent.turn_scale = config.crawl_turn_scale;
        }
    }

    void ApplyWoundOptionValues(float melee_wound_gain, float wound_threshold,
        float wound_decay_per_second, float leg_agonising_seconds,
        float torso_agonising_seconds, float head_passed_out_seconds) noexcept {
        for (AgentRuntime& agent : agents) MaterializeWounds(agent);
        config.melee_wound_gain = std::clamp(melee_wound_gain, 0.0f, 500.0f);
        config.wound_threshold = std::clamp(wound_threshold, 1.0f, 500.0f);
        config.wound_decay_per_second = std::clamp(wound_decay_per_second, 0.0f, 100.0f);
        config.leg_agonising_seconds = std::clamp(leg_agonising_seconds, 0.0f, 120.0f);
        config.torso_agonising_seconds = std::clamp(torso_agonising_seconds, 0.0f, 120.0f);
        config.head_passed_out_seconds = std::clamp(head_passed_out_seconds, 0.0f, 120.0f);
        for (AgentRuntime& agent : agents) {
            for (std::size_t index = 0; index < agent.wounds.size(); ++index) {
                LimbWoundRuntime& wound = agent.wounds[index];
                const float materialized_gauge = wound.gauge;
                wound.gauge = 0.0f;
                wound.updated_tick = tick;
                if (agent.state == AgentState::Dead) {
                    wound.gauge = std::min(materialized_gauge, config.wound_threshold);
                    continue;
                }
                ApplyGaugeDamage(agent, static_cast<Limb>(index), materialized_gauge);
            }
        }
    }

    void ApplyTacticsOptionValues(float target_commitment_seconds,
        float sector_influence_distance_m, float containment_early_influence,
        float sector_angle_variation_degrees, float sector_radius_variation_m,
        float ally_spacing_distance_m) noexcept {
        config.target_commitment_seconds = std::clamp(target_commitment_seconds, 0.0f, 10.0f);
        config.sector_influence_distance_m = std::clamp(sector_influence_distance_m,
            config.attack_range_m, 50.0f);
        config.containment_early_influence = std::clamp(
            containment_early_influence, 0.0f, 0.2f);
        config.sector_angle_variation_degrees = std::clamp(
            sector_angle_variation_degrees, 0.0f, 22.5f);
        config.sector_radius_variation_m = std::clamp(
            sector_radius_variation_m, 0.0f, 1.0f);
        config.ally_spacing_distance_m = std::clamp(
            ally_spacing_distance_m, 0.0f, 5.0f);
        const std::uint32_t maximum_commitment = CooldownTicks(config.target_commitment_seconds);
        for (AgentRuntime& agent : agents) {
            agent.target_commitment_ticks_remaining = std::min(
                agent.target_commitment_ticks_remaining, maximum_commitment);
            ClearApproachSector(agent);
        }
        RefreshApproachSectors();
    }

    bool ApplyAgentTransformValues(AgentTransform transform) noexcept {
        if (transform.id == kInvalidEntityId || transform.id > agents.size() ||
            !NormalizeTransform(config, transform)) return false;
        AgentRuntime& agent = agents[static_cast<std::size_t>(transform.id - 1U)];
        agent.locomotion.position = {transform.position.x, transform.position.y};
        agent.locomotion.yaw_radians = transform.facing_radians;
        agent.locomotion.previous_yaw_radians = transform.facing_radians;
        return true;
    }

#if PROPHECY_ENABLE_REWIND
    void ApplyReplayValidations() noexcept {
        while (replaying && replay_validation_index < replay_source.validation_events.size()) {
            const ReplayLog::ValidationEvent& event = replay_source.validation_events[replay_validation_index];
            if (event.tick > tick) break;
            if (event.tick == tick) {
                (void)ResolveValidation(event.agent_id, event.action_sequence, event.success);
            }
            ++replay_validation_index;
        }
    }

    void ApplyReplayCombatOptions() noexcept {
        while (replaying && replay_combat_options_index < replay_source.combat_options_events.size()) {
            const ReplayLog::CombatOptionsEvent& event =
                replay_source.combat_options_events[replay_combat_options_index];
            if (event.tick > tick) break;
            config.attack_cooldown_seconds = std::clamp(event.attack_cooldown_seconds, 0.0f, 30.0f);
            config.parried_attack_cooldown_seconds = std::clamp(
                event.parried_attack_cooldown_seconds, 0.0f, 30.0f);
            config.attack_followup_probability = std::clamp(
                event.attack_followup_probability, 0.0f, 1.0f);
            config.drawn_sword_attack_probability = std::clamp(
                event.drawn_sword_attack_probability, 0.0f, 1.0f);
            config.parry_probability = std::clamp(event.parry_probability, 0.0f, 1.0f);
            config.sword_attack_stun_seconds = event.sword_attack_stun_seconds;
            config.melee_attack_stun_seconds = event.melee_attack_stun_seconds;
            NormalizeStunDurations(config.sword_attack_stun_seconds);
            NormalizeStunDurations(config.melee_attack_stun_seconds);
            ++replay_combat_options_index;
        }
    }

    void ApplyReplayLocomotionOptions() noexcept {
        while (replaying &&
            replay_locomotion_options_index < replay_source.locomotion_options_events.size()) {
            const ReplayLog::LocomotionOptionsEvent& event =
                replay_source.locomotion_options_events[replay_locomotion_options_index];
            if (event.tick > tick) break;
            ApplyLocomotionOptionValues(event.crawl_speed_scale, event.crawl_turn_scale);
            ++replay_locomotion_options_index;
        }
    }

    void ApplyReplayWoundOptions() noexcept {
        while (replaying && replay_wound_options_index < replay_source.wound_options_events.size()) {
            const ReplayLog::WoundOptionsEvent& event =
                replay_source.wound_options_events[replay_wound_options_index];
            if (event.tick > tick) break;
            ApplyWoundOptionValues(event.melee_wound_gain, event.wound_threshold,
                event.wound_decay_per_second, event.leg_agonising_seconds,
                event.torso_agonising_seconds, event.head_passed_out_seconds);
            ++replay_wound_options_index;
        }
    }

    void ApplyReplayLookOptions() noexcept {
        while (replaying && replay_look_options_index < replay_source.look_options_events.size()) {
            const ReplayLog::LookOptionsEvent& event =
                replay_source.look_options_events[replay_look_options_index];
            if (event.tick > tick) break;
            config.head_turn_speed_degrees_per_second = NormalizeHeadTurnSpeed(
                event.head_turn_speed_degrees_per_second);
            ApplyPerceptionOptionValues(event.proximity_threat_range_m,
                event.vision_range_m, event.head_vision_angle_degrees,
                event.sound_maximum_range_m,
                event.running_sound_toward_leeway_degrees,
                event.non_threatening_minimum_seconds,
                event.non_threatening_maximum_seconds,
                event.follow_walk_distance_m, event.follow_stop_distance_m);
            ++replay_look_options_index;
        }
    }

    void ApplyReplayTacticsOptions() noexcept {
        while (replaying &&
            replay_tactics_options_index < replay_source.tactics_options_events.size()) {
            const ReplayLog::TacticsOptionsEvent& event =
                replay_source.tactics_options_events[replay_tactics_options_index];
            if (event.tick > tick) break;
            ApplyTacticsOptionValues(event.target_commitment_seconds,
                event.sector_influence_distance_m, event.containment_early_influence,
                event.sector_angle_variation_degrees, event.sector_radius_variation_m,
                event.ally_spacing_distance_m);
            ++replay_tactics_options_index;
        }
    }

    void ApplyReplayTransforms() noexcept {
        bool changed = false;
        while (replaying && replay_transform_index < replay_source.transform_events.size()) {
            const ReplayLog::TransformEvent& event =
                replay_source.transform_events[replay_transform_index];
            if (event.tick > tick) break;
            if (event.tick == tick) changed |= ApplyAgentTransformValues(event.transform);
            ++replay_transform_index;
        }
        if (changed) RefreshTargetDistances();
    }

    void ApplyReplayStickCommands() noexcept {
        while (replaying &&
            replay_stick_command_index < replay_source.stick_command_events.size()) {
            const ReplayLog::StickCommandEvent& event =
                replay_source.stick_command_events[replay_stick_command_index];
            if (event.tick > tick) break;
            if (event.kind == ReplayLog::StickCommandKind::Spawn) {
                (void)SpawnStickValues(event.transform);
            } else if (event.kind == ReplayLog::StickCommandKind::PickUp) {
                (void)RequestPickUpStickValues(event.agent_id, event.stick_id);
            } else {
                (void)RequestDropStickValues(event.agent_id);
            }
            ++replay_stick_command_index;
        }
    }
#endif

    void ResizeAgentScratch() {
        combat_contexts.resize(agents.size());
        committed_heads.resize(agents.size());
        active_heads.resize(agents.size());
        next_committed.resize(agents.size());
        next_active.resize(agents.size());
        committed_counts.resize(agents.size());
        perceptions.resize(agents.size());
    }

    void BuildAgents() noexcept {
        agents.clear();
        const std::uint32_t hero_count = config.hero_agent_count;
        const std::uint32_t villain_count = config.villain_agent_count;
        for (std::uint32_t index = 0; index < config.agent_count; ++index) {
            AgentRuntime agent{};
            agent.id = index + 1U;
            agent.team = index < hero_count ? Team::Hero : Team::Villain;
            const std::uint32_t team_index = agent.team == Team::Hero ? index : index - hero_count;
            const std::uint32_t team_count = agent.team == Team::Hero ? hero_count : villain_count;
            const double lane = (static_cast<double>(team_index) -
                0.5 * static_cast<double>(team_count - 1U)) * 3.0;
            agent.locomotion.position = agent.team == Team::Hero
                ? Vec2{-2.5, lane}
                : Vec2{2.5, lane};
            agent.locomotion.yaw_radians = agent.team == Team::Hero ? 0.5 * kPi : -0.5 * kPi;
            if (config.opening_transforms.size() == config.agent_count) {
                const AgentTransform& transform = config.opening_transforms[index];
                agent.locomotion.position = {transform.position.x, transform.position.y};
                agent.locomotion.yaw_radians = transform.facing_radians;
            }
            agent.locomotion.previous_yaw_radians = agent.locomotion.yaw_radians;
            agent.engagement_anchor = agent.locomotion.position;
            agent.head_yaw_offset_radians = 0.0;
            agent.head_pitch_radians = 0.0;
            agent.intent = {LocomotionMode::Walk, 0.0, 0.0, agent.locomotion.yaw_radians};
            agent.sword_equipped = true;
            agent.sword_state = SwordState::Sheathed;
            agent.combat_enabled = true;
            agent.head_scan_endpoint_count = 2U;
            agents.push_back(agent);
        }
        ResizeAgentScratch();
    }

    void BuildSticks() noexcept {
        sticks.clear();
        for (const StickTransform& transform : config.initial_sticks) {
            StickRuntime stick{};
            stick.id = transform.id;
            stick.position = {transform.position.x, transform.position.y};
            stick.facing_radians = transform.facing_radians;
            sticks.push_back(stick);
        }
    }

    void BuildTargetGroups() noexcept {
        std::fill(committed_heads.begin(), committed_heads.end(), -1);
        std::fill(next_committed.begin(), next_committed.end(), -1);
        std::fill(committed_counts.begin(), committed_counts.end(), 0U);

        for (std::size_t reverse = agents.size(); reverse > 0; --reverse) {
            const std::size_t attacker_index = reverse - 1U;
            const AgentRuntime& attacker = agents[attacker_index];
            if (attacker.behavior_mode != BehaviorMode::Attack ||
                attacker.attack_target_id == kInvalidEntityId ||
                attacker.attack_target_id > agents.size()) continue;
            const std::size_t target_index = static_cast<std::size_t>(attacker.attack_target_id - 1U);
            next_committed[attacker_index] = committed_heads[target_index];
            committed_heads[target_index] = static_cast<std::int32_t>(attacker_index);
            ++committed_counts[target_index];
        }
    }

    void BuildCombatContexts() noexcept {
        BuildTargetGroups();
        std::fill(active_heads.begin(), active_heads.end(), -1);
        std::fill(next_active.begin(), next_active.end(), -1);
        std::fill(combat_contexts.begin(), combat_contexts.end(), CombatContextSnapshot{});

        for (std::size_t reverse = agents.size(); reverse > 0; --reverse) {
            const std::size_t attacker_index = reverse - 1U;
            const AgentRuntime& attacker = agents[attacker_index];
            if (attacker.behavior_mode != BehaviorMode::Attack || !IsAttacking(attacker) ||
                attacker.attack_target_id == kInvalidEntityId ||
                attacker.attack_target_id > agents.size()) continue;
            const std::size_t target_index = static_cast<std::size_t>(attacker.attack_target_id - 1U);
            if (IsAttacking(attacker)) {
                next_active[attacker_index] = active_heads[target_index];
                active_heads[target_index] = static_cast<std::int32_t>(attacker_index);
            }
        }

        for (std::size_t agent_index = 0; agent_index < agents.size(); ++agent_index) {
            CombatContextSnapshot& context = combat_contexts[agent_index];
            for (std::int32_t attacker_index = committed_heads[agent_index]; attacker_index >= 0;
                attacker_index = next_committed[static_cast<std::size_t>(attacker_index)]) {
                ++context.committed_attacker_count;
                if (context.committed_attacker_id_count < context.committed_attacker_ids.size()) {
                    context.committed_attacker_ids[context.committed_attacker_id_count++] =
                        agents[static_cast<std::size_t>(attacker_index)].id;
                }
            }
            for (std::int32_t attacker_index = active_heads[agent_index]; attacker_index >= 0;
                attacker_index = next_active[static_cast<std::size_t>(attacker_index)]) {
                ++context.active_attacker_count;
                if (context.active_attacker_id_count < context.active_attacker_ids.size()) {
                    context.active_attacker_ids[context.active_attacker_id_count++] =
                        agents[static_cast<std::size_t>(attacker_index)].id;
                }
            }
            const AgentRuntime& agent = agents[agent_index];
            if (agent.behavior_mode == BehaviorMode::Attack &&
                agent.attack_target_id != kInvalidEntityId && agent.attack_target_id <= agents.size()) {
                const std::size_t target_index = static_cast<std::size_t>(agent.attack_target_id - 1U);
                context.allies_attacking_target = committed_counts[target_index] > 0U
                    ? committed_counts[target_index] - 1U
                    : 0U;
            }
        }
    }

    void PublishSnapshot() noexcept {
        BuildCombatContexts();
        snapshot.tick = tick;
        snapshot.time_seconds = static_cast<double>(tick) / static_cast<double>(config.tick_rate_hz);
        snapshot.seed = seed;
        snapshot.agents.resize(agents.size());
        snapshot.sticks.resize(sticks.size());
        for (std::size_t index = 0; index < sticks.size(); ++index) {
            const StickRuntime& source = sticks[index];
            StickSnapshot& target = snapshot.sticks[index];
            target.id = source.id;
            target.position = {static_cast<float>(source.position.x),
                static_cast<float>(source.position.z), 0.0f};
            target.facing_radians = static_cast<float>(source.facing_radians);
            target.holder_id = source.holder_id;
        }
        snapshot.sound_event_count = sound_event_count;
        for (std::size_t index = 0; index < sound_event_count; ++index) {
            snapshot.sound_events[index] = sound_events[(sound_event_start + index) % sound_events.size()];
        }
        const double dt = 1.0 / static_cast<double>(config.tick_rate_hz);
        for (std::size_t index = 0; index < agents.size(); ++index) {
            const AgentRuntime& source = agents[index];
            AgentSnapshot& target = snapshot.agents[index];
            target.id = source.id;
            target.team = source.team;
            target.position = {static_cast<float>(source.locomotion.position.x),
                static_cast<float>(source.locomotion.position.z), 0.0f};
            target.facing_radians = static_cast<float>(source.locomotion.yaw_radians);
            target.locomotion_mode = source.intent.mode;
            target.locomotion_response = source.locomotion.response;
            target.root_velocity = {static_cast<float>(source.locomotion.velocity.x),
                static_cast<float>(source.locomotion.velocity.z), 0.0f};
            target.root_speed_mps = static_cast<float>(std::hypot(
                source.locomotion.velocity.x, source.locomotion.velocity.z));
            target.speed_stick_direction_radians = static_cast<float>(source.intent.speed_direction_radians);
            target.speed_stick_amplitude = static_cast<float>(source.intent.speed_amplitude);
            target.orientation_stick_yaw_radians = static_cast<float>(source.intent.orientation_yaw_radians);
            target.pose_phase = PosePhase(source.locomotion, source.intent.mode);
            target.sword_equipped = source.sword_equipped;
            target.sword_state = source.sword_state;
            target.held_weapon = HeldWeapon(source);
            target.held_stick_id = source.held_stick_id;
            target.dropped_sword_position = {static_cast<float>(source.dropped_sword_position.x),
                static_cast<float>(source.dropped_sword_position.z), 0.0f};
            target.dropped_sword_yaw_radians = static_cast<float>(source.dropped_sword_yaw_radians);
            target.behavior_mode = source.behavior_mode;
            target.attack_target_id = source.attack_target_id;
            target.follow_target_id = source.follow_target_id;
            target.draw_retreat_target_id = source.draw_retreat_target_id;
            target.rescue_executioner_id = source.rescue_executioner_id;
            target.rescue_former_target_id = source.rescue_former_target_id;
            target.rescue_head_hold_seconds_remaining =
                source.rescue_head_hold_until_tick > tick
                ? static_cast<float>(source.rescue_head_hold_until_tick - tick) /
                    config.tick_rate_hz
                : 0.0f;
            target.target_distance_m = source.target_distance_m;
            target.completed_attacks = source.completed_attacks;
            target.attack_cooldown_seconds_remaining = static_cast<float>(
                source.attack_cooldown_ticks_remaining) / config.tick_rate_hz;
            target.cooldown_strafe = source.cooldown_strafe_enabled &&
                source.attack_cooldown_ticks_remaining > 0U;
            target.cooldown_strafe_direction = target.cooldown_strafe
                ? static_cast<float>(source.cooldown_strafe_direction)
                : 0.0f;
            target.cooldown_strafe_target_distance_m = static_cast<float>(
                source.cooldown_strafe_target_distance_m);
            target.cooldown_strafe_distance_remaining_m = static_cast<float>(
                source.cooldown_strafe_distance_remaining_m);
            target.combat_context = combat_contexts[index];
            target.perception = perceptions[index].snapshot;
            target.perception.sound_investigation_source_id =
                source.sound_investigation_source_id;
            target.perception.scanning = source.head_look_mode == HeadLookMode::SearchScan;
            target.tactical_steering = source.tactical_steering;
            target.tactical_threat_count = source.tactical_threat_count;
            target.tactical_containment_influence = static_cast<float>(
                source.tactical_containment_influence);
            target.tactical_threat_arc_radians = static_cast<float>(source.tactical_threat_arc_radians);
            target.tactical_nearest_peer_separation_radians = static_cast<float>(
                source.tactical_nearest_peer_separation_radians);
            target.tactical_view_center_yaw_radians = static_cast<float>(
                source.tactical_view_center_yaw_radians);
            target.tactical_move_yaw_radians = static_cast<float>(source.tactical_move_yaw_radians);
            target.tactical_sector_target_id = source.approach_sector_target_id;
            target.tactical_sector_index = source.approach_sector_index;
            target.tactical_sector_yaw_radians = static_cast<float>(
                source.approach_sector_yaw_radians);
            target.tactical_sector_radius_m = static_cast<float>(
                source.approach_sector_radius_m);
            target.tactical_sector_error_radians = static_cast<float>(
                source.tactical_sector_error_radians);
            target.tactical_sector_influence = static_cast<float>(
                source.tactical_sector_influence);
            target.target_commitment_seconds_remaining = static_cast<float>(
                source.target_commitment_ticks_remaining) / config.tick_rate_hz;
            target.head_look_mode = source.head_look_mode;
            target.head_look_target_id = source.head_look_target_id;
            target.head_yaw_radians = static_cast<float>(WrapAngle(
                source.locomotion.yaw_radians + source.head_yaw_offset_radians));
            target.head_pitch_radians = static_cast<float>(source.head_pitch_radians);
            target.state = source.state;
            target.state_seconds_remaining = static_cast<float>(source.state_ticks_remaining) /
                config.tick_rate_hz;
            for (std::size_t limb = 0; limb < source.wounds.size(); ++limb) {
                const LimbWoundRuntime& source_wound = source.wounds[limb];
                LimbWoundSnapshot& target_wound = target.wounds[limb];
                target_wound.gauge = CurrentWoundGauge(source_wound);
                target_wound.gauge_percent = std::clamp(
                    100.0f * target_wound.gauge / config.wound_threshold, 0.0f, 100.0f);
                target_wound.condition = source_wound.condition;
                target_wound.injured = source_wound.condition != LimbCondition::Normal;
                target_wound.badly_injured = source_wound.condition == LimbCondition::BadlyInjured;
            }
            target.action.sequence = source.action.sequence;
            target.action.kind = source.action.kind;
            target.action.phase = source.action.phase;
            target.action.hands = source.action.hands;
            target.action.weapon = source.action.weapon;
            target.action.target_stick_id = source.action.target_stick_id;
            target.action.target_position = {static_cast<float>(source.action.target_position.x),
                static_cast<float>(source.action.target_position.z), 0.0f};
            target.action.elapsed_seconds = static_cast<float>(source.action.total_elapsed_ticks) /
                config.tick_rate_hz;
            target.action.duration_seconds = source.action.duration_seconds;
            target.action.animation_index = source.action.animation_index;
            target.action.stun_duration_seconds = source.action.stun_duration_seconds;
            target.action.validation_required = source.action.validation_required;
            target.action.progress = source.action.phase == ActionPhase::AwaitingValidation
                ? 1.0f
                : static_cast<float>(source.action.phase_elapsed_ticks) /
                    static_cast<float>(source.action.duration_ticks);
            target.action.progress = std::clamp(target.action.progress, 0.0f, 1.0f);
            const bool reaching = source.action.kind == ActionKind::Reach ||
                source.action.kind == ActionKind::Hold ||
                source.action.kind == ActionKind::SheatheSword ||
                source.action.kind == ActionKind::UnsheatheSword ||
                source.action.kind == ActionKind::PickUpStick ||
                source.action.kind == ActionKind::DropStick;
            target.action.reach_alpha = reaching ? target.action.progress : 0.0f;
            target.action.reach_alpha = std::clamp(target.action.reach_alpha, 0.0f, 1.0f);
            target.action.parried = source.action.parried;
            target.reaction.kind = source.reaction.kind;
            target.reaction.elapsed_seconds = static_cast<float>(source.reaction.elapsed_ticks) /
                config.tick_rate_hz;
            target.reaction.duration_seconds = source.reaction.duration_seconds;
            target.reaction.progress = source.reaction.kind == ReactionKind::None
                ? 0.0f
                : static_cast<float>(source.reaction.elapsed_ticks) /
                    static_cast<float>(source.reaction.duration_ticks);
            target.reaction.progress = std::clamp(target.reaction.progress, 0.0f, 1.0f);
            target.future_roots = PredictFutureRoots(source.locomotion, source.intent, dt);
        }
    }

    void Reset(std::uint64_t new_seed) noexcept {
        seed = new_seed;
        tick = 0;
        next_action_sequence = 1;
        next_sound_event_sequence = 1;
        sound_events = {};
        sound_event_start = 0;
        sound_event_count = 0;
#if PROPHECY_ENABLE_REWIND
        replaying = false;
        replay_source = {};
        replay.seed = seed;
        replay.end_tick = 0;
        replay.initial_config = config;
        replay.validation_events.clear();
        replay.locomotion_options_events.clear();
        replay.combat_options_events.clear();
        replay.wound_options_events.clear();
        replay.look_options_events.clear();
        replay.tactics_options_events.clear();
        replay.transform_events.clear();
        replay.stick_command_events.clear();
        replay_validation_index = 0;
        replay_locomotion_options_index = 0;
        replay_combat_options_index = 0;
        replay_wound_options_index = 0;
        replay_look_options_index = 0;
        replay_tactics_options_index = 0;
        replay_transform_index = 0;
        replay_stick_command_index = 0;
#endif
        BuildAgents();
        BuildSticks();
        UpdateHeadLooks(0.0);
        BuildPerceptions();
        PublishSnapshot();
    }

    void Tick() noexcept {
        const double dt = 1.0 / static_cast<double>(config.tick_rate_hz);
        for (AgentRuntime& agent : agents) StepAgentState(agent);
        RefreshExecutionRescues();
        BuildPerceptions();
        ProcessGruntDiscoveries();
        if (NeedsBalancedTargetAssignment()) AssignBalancedStandingTargets();
        RefreshApproachSectors();
        BuildTargetGroups();
        for (AgentRuntime& agent : agents) UpdateBehavior(agent);
        StartRequestedAttacks();
        StepActions();
        for (AgentRuntime& agent : agents) StepReaction(agent);
        for (AgentRuntime& agent : agents) {
            if (agent.state != AgentState::Dead) StepLocomotion(agent.locomotion, agent.intent, dt);
        }
        EmitLocomotionSounds();
        UpdateSoundAwareness(tick + 1U);
        UpdateHeadLooks(dt);
        RefreshTargetDistances();
        ++tick;
#if PROPHECY_ENABLE_REWIND
        ApplyReplayLocomotionOptions();
        ApplyReplayCombatOptions();
        ApplyReplayWoundOptions();
        ApplyReplayLookOptions();
        ApplyReplayTacticsOptions();
        ApplyReplayValidations();
        ApplyReplayTransforms();
        ApplyReplayStickCommands();
        if (!replaying) replay.end_tick = tick;
#endif
        PublishSnapshot();
    }

    bool ValidateAction(EntityId agent_id, std::uint64_t action_sequence, bool success) noexcept {
        if (config.mode != SimulationMode::Paired ||
            !ResolveValidation(agent_id, action_sequence, success)) return false;
#if PROPHECY_ENABLE_REWIND
        if (!replaying) {
            replay.validation_events.push_back({tick, agent_id, action_sequence, success});
        }
#endif
        PublishSnapshot();
        return true;
    }

    bool SetOpeningTransforms(std::vector<AgentTransform> opening_transforms) noexcept {
        SimulationConfig candidate = config;
        candidate.opening_transforms = std::move(opening_transforms);
        candidate = NormalizeConfig(std::move(candidate));
        if (candidate.opening_transforms.size() != candidate.agent_count) return false;
        config.opening_transforms = std::move(candidate.opening_transforms);
        return true;
    }

    bool SetAgentTransform(AgentTransform transform) noexcept {
#if PROPHECY_ENABLE_REWIND
        if (replaying) return false;
#endif
        if (!NormalizeTransform(config, transform) || !ApplyAgentTransformValues(transform)) return false;
#if PROPHECY_ENABLE_REWIND
        RecordTransformEvent(transform);
#endif
        RefreshTargetDistances();
        BuildPerceptions();
        PublishSnapshot();
        return true;
    }

#if PROPHECY_ENABLE_REWIND
    void RecordTransformEvent(const AgentTransform& transform) noexcept {
        for (auto event = replay.transform_events.rbegin(); event != replay.transform_events.rend(); ++event) {
            if (event->tick != tick) break;
            if (event->transform.id == transform.id) {
                event->transform = transform;
                return;
            }
        }
        replay.transform_events.push_back({tick, transform});
    }
#endif

    bool SetAgentTransforms(const std::vector<AgentTransform>& transforms) noexcept {
#if PROPHECY_ENABLE_REWIND
        if (replaying) return false;
#endif
        if (transforms.empty() || transforms.size() > agents.size()) return false;

        std::array<AgentTransform, kMaxSimulationAgentCount> normalized{};
        std::bitset<kMaxSimulationAgentCount> transformed_ids{};
        for (std::size_t index = 0; index < transforms.size(); ++index) {
            AgentTransform transform = transforms[index];
            if (transform.id == kInvalidEntityId || transform.id > agents.size() ||
                transformed_ids.test(static_cast<std::size_t>(transform.id - 1U)) ||
                !NormalizeTransform(config, transform)) return false;
            transformed_ids.set(static_cast<std::size_t>(transform.id - 1U));
            normalized[index] = transform;
        }

        for (std::size_t index = 0; index < transforms.size(); ++index) {
            (void)ApplyAgentTransformValues(normalized[index]);
#if PROPHECY_ENABLE_REWIND
            RecordTransformEvent(normalized[index]);
#endif
        }
        RefreshTargetDistances();
        BuildPerceptions();
        PublishSnapshot();
        return true;
    }

    StickId SpawnStickValues(StickTransform transform) noexcept {
        if (sticks.size() >= kMaxSimulationStickCount ||
            !NormalizeStickTransform(config, transform)) return kInvalidStickId;
        const StickId expected_id = static_cast<StickId>(sticks.size() + 1U);
        if (transform.id != kInvalidStickId && transform.id != expected_id) {
            return kInvalidStickId;
        }
        StickRuntime stick{};
        stick.id = expected_id;
        stick.position = {transform.position.x, transform.position.y};
        stick.facing_radians = transform.facing_radians;
        sticks.push_back(stick);
        return stick.id;
    }

    bool RequestPickUpStickValues(EntityId agent_id, StickId stick_id) noexcept {
        AgentRuntime* agent = FindRuntime(agent_id);
        StickRuntime* stick = FindStick(stick_id);
        if (agent == nullptr || stick == nullptr ||
            stick->holder_id != kInvalidEntityId ||
            agent->held_stick_id != kInvalidStickId ||
            IsIncapacitated(agent->state) || LimbInjured(*agent, Limb::RightArm) ||
            agent->action.phase != ActionPhase::Idle) return false;
        if (agent->sword_state == SwordState::Drawn) {
            agent->pending_stick_pickup_id = stick_id;
            BeginTimedAction(*agent, ActionKind::SheatheSword, HandUsage::Right,
                ActionPhase::Reaching, config.sheathe_action_seconds, false);
            return true;
        }
        if (agent->sword_state != SwordState::Sheathed) return false;
        return BeginStickPickup(*agent, stick_id);
    }

    bool RequestDropStickValues(EntityId agent_id) noexcept {
        AgentRuntime* agent = FindRuntime(agent_id);
        if (agent == nullptr || agent->held_stick_id == kInvalidStickId ||
            agent->action.phase != ActionPhase::Idle || IsIncapacitated(agent->state)) return false;
        BeginTimedAction(*agent, ActionKind::DropStick, HandUsage::Right,
            ActionPhase::Reaching, config.stick_drop_action_seconds, false);
        agent->action.target_stick_id = agent->held_stick_id;
        agent->action.target_position = agent->locomotion.position;
        return true;
    }

    StickId SpawnStick(Vec3 position, float facing_radians) noexcept {
#if PROPHECY_ENABLE_REWIND
        if (replaying) return kInvalidStickId;
#endif
        StickTransform transform{};
        transform.position = position;
        transform.facing_radians = facing_radians;
        const StickId id = SpawnStickValues(transform);
        if (id == kInvalidStickId) return id;
#if PROPHECY_ENABLE_REWIND
        transform.id = id;
        replay.stick_command_events.push_back({tick, ReplayLog::StickCommandKind::Spawn,
            kInvalidEntityId, id, transform});
#endif
        PublishSnapshot();
        return id;
    }

    bool RequestPickUpStick(EntityId agent_id, StickId stick_id) noexcept {
#if PROPHECY_ENABLE_REWIND
        if (replaying) return false;
#endif
        if (!RequestPickUpStickValues(agent_id, stick_id)) return false;
#if PROPHECY_ENABLE_REWIND
        replay.stick_command_events.push_back({tick, ReplayLog::StickCommandKind::PickUp,
            agent_id, stick_id, {}});
#endif
        PublishSnapshot();
        return true;
    }

    bool RequestDropStick(EntityId agent_id) noexcept {
#if PROPHECY_ENABLE_REWIND
        if (replaying) return false;
#endif
#if PROPHECY_ENABLE_REWIND
        AgentRuntime* agent = FindRuntime(agent_id);
        const StickId stick_id = agent == nullptr ? kInvalidStickId : agent->held_stick_id;
#endif
        if (!RequestDropStickValues(agent_id)) return false;
#if PROPHECY_ENABLE_REWIND
        replay.stick_command_events.push_back({tick, ReplayLog::StickCommandKind::Drop,
            agent_id, stick_id, {}});
#endif
        PublishSnapshot();
        return true;
    }

    EntityId SpawnTransientAgent(Team team, Vec3 position, float facing_radians) noexcept {
        if (agents.size() >= kMaxSimulationAgentCount) return kInvalidEntityId;
        const std::size_t team_count = static_cast<std::size_t>(std::count_if(
            agents.begin(), agents.end(), [team](const AgentRuntime& agent) {
                return agent.team == team;
            }));
        if (team_count >= kMaxTeamAgentCount) return kInvalidEntityId;

        AgentTransform transform{};
        transform.position = position;
        transform.facing_radians = facing_radians;
        if (!NormalizeTransform(config, transform)) return kInvalidEntityId;

        AgentRuntime agent{};
        agent.id = static_cast<EntityId>(agents.size() + 1U);
        agent.team = team;
        agent.locomotion.position = {transform.position.x, transform.position.y};
        agent.locomotion.yaw_radians = transform.facing_radians;
        agent.locomotion.previous_yaw_radians = transform.facing_radians;
        agent.engagement_anchor = agent.locomotion.position;
        agent.intent = {LocomotionMode::Walk, 0.0, 0.0, transform.facing_radians};
        agent.sword_equipped = true;
        agent.sword_state = SwordState::Sheathed;
        agent.combat_enabled = true;
        agent.head_scan_endpoint_count = 2U;
        agents.push_back(agent);
        ResizeAgentScratch();
        PublishSnapshot();
        return agent.id;
    }

    bool HasTransientAgents() const noexcept {
        return agents.size() > static_cast<std::size_t>(config.agent_count);
    }

    void UpdateLocomotionOptions(float crawl_speed_scale, float crawl_turn_scale) noexcept {
        ApplyLocomotionOptionValues(crawl_speed_scale, crawl_turn_scale);
#if PROPHECY_ENABLE_REWIND
        if (!replaying) {
            replay.locomotion_options_events.push_back(
                {tick, config.crawl_speed_scale, config.crawl_turn_scale});
        }
#endif
        PublishSnapshot();
    }

    void UpdateCombatOptions(float attack_cooldown_seconds,
        float parried_attack_cooldown_seconds, float attack_followup_probability,
        float drawn_sword_attack_probability, float parry_probability,
        const std::array<float, kSwordAttackClipCount>& sword_attack_stun_seconds,
        const std::array<float, kMeleeAttackClipCount>& melee_attack_stun_seconds) noexcept {
        config.attack_cooldown_seconds = std::clamp(attack_cooldown_seconds, 0.0f, 30.0f);
        config.parried_attack_cooldown_seconds = std::clamp(
            parried_attack_cooldown_seconds, 0.0f, 30.0f);
        config.attack_followup_probability = std::clamp(
            attack_followup_probability, 0.0f, 1.0f);
        config.drawn_sword_attack_probability = std::clamp(
            drawn_sword_attack_probability, 0.0f, 1.0f);
        config.parry_probability = std::clamp(parry_probability, 0.0f, 1.0f);
        config.sword_attack_stun_seconds = sword_attack_stun_seconds;
        config.melee_attack_stun_seconds = melee_attack_stun_seconds;
        NormalizeStunDurations(config.sword_attack_stun_seconds);
        NormalizeStunDurations(config.melee_attack_stun_seconds);
#if PROPHECY_ENABLE_REWIND
        if (!replaying) {
            replay.combat_options_events.push_back({tick, config.attack_cooldown_seconds,
                config.parried_attack_cooldown_seconds, config.attack_followup_probability,
                config.drawn_sword_attack_probability, config.parry_probability,
                config.sword_attack_stun_seconds, config.melee_attack_stun_seconds});
        }
#endif
        PublishSnapshot();
    }

    void UpdateWoundOptions(float melee_wound_gain, float wound_threshold,
        float wound_decay_per_second, float leg_agonising_seconds,
        float torso_agonising_seconds, float head_passed_out_seconds) noexcept {
        ApplyWoundOptionValues(melee_wound_gain, wound_threshold, wound_decay_per_second,
            leg_agonising_seconds, torso_agonising_seconds, head_passed_out_seconds);
#if PROPHECY_ENABLE_REWIND
        if (!replaying) {
            replay.wound_options_events.push_back({tick, config.melee_wound_gain,
                config.wound_threshold, config.wound_decay_per_second,
                config.leg_agonising_seconds, config.torso_agonising_seconds,
                config.head_passed_out_seconds});
        }
#endif
        PublishSnapshot();
    }

    void UpdateLookOptions(float head_turn_speed_degrees_per_second) noexcept {
        config.head_turn_speed_degrees_per_second = NormalizeHeadTurnSpeed(
            head_turn_speed_degrees_per_second);
#if PROPHECY_ENABLE_REWIND
        if (!replaying) {
            RecordLookOptionsEvent();
        }
#endif
        PublishSnapshot();
    }

    void ApplyPerceptionOptionValues(float proximity_threat_range_m, float vision_range_m,
        float head_vision_angle_degrees, float sound_maximum_range_m,
        float running_sound_toward_leeway_degrees,
        float non_threatening_minimum_seconds,
        float non_threatening_maximum_seconds,
        float follow_walk_distance_m, float follow_stop_distance_m) noexcept {
        config.proximity_threat_range_m = std::clamp(proximity_threat_range_m, 0.0f, 100.0f);
        config.vision_range_m = std::clamp(vision_range_m, 0.0f, 500.0f);
        config.head_vision_angle_degrees = std::clamp(
            head_vision_angle_degrees, 0.0f, 360.0f);
        config.sound_maximum_range_m = std::clamp(sound_maximum_range_m, 0.0f, 50.0f);
        config.running_sound_toward_leeway_degrees = std::clamp(
            running_sound_toward_leeway_degrees, 0.0f, 180.0f);
        config.non_threatening_minimum_seconds = std::clamp(
            non_threatening_minimum_seconds, 0.0f, 600.0f);
        config.non_threatening_maximum_seconds = std::clamp(
            non_threatening_maximum_seconds, 0.0f, 600.0f);
        if (config.non_threatening_minimum_seconds > config.non_threatening_maximum_seconds) {
            std::swap(config.non_threatening_minimum_seconds,
                config.non_threatening_maximum_seconds);
        }
        config.follow_walk_distance_m = std::clamp(follow_walk_distance_m, 0.0f, 100.0f);
        config.follow_stop_distance_m = std::clamp(
            follow_stop_distance_m, 0.0f, config.follow_walk_distance_m);
        BuildPerceptions();
    }

#if PROPHECY_ENABLE_REWIND
    void RecordLookOptionsEvent() {
        replay.look_options_events.push_back({tick,
            config.head_turn_speed_degrees_per_second,
            config.proximity_threat_range_m,
            config.vision_range_m,
            config.head_vision_angle_degrees,
            config.sound_maximum_range_m,
            config.running_sound_toward_leeway_degrees,
            config.non_threatening_minimum_seconds,
            config.non_threatening_maximum_seconds,
            config.follow_walk_distance_m,
            config.follow_stop_distance_m});
    }
#endif

    void UpdatePerceptionOptions(float proximity_threat_range_m, float vision_range_m,
        float head_vision_angle_degrees, float sound_maximum_range_m,
        float running_sound_toward_leeway_degrees,
        float non_threatening_minimum_seconds,
        float non_threatening_maximum_seconds,
        float follow_walk_distance_m, float follow_stop_distance_m) noexcept {
        ApplyPerceptionOptionValues(proximity_threat_range_m, vision_range_m,
            head_vision_angle_degrees, sound_maximum_range_m,
            running_sound_toward_leeway_degrees,
            non_threatening_minimum_seconds, non_threatening_maximum_seconds,
            follow_walk_distance_m, follow_stop_distance_m);
#if PROPHECY_ENABLE_REWIND
        if (!replaying) RecordLookOptionsEvent();
#endif
        PublishSnapshot();
    }

    void UpdateTacticsOptions(float target_commitment_seconds,
        float sector_influence_distance_m, float containment_early_influence,
        float sector_angle_variation_degrees, float sector_radius_variation_m,
        float ally_spacing_distance_m) noexcept {
        ApplyTacticsOptionValues(target_commitment_seconds, sector_influence_distance_m,
            containment_early_influence, sector_angle_variation_degrees,
            sector_radius_variation_m, ally_spacing_distance_m);
#if PROPHECY_ENABLE_REWIND
        if (!replaying) {
            replay.tactics_options_events.push_back({tick,
                config.target_commitment_seconds,
                config.sector_influence_distance_m,
                config.containment_early_influence,
                config.sector_angle_variation_degrees,
                config.sector_radius_variation_m,
                config.ally_spacing_distance_m});
        }
#endif
        PublishSnapshot();
    }

    void RestartWithTeamCounts(std::uint32_t hero_count, std::uint32_t villain_count) noexcept {
        config.hero_agent_count = hero_count;
        config.villain_agent_count = villain_count;
        config = NormalizeConfig(config);
        agents.reserve(config.agent_count);
        snapshot.agents.reserve(config.agent_count);
        landing_events.reserve(config.agent_count);
        started_attacks.reserve(config.agent_count);
        Reset(seed);
    }

    void RestartWithTeamCounts(std::uint32_t hero_count, std::uint32_t villain_count,
        std::vector<AgentTransform> opening_transforms) noexcept {
        config.hero_agent_count = hero_count;
        config.villain_agent_count = villain_count;
        config.opening_transforms = std::move(opening_transforms);
        config = NormalizeConfig(std::move(config));
        agents.reserve(config.agent_count);
        snapshot.agents.reserve(config.agent_count);
        landing_events.reserve(config.agent_count);
        started_attacks.reserve(config.agent_count);
        Reset(seed);
    }

    SimulationConfig config{};
    SimulationSnapshot snapshot{};
    std::vector<AgentRuntime> agents{};
    std::vector<StickRuntime> sticks{};
    std::vector<LandingEvent> landing_events{};
    std::vector<StartedAttack> started_attacks{};
    std::vector<CombatContextSnapshot> combat_contexts{};
    std::vector<PerceptionRuntime> perceptions{};
    std::vector<std::int32_t> committed_heads{};
    std::vector<std::int32_t> active_heads{};
    std::vector<std::int32_t> next_committed{};
    std::vector<std::int32_t> next_active{};
    std::vector<std::uint32_t> committed_counts{};
    std::array<SoundEventSnapshot, kSoundEventCapacity> sound_events{};
    std::uint64_t next_action_sequence = 1;
    std::uint64_t next_sound_event_sequence = 1;
    std::size_t sound_event_start = 0;
    std::size_t sound_event_count = 0;
    std::uint64_t seed = 0;
    std::uint64_t tick = 0;
#if PROPHECY_ENABLE_REWIND
    ReplayLog replay{};
    ReplayLog replay_source{};
    bool replaying = false;
    std::size_t replay_validation_index = 0;
    std::size_t replay_locomotion_options_index = 0;
    std::size_t replay_combat_options_index = 0;
    std::size_t replay_wound_options_index = 0;
    std::size_t replay_look_options_index = 0;
    std::size_t replay_tactics_options_index = 0;
    std::size_t replay_transform_index = 0;
    std::size_t replay_stick_command_index = 0;
#endif
};

SimulationConfig MakeDefaultConfig() { return {}; }
const char* ToString(Team team) noexcept { return team == Team::Hero ? "Hero" : "Villain"; }
const char* ToString(SwordState state) noexcept {
    if (state == SwordState::Drawn) return "drawn";
    if (state == SwordState::Dropped) return "dropped";
    return "sheathed";
}
const char* ToString(WeaponKind kind) noexcept {
    if (kind == WeaponKind::Sword) return "sword";
    if (kind == WeaponKind::Stick) return "club";
    return "none";
}
const char* ToString(SimulationMode mode) noexcept {
    return mode == SimulationMode::Paired ? "paired" : "autonomous";
}
const char* ToString(BehaviorMode mode) noexcept {
    if (mode == BehaviorMode::Follow) return "follow";
    if (mode == BehaviorMode::Attack) return "attack";
    if (mode == BehaviorMode::Wrath) return "wrath";
    return "idle";
}
const char* ToString(HeadLookMode mode) noexcept {
    if (mode == HeadLookMode::RootVelocity) return "velocity";
    if (mode == HeadLookMode::CombatTarget) return "combat";
    if (mode == HeadLookMode::RescueFormerTarget) return "rescue_hold";
    if (mode == HeadLookMode::FollowTarget) return "follow";
    if (mode == HeadLookMode::SoundInvestigation) return "sound";
    if (mode == HeadLookMode::SearchScan) return "scan";
    return "heading";
}
const char* ToString(TacticalSteeringMode mode) noexcept {
    if (mode == TacticalSteeringMode::ApproachSector) return "sector";
    if (mode == TacticalSteeringMode::AttackerSpacing) return "spacing";
    if (mode == TacticalSteeringMode::OutnumberedView) return "contain";
    return "direct";
}
const char* ToString(ActionKind kind) noexcept {
    switch (kind) {
        case ActionKind::Reach: return "reach";
        case ActionKind::Hold: return "hold";
        case ActionKind::SheatheSword: return "sheathe";
        case ActionKind::UnsheatheSword: return "unsheathe";
        case ActionKind::PickUpStick: return "pick_up_club";
        case ActionKind::DropStick: return "drop_club";
        case ActionKind::SwordAttack: return "sword_attack";
        case ActionKind::MeleeAttack: return "melee_attack";
        default: return "none";
    }
}
const char* ToString(ReactionKind kind) noexcept {
    switch (kind) {
        case ReactionKind::Parry: return "parry";
        case ReactionKind::Dodge: return "dodge";
        case ReactionKind::Hit: return "hit";
        default: return "none";
    }
}
const char* ToString(SoundEventKind kind) noexcept {
    if (kind == SoundEventKind::Parry) return "parry";
    if (kind == SoundEventKind::CrawlYell) return "crawl_yell";
    if (kind == SoundEventKind::Grunt) return "grunt";
    if (kind == SoundEventKind::ExecutionScream) return "execution_scream";
    return "locomotion";
}
const char* ToString(Limb limb) noexcept {
    switch (limb) {
        case Limb::Head: return "head";
        case Limb::Torso: return "torso";
        case Limb::LeftArm: return "left_arm";
        case Limb::RightArm: return "right_arm";
        case Limb::LeftLeg: return "left_leg";
        case Limb::RightLeg: return "right_leg";
        default: return "unknown";
    }
}
const char* ToString(LimbCondition condition) noexcept {
    switch (condition) {
        case LimbCondition::Injured: return "injured";
        case LimbCondition::BadlyInjured: return "badly_injured";
        default: return "normal";
    }
}
const char* ToString(AgentState state) noexcept {
    switch (state) {
        case AgentState::Slow: return "slow";
        case AgentState::Stunned: return "stunned";
        case AgentState::Agonising: return "agonising";
        case AgentState::PassedOut: return "passed_out";
        case AgentState::Crawling: return "crawling";
        case AgentState::Dead: return "dead";
        default: return "normal";
    }
}
const char* ToString(ActionPhase phase) noexcept {
    switch (phase) {
        case ActionPhase::Reaching: return "reaching";
        case ActionPhase::Executing: return "executing";
        case ActionPhase::AwaitingValidation: return "awaiting_validation";
        default: return "idle";
    }
}
const char* ToString(HandUsage hands) noexcept {
    switch (hands) {
        case HandUsage::Left: return "left";
        case HandUsage::Right: return "right";
        case HandUsage::Both: return "both";
        default: return "none";
    }
}

Simulation::Simulation(SimulationConfig config, std::uint64_t seed) noexcept
    : impl_(std::make_unique<Impl>(std::move(config), seed)) {}
Simulation::~Simulation() = default;
Simulation::Simulation(Simulation&&) noexcept = default;
Simulation& Simulation::operator=(Simulation&&) noexcept = default;

void Simulation::Tick() noexcept { impl_->Tick(); }
void Simulation::Reset(std::uint64_t seed) noexcept { impl_->Reset(seed); }
void Simulation::RestartInMode(SimulationMode mode) noexcept {
    impl_->config.mode = mode;
    impl_->Reset(impl_->seed);
}
void Simulation::RestartWithTeamCounts(std::uint32_t hero_count, std::uint32_t villain_count) noexcept {
    impl_->RestartWithTeamCounts(hero_count, villain_count);
}
void Simulation::RestartWithTeamCounts(std::uint32_t hero_count, std::uint32_t villain_count,
    std::vector<AgentTransform> opening_transforms) noexcept {
    impl_->RestartWithTeamCounts(hero_count, villain_count, std::move(opening_transforms));
}
bool Simulation::SetOpeningTransforms(std::vector<AgentTransform> opening_transforms) noexcept {
    return impl_->SetOpeningTransforms(std::move(opening_transforms));
}
bool Simulation::SetAgentTransform(const AgentTransform& transform) noexcept {
    return impl_->SetAgentTransform(transform);
}
bool Simulation::SetAgentTransforms(const std::vector<AgentTransform>& transforms) noexcept {
    return impl_->SetAgentTransforms(transforms);
}
EntityId Simulation::SpawnTransientAgent(Team team, Vec3 position, float facing_radians) noexcept {
    return impl_->SpawnTransientAgent(team, position, facing_radians);
}
StickId Simulation::SpawnStick(Vec3 position, float facing_radians) noexcept {
    return impl_->SpawnStick(position, facing_radians);
}
bool Simulation::RequestPickUpStick(EntityId agent_id, StickId stick_id) noexcept {
    return impl_->RequestPickUpStick(agent_id, stick_id);
}
bool Simulation::RequestDropStick(EntityId agent_id) noexcept {
    return impl_->RequestDropStick(agent_id);
}
bool Simulation::HasTransientAgents() const noexcept {
    return impl_->HasTransientAgents();
}
void Simulation::UpdateLocomotionOptions(float crawl_speed_scale, float crawl_turn_scale) noexcept {
    impl_->UpdateLocomotionOptions(crawl_speed_scale, crawl_turn_scale);
}
void Simulation::UpdateCombatOptions(float attack_cooldown_seconds,
    float parried_attack_cooldown_seconds, float attack_followup_probability,
    float drawn_sword_attack_probability, float parry_probability,
    const std::array<float, kSwordAttackClipCount>& sword_attack_stun_seconds,
    const std::array<float, kMeleeAttackClipCount>& melee_attack_stun_seconds) noexcept {
    impl_->UpdateCombatOptions(attack_cooldown_seconds,
        parried_attack_cooldown_seconds, attack_followup_probability,
        drawn_sword_attack_probability, parry_probability,
        sword_attack_stun_seconds, melee_attack_stun_seconds);
}
void Simulation::UpdateWoundOptions(float melee_wound_gain, float wound_threshold,
    float wound_decay_per_second, float leg_agonising_seconds,
    float torso_agonising_seconds, float head_passed_out_seconds) noexcept {
    impl_->UpdateWoundOptions(melee_wound_gain, wound_threshold, wound_decay_per_second,
        leg_agonising_seconds, torso_agonising_seconds, head_passed_out_seconds);
}
void Simulation::UpdateLookOptions(float head_turn_speed_degrees_per_second) noexcept {
    impl_->UpdateLookOptions(head_turn_speed_degrees_per_second);
}
void Simulation::UpdatePerceptionOptions(float proximity_threat_range_m, float vision_range_m,
    float head_vision_angle_degrees, float sound_maximum_range_m,
    float running_sound_toward_leeway_degrees,
    float non_threatening_minimum_seconds,
    float non_threatening_maximum_seconds,
    float follow_walk_distance_m, float follow_stop_distance_m) noexcept {
    impl_->UpdatePerceptionOptions(proximity_threat_range_m, vision_range_m,
        head_vision_angle_degrees, sound_maximum_range_m,
        running_sound_toward_leeway_degrees,
        non_threatening_minimum_seconds, non_threatening_maximum_seconds,
        follow_walk_distance_m, follow_stop_distance_m);
}
void Simulation::UpdateTacticsOptions(float target_commitment_seconds,
    float sector_influence_distance_m, float containment_early_influence,
    float sector_angle_variation_degrees, float sector_radius_variation_m,
    float ally_spacing_distance_m) noexcept {
    impl_->UpdateTacticsOptions(target_commitment_seconds, sector_influence_distance_m,
        containment_early_influence, sector_angle_variation_degrees,
        sector_radius_variation_m, ally_spacing_distance_m);
}
bool Simulation::ValidateAction(EntityId agent_id, std::uint64_t action_sequence, bool success) noexcept {
    return impl_->ValidateAction(agent_id, action_sequence, success);
}

void Simulation::BeginReplay(const ReplayLog& replay) noexcept {
#if PROPHECY_ENABLE_REWIND
    const ReplayLog source = replay;
    impl_->config = NormalizeConfig(source.initial_config);
    impl_->Reset(source.seed);
    impl_->replay_source = source;
    impl_->replaying = true;
    impl_->ApplyReplayLocomotionOptions();
    impl_->ApplyReplayCombatOptions();
    impl_->ApplyReplayWoundOptions();
    impl_->ApplyReplayLookOptions();
    impl_->ApplyReplayTacticsOptions();
    impl_->ApplyReplayTransforms();
    impl_->ApplyReplayStickCommands();
    impl_->PublishSnapshot();
#else
    (void)replay;
#endif
}

bool Simulation::SeekReplay(const ReplayLog& replay, std::uint64_t target_tick) noexcept {
#if PROPHECY_ENABLE_REWIND
    if (target_tick > replay.end_tick) return false;
    BeginReplay(replay);
    while (impl_->tick < target_tick) impl_->Tick();
    return impl_->tick == target_tick;
#else
    (void)replay;
    (void)target_tick;
    return false;
#endif
}

#if PROPHECY_ENABLE_REWIND
std::unique_ptr<Simulation> Simulation::CreateRewindCheckpoint() const {
    auto checkpoint = std::make_unique<Simulation>(impl_->config, impl_->seed);
    *checkpoint->impl_ = *impl_;
    checkpoint->impl_->replay = {};
    checkpoint->impl_->replay_source = {};
    checkpoint->impl_->replaying = false;
    checkpoint->impl_->replay_validation_index = 0;
    checkpoint->impl_->replay_locomotion_options_index = 0;
    checkpoint->impl_->replay_combat_options_index = 0;
    checkpoint->impl_->replay_wound_options_index = 0;
    checkpoint->impl_->replay_look_options_index = 0;
    checkpoint->impl_->replay_tactics_options_index = 0;
    checkpoint->impl_->replay_transform_index = 0;
    checkpoint->impl_->replay_stick_command_index = 0;
    return checkpoint;
}

bool Simulation::RestoreRewindCheckpoint(
    const Simulation& checkpoint, const ReplayLog& replay) {
    if (checkpoint.impl_->seed != replay.seed || checkpoint.impl_->tick > replay.end_tick) return false;

    *impl_ = *checkpoint.impl_;
    impl_->replay = {};
    impl_->replay_source = replay;
    impl_->replaying = true;
    const auto first_event_after_tick = [this](const auto& events) {
        return static_cast<std::size_t>(std::distance(events.begin(), std::upper_bound(
            events.begin(), events.end(), impl_->tick,
            [](std::uint64_t current_tick, const auto& event) {
                return current_tick < event.tick;
            })));
    };
    impl_->replay_validation_index = first_event_after_tick(replay.validation_events);
    impl_->replay_locomotion_options_index = first_event_after_tick(
        replay.locomotion_options_events);
    impl_->replay_combat_options_index = first_event_after_tick(replay.combat_options_events);
    impl_->replay_wound_options_index = first_event_after_tick(replay.wound_options_events);
    impl_->replay_look_options_index = first_event_after_tick(replay.look_options_events);
    impl_->replay_tactics_options_index = first_event_after_tick(replay.tactics_options_events);
    impl_->replay_transform_index = first_event_after_tick(replay.transform_events);
    impl_->replay_stick_command_index = first_event_after_tick(replay.stick_command_events);
    impl_->PublishSnapshot();
    return true;
}
#endif

bool Simulation::ResumeRecordingFromReplay() noexcept {
#if PROPHECY_ENABLE_REWIND
    if (!impl_->replaying || impl_->tick != impl_->replay_source.end_tick) return false;
    impl_->replay = impl_->replay_source;
    impl_->replay.end_tick = impl_->tick;
    impl_->replay_source = {};
    impl_->replaying = false;
    return true;
#else
    return false;
#endif
}

bool Simulation::BranchRecordingFromReplay() noexcept {
#if PROPHECY_ENABLE_REWIND
    if (!impl_->replaying) return true;
    impl_->replay = impl_->replay_source;
    impl_->replay.end_tick = impl_->tick;
    const auto remove_future = [this](auto& events) {
        events.erase(std::upper_bound(events.begin(), events.end(), impl_->tick,
            [](std::uint64_t current_tick, const auto& event) {
                return current_tick < event.tick;
            }), events.end());
    };
    remove_future(impl_->replay.validation_events);
    remove_future(impl_->replay.locomotion_options_events);
    remove_future(impl_->replay.combat_options_events);
    remove_future(impl_->replay.wound_options_events);
    remove_future(impl_->replay.look_options_events);
    remove_future(impl_->replay.tactics_options_events);
    remove_future(impl_->replay.transform_events);
    remove_future(impl_->replay.stick_command_events);
    impl_->replay_source = {};
    impl_->replaying = false;
    return true;
#else
    return false;
#endif
}

const ReplayLog& Simulation::RecordedReplay() const noexcept {
#if PROPHECY_ENABLE_REWIND
    return impl_->replay;
#else
    static const ReplayLog empty{};
    return empty;
#endif
}

bool Simulation::IsReplaying() const noexcept {
#if PROPHECY_ENABLE_REWIND
    return impl_->replaying;
#else
    return false;
#endif
}

const SimulationSnapshot& Simulation::Snapshot() const noexcept { return impl_->snapshot; }
const SimulationConfig& Simulation::Config() const noexcept { return impl_->config; }
std::uint64_t Simulation::Seed() const noexcept { return impl_->seed; }
double Simulation::TickSeconds() const noexcept { return 1.0 / static_cast<double>(impl_->config.tick_rate_hz); }

}  // namespace prophecy::sim
