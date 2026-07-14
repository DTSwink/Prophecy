#include "window_placement.h"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

namespace prophecy::viewer {

bool IsCharacterKeyDown(char character) noexcept {
#if defined(_WIN32)
    const HWND foreground_window = GetForegroundWindow();
    DWORD foreground_process_id = 0;
    const DWORD foreground_thread_id = foreground_window != nullptr
        ? GetWindowThreadProcessId(foreground_window, &foreground_process_id)
        : 0;
    if (foreground_thread_id == 0 || foreground_process_id != GetCurrentProcessId()) {
        return false;
    }

    const HKL keyboard_layout = GetKeyboardLayout(foreground_thread_id);
    const SHORT mapped_key = VkKeyScanExW(
        static_cast<WCHAR>(static_cast<unsigned char>(character)), keyboard_layout);
    if (mapped_key == -1) {
        return false;
    }

    const int virtual_key = LOBYTE(mapped_key);
    const int required_modifiers = HIBYTE(mapped_key);
    const bool modifiers_match =
        ((required_modifiers & 1) == 0 || (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0) &&
        ((required_modifiers & 2) == 0 || (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0) &&
        ((required_modifiers & 4) == 0 || (GetAsyncKeyState(VK_MENU) & 0x8000) != 0);
    return modifiers_match && (GetAsyncKeyState(virtual_key) & 0x8000) != 0;
#else
    (void)character;
    return false;
#endif
}

void ShowWindowAtBottom(void* native_handle, std::uintptr_t restore_foreground) noexcept {
#if defined(_WIN32)
    const HWND window = static_cast<HWND>(native_handle);
    if (window != nullptr) {
        SetWindowPos(window, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_SHOWWINDOW);
        const HWND previous_window = reinterpret_cast<HWND>(restore_foreground);
        if (previous_window != nullptr && IsWindow(previous_window)) {
            SetForegroundWindow(previous_window);
        }
        SetWindowPos(window, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
    }
#else
    (void)native_handle;
    (void)restore_foreground;
#endif
}

}  // namespace prophecy::viewer
