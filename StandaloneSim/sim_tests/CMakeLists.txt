add_executable(prophecy_sim_tests
    simulation_tests.cpp
)

target_link_libraries(prophecy_sim_tests PRIVATE prophecy_sim_core)
target_compile_features(prophecy_sim_tests PRIVATE cxx_std_17)

if(MSVC)
    target_compile_options(prophecy_sim_tests PRIVATE /W4 /permissive-)
else()
    target_compile_options(prophecy_sim_tests PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_test(NAME prophecy_sim_determinism COMMAND prophecy_sim_tests)

add_executable(prophecy_locomotion_trace
    locomotion_trace.cpp
)
target_link_libraries(prophecy_locomotion_trace PRIVATE prophecy_sim_core)
target_compile_features(prophecy_locomotion_trace PRIVATE cxx_std_17)

if(TARGET nlohmann_json::nlohmann_json)
    add_executable(prophecy_control_settings_tests
        control_settings_tests.cpp
        ../viewer_raylib/src/control_settings.cpp
    )
    target_include_directories(prophecy_control_settings_tests PRIVATE ../viewer_raylib/src)
    target_link_libraries(prophecy_control_settings_tests PRIVATE prophecy_sim_core nlohmann_json::nlohmann_json)
    target_compile_features(prophecy_control_settings_tests PRIVATE cxx_std_17)
    if(MSVC)
        target_compile_options(prophecy_control_settings_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(prophecy_control_settings_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()
    add_test(NAME prophecy_control_settings_roundtrip COMMAND prophecy_control_settings_tests)

    add_executable(prophecy_telemetry_tests
        telemetry_tests.cpp
        ../viewer_raylib/src/telemetry.cpp
    )
    target_include_directories(prophecy_telemetry_tests PRIVATE ../viewer_raylib/src)
    target_link_libraries(prophecy_telemetry_tests PRIVATE prophecy_sim_core nlohmann_json::nlohmann_json)
    if(WIN32)
        target_link_libraries(prophecy_telemetry_tests PRIVATE ws2_32)
    endif()
    target_compile_features(prophecy_telemetry_tests PRIVATE cxx_std_17)
    if(MSVC)
        target_compile_options(prophecy_telemetry_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(prophecy_telemetry_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()
    add_test(NAME prophecy_telemetry_serialization COMMAND prophecy_telemetry_tests)
endif()
