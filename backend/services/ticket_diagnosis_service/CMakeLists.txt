add_executable(ticket_diagnosis_service
    src/ticket_diagnosis_store.cc
    src/ticket_diagnosis_service_impl.cc
    src/main.cc)

target_include_directories(ticket_diagnosis_service
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include)

target_link_libraries(ticket_diagnosis_service
    PRIVATE
        ${ROBOTOPS_SCAFFOLD_TARGET}
        robotops_proto)
