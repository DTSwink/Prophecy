cmake_minimum_required(VERSION 3.24)

project(ProphecyStandaloneSim VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(PROPHECY_BUILD_VIEWER "Build the raylib visualization application" ON)
option(PROPHECY_BUILD_TESTS "Build deterministic headless tests" ON)
option(PROPHECY_ENABLE_REWIND "Compile deterministic rewind/debug history" ON)

include(FetchContent)

set(RECASTNAVIGATION_DEMO OFF CACHE BOOL "" FORCE)
set(RECASTNAVIGATION_TESTS OFF CACHE BOOL "" FORCE)
set(RECASTNAVIGATION_EXAMPLES OFF CACHE BOOL "" FORCE)
FetchContent_Declare(
    recastnavigation
    GIT_REPOSITORY https://github.com/recastnavigation/recastnavigation.git
    GIT_TAG v1.6.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(recastnavigation)

add_library(prophecy_navigation_runtime
    navigation/crowd_runtime.cpp
)
target_include_directories(prophecy_navigation_runtime PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/navigation"
)
target_link_libraries(prophecy_navigation_runtime PUBLIC Detour DetourCrowd)
target_compile_features(prophecy_navigation_runtime PUBLIC cxx_std_17)
if(MSVC)
    target_compile_options(prophecy_navigation_runtime PRIVATE /W4 /permissive-)
else()
    target_compile_options(prophecy_navigation_runtime PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(prophecy_navigation_crowd_benchmark
    tools/benchmark_navigation_crowd.cpp
)
target_link_libraries(prophecy_navigation_crowd_benchmark
    PRIVATE prophecy_navigation_runtime
)
target_compile_features(prophecy_navigation_crowd_benchmark PRIVATE cxx_std_17)
if(MSVC)
    target_compile_options(prophecy_navigation_crowd_benchmark PRIVATE /W4 /permissive-)
else()
    target_compile_options(prophecy_navigation_crowd_benchmark PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_subdirectory(sim_core)

if(PROPHECY_BUILD_VIEWER)
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

    add_executable(prophecy_landscape_collision_baker
        tools/bake_landscape_collision.cpp
    )
    target_link_libraries(prophecy_landscape_collision_baker
        PRIVATE nlohmann_json::nlohmann_json
    )
    target_compile_features(prophecy_landscape_collision_baker PRIVATE cxx_std_17)
    if(MSVC)
        target_compile_options(prophecy_landscape_collision_baker PRIVATE /W4 /permissive-)
    else()
        target_compile_options(prophecy_landscape_collision_baker PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_executable(prophecy_navigation_baker
        tools/bake_navigation.cpp
        "${recastnavigation_SOURCE_DIR}/RecastDemo/Source/ChunkyTriMesh.cpp"
    )
    target_include_directories(prophecy_navigation_baker PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/navigation"
        "${recastnavigation_SOURCE_DIR}/RecastDemo/Include"
    )
    target_link_libraries(prophecy_navigation_baker
        PRIVATE
            Recast
            Detour
            nlohmann_json::nlohmann_json
    )
    target_compile_features(prophecy_navigation_baker PRIVATE cxx_std_17)
    if(MSVC)
        target_compile_options(prophecy_navigation_baker PRIVATE /W4 /permissive-)
    else()
        target_compile_options(prophecy_navigation_baker PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_executable(prophecy_navigation_inspector
        tools/inspect_navigation.cpp
    )
    target_include_directories(prophecy_navigation_inspector PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/navigation"
    )
    target_link_libraries(prophecy_navigation_inspector PRIVATE Detour)
    target_compile_features(prophecy_navigation_inspector PRIVATE cxx_std_17)
    if(MSVC)
        target_compile_options(prophecy_navigation_inspector PRIVATE /W4 /permissive-)
    else()
        target_compile_options(prophecy_navigation_inspector PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_executable(prophecy_collision_replacer
        tools/replace_collision_objects.cpp
    )
    target_link_libraries(prophecy_collision_replacer
        PRIVATE nlohmann_json::nlohmann_json
    )
    target_compile_features(prophecy_collision_replacer PRIVATE cxx_std_17)
    if(MSVC)
        target_compile_options(prophecy_collision_replacer PRIVATE /W4 /permissive-)
    else()
        target_compile_options(prophecy_collision_replacer PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_subdirectory(viewer_raylib)
endif()

if(PROPHECY_BUILD_TESTS)
    enable_testing()
    add_test(
        NAME prophecy_navigation_crowd_100_agents
        COMMAND prophecy_navigation_crowd_benchmark
            "${CMAKE_CURRENT_SOURCE_DIR}/data/mybasic.navbin" 900 60
    )
    add_subdirectory(sim_tests)
endif()
