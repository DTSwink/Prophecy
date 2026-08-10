#pragma once

#include "prophecy/sim/locomotion.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

#ifndef PROPHECY_ENABLE_REWIND
#define PROPHECY_ENABLE_REWIND 1
#endif

namespace prophecy::sim {

using EntityId = std::uint32_t;
using StickId = std::uint32_t;
constexpr EntityId kInvalidEntityId = 0;
constexpr StickId kInvalidStickId = 0;
inline constexpr bool kRewindEnabled = PROPHECY_ENABLE_REWIND != 0;
inline constexpr std::size_t kLimbCount = 6;
inline constexpr std::size_t kSwordAttackClipCount = 7;
inline constexpr std::size_t kMeleeAttackClipCount = 9;
inline constexpr std::size_t kAttackClipCount = kSwordAttackClipCount + kMeleeAttackClipCount;
inline constexpr std::size_t kCombatContextIdCapacity = 4;
inline constexpr std::size_t kSoundEventCapacity = 512;
inline constexpr float kLocomotionSoundIntervalSeconds = 0.2f;
inline constexpr float kSoundMaximumRangeMeters = 3.0f;
inline constexpr float kSoundPropagationMetersPerSecond = 1.0f;
inline constexpr float kRunSoundReferenceSpeedMps = 5.0f;
inline constexpr std::array<float, kSwordAttackClipCount> kDefaultSwordAttackStunSeconds{
    0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f};
inline constexpr std::array<float, kMeleeAttackClipCount> kDefaultMeleeAttackStunSeconds{
    0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f};
inline constexpr float kHeadVelocityThresholdMps = 0.5f;
inline constexpr float kHeadYawLimitRadians = 2.0943951f;
inline constexpr float kHeadPitchLimitRadians = 1.3962634f;
inline constexpr float kDefaultHeadTurnSpeedDegreesPerSecond = 360.0f;
inline constexpr float kProximityThreatRangeMeters = 3.0f;
inline constexpr float kVisionRangeMeters = 100.0f;
inline constexpr float kHeadVisionHemisphereRadians = 3.1415927f;
inline constexpr float kRunningSoundTowardToleranceRadians = 0.2617994f;
inline constexpr float kDefaultFollowWalkDistanceMeters = 7.0f;
inline constexpr float kDefaultFollowStopDistanceMeters = 2.0f;
inline constexpr std::size_t kGruntPropagationAgentLimit = 5U;
inline constexpr float kWrathProbability = 0.2f;
inline constexpr float kNonThreateningMinimumSeconds = 30.0f;
inline constexpr float kNonThreateningMaximumSeconds = 40.0f;
inline constexpr float kOutnumberedViewConeRadians = 2.7925268f;
inline constexpr float kAttackerSeparationRadians = 0.7853982f;
inline constexpr std::size_t kApproachSectorCount = 8U;
inline constexpr float kTargetAssignmentRateHz = 5.0f;
inline constexpr float kDefaultTargetCommitmentSeconds = 1.5f;
inline constexpr float kDefaultSectorInfluenceDistanceMeters = 30.0f;
inline constexpr float kDefaultContainmentEarlyInfluence = 0.10f;
inline constexpr float kDefaultAttackFollowupProbability = 0.50f;
inline constexpr float kDefaultDrawnSwordAttackProbability = 0.80f;
inline constexpr float kDefaultSectorAngleVariationDegrees = 12.0f;
inline constexpr float kDefaultSectorRadiusVariationMeters = 0.15f;
inline constexpr float kDefaultAllySpacingDistanceMeters = 2.0f;
inline constexpr float kDefaultCrawlSpeedScale = 0.2f;
inline constexpr float kDefaultCrawlTurnScale = 0.2f;
inline constexpr std::uint32_t kMinTeamAgentCount = 0;
inline constexpr std::uint32_t kMaxTeamAgentCount = 100;
inline constexpr std::size_t kMaxSimulationAgentCount = 2U * kMaxTeamAgentCount;
inline constexpr std::size_t kMaxSimulationStickCount = 256U;

struct Vec3 {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

enum class Team : std::uint8_t {
    Hero,
    Villain,
};

enum class SwordState : std::uint8_t {
    Sheathed,
    Drawn,
    Dropped,
};

enum class WeaponKind : std::uint8_t {
    None,
    Sword,
    Stick,
};

enum class SimulationMode : std::uint8_t {
    Autonomous,
    Paired,
};

enum class BehaviorMode : std::uint8_t {
    Idle,
    Follow,
    Attack,
    Wrath,
};

enum class HeadLookMode : std::uint8_t {
    RootHeading,
    RootVelocity,
    CombatTarget,
    RescueFormerTarget,
    FollowTarget,
    SoundInvestigation,
    SearchScan,
};

enum class TacticalSteeringMode : std::uint8_t {
    Direct,
    ApproachSector,
    AttackerSpacing,
    OutnumberedView,
};

enum class ActionKind : std::uint8_t {
    None,
    Reach,
    Hold,
    SheatheSword,
    UnsheatheSword,
    PickUpStick,
    DropStick,
    SwordAttack,
    MeleeAttack,
};

enum class ReactionKind : std::uint8_t {
    None,
    Parry,
    Dodge,
    Hit,
};

enum class SoundEventKind : std::uint8_t {
    Locomotion,
    Parry,
    CrawlYell,
    Grunt,
    ExecutionScream,
};

enum class Limb : std::uint8_t {
    Head,
    Torso,
    LeftArm,
    RightArm,
    LeftLeg,
    RightLeg,
};

enum class LimbCondition : std::uint8_t {
    Normal,
    Injured,
    BadlyInjured,
};

enum class AgentState : std::uint8_t {
    Normal,
    Slow,
    Stunned,
    Agonising,
    PassedOut,
    Crawling,
    Dead,
};

enum class ActionPhase : std::uint8_t {
    Idle,
    Reaching,
    Executing,
    AwaitingValidation,
};

enum class HandUsage : std::uint8_t {
    None,
    Left,
    Right,
    Both,
};

struct AgentTransform {
    EntityId id = kInvalidEntityId;
    Vec3 position{};
    float facing_radians = 0.0f;
};

struct StickTransform {
    StickId id = kInvalidStickId;
    Vec3 position{};
    float facing_radians = 0.0f;
};

struct SimulationConfig {
    std::uint32_t agent_count = 2;
    std::uint32_t hero_agent_count = 1;
    std::uint32_t villain_agent_count = 1;
    float tick_rate_hz = 30.0f;
    Vec3 world_min{-32.0f, -24.0f, 0.0f};
    Vec3 world_max{32.0f, 24.0f, 0.0f};
    SimulationMode mode = SimulationMode::Autonomous;
    float sheathe_action_seconds = 1.6f / 1.7f;
    float unsheathe_action_seconds = 1.4f / 1.7f;
    float stick_pickup_action_seconds = 1.0f;
    float stick_drop_action_seconds = 0.1f;
    float attack_range_m = 1.25f;
    float attack_cooldown_seconds = 1.0f;
    float parried_attack_cooldown_seconds = 1.5f;
    float attack_followup_probability = kDefaultAttackFollowupProbability;
    float drawn_sword_attack_probability = kDefaultDrawnSwordAttackProbability;
    float hit_probability = 0.2f;
    float parry_probability = 0.5f;
    float head_turn_speed_degrees_per_second = kDefaultHeadTurnSpeedDegreesPerSecond;
    float proximity_threat_range_m = kProximityThreatRangeMeters;
    float vision_range_m = kVisionRangeMeters;
    float head_vision_angle_degrees = 180.0f;
    float sound_maximum_range_m = kSoundMaximumRangeMeters;
    float running_sound_toward_leeway_degrees = 15.0f;
    float non_threatening_minimum_seconds = kNonThreateningMinimumSeconds;
    float non_threatening_maximum_seconds = kNonThreateningMaximumSeconds;
    float follow_walk_distance_m = kDefaultFollowWalkDistanceMeters;
    float follow_stop_distance_m = kDefaultFollowStopDistanceMeters;
    float target_commitment_seconds = kDefaultTargetCommitmentSeconds;
    float sector_influence_distance_m = kDefaultSectorInfluenceDistanceMeters;
    float containment_early_influence = kDefaultContainmentEarlyInfluence;
    float sector_angle_variation_degrees = kDefaultSectorAngleVariationDegrees;
    float sector_radius_variation_m = kDefaultSectorRadiusVariationMeters;
    float ally_spacing_distance_m = kDefaultAllySpacingDistanceMeters;
    float crawl_speed_scale = kDefaultCrawlSpeedScale;
    float crawl_turn_scale = kDefaultCrawlTurnScale;
    std::array<float, kSwordAttackClipCount> sword_attack_stun_seconds =
        kDefaultSwordAttackStunSeconds;
    std::array<float, kMeleeAttackClipCount> melee_attack_stun_seconds =
        kDefaultMeleeAttackStunSeconds;
    float melee_wound_gain = 20.0f;
    float wound_threshold = 100.0f;
    float wound_decay_per_second = 1.0f;
    float leg_agonising_seconds = 3.0f;
    float torso_agonising_seconds = 10.0f;
    float head_passed_out_seconds = 30.0f;
    std::vector<AgentTransform> opening_transforms{};
    std::vector<StickTransform> initial_sticks{};
};

struct ActionSnapshot {
    std::uint64_t sequence = 0;
    ActionKind kind = ActionKind::None;
    ActionPhase phase = ActionPhase::Idle;
    HandUsage hands = HandUsage::None;
    WeaponKind weapon = WeaponKind::None;
    StickId target_stick_id = kInvalidStickId;
    Vec3 target_position{};
    float elapsed_seconds = 0.0f;
    float duration_seconds = 0.0f;
    float progress = 0.0f;
    float reach_alpha = 0.0f;
    std::uint8_t animation_index = 0;
    float stun_duration_seconds = 0.0f;
    bool parried = false;
    bool validation_required = false;
};

struct ReactionSnapshot {
    ReactionKind kind = ReactionKind::None;
    float elapsed_seconds = 0.0f;
    float duration_seconds = 0.0f;
    float progress = 0.0f;
};

struct LimbWoundSnapshot {
    float gauge = 0.0f;
    float gauge_percent = 0.0f;
    LimbCondition condition = LimbCondition::Normal;
    bool injured = false;
    bool badly_injured = false;
};

struct CombatContextSnapshot {
    std::uint32_t committed_attacker_count = 0;
    std::uint32_t active_attacker_count = 0;
    std::uint32_t allies_attacking_target = 0;
    std::array<EntityId, kCombatContextIdCapacity> committed_attacker_ids{};
    std::array<EntityId, kCombatContextIdCapacity> active_attacker_ids{};
    std::uint8_t committed_attacker_id_count = 0;
    std::uint8_t active_attacker_id_count = 0;
};

struct PerceptionSnapshot {
    std::uint32_t active_threat_count = 0;
    std::uint32_t finishing_target_count = 0;
    std::uint32_t recognized_threat_count = 0;
    std::uint32_t proximity_threat_count = 0;
    std::uint32_t visible_threat_count = 0;
    std::array<EntityId, kCombatContextIdCapacity> active_threat_ids{};
    std::array<EntityId, kCombatContextIdCapacity> finishing_target_ids{};
    std::uint8_t active_threat_id_count = 0;
    std::uint8_t finishing_target_id_count = 0;
    EntityId sound_investigation_source_id = kInvalidEntityId;
    std::uint32_t non_threatening_source_count = 0;
    bool scanning = false;
};

struct AgentSnapshot {
    EntityId id = kInvalidEntityId;
    Vec3 position{};
    float facing_radians = 0.0f;
    Team team = Team::Hero;
    LocomotionMode locomotion_mode = LocomotionMode::Walk;
    LocomotionResponse locomotion_response = LocomotionResponse::Normal;
    Vec3 root_velocity{};
    float root_speed_mps = 0.0f;
    float speed_stick_direction_radians = 0.0f;
    float speed_stick_amplitude = 0.0f;
    float orientation_stick_yaw_radians = 0.0f;
    float pose_phase = 0.0f;
    bool sword_equipped = false;
    SwordState sword_state = SwordState::Sheathed;
    WeaponKind held_weapon = WeaponKind::None;
    StickId held_stick_id = kInvalidStickId;
    Vec3 dropped_sword_position{};
    float dropped_sword_yaw_radians = 0.0f;
    BehaviorMode behavior_mode = BehaviorMode::Idle;
    EntityId attack_target_id = kInvalidEntityId;
    EntityId follow_target_id = kInvalidEntityId;
    EntityId draw_retreat_target_id = kInvalidEntityId;
    EntityId rescue_executioner_id = kInvalidEntityId;
    EntityId rescue_former_target_id = kInvalidEntityId;
    float rescue_head_hold_seconds_remaining = 0.0f;
    float target_distance_m = 0.0f;
    HeadLookMode head_look_mode = HeadLookMode::RootHeading;
    EntityId head_look_target_id = kInvalidEntityId;
    float head_yaw_radians = 0.0f;
    float head_pitch_radians = 0.0f;
    std::uint32_t completed_attacks = 0;
    float attack_cooldown_seconds_remaining = 0.0f;
    bool cooldown_strafe = false;
    float cooldown_strafe_direction = 0.0f;
    float cooldown_strafe_target_distance_m = 0.0f;
    float cooldown_strafe_distance_remaining_m = 0.0f;
    CombatContextSnapshot combat_context{};
    PerceptionSnapshot perception{};
    TacticalSteeringMode tactical_steering = TacticalSteeringMode::Direct;
    std::uint32_t tactical_threat_count = 0;
    float tactical_containment_influence = 0.0f;
    float tactical_threat_arc_radians = 0.0f;
    float tactical_nearest_peer_separation_radians = 0.0f;
    float tactical_view_center_yaw_radians = 0.0f;
    float tactical_move_yaw_radians = 0.0f;
    EntityId tactical_sector_target_id = kInvalidEntityId;
    std::uint8_t tactical_sector_index = static_cast<std::uint8_t>(kApproachSectorCount);
    float tactical_sector_yaw_radians = 0.0f;
    float tactical_sector_radius_m = 0.0f;
    float tactical_sector_error_radians = 0.0f;
    float tactical_sector_influence = 0.0f;
    float target_commitment_seconds_remaining = 0.0f;
    AgentState state = AgentState::Normal;
    float state_seconds_remaining = 0.0f;
    std::array<LimbWoundSnapshot, kLimbCount> wounds{};
    ActionSnapshot action{};
    ReactionSnapshot reaction{};
    FutureRootWindow future_roots{};
};

struct SoundEventSnapshot {
    std::uint64_t sequence = 0;
    std::uint64_t emitted_tick = 0;
    EntityId source_id = kInvalidEntityId;
    EntityId secondary_source_id = kInvalidEntityId;
    SoundEventKind kind = SoundEventKind::Locomotion;
    Vec3 position{};
    float maximum_range_m = 0.0f;
    std::uint8_t recipient_count = 0;
};

struct StickSnapshot {
    StickId id = kInvalidStickId;
    Vec3 position{};
    float facing_radians = 0.0f;
    EntityId holder_id = kInvalidEntityId;
};

struct SimulationSnapshot {
    std::uint64_t tick = 0;
    double time_seconds = 0.0;
    std::uint64_t seed = 0;
    std::vector<AgentSnapshot> agents{};
    std::vector<StickSnapshot> sticks{};
    std::array<SoundEventSnapshot, kSoundEventCapacity> sound_events{};
    std::size_t sound_event_count = 0;
};

struct ReplayLog {
    std::uint64_t seed = 0;
    std::uint64_t end_tick = 0;
    SimulationConfig initial_config{};
#if PROPHECY_ENABLE_REWIND
    struct ValidationEvent {
        std::uint64_t tick = 0;
        EntityId agent_id = kInvalidEntityId;
        std::uint64_t action_sequence = 0;
        bool success = false;
    };
    struct CombatOptionsEvent {
        std::uint64_t tick = 0;
        float attack_cooldown_seconds = 1.0f;
        float parried_attack_cooldown_seconds = 1.5f;
        float attack_followup_probability = kDefaultAttackFollowupProbability;
        float drawn_sword_attack_probability = kDefaultDrawnSwordAttackProbability;
        float parry_probability = 0.5f;
        std::array<float, kSwordAttackClipCount> sword_attack_stun_seconds =
            kDefaultSwordAttackStunSeconds;
        std::array<float, kMeleeAttackClipCount> melee_attack_stun_seconds =
            kDefaultMeleeAttackStunSeconds;
    };
    struct LocomotionOptionsEvent {
        std::uint64_t tick = 0;
        float crawl_speed_scale = kDefaultCrawlSpeedScale;
        float crawl_turn_scale = kDefaultCrawlTurnScale;
    };
    struct WoundOptionsEvent {
        std::uint64_t tick = 0;
        float melee_wound_gain = 20.0f;
        float wound_threshold = 100.0f;
        float wound_decay_per_second = 1.0f;
        float leg_agonising_seconds = 3.0f;
        float torso_agonising_seconds = 10.0f;
        float head_passed_out_seconds = 30.0f;
    };
    struct LookOptionsEvent {
        std::uint64_t tick = 0;
        float head_turn_speed_degrees_per_second = kDefaultHeadTurnSpeedDegreesPerSecond;
        float proximity_threat_range_m = kProximityThreatRangeMeters;
        float vision_range_m = kVisionRangeMeters;
        float head_vision_angle_degrees = 180.0f;
        float sound_maximum_range_m = kSoundMaximumRangeMeters;
        float running_sound_toward_leeway_degrees = 15.0f;
        float non_threatening_minimum_seconds = kNonThreateningMinimumSeconds;
        float non_threatening_maximum_seconds = kNonThreateningMaximumSeconds;
        float follow_walk_distance_m = kDefaultFollowWalkDistanceMeters;
        float follow_stop_distance_m = kDefaultFollowStopDistanceMeters;
    };
    struct TacticsOptionsEvent {
        std::uint64_t tick = 0;
        float target_commitment_seconds = kDefaultTargetCommitmentSeconds;
        float sector_influence_distance_m = kDefaultSectorInfluenceDistanceMeters;
        float containment_early_influence = kDefaultContainmentEarlyInfluence;
        float sector_angle_variation_degrees = kDefaultSectorAngleVariationDegrees;
        float sector_radius_variation_m = kDefaultSectorRadiusVariationMeters;
        float ally_spacing_distance_m = kDefaultAllySpacingDistanceMeters;
    };
    struct TransformEvent {
        std::uint64_t tick = 0;
        AgentTransform transform{};
    };
    enum class StickCommandKind : std::uint8_t {
        Spawn,
        PickUp,
        Drop,
    };
    struct StickCommandEvent {
        std::uint64_t tick = 0;
        StickCommandKind kind = StickCommandKind::Spawn;
        EntityId agent_id = kInvalidEntityId;
        StickId stick_id = kInvalidStickId;
        StickTransform transform{};
    };
    std::vector<ValidationEvent> validation_events{};
    std::vector<LocomotionOptionsEvent> locomotion_options_events{};
    std::vector<CombatOptionsEvent> combat_options_events{};
    std::vector<WoundOptionsEvent> wound_options_events{};
    std::vector<LookOptionsEvent> look_options_events{};
    std::vector<TacticsOptionsEvent> tactics_options_events{};
    std::vector<TransformEvent> transform_events{};
    std::vector<StickCommandEvent> stick_command_events{};
#endif
};

SimulationConfig MakeDefaultConfig();
const char* ToString(Team team) noexcept;
const char* ToString(SwordState state) noexcept;
const char* ToString(WeaponKind kind) noexcept;
const char* ToString(SimulationMode mode) noexcept;
const char* ToString(BehaviorMode mode) noexcept;
const char* ToString(HeadLookMode mode) noexcept;
const char* ToString(TacticalSteeringMode mode) noexcept;
const char* ToString(ActionKind kind) noexcept;
const char* ToString(ReactionKind kind) noexcept;
const char* ToString(SoundEventKind kind) noexcept;
const char* ToString(Limb limb) noexcept;
const char* ToString(LimbCondition condition) noexcept;
const char* ToString(AgentState state) noexcept;
const char* ToString(ActionPhase phase) noexcept;
const char* ToString(HandUsage hands) noexcept;

class Simulation final {
public:
    explicit Simulation(SimulationConfig config = MakeDefaultConfig(), std::uint64_t seed = 1) noexcept;
    ~Simulation();

