#include "telemetry.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <utility>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

namespace prophecy::viewer {
namespace {

using Json = nlohmann::json;
namespace sim = ::prophecy::sim;

Json Vec(const sim::Vec3& value) {
    return Json::array({value.x, value.y, value.z});
}

Json Root(const sim::RootTransform& value) {
    return {
        {"position", Json::array({value.position.x, value.position.z})},
        {"yaw_radians", value.yaw_radians},
    };
}

#ifdef _WIN32
bool SendAll(SOCKET socket, const std::string& data) noexcept {
    std::size_t sent = 0;
    while (sent < data.size()) {
        const int chunk = send(socket, data.data() + sent,
            static_cast<int>(std::min<std::size_t>(data.size() - sent, 64U * 1024U)), 0);
        if (chunk <= 0) return false;
        sent += static_cast<std::size_t>(chunk);
    }
    return true;
}
#endif

}  // namespace

std::string SerializeTelemetrySnapshot(const std::string& scenario_name,
    const sim::SimulationSnapshot& snapshot, const sim::SimulationConfig& config,
    const TelemetryViewState& view) {
    Json agents = Json::array();
    for (const sim::AgentSnapshot& agent : snapshot.agents) {
        Json committed_attackers = Json::array();
        for (std::size_t index = 0; index < agent.combat_context.committed_attacker_id_count; ++index) {
            committed_attackers.push_back(agent.combat_context.committed_attacker_ids[index]);
        }
        Json active_attackers = Json::array();
        for (std::size_t index = 0; index < agent.combat_context.active_attacker_id_count; ++index) {
            active_attackers.push_back(agent.combat_context.active_attacker_ids[index]);
        }
        Json active_threats = Json::array();
        for (std::size_t index = 0; index < agent.perception.active_threat_id_count; ++index) {
            active_threats.push_back(agent.perception.active_threat_ids[index]);
        }
        Json finishing_targets = Json::array();
        for (std::size_t index = 0; index < agent.perception.finishing_target_id_count; ++index) {
            finishing_targets.push_back(agent.perception.finishing_target_ids[index]);
        }
        Json future_roots = Json::array();
        for (const sim::RootTransform& root : agent.future_roots) future_roots.push_back(Root(root));
        Json wounds = Json::object();
        for (std::size_t index = 0; index < agent.wounds.size(); ++index) {
            const sim::LimbWoundSnapshot& wound = agent.wounds[index];
            wounds[sim::ToString(static_cast<sim::Limb>(index))] = {
                {"gauge", wound.gauge},
                {"gauge_percent", wound.gauge_percent},
                {"condition", sim::ToString(wound.condition)},
                {"injured", wound.injured},
                {"badly_injured", wound.badly_injured},
            };
        }
        agents.push_back({
            {"id", agent.id},
            {"team", sim::ToString(agent.team)},
            {"position", Vec(agent.position)},
            {"facing_radians", agent.facing_radians},
            {"equipment", {
                {"sword_equipped", agent.sword_equipped},
                {"sword_state", sim::ToString(agent.sword_state)},
                {"held_weapon", sim::ToString(agent.held_weapon)},
                {"held_club_id", agent.held_stick_id},
                {"dropped_sword_position", Vec(agent.dropped_sword_position)},
                {"dropped_sword_yaw_radians", agent.dropped_sword_yaw_radians},
            }},
            {"behavior", {
                {"mode", sim::ToString(agent.behavior_mode)},
                {"attack_target_id", agent.attack_target_id},
                {"follow_target_id", agent.follow_target_id},
                {"draw_retreat_target_id", agent.draw_retreat_target_id},
                {"rescue_executioner_id", agent.rescue_executioner_id},
                {"rescue_former_target_id", agent.rescue_former_target_id},
                {"rescue_head_hold_seconds_remaining",
                    agent.rescue_head_hold_seconds_remaining},
                {"target_distance_m", agent.target_distance_m},
                {"completed_attacks", agent.completed_attacks},
                {"attack_cooldown_seconds_remaining", agent.attack_cooldown_seconds_remaining},
                {"cooldown_strafe", agent.cooldown_strafe},
                {"cooldown_strafe_direction", agent.cooldown_strafe_direction},
                {"cooldown_strafe_target_distance_m", agent.cooldown_strafe_target_distance_m},
                {"cooldown_strafe_distance_remaining_m",
                    agent.cooldown_strafe_distance_remaining_m},
                {"state", sim::ToString(agent.state)},
                {"state_seconds_remaining", agent.state_seconds_remaining},
            }},
            {"combat_context", {
                {"committed_attacker_count", agent.combat_context.committed_attacker_count},
                {"active_attacker_count", agent.combat_context.active_attacker_count},
                {"allies_attacking_target", agent.combat_context.allies_attacking_target},
                {"committed_attacker_ids", std::move(committed_attackers)},
                {"active_attacker_ids", std::move(active_attackers)},
            }},
            {"perception", {
                {"active_threat_count", agent.perception.active_threat_count},
                {"finishing_target_count", agent.perception.finishing_target_count},
                {"recognized_threat_count", agent.perception.recognized_threat_count},
                {"proximity_threat_count", agent.perception.proximity_threat_count},
                {"visible_threat_count", agent.perception.visible_threat_count},
                {"active_threat_ids", std::move(active_threats)},
                {"finishing_target_ids", std::move(finishing_targets)},
                {"sound_investigation_source_id",
                    agent.perception.sound_investigation_source_id},
                {"non_threatening_source_count",
                    agent.perception.non_threatening_source_count},
                {"scanning", agent.perception.scanning},
            }},
            {"tactical_steering", {
                {"mode", sim::ToString(agent.tactical_steering)},
                {"threat_count", agent.tactical_threat_count},
                {"containment_influence", agent.tactical_containment_influence},
                {"threat_arc_radians", agent.tactical_threat_arc_radians},
                {"nearest_peer_separation_radians",
                    agent.tactical_nearest_peer_separation_radians},
                {"view_center_yaw_radians", agent.tactical_view_center_yaw_radians},
                {"move_yaw_radians", agent.tactical_move_yaw_radians},
                {"sector_target_id", agent.tactical_sector_target_id},
                {"sector_index", agent.tactical_sector_index},
                {"sector_yaw_radians", agent.tactical_sector_yaw_radians},
                {"sector_radius_m", agent.tactical_sector_radius_m},
                {"sector_error_radians", agent.tactical_sector_error_radians},
                {"sector_influence", agent.tactical_sector_influence},
                {"target_commitment_seconds_remaining",
                    agent.target_commitment_seconds_remaining},
            }},
            {"look", {
                {"mode", sim::ToString(agent.head_look_mode)},
                {"target_id", agent.head_look_target_id},
                {"yaw_radians", agent.head_yaw_radians},
                {"pitch_radians", agent.head_pitch_radians},
            }},
            {"wounds", std::move(wounds)},
            {"action", {
                {"sequence", agent.action.sequence},
                {"kind", sim::ToString(agent.action.kind)},
                {"phase", sim::ToString(agent.action.phase)},
                {"hands", sim::ToString(agent.action.hands)},
                {"weapon", sim::ToString(agent.action.weapon)},
                {"target_club_id", agent.action.target_stick_id},
                {"target_position", Vec(agent.action.target_position)},
                {"elapsed_seconds", agent.action.elapsed_seconds},
                {"duration_seconds", agent.action.duration_seconds},
                {"stun_duration_seconds", agent.action.stun_duration_seconds},
                {"progress", agent.action.progress},
                {"reach_alpha", agent.action.reach_alpha},
                {"animation_index", agent.action.animation_index},
                {"parried", agent.action.parried},
                {"validation_required", agent.action.validation_required},
            }},
            {"reaction", {
                {"kind", sim::ToString(agent.reaction.kind)},
                {"elapsed_seconds", agent.reaction.elapsed_seconds},
                {"duration_seconds", agent.reaction.duration_seconds},
                {"progress", agent.reaction.progress},
            }},
            {"locomotion", {
                {"mode", sim::ToString(agent.locomotion_mode)},
                {"response", sim::ToString(agent.locomotion_response)},
                {"root_velocity", Vec(agent.root_velocity)},
                {"root_speed_mps", agent.root_speed_mps},
                {"speed_stick_direction_radians", agent.speed_stick_direction_radians},
                {"speed_stick_amplitude", agent.speed_stick_amplitude},
                {"orientation_stick_yaw_radians", agent.orientation_stick_yaw_radians},
                {"pose_phase", agent.pose_phase},
                {"future_roots", std::move(future_roots)},
            }},
        });
    }
    Json clubs = Json::array();
    for (const sim::StickSnapshot& stick : snapshot.sticks) {
        clubs.push_back({
            {"id", stick.id},
            {"position", Vec(stick.position)},
            {"facing_radians", stick.facing_radians},
            {"holder_id", stick.holder_id},
        });
    }
    Json sound_events = Json::array();
    for (std::size_t index = 0; index < snapshot.sound_event_count; ++index) {
        const sim::SoundEventSnapshot& event = snapshot.sound_events[index];
        sound_events.push_back({
            {"sequence", event.sequence},
            {"emitted_tick", event.emitted_tick},
            {"source_id", event.source_id},
            {"secondary_source_id", event.secondary_source_id},
            {"kind", sim::ToString(event.kind)},
            {"position", Vec(event.position)},
            {"maximum_range_m", event.maximum_range_m},
            {"recipient_count", event.recipient_count},
        });
    }
    const auto published_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    return Json{
        {"schema", "prophecy.locomotion-sim.snapshot.v1"},
        {"published_unix_ms", published_ms},
        {"scenario", scenario_name},
        {"simulation", {
            {"tick", snapshot.tick},
            {"time_seconds", snapshot.time_seconds},
            {"seed", snapshot.seed},
            {"tick_rate_hz", config.tick_rate_hz},
            {"agent_count", snapshot.agents.size()},
            {"hero_agent_count", config.hero_agent_count},
            {"villain_agent_count", config.villain_agent_count},
            {"mode", sim::ToString(config.mode)},
            {"sheathe_action_seconds", config.sheathe_action_seconds},
            {"unsheathe_action_seconds", config.unsheathe_action_seconds},
            {"club_pickup_action_seconds", config.stick_pickup_action_seconds},
            {"club_drop_action_seconds", config.stick_drop_action_seconds},
            {"attack_range_m", config.attack_range_m},
            {"attack_cooldown_seconds", config.attack_cooldown_seconds},
            {"parried_attack_cooldown_seconds", config.parried_attack_cooldown_seconds},
            {"attack_followup_probability", config.attack_followup_probability},
            {"drawn_sword_attack_probability", config.drawn_sword_attack_probability},
            {"hit_probability", config.hit_probability},
            {"parry_probability", config.parry_probability},
            {"head_velocity_threshold_mps", sim::kHeadVelocityThresholdMps},
            {"head_yaw_limit_radians", sim::kHeadYawLimitRadians},
            {"head_pitch_limit_radians", sim::kHeadPitchLimitRadians},
            {"head_turn_speed_degrees_per_second",
                config.head_turn_speed_degrees_per_second},
            {"proximity_threat_range_m", config.proximity_threat_range_m},
            {"vision_range_m", config.vision_range_m},
            {"head_vision_angle_degrees", config.head_vision_angle_degrees},
            {"running_sound_toward_leeway_degrees",
                config.running_sound_toward_leeway_degrees},
            {"non_threatening_minimum_seconds",
                config.non_threatening_minimum_seconds},
            {"non_threatening_maximum_seconds",
                config.non_threatening_maximum_seconds},
            {"follow_walk_distance_m", config.follow_walk_distance_m},
            {"follow_stop_distance_m", config.follow_stop_distance_m},
            {"target_assignment_rate_hz", sim::kTargetAssignmentRateHz},
            {"approach_sector_count", sim::kApproachSectorCount},
            {"target_commitment_seconds", config.target_commitment_seconds},
            {"sector_influence_distance_m", config.sector_influence_distance_m},
            {"containment_early_influence", config.containment_early_influence},
            {"sector_angle_variation_degrees", config.sector_angle_variation_degrees},
            {"sector_radius_variation_m", config.sector_radius_variation_m},
            {"ally_spacing_distance_m", config.ally_spacing_distance_m},
            {"crawl_speed_scale", config.crawl_speed_scale},
            {"crawl_turn_scale", config.crawl_turn_scale},
            {"grunt_propagation_agent_limit", sim::kGruntPropagationAgentLimit},
            {"wrath_probability", sim::kWrathProbability},
            {"outnumbered_view_cone_radians", sim::kOutnumberedViewConeRadians},
            {"attacker_separation_radians", sim::kAttackerSeparationRadians},
            {"sword_attack_stun_seconds", config.sword_attack_stun_seconds},
            {"melee_attack_stun_seconds", config.melee_attack_stun_seconds},
            {"melee_wound_gain", config.melee_wound_gain},
            {"wound_threshold", config.wound_threshold},
            {"wound_decay_per_second", config.wound_decay_per_second},
            {"leg_agonising_seconds", config.leg_agonising_seconds},
            {"torso_agonising_seconds", config.torso_agonising_seconds},
            {"head_passed_out_seconds", config.head_passed_out_seconds},
        }},
        {"viewer", {
            {"paused", view.paused},
            {"time_scale", view.time_scale},
            {"render_fps", view.render_fps},
            {"replaying", view.replaying},
            {"rewind_enabled", view.rewind_enabled},
            {"rewind_active", view.rewind_active},
            {"rewind_head_tick", view.rewind_head_tick},
            {"selected_agent_id", view.selected_agent_id},
        }},
        {"world", {
            {"minimum", Vec(config.world_min)},
            {"maximum", Vec(config.world_max)},
        }},
        {"sound", {
            {"locomotion_interval_seconds", sim::kLocomotionSoundIntervalSeconds},
            {"maximum_range_m", config.sound_maximum_range_m},
            {"propagation_mps", sim::kSoundPropagationMetersPerSecond},
            {"run_reference_speed_mps", sim::kRunSoundReferenceSpeedMps},
            {"events", std::move(sound_events)},
        }},
        {"agents", std::move(agents)},
        {"clubs", std::move(clubs)},
    }.dump();
}

struct TelemetryServer::Impl {
    struct Capture {
        std::string scenario_name{};
        sim::SimulationSnapshot snapshot{};
        sim::SimulationConfig config{};
        TelemetryViewState view{};
    };

