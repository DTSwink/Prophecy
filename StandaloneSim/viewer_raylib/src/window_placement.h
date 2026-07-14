#pragma once

#include <cstdint>

namespace prophecy::viewer {

bool IsCharacterKeyDown(char character) noexcept;
void ShowWindowAtBottom(void* native_handle, std::uintptr_t restore_foreground) noexcept;

}  // namespace prophecy::viewer
