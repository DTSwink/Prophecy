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
        Json future_roots = Json::array();
        for (const sim::RootTransform& root : agent.future_roots) future_roots.push_back(Root(root));
        agents.push_back({
            {"id", agent.id},
            {"team", sim::ToString(agent.team)},
            {"position", Vec(agent.position)},
            {"facing_radians", agent.facing_radians},
            {"equipment", {
                {"sword_equipped", agent.sword_equipped},
                {"sword_state", sim::ToString(agent.sword_state)},
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
        {"agents", std::move(agents)},
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
