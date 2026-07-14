add_executable(prophecy_viewer
    src/control_settings.cpp
    src/locomotion_poses.cpp
    src/main.cpp
    src/raygui_impl.cpp
    src/rig.cpp
    src/scenario.cpp
    src/telemetry.cpp
    src/window_placement.cpp
)

target_include_directories(prophecy_viewer
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${PROPHECY_RAYGUI_INCLUDE_DIR}
)

target_link_libraries(prophecy_viewer
    PRIVATE
        prophecy_sim_core
        raylib
        nlohmann_json::nlohmann_json
)

file(TO_CMAKE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../data" PROPHECY_DATA_DIR_NORMALIZED)
target_compile_definitions(prophecy_viewer PRIVATE PROPHECY_DATA_DIR="${PROPHECY_DATA_DIR_NORMALIZED}")
target_compile_features(prophecy_viewer PRIVATE cxx_std_17)

if(WIN32)
    target_link_libraries(prophecy_viewer PRIVATE ws2_32)
endif()

if(MSVC)
    target_compile_options(prophecy_viewer PRIVATE /W4 /permissive-)
    set_source_files_properties(src/raygui_impl.cpp PROPERTIES COMPILE_OPTIONS /W0)
else()
    target_compile_options(prophecy_viewer PRIVATE -Wall -Wextra -Wpedantic)
    set_source_files_properties(src/raygui_impl.cpp PROPERTIES COMPILE_OPTIONS -w)
endif()

add_custom_target(prophecy_viewer_data ALL
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/../data"
        "$<TARGET_FILE_DIR:prophecy_viewer>/data"
)
add_dependencies(prophecy_viewer prophecy_viewer_data)
