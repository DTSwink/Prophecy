add_library(prophecy_sim_core STATIC
    src/locomotion.cpp
    src/simulation.cpp
)

target_include_directories(prophecy_sim_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(prophecy_sim_core PUBLIC cxx_std_17)

if(PROPHECY_ENABLE_REWIND)
    target_compile_definitions(prophecy_sim_core PUBLIC PROPHECY_ENABLE_REWIND=1)
else()
    target_compile_definitions(prophecy_sim_core PUBLIC PROPHECY_ENABLE_REWIND=0)
endif()

if(MSVC)
    target_compile_options(prophecy_sim_core PRIVATE /W4 /permissive- /EHsc- /GR-)
else()
    target_compile_options(prophecy_sim_core PRIVATE -Wall -Wextra -Wpedantic -fno-exceptions -fno-rtti)
endif()
