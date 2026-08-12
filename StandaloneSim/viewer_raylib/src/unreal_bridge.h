#pragma once

#include "crowd_runtime.h"

#include <cstddef>
#include <string>

namespace prophecy::viewer {

class UnrealBridge {
public:
    UnrealBridge() = default;
    ~UnrealBridge();
    UnrealBridge(const UnrealBridge&) = delete;
    UnrealBridge& operator=(const UnrealBridge&) = delete;

    bool Open(const std::string& mapping_name, std::string& error);
    void Close() noexcept;
    [[nodiscard]] bool IsOpen() const noexcept;
    [[nodiscard]] bool ShutdownRequested() const noexcept;
    [[nodiscard]] std::size_t VillagerCount() const noexcept;
    [[nodiscard]] std::size_t TotalAgentCount() const noexcept;

    bool InitializeCrowd(navigation::CrowdRuntime& crowd, std::string& error) noexcept;
    void ApplyUnrealTransforms(navigation::CrowdRuntime& crowd) noexcept;
    void Publish(const navigation::CrowdRuntime& crowd) noexcept;
    [[nodiscard]] navigation::CrowdAgentSample DisplayAgent(std::size_t index,
        const navigation::CrowdAgentSample& planned) const noexcept;
    void PublishError(const std::string& error) noexcept;

private:
    struct Impl;
    Impl* impl_ = nullptr;
};

}  // namespace prophecy::viewer
