cmake_minimum_required(VERSION 3.24)

project(ProphecyStandaloneSim VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(PROPHECY_BUILD_VIEWER "Build the raylib visualization application" ON)
option(PROPHECY_BUILD_TESTS "Build deterministic headless tests" ON)
option(PROPHECY_ENABLE_REWIND "Compile deterministic rewind/debug history" ON)

add_subdirectory(sim_core)

if(PROPHECY_BUILD_VIEWER)
    include(FetchContent)

    set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(BUILD_GAMES OFF CACHE BOOL "" FORCE)
    set(SUPPORT_FILEFORMAT_FLAC OFF CACHE BOOL "" FORCE)

    FetchContent_Declare(
        raylib
        GIT_REPOSITORY https://github.com/raysan5/raylib.git
        GIT_TAG 6.0
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(raylib)

    FetchContent_Declare(
        raygui
        GIT_REPOSITORY https://github.com/raysan5/raygui.git
        GIT_TAG 4.0
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(raygui)
    set(PROPHECY_RAYGUI_INCLUDE_DIR "${raygui_SOURCE_DIR}/src")

    FetchContent_Declare(
        nlohmann_json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG v3.11.3
        GIT_SHALLOW TRUE
    )
    set(JSON_BuildTests OFF CACHE INTERNAL "")
    FetchContent_MakeAvailable(nlohmann_json)

    add_subdirectory(viewer_raylib)
endif()

if(PROPHECY_BUILD_TESTS)
    enable_testing()
    add_subdirectory(sim_tests)
endif()