    std::atomic<bool> running{false};
    std::atomic<bool> stop_requested{false};
    std::atomic<std::uint64_t> requested_generation{0};
    std::atomic<std::uint64_t> fulfilled_generation{0};
    std::mutex response_mutex{};
    std::condition_variable response_ready{};
    Capture capture{};
    std::thread worker{};
#ifdef _WIN32
    SOCKET listen_socket = INVALID_SOCKET;
    bool winsock_started = false;
#endif
};

TelemetryServer::TelemetryServer() : impl_(std::make_unique<Impl>()) {}
TelemetryServer::~TelemetryServer() { Stop(); }

bool TelemetryServer::Start(std::uint16_t port, std::string& error) {
    if (impl_->running.load(std::memory_order_acquire)) {
        error.clear();
        return true;
    }
#ifdef _WIN32
    WSADATA data{};
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) {
        error = "Winsock startup failed for telemetry.";
        return false;
    }
    impl_->winsock_started = true;
    impl_->listen_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (impl_->listen_socket == INVALID_SOCKET) {
        error = "Could not create the telemetry socket.";
        WSACleanup();
        impl_->winsock_started = false;
        return false;
    }
    BOOL reuse = TRUE;
    setsockopt(impl_->listen_socket, SOL_SOCKET, SO_REUSEADDR,
        reinterpret_cast<const char*>(&reuse), sizeof(reuse));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons(port);
    if (bind(impl_->listen_socket, reinterpret_cast<const sockaddr*>(&address), sizeof(address)) == SOCKET_ERROR ||
        listen(impl_->listen_socket, 2) == SOCKET_ERROR) {
        error = "Telemetry port " + std::to_string(port) + " is unavailable.";
        closesocket(impl_->listen_socket);
        impl_->listen_socket = INVALID_SOCKET;
        WSACleanup();
        impl_->winsock_started = false;
        return false;
    }