    Simulation(const Simulation&) = delete;
    Simulation& operator=(const Simulation&) = delete;
    Simulation(Simulation&&) noexcept;
    Simulation& operator=(Simulation&&) noexcept;

    void Tick() noexcept;
    void Reset(std::uint64_t seed) noexcept;
    void RestartInMode(SimulationMode mode) noexcept;
    void RestartWithTeamCounts(std::uint32_t hero_count, std::uint32_t villain_count) noexcept;
    void RestartWithTeamCounts(std::uint32_t hero_count, std::uint32_t villain_count,
        std::vector<AgentTransform> opening_transforms) noexcept;
    bool SetOpeningTransforms(std::vector<AgentTransform> opening_transforms) noexcept;
    bool SetAgentTransform(const AgentTransform& transform) noexcept;
    bool SetAgentTransforms(const std::vector<AgentTransform>& transforms) noexcept;
    EntityId SpawnTransientAgent(Team team, Vec3 position, float facing_radians) noexcept;
    StickId SpawnStick(Vec3 position, float facing_radians) noexcept;
    bool RequestPickUpStick(EntityId agent_id, StickId stick_id) noexcept;
    bool RequestDropStick(EntityId agent_id) noexcept;
    bool HasTransientAgents() const noexcept;
    void UpdateLocomotionOptions(float crawl_speed_scale, float crawl_turn_scale) noexcept;
    void UpdateCombatOptions(float attack_cooldown_seconds,
        float parried_attack_cooldown_seconds, float attack_followup_probability,
        float drawn_sword_attack_probability, float parry_probability,
        const std::array<float, kSwordAttackClipCount>& sword_attack_stun_seconds,
        const std::array<float, kMeleeAttackClipCount>& melee_attack_stun_seconds) noexcept;
    void UpdateWoundOptions(float melee_wound_gain, float wound_threshold,
        float wound_decay_per_second, float leg_agonising_seconds,
        float torso_agonising_seconds, float head_passed_out_seconds) noexcept;
    void UpdateLookOptions(float head_turn_speed_degrees_per_second) noexcept;
    void UpdatePerceptionOptions(float proximity_threat_range_m, float vision_range_m,
        float head_vision_angle_degrees, float sound_maximum_range_m,
        float running_sound_toward_leeway_degrees,
        float non_threatening_minimum_seconds,
        float non_threatening_maximum_seconds,
        float follow_walk_distance_m, float follow_stop_distance_m) noexcept;
    void UpdateTacticsOptions(float target_commitment_seconds,
        float sector_influence_distance_m, float containment_early_influence,
        float sector_angle_variation_degrees, float sector_radius_variation_m,
        float ally_spacing_distance_m) noexcept;
    bool ValidateAction(EntityId agent_id, std::uint64_t action_sequence, bool success) noexcept;

    void BeginReplay(const ReplayLog& replay) noexcept;
    bool SeekReplay(const ReplayLog& replay, std::uint64_t target_tick) noexcept;
#if PROPHECY_ENABLE_REWIND
    std::unique_ptr<Simulation> CreateRewindCheckpoint() const;
    bool RestoreRewindCheckpoint(const Simulation& checkpoint, const ReplayLog& replay);
#endif
    bool ResumeRecordingFromReplay() noexcept;
    bool BranchRecordingFromReplay() noexcept;
    const ReplayLog& RecordedReplay() const noexcept;
    bool IsReplaying() const noexcept;

    const SimulationSnapshot& Snapshot() const noexcept;
    const SimulationConfig& Config() const noexcept;
    std::uint64_t Seed() const noexcept;
    double TickSeconds() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace prophecy::sim
