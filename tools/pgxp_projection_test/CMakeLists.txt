# Regression test for the pinned framework's PGXP precision shadow engine.
# Compiles the same white-box test and implementation sources as
# psxrecomp/runtime/CMakeLists.txt, without creating another runtime executable.
set(PSXRECOMP_RUNTIME_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../psxrecomp-v4/runtime")

add_executable(ape_pgxp_projection_test
    "${PSXRECOMP_RUNTIME_ROOT}/tests/test_pgxp.cpp"
    "${PSXRECOMP_RUNTIME_ROOT}/src/pgxp.cpp"
    "${PSXRECOMP_RUNTIME_ROOT}/src/psx_ram_geometry.c"
)
target_include_directories(ape_pgxp_projection_test PRIVATE
    "${PSXRECOMP_RUNTIME_ROOT}/include"
)
add_test(NAME ape_pgxp_projection_test COMMAND ape_pgxp_projection_test)