    impl_->stop_requested.store(false, std::memory_order_release);
    impl_->running.store(true, std::memory_order_release);
    Impl* impl = impl_.get();
    impl_->worker = std::thread([impl, port]() {
        while (!impl->stop_requested.load(std::memory_order_acquire)) {
            SOCKET client = accept(impl->listen_socket, nullptr, nullptr);
            if (client == INVALID_SOCKET) break;
            DWORD timeout_ms = 1500;
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO,
                reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));
            setsockopt(client, SOL_SOCKET, SO_SNDTIMEO,
                reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));
            char request[2048]{};
            const int received = recv(client, request, static_cast<int>(sizeof(request) - 1U), 0);
            std::string body;
            const char* status = "200 OK";
            const std::string request_text = received > 0
                ? std::string(request, static_cast<std::size_t>(received)) : std::string{};
            if (request_text.rfind("GET /snapshot", 0) == 0U) {
                const std::uint64_t generation = impl->requested_generation.fetch_add(1, std::memory_order_acq_rel) + 1U;
                std::unique_lock<std::mutex> lock(impl->response_mutex);
                const bool ready = impl->response_ready.wait_for(lock, std::chrono::milliseconds(1500), [impl, generation]() {
                    return impl->stop_requested.load(std::memory_order_acquire) ||
                        impl->fulfilled_generation.load(std::memory_order_acquire) >= generation;
                });
                if (ready && !impl->stop_requested.load(std::memory_order_acquire)) {
                    Impl::Capture capture = std::move(impl->capture);
                    lock.unlock();
                    body = SerializeTelemetrySnapshot(capture.scenario_name, capture.snapshot, capture.config, capture.view);
                } else {
                    status = "503 Service Unavailable";
                    body = "{\"error\":\"simulation did not publish before timeout\"}";
                }
            } else if (request_text.rfind("GET /health", 0) == 0U) {
                body = "{\"status\":\"ok\",\"snapshot\":\"http://127.0.0.1:" +
                    std::to_string(port) + "/snapshot\"}";
            } else {
                status = "404 Not Found";
                body = "{\"error\":\"use GET /snapshot or GET /health\"}";
            }
            const std::string header = "HTTP/1.1 " + std::string(status) + "\r\nContent-Type: application/json\r\n" +
                "Cache-Control: no-store\r\nConnection: close\r\nContent-Length: " + std::to_string(body.size()) + "\r\n\r\n";
            (void)SendAll(client, header + body);
            shutdown(client, SD_BOTH);
            closesocket(client);
        }
        impl->running.store(false, std::memory_order_release);
    });
    error.clear();
    return true;
