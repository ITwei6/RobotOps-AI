add_executable(log_service
    src/log_index.cc
    src/log_parser.cc
    src/log_service_impl.cc
    src/main.cc)

target_include_directories(log_service
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include)

target_link_libraries(log_service
    PRIVATE
        ${ROBOTOPS_SCAFFOLD_TARGET}
        robotops_proto)
