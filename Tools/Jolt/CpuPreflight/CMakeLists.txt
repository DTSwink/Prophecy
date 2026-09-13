cmake_minimum_required(VERSION 3.20)
project(ProphecyJoltCpuPreflight LANGUAGES CXX)
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "The local diagnostic preflight requires the verified MSVC Win64 toolchain.")
endif()
# This is an independent baseline target. Never link Jolt or inherit its /arch.
add_executable(ProphecyJoltCpuPreflight ProphecyJoltCpuPreflight.cpp)
set_target_properties(ProphecyJoltCpuPreflight PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES
    MSVC_RUNTIME_LIBRARY MultiThreaded)
target_compile_options(ProphecyJoltCpuPreflight PRIVATE /fp:precise /EHsc /GR-)