#else
    (void)port;
    error = "Live telemetry is currently implemented for the Windows viewer.";
    return false;
#endif
}

void TelemetryServer::Stop() noexcept {
    if (!impl_) return;
    impl_->stop_requested.store(true, std::memory_order_release);
    impl_->response_ready.notify_all();
#ifdef _WIN32
    if (impl_->listen_socket != INVALID_SOCKET) {
        closesocket(impl_->listen_socket);
        impl_->listen_socket = INVALID_SOCKET;
    }
#endif
    if (impl_->worker.joinable()) impl_->worker.join();
#ifdef _WIN32
    if (impl_->winsock_started) {
        WSACleanup();
        impl_->winsock_started = false;
    }
#endif
    impl_->running.store(false, std::memory_order_release);
}

bool TelemetryServer::Running() const noexcept {
    return impl_->running.load(std::memory_order_acquire);
}

bool TelemetryServer::SnapshotRequested() const noexcept {
    return impl_->requested_generation.load(std::memory_order_acquire) >
        impl_->fulfilled_generation.load(std::memory_order_acquire);
}

void TelemetryServer::FulfillSnapshot(std::string scenario_name,
    sim::SimulationSnapshot snapshot, sim::SimulationConfig config, TelemetryViewState view) {
    std::lock_guard<std::mutex> lock(impl_->response_mutex);
    impl_->capture = Impl::Capture{
        std::move(scenario_name), std::move(snapshot), std::move(config), view};
    impl_->fulfilled_generation.store(impl_->requested_generation.load(std::memory_order_acquire),
        std::memory_order_release);
    impl_->response_ready.notify_all();
}

}  // namespace prophecy::viewer
